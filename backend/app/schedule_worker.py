"""Claim jobs transactionally; solve outside transactions; commit one final outcome."""
import logging
import threading
import time
import platform
import hashlib
from pathlib import Path
from app.provenance import verify_snapshot, VALIDATOR_VERSION
from datetime import timedelta
from sqlalchemy import select
from app.models import ScheduleRun, SessionLocal, WorkerHeartbeat, utcnow
from app.solver import generate
from app.validation import validate_schedule
from app.statistics import build_statistics

logger = logging.getLogger("jadwai.scheduler")
REPAIR_SECONDS = 240  # longest the worker spends finding a fix for an impossible timetable


def recover_interrupted(factory=SessionLocal):
    with factory.begin() as db:
        rows = db.scalars(select(ScheduleRun).where(ScheduleRun.status == "running", ScheduleRun.updated_at < utcnow() - timedelta(seconds=90)).with_for_update(skip_locked=True))
        for row in rows:
            row.status = "cancelled" if row.cancel_requested else "failed"
            row.result = {"reason": "worker_interrupted", "assignments": [], "lifecycle": {**((row.result or {}).get("lifecycle") or {}), "finished_at":utcnow().isoformat()}, "interrupted": True, "automatic_retry_limit":0}
            row.updated_at = utcnow()


