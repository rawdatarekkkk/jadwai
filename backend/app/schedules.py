from uuid import UUID, uuid4
import json
from app.statistics import build_statistics, html_report
from app.statistics_pdf import pdf_report
from app.export_names import report_disposition
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from app.schemas import Name, Strict
from app.provenance import SolverSettings
from sqlalchemy import select
from sqlalchemy.orm import Session as DB
from app.dependencies import administrator, db_session, event, fail, lock_workspace
from app.models import AssignmentLock, Record, Rule, ScheduleRun, Workspace, WorkerHeartbeat, utcnow

router = APIRouter(prefix="/api/schedules")


class ScopeItem(Strict):
    programme: Name
    year: int | None = Field(default=None, ge=1, le=10, strict=True)
    # One student group of that programme (its record id): only that group's courses are placed.
    group: str | None = Field(default=None, min_length=1, max_length=64)


class GenerateInput(Strict):
    request_key: UUID
    settings: SolverSettings = Field(default_factory=SolverSettings)
    source_run_id: UUID | None = None
    # Build in parts: schedule these programmes (or programme years), keeping the base run's sessions fixed.
    scope: list[ScopeItem] | None = Field(default=None, min_length=1, max_length=100)
    base_run_id: UUID | None = None


def snapshot_of(db, ws):
    from app.advising import student_rows
    from app.advising_rules import snapshot_students
    return {"name": ws.name, "term": ws.term, "input_version": ws.version,
        "calendar": {**{k: getattr(ws, k) for k in ("timezone", "days", "start_hour", "end_hour", "period_minutes", "teaching_periods", "realism_policy")}, "weekly_load_policy": {"regular_hours": 12, "allow_overtime": True}},
        "records": [{"id": r.id, "kind": r.kind, **r.data} for r in db.scalars(select(Record).order_by(Record.id))],
        "assignment_locks": [lock.data for lock in db.scalars(select(AssignmentLock).where(AssignmentLock.status == "approved").order_by(AssignmentLock.id))],
        "rules": [{"id": r.id, "status": r.status, **r.data} for r in db.scalars(select(Rule).where(Rule.status == "approved").order_by(Rule.id))],
        "students": snapshot_students(student_rows(db))}


def progress(snapshot):
    from app.partial_plan import progress as measure
    return {**measure(snapshot), "scope": (snapshot.get("plan") or {}).get("scope"), "base_run_id": (snapshot.get("plan") or {}).get("base_run_id")}


def with_plan(db, ws, snapshot, body):
    """Add the part plan to an unsealed snapshot."""
    from app.partial_plan import matches, scope_activities
    from app.scenarios import completed
    fixed, base_id = [], None
    if body.base_run_id:
        base = db.get(ScheduleRun, str(body.base_run_id))
        if not completed(base):
            fail(409, "invalid_base_run")
        if base.input_version != ws.version:
            fail(409, "stale_schedule")
        fixed, base_id = base.result["assignments"], base.id
    scope = scope_key(body.scope)
    groups = [r for r in snapshot["records"] if r["kind"] == "groups"]
    if any(not matches(g, [item]) for item in scope for g in [next((g for g in groups if matches(g, [item])), {})]):
        fail(422, "invalid_scope")  # names a programme or year with no student groups
    ids = scope_activities(snapshot["records"], scope, {r["activity_id"] for r in fixed})
    if not ids:
        fail(422, "scope_empty")
    return {**snapshot, "plan": {"scope": scope, "base_run_id": base_id, "activity_ids": ids, "fixed": fixed}}


def scope_key(items):
    return sorted(({"programme": i.programme, "year": i.year, **({"group": i.group} if i.group else {})} for i in items or []),
                  key=lambda i: (i["programme"], i["year"] or 0, i.get("group") or ""))


def representation(row, current_version):
    return {"id": row.id, "input_version": row.input_version, "stale": row.input_version != current_version,
            "status": row.status, "cancel_requested": row.cancel_requested, "created_at": row.created_at,
            "snapshot": row.snapshot, "result": row.result, "progress": progress(row.snapshot) if row.snapshot else None,
            "name": row.name, "parent_run_id": row.parent_run_id, "published_at": row.published_at}


