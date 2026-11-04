from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as DB

from app.academic import validate_record
from app.accounts import router as accounts_router
from app.dependencies import audit, current_user, db_session, fail, lock_workspace
from app.imports import router as import_router
from app.locks import router as locks_router
from app.models import AssignmentLock, CourseCatalog
from app.models import (
    Audit,
    Record,
    Rule,
    User,
    Workspace,
)
from app.schemas import CalendarInput, RuleInput
from app.schedules import router as schedules_router

app = FastAPI(title="JadwAI API", version="0.2.0")
app.include_router(accounts_router)
app.include_router(import_router)
app.include_router(locks_router)
app.include_router(schedules_router)
from app.exams import router as exams_router
app.include_router(exams_router)
from app.course_catalog import router as course_catalog_router
app.include_router(course_catalog_router)
from app.proposals import router as proposals_router
app.include_router(proposals_router)


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    return JSONResponse(status_code=422, content={"detail": "invalid_input"})


@app.exception_handler(DBAPIError)
async def database_unavailable(request, error):
    return JSONResponse(status_code=503, content={"detail": "database_unavailable"})


@app.get("/api/workspace")
def workspace(
    response: Response, user=Depends(current_user), db: DB = Depends(db_session)
):
    ws = db.scalar(
        select(Workspace).where(Workspace.id == 1).with_for_update(read=True)
    )
    if not ws:
        fail(503, "workspace_missing")
    response.headers["ETag"] = f'"{ws.version}"'
    records = db.scalars(select(Record).order_by(Record.kind, Record.id)).all()
    rules = db.scalars(select(Rule).order_by(Rule.id)).all()
    events = db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(30)).all()
    return {
        "name": ws.name,
        "term": ws.term,
        "version": ws.version,
        "calendar": {
            key: getattr(ws, key)
            for key in [
                "timezone",
                "days",
                "start_hour",
                "end_hour",
                "period_minutes",
                "teaching_periods",
                "realism_policy",
                "start_date",
                "end_date",
            ]
        },
        "course_catalog": [dict(id=c.id, name=c.name, code=c.code, source_info=c.source_info, eligibility=c.eligibility, group_ids=c.group_ids, expected_students=c.expected_students) for c in db.scalars(select(CourseCatalog).order_by(CourseCatalog.name))],
        "records": [{"id": r.id, "kind": r.kind, **r.data} for r in records],
        "assignment_locks": [row.data for row in db.scalars(select(AssignmentLock).order_by(AssignmentLock.created_at,AssignmentLock.id))],
        "rules": [
            {"id": r.id, **r.data, "status": r.status, "approved_by": r.approved_by}
            for r in rules
        ],
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "actor": e.actor,
                "action_code": e.action_code,
                "params": e.params,
                "at": e.created_at,
                "version": e.input_version,
            }
            for e in events
        ],
    }


