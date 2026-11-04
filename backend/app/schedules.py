from uuid import UUID, uuid4
import json
from app.statistics import build_statistics, html_report
from app.statistics_pdf import pdf_report
from app.export_names import report_disposition
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from app.schemas import Strict
from app.provenance import SolverSettings
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from app.dependencies import administrator, db_session, event, fail, lock_workspace
from app.models import AssignmentLock, Record, Rule, ScheduleRun, Workspace, WorkerHeartbeat, utcnow

router = APIRouter(prefix="/api/schedules")


class GenerateInput(Strict):
    request_key: UUID
    settings: SolverSettings = Field(default_factory=SolverSettings)
    source_run_id: UUID | None = None


def snapshot_of(db, ws):
    return {"name": ws.name, "term": ws.term, "input_version": ws.version,
        "calendar": {**{k: getattr(ws, k) for k in ("timezone", "days", "start_hour", "end_hour", "period_minutes", "teaching_periods", "realism_policy")}, "weekly_load_policy": {"regular_hours": 12, "allow_overtime": True}},
        "records": [{"id": r.id, "kind": r.kind, **r.data} for r in db.scalars(select(Record).order_by(Record.id))],
        "assignment_locks": [lock.data for lock in db.scalars(select(AssignmentLock).where(AssignmentLock.status == "approved").order_by(AssignmentLock.id))],
        "rules": [{"id": r.id, "status": r.status, **r.data} for r in db.scalars(select(Rule).where(Rule.status == "approved").order_by(Rule.id))]}


def representation(row, current_version):
    return {"id": row.id, "input_version": row.input_version, "stale": row.input_version != current_version,
            "status": row.status, "cancel_requested": row.cancel_requested, "created_at": row.created_at,
            "snapshot": row.snapshot, "result": row.result}


@router.get("")
def list_runs(user=Depends(administrator), db: DB = Depends(db_session)):
    ws = db.get(Workspace, 1)
    return [representation(r, ws.version) for r in db.scalars(select(ScheduleRun).order_by(ScheduleRun.created_at.desc()).limit(10))]


@router.get("/preflight/current")
def preflight(user=Depends(administrator), db: DB = Depends(db_session)):
    from app.preflight import inspect_inputs
    return inspect_inputs(snapshot_of(db, db.get(Workspace, 1)))


@router.get("/{ident}")
def get_run(ident: str, user=Depends(administrator), db: DB = Depends(db_session)):
    row = db.get(ScheduleRun, ident)
    if not row:
        fail(404, "not_found")
    return representation(row, db.get(Workspace, 1).version)


@router.post("", status_code=202)
def create_run(body: GenerateInput, request: Request, user=Depends(administrator), db: DB = Depends(db_session)):
    ws = db.get(Workspace, 1)  # authentication already locks the workspace
    existing = db.scalar(select(ScheduleRun).where(ScheduleRun.request_key == str(body.request_key)))
    if existing:
        from app.provenance import CONFIG
        if SolverSettings.model_validate(existing.snapshot.get("provenance", {}).get("solver_config", CONFIG)).model_dump() != body.settings.model_dump() or existing.snapshot.get("provenance", {}).get("source_run_id") != (str(body.source_run_id) if body.source_run_id else None):
            fail(409, "request_conflict")
        return representation(existing, ws.version)
    ws = lock_workspace(request, db)
    if db.scalar(select(ScheduleRun.id).where(ScheduleRun.status.in_(["queued", "running"]))):
        fail(409, "schedule_active")
    heartbeat = db.get(WorkerHeartbeat, 1)
    if not heartbeat or (utcnow() - heartbeat.seen_at).total_seconds() > 45:
        fail(503, "worker_unavailable")
    from app.provenance import seal_snapshot, verify_snapshot
    if body.source_run_id:
        source = db.get(ScheduleRun, str(body.source_run_id))
        if not source or source.status in ('queued','running'):
            fail(422, 'invalid_snapshot_source')
        if not verify_snapshot(source.snapshot):
            fail(422, 'snapshot_integrity_failed')
        snap = seal_snapshot(source.snapshot, body.settings.model_dump())
        snap['provenance']['source_run_id'] = source.id
    else:
        from app.locks import validate_lock
        for lock in db.scalars(select(AssignmentLock).where(AssignmentLock.status == "approved")):
            validate_lock(lock, db)
        snap = seal_snapshot(snapshot_of(db, ws), body.settings.model_dump())
    if not any(r["kind"] == "courses" for r in snap["records"]) or not any(r["kind"] == "rooms" for r in snap["records"]):
        fail(422, "schedule_missing_data")
    row = ScheduleRun(id=str(uuid4()), workspace_id=1, created_by=user.id, input_version=snap["input_version"], request_key=str(body.request_key), snapshot=snap)
    db.add(row)
    event(db, ws, user, "schedule.queued", row.id)
    db.commit()
    return representation(row, ws.version)


@router.post("/{ident}/cancel")
def cancel_run(ident: str, user=Depends(administrator), db: DB = Depends(db_session)):
    row = db.scalar(select(ScheduleRun).where(ScheduleRun.id == ident).with_for_update())
    if not row:
        fail(404, "not_found")
    if row.status in ("queued", "running") and not row.cancel_requested:
        row.cancel_requested = True
        if row.status == "queued":
            row.status, row.result = "cancelled", {"assignments": [], "lifecycle":{"queued_at":row.created_at.isoformat(),"finished_at":utcnow().isoformat()}}
        event(db, db.get(Workspace, 1), user, "schedule.cancel_requested", row.id)
        db.commit()
    return representation(row, db.get(Workspace, 1).version)


@router.get("/{ident}/statistics")
def download_statistics(ident: str, format: str = "pdf", user=Depends(administrator), db: DB = Depends(db_session)):
    row = db.get(ScheduleRun, ident)
    if not row:
        fail(404, "not_found")
    if row.status != "completed" or not row.result or not row.result.get("validation", {}).get("passed"):
        fail(409, "statistics_unavailable")
    if format not in ("pdf", "html", "json"):
        fail(422, "invalid_input")
    stats = row.result.get("statistics") or build_statistics(row.snapshot, row.result)
    if not row.result.get("statistics"):
        stats["generated_at"] = row.created_at.isoformat()
    stale = row.input_version != db.get(Workspace, 1).version
    if format == "pdf":
        content = pdf_report(row.id, row.snapshot, stats, stale)
        media = "application/pdf"
    elif format == "json":
        content = json.dumps({"run_id": row.id, "stale": stale, "statistics": stats}, ensure_ascii=False, indent=2)
        media = "application/json"
    else:
        content = html_report(row.id, row.snapshot, stats, stale)
        media = "text/html"
    return Response(content=content, media_type=media, headers={"Content-Disposition": report_disposition(row, format), "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
