from pydantic import ValidationError
from sqlalchemy import select

from app.dependencies import fail
from app.models import Record
from app.schemas import SCHEMAS


def validate_record(kind, data, db, record_id=None):
    if kind not in SCHEMAS:
        fail(404, "not_found")
    try:
        body = SCHEMAS[kind].model_validate(data).model_dump()
    except ValidationError:
        fail(422, "invalid_input")
    if kind == "instructors" and body.get("max_weekly_hours") is None:
        body.pop("max_weekly_hours", None)
    others = db.scalars(select(Record).where(Record.kind == kind)).all()
    if any(
        r.id != record_id and r.data["code"].casefold() == body["code"].casefold()
        for r in others
    ):
        fail(409, "duplicate_code")
    if kind == "groups" and body.get("major"):
        if not body.get("year"):
            fail(422, "invalid_input")
        # Keep one spelling for a major within a year when only case differs.
        canonical = next((r.data["major"] for r in others if r.id != record_id and r.data.get("year") == body["year"] and r.data.get("major") and r.data["major"].casefold() == body["major"].casefold()), None)
        if canonical:
            body["major"] = canonical
    if kind == "rooms" and (body.get("reserved_majors") or body.get("reserved_course_ids")):
        # A special room is reserved for programmes that exist and catalogue courses that exist.
        from app.models import CourseCatalog
        majors = {r.data.get("major") for r in db.scalars(select(Record).where(Record.kind == "groups")) if r.data.get("major")}
        canonical = {m.casefold(): m for m in majors}
        if any(m.casefold() not in canonical for m in body["reserved_majors"]):
            fail(422, "unknown_programme")
        body["reserved_majors"] = sorted({canonical[m.casefold()] for m in body["reserved_majors"]})
        if any(not db.get(CourseCatalog, c) for c in body["reserved_course_ids"]):
            fail(422, "invalid_reference")
        body["reserved_course_ids"] = sorted(set(body["reserved_course_ids"]))
    if kind == "courses" and body.get("course_id"):
        from app.models import CourseCatalog
        course = db.get(CourseCatalog, body["course_id"])
        if not course or not set(body["eligible_instructors"]) <= set(course.eligibility.get(body["activity_type"], [])) or not set(body["group_ids"]) <= set(course.group_ids):
            fail(422, "invalid_course_eligibility")
        body["name"] = course.name
    if kind == "courses":
        from app.models import Workspace

        from app.calendar_slots import day_placements
        calendar = db.get(Workspace, 1)
        cal = {"teaching_periods": calendar.teaching_periods, "start_hour": calendar.start_hour, "end_hour": calendar.end_hour, "period_minutes": calendar.period_minutes}
        if not day_placements(cal, body["duration"]):
            fail(422, "outside_calendar")
    if kind == "courses":
        from app.positions import position_conflict
        for key, expected in [
            ("eligible_instructors", "instructors"),
            ("group_ids", "groups"),
        ]:
            for ident in body[key]:
                ref = db.get(Record, ident)
                if not ref or ref.kind != expected:
                    fail(422, "invalid_reference")
                if expected == "instructors" and position_conflict(body["activity_type"], ref.data):
                    fail(422, "instructor_position")
    if kind == "instructors" and record_id and body.get("position"):
        # A new position may not contradict teaching eligibility that is already saved.
        from app.models import CourseCatalog
        from app.positions import REQUIRED
        wrong = {t for t, needed in REQUIRED.items() if needed != body["position"]}
        if any(r.data["activity_type"] in wrong and record_id in r.data["eligible_instructors"] for r in db.scalars(select(Record).where(Record.kind == "courses"))) or any(record_id in c.eligibility.get(t, []) for c in db.scalars(select(CourseCatalog)) for t in wrong):
            fail(409, "position_in_use")
    return body