@app.post("/api/records/{kind}", status_code=201)
def create_record(
    kind: str,
    data: dict,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    body = validate_record(kind, data, db)
    record = Record(id=str(uuid4()), kind=kind, data=body)
    db.add(record)
    audit(db, ws, user, f"Added {body['code']}")
    db.commit()
    return {"id": record.id, "version": ws.version}


@app.put("/api/records/{kind}/{ident}")
def update_record(
    kind: str,
    ident: str,
    data: dict,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    record = db.get(Record, ident)
    if not record or record.kind != kind:
        fail(404, "not_found")
    record.data = validate_record(kind, data, db, ident)
    audit(db, ws, user, f"Updated {record.data['code']}")
    db.commit()
    return {"version": ws.version}


@app.delete("/api/records/{kind}/{ident}", status_code=204)
def delete_record(
    kind: str,
    ident: str,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    record = db.get(Record, ident)
    if not record or record.kind != kind:
        fail(404, "not_found")
    courses = db.scalars(select(Record).where(Record.kind == "courses")).all()
    rules = db.scalars(select(Rule)).all()
    if any(
        ident in c.data.get("eligible_instructors", []) + c.data.get("group_ids", [])
        for c in courses
    ) or any(ident in [r.instructor_id, r.room_id, r.group_id, r.activity_id] for r in rules):
        fail(409, "record_in_use")
    if any(ident in (lock.activity_id,lock.instructor_id,lock.room_id) for lock in db.scalars(select(AssignmentLock))):
        fail(409, "record_in_use")
    if any(ident in c.group_ids or any(ident in ids for ids in c.eligibility.values()) for c in db.scalars(select(CourseCatalog))):
        fail(409, "record_in_use")
    if db.scalar(select(User.id).where((User.group_id == ident) | (User.instructor_id == ident))):
        fail(409, "record_in_use")
    db.delete(record)
    audit(db, ws, user, f"Removed {record.data['code']}")
    db.commit()


def validate_rule(body, db):
    from app.rule_validation import rule_error
    def kind_of(ident):
        record = db.get(Record, ident) if isinstance(ident, str) else None
        return record.kind if record else None
    calendar = db.get(Workspace, 1)
    error = rule_error(body, kind_of, {
        "days": calendar.days, "start_hour": calendar.start_hour, "end_hour": calendar.end_hour,
    })
    if error:
        fail(422, error)


@app.post("/api/rules", status_code=201)
def create_rule(
    body: RuleInput,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    validate_rule(body, db)
    rule = Rule(id=str(uuid4()), data=body.model_dump(), status="draft")
    db.add(rule)
    audit(db, ws, user, f"Created rule: {body.title}")
    db.commit()
    return {"id": rule.id, "version": ws.version}


@app.post("/api/rules/{ident}/{action}")
def transition_rule(
    ident: str,
    action: str,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    rule = db.get(Rule, ident)
    if not rule:
        fail(404, "not_found")
    if action not in ("approve", "revoke"):
        fail(404, "not_found")
    if (action == "approve") == (rule.status == "approved"):
        fail(409, "invalid_transition")
    if action == "approve":
        validate_rule(RuleInput(**rule.data), db)
    rule.status = "approved" if action == "approve" else "draft"
    rule.approved_by = user.id if action == "approve" else None
    audit(db, ws, user, f"{action.capitalize()} rule: {rule.data['title']}")
    db.commit()
    return {"version": ws.version}


@app.delete("/api/rules/{ident}", status_code=204)
def delete_rule(
    ident: str,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    rule = db.get(Rule, ident)
    if not rule:
        fail(404, "not_found")
    if rule.status == "approved":
        fail(409, "revoke_before_delete")
    db.delete(rule)
    audit(db, ws, user, f"Removed rule: {rule.data['title']}")
    db.commit()


@app.put("/api/workspace")
def update_calendar(
    body: CalendarInput,
    request: Request,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    for rule in db.scalars(select(Rule)):
        data = rule.data
        if (
            data["start_hour"] is not None and (
                (data["day"] is not None and data["day"] not in body.days)
                or data["start_hour"] < body.start_hour
                or data["end_hour"] > body.end_hour
            )
        ):
            fail(409, "calendar_conflict")
    for record in db.scalars(select(Record).where(Record.kind == "courses")):
        from app.calendar_slots import day_placements
        if not day_placements(body.model_dump(), record.data["duration"]):
            fail(409, "calendar_conflict")
    for key, value in body.model_dump().items():
        setattr(ws, key, value)
    from app.dependencies import event

    event(db, ws, user, "calendar.updated", body.term, changes_inputs=True)
    db.commit()
    return {"version": ws.version}


from app.source_timetables import router as source_timetables_router
app.include_router(source_timetables_router)

from app.evaluation_portal import router as evaluation_router
app.include_router(evaluation_router)

from app.model_calls import router as model_calls_router
app.include_router(model_calls_router)

from app.scenarios import router as scenarios_router
app.include_router(scenarios_router)

from app.portal import router as portal_router
app.include_router(portal_router)