@router.get("")
def list_runs(user=Depends(administrator), db: DB = Depends(db_session)):
    ws = db.get(Workspace, 1)
    rows = list(db.scalars(select(ScheduleRun).order_by(ScheduleRun.created_at.desc()).limit(20)))
    published = db.scalar(select(ScheduleRun).where(ScheduleRun.published_at.isnot(None)))
    if published and published not in rows:
        rows.append(published)
    return [representation(r, ws.version) for r in rows]


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
        plan = existing.snapshot.get("plan") or {}
        same_scope = (plan.get("scope"), plan.get("base_run_id")) == (scope_key(body.scope) if body.scope else None, str(body.base_run_id) if body.base_run_id else None)
        if SolverSettings.model_validate(existing.snapshot.get("provenance", {}).get("solver_config", CONFIG)).model_dump() != body.settings.model_dump() or existing.snapshot.get("provenance", {}).get("source_run_id") != (str(body.source_run_id) if body.source_run_id else None) or not same_scope:
            fail(409, "request_conflict")
        return representation(existing, ws.version)
    ws = lock_workspace(request, db)
    if (body.base_run_id and not body.scope) or (body.scope and body.source_run_id):
        fail(422, "invalid_scope")
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
        snap = snapshot_of(db, ws)
        if body.scope:
            snap = with_plan(db, ws, snap, body)
        snap = seal_snapshot(snap, body.settings.model_dump())
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
def download_statistics(ident: str, format: str = "pdf", group: str | None = None, year: str | None = None, major: str | None = None,
                        user=Depends(administrator), db: DB = Depends(db_session)):
    row = db.get(ScheduleRun, ident)
    if not row:
        fail(404, "not_found")
    if row.status != "completed" or not row.result or not row.result.get("validation", {}).get("passed"):
        fail(409, "statistics_unavailable")
    if format not in ("pdf", "html", "json"):
        fail(422, "invalid_input")
    # Recompute from the saved snapshot and assignments so every report uses the current
    # definitions; keep the time the statistics were first saved.
    # A report for one group, or a year and/or programme: the Timetable page's filters.
    scope = {"group": group} if group else {k: v for k, v in (("year", year), ("major", major)) if v} or None
    from app.statistics import scope_groups
    if scope and not scope_groups(row.snapshot, scope):
        fail(422, "invalid_scope")
    saved = row.result.get("statistics") or {}
    stats = build_statistics(row.snapshot, row.result, scope)
    stats["generated_at"] = saved.get("generated_at") or row.created_at.isoformat()
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
    return Response(content=content, media_type=media, headers={"Content-Disposition": report_disposition(row, format, (stats.get("scope") or {}).get("label")), "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/{ident}/timetable.pdf")
def download_timetable(ident: str, group: str | None = None, year: str | None = None, major: str | None = None,
                       user=Depends(administrator), db: DB = Depends(db_session)):
    """The timetable (or one group's, year's or programme's part of it) as a landscape PDF."""
    from urllib.parse import quote
    from app.statistics import scope_groups, scope_label
    from app.timetable_pdf import short_name, timetable_pdf
    row = db.get(ScheduleRun, ident)
    if not row:
        fail(404, "not_found")
    if row.status != "completed" or not (row.result or {}).get("validation", {}).get("passed"):
        fail(409, "statistics_unavailable")
    scope = {"group": group} if group else {k: v for k, v in (("year", year), ("major", major)) if v} or None
    chosen = scope_groups(row.snapshot, scope)
    if scope and not chosen:
        fail(422, "invalid_scope")
    groups_of = {r["id"]: set(r.get("group_ids", [])) for r in row.snapshot["records"] if r["kind"] == "courses"}
    rows = [a for a in row.result["assignments"] if chosen is None or groups_of.get(a["activity_id"], set()) & chosen]
    stale = row.input_version != db.get(Workspace, 1).version
    status = "Published" if row.published_at else "Draft - not published"
    subtitle = " · ".join(x for x in [scope_label(row.snapshot, scope) or "All groups", f"{len(rows)} sessions", status,
                                      "Outdated: inputs changed since generation" if stale else "", f"Draft {row.id[:8]}"] if x)
    name = short_name(row.snapshot, scope)
    content = timetable_pdf(row.snapshot, rows, name, subtitle)
    fallback = name.encode("ascii", "ignore").decode("ascii") or "Schedule"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=\"{fallback}.pdf\"; filename*=UTF-8''{quote(name + '.pdf', safe='')}"})
