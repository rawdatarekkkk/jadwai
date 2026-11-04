"""Shared course eligibility, used by teaching-activity creation and editing."""
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import Field, field_validator
from sqlalchemy import select, func
from app.schemas import Strict, Name, Code
from app.models import CourseCatalog, Record
from app.dependencies import administrator, current_user, db_session, lock_workspace, audit, fail

router = APIRouter()

class CourseSetup(Strict):
    name: Name
    code: Code
    eligibility: dict[str, list[str]]
    # Imported catalogue courses may have no groups yet; then expected_students sizes their exam.
    group_ids: list[str] = Field(max_length=200)
    expected_students: int | None = Field(default=None, ge=1, le=5000, strict=True)

    @field_validator('eligibility')
    @classmethod
    def valid_types(cls, value):
        if set(value) != {'lecture', 'tutorial', 'lab'} or not any(value.values()):
            raise ValueError('Define at least one teaching type')
        if any(len(ids) > 30 or len(ids) != len(set(ids)) for ids in value.values()):
            raise ValueError('Invalid eligibility')
        return value

    @field_validator('group_ids')
    @classmethod
    def distinct_groups(cls, value):
        if len(value) != len(set(value)): raise ValueError('Duplicate groups')
        return value

@router.post('/api/course-catalog', status_code=201)
@router.put('/api/course-catalog/{ident}')
def save_course(body: CourseSetup, request: Request, ident: str | None = None,
                user=Depends(administrator), db=Depends(db_session)):
    ws = lock_workspace(request, db)
    row = db.get(CourseCatalog, ident) if ident else CourseCatalog(id=str(uuid4()))
    if row is None: fail(404, 'not_found')
    if db.scalar(select(CourseCatalog).where(func.lower(CourseCatalog.code) == body.code.lower(), CourseCatalog.id != row.id)):
        fail(409, 'duplicate_code')
    for ids, kind in [(body.group_ids, 'groups')] + [(ids, 'instructors') for ids in body.eligibility.values()]:
        for ref in ids:
            record = db.get(Record, ref)
            if not record or record.kind != kind: fail(422, 'invalid_reference')
    from app.positions import position_conflict
    if any(position_conflict(kind, db.get(Record, ref).data) for kind, ids in body.eligibility.items() for ref in ids):
        fail(422, 'instructor_position')
    linked = [r for r in db.scalars(select(Record).where(Record.kind == 'courses')) if r.activity.course_id == row.id]
    if any(not set(r.data['eligible_instructors']) <= set(body.eligibility[r.data['activity_type']]) or not set(r.data['group_ids']) <= set(body.group_ids) for r in linked):
        fail(409, 'course_eligibility_in_use')
    row.name, row.code, row.eligibility, row.group_ids = body.name, body.code, body.eligibility, body.group_ids
    row.expected_students = body.expected_students
    for activity in linked: activity.name = body.name
    db.add(row)
    audit(db, ws, user, f'Updated course {body.code}' if ident else f'Added course {body.code}')
    db.commit()
    return {'id': row.id, 'version': ws.version}