def process_one(factory=SessionLocal, shutdown=None):
    recover_interrupted(factory)
    with factory.begin() as db:
        row = db.scalar(select(ScheduleRun).where(ScheduleRun.status == "queued").order_by(ScheduleRun.created_at).with_for_update(skip_locked=True).limit(1))
        if not row:
            return False
        row.status, row.updated_at = "running", utcnow()
        ident, snapshot = row.id, row.snapshot
        queued_at, started_at = row.created_at.isoformat(), row.updated_at.isoformat()
        row.result = {"assignments":[],"lifecycle":{"queued_at":queued_at,"started_at":started_at}}
    cancelled, finished = threading.Event(), threading.Event()
    holder = {}
    abort_reason = {}

    def watch():
        while not finished.wait(0.5):
            try:
                with factory.begin() as db:
                    job = db.get(ScheduleRun, ident)
                    if not job or job.status != "running" or job.cancel_requested or (shutdown and shutdown.is_set()):
                        if not job or job.status != "running" or (shutdown and shutdown.is_set()):
                            abort_reason["reason"] = "worker_interrupted"
                        cancelled.set()
                        if "solver" in holder:
                            holder["solver"].stop_search()
                        return
                    job.updated_at = utcnow()
                    # A long solve is a busy worker, not a missing one.
                    beat = db.get(WorkerHeartbeat, 1)
                    if beat:
                        beat.seen_at = utcnow()
                    job.result = {"assignments":[],"lifecycle":{"queued_at":queued_at,"started_at":started_at},"progress":holder.get("progress")}
            except Exception:
                # Losing access to cancellation/state invalidates this run rather than
                # committing an unmonitored solver result.
                abort_reason["reason"] = "monitoring_failed"
                cancelled.set()
                if "solver" in holder:
                    holder["solver"].stop_search()
                return

    def solver_started(solver):
        holder["solver"] = solver
        return lambda progress: holder.update(progress=progress)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    from app.preflight import inspect_inputs
    started = time.monotonic()
    try:
        if not verify_snapshot(snapshot):
            result = {"status": "failed", "reason": "snapshot_integrity_failed", "assignments": []}
        else:
            preparation = inspect_inputs(snapshot)
            if not preparation["ready"]:
                result = {"status": "blocked", "reason": "input_checks_failed", "assignments": [], "preflight": preparation}
            else:
                result = generate(snapshot, cancelled, solver_started)
                result["preflight"] = preparation
        if result["status"] == "infeasible" or (result["status"] == "blocked" and result.get("reason") == "input_checks_failed"):
            # Say what must give way, with a fix proven by the solver and the validator.
            from app.repair import diagnose
            repair = diagnose(snapshot, budget=REPAIR_SECONDS, cancel=cancelled,
                              hints=[result.get("activity_id")] + [b.get("activity_id") for b in (result.get("preflight") or {}).get("blockers", [])])
            repair.pop("assignments", None)
            result["repair"] = repair
        if result["status"] == "completed":
            report = validate_schedule(snapshot, result["assignments"])
            from app.validation_details import preference_penalty
            objective = preference_penalty(snapshot, result["assignments"])
            report["preference_evaluation"] = objective
            report["checks"].append("independent_preference_penalty")
            correct = objective["total"] == result.get("preference_penalty")
            if result.get("idle_period_penalty") is not None:
                idle_correct = result["idle_period_penalty"] == (report.get("realism") or {}).get("idle_periods")
                report["checks"].append("independent_idle_penalty")
                report.setdefault("coverage", []).append({"check":"independent_idle_penalty","required":True,"applicable":len((report.get("realism") or {}).get("daily_resources",[])),"basis":"observed resource-days","status":"passed" if idle_correct else "failed"})
                if not idle_correct:
                    report["passed"] = False
                    report["errors"].append("idle_penalty_mismatch")
            report.setdefault("coverage", []).append({"check":"independent_preference_penalty","required":True,"applicable":len(objective["sessions"]),"basis":"sessions with preferred instructor windows","status":"passed" if correct else "failed"})
            if not correct:
                report["passed"] = False
                report["errors"].append("preference_penalty_mismatch")
                report.setdefault("violations", []).append({"code":"preference_penalty_mismatch","message":"Solver penalty does not match independent evaluation.","sessions":[],"resource_ids":[],"rule_ids":[]})
            from app.objective import weights as profile_weights, effective
            from app.provenance import CONFIG
            from app.realism_validation import convenience_components
            config = snapshot.get('provenance',{}).get('solver_config',CONFIG)
            weights, scored = profile_weights(snapshot, config), effective(snapshot, config)
            observed = {'preferences': objective['total'], **convenience_components(snapshot, result['assignments'])}
            observed['idle_periods'] = observed['student_gaps'] + observed['instructor_gaps']
            expected_score = sum(weight * observed[name] for name, weight in scored.items())
            diagnostic = result.get('solver_diagnostics') or {}
            reported = result.get('objective_components') or {}
            components_correct = all(reported.get(name) == observed[name] for name, weight in scored.items() if weight)
            score_correct = components_correct and diagnostic.get('objective_weights') == weights and diagnostic.get('objective_value') == expected_score
            report['objective_evaluation'] = {'weights':weights,'observed_components':observed,'expected_score':expected_score,'passed':score_correct}
            report['checks'].append('independent_objective_score')
            report.setdefault('coverage',[]).append({'check':'independent_objective_score','required':True,'applicable':1,'basis':'selected objective profile and independently observed components','status':'passed' if score_correct else 'failed'})
            if not score_correct:
                report['passed'] = False
                report['errors'].append('objective_score_mismatch')
            result["validation"] = report
            if not report["passed"]:
                result.update(status="failed", reason="validation_failed", assignments=[])
    except Exception:
        logger.exception("Schedule generation failed for job %s", ident)
        result = {"status": "failed", "reason": "generation_failed", "assignments": []}
    finally:
        finished.set()
        thread.join(timeout=2)
    with factory.begin() as db:
        row = db.scalar(select(ScheduleRun).where(ScheduleRun.id == ident).with_for_update())
        if row.status != "running":
            return True
        # Cancellation wins if committed before the terminal write. No partial
        # result is retained, and no cancelled run claims optimality.
        if row.cancel_requested:
            result = {"status": "cancelled", "assignments": []}
        elif cancelled.is_set():
            result = {"status": "failed", "reason": abort_reason.get("reason", "worker_interrupted"), "assignments": []}
        source_files = sorted(Path(__file__).parent.glob('*.py'))
        source_hash = hashlib.sha256(b''.join(p.name.encode()+b'\0'+p.read_bytes()+b'\0' for p in source_files)).hexdigest()
        result["provenance"] = {"snapshot": snapshot.get("provenance"), "validator_version": VALIDATOR_VERSION if "validation" in result else None,
            "application_sources_sha256": source_hash, "python_version": platform.python_version(), "platform": platform.system()+" "+platform.machine(),
            "automatic_retry_limit": 0, "worker_elapsed_seconds": round(time.monotonic() - started, 6),
            "lifecycle": {"queued_at":queued_at,"started_at":started_at,"finished_at":utcnow().isoformat()},
            "reproducibility_note": "Parallel search can produce different feasible schedules with identical inputs and seed."}

        if result["status"] == "completed":
            result["statistics"] = build_statistics(snapshot, result)
        row.status, row.result, row.updated_at = result["status"], result, utcnow()
    return True
