"""Advising students: students whose courses differ from their home group's.

Each student keeps their home group's sessions except for dropped courses, and joins
another group's sessions for added courses (a retake, or a course from another plan).
The resulting personal session list is a hard constraint in teaching generation (no two
of their sessions overlap) and each student is an exam cohort of their own."""
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import Field, model_validator
from sqlalchemy import select, func
from app.dependencies import administrator, audit, db_session, fail, lock_workspace
from app.models import AdvisingChange, AdvisingStudent, CourseCatalog, Record
from app.schemas import Code, Name, Strict
from app.advising_rules import personal_sessions

router = APIRouter(prefix='/api/advising-students')


def student_rows(db):
    """Every advising student with their personal sessions and courses, for snapshots."""
    activities = [{'id': r.id, 'course_id': r.activity.course_id, 'group_ids': [g.group_id for g in r.activity.groups]}
                  for r in db.scalars(select(Record).where(Record.kind == 'courses'))]
    catalogue = {c.id: c.group_ids or [] for c in db.scalars(select(CourseCatalog))}
    rows = []
    for s in db.scalars(select(AdvisingStudent).order_by(AdvisingStudent.code)):
        data = describe(s)
        data['activity_ids'], data['course_ids'] = personal_sessions(data, activities, catalogue)
        rows.append(data)
    return rows


def describe(s):
    return {'id': s.id, 'code': s.code, 'name': s.name, 'group_id': s.group_id,
            'changes': sorted(({'action': c.action, 'course_id': c.course_id, 'group_id': c.group_id} for c in s.changes), key=lambda c: (c['action'], c['course_id']))}


class Change(Strict):
    action: str = Field(pattern='^(drop|add)$')
    course_id: str
    group_id: str | None = None


class StudentInput(Strict):
    code: Code
    name: Name
    group_id: str | None = None
    changes: list[Change] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def consistent(self):
        keys = [(c.action, c.course_id) for c in self.changes]
        if len(keys) != len(set(keys)):
            raise ValueError('Each course may be dropped or added once')
        for c in self.changes:
            if (c.action == 'add') != (c.group_id is not None):
                raise ValueError('An added course needs the group whose sessions the student joins; a dropped course has none')
        if not self.changes:
            raise ValueError('An advising student needs at least one dropped or added course')
        return self


@router.get('')
def list_students(user=Depends(administrator), db=Depends(db_session)):
    return {'students': student_rows(db)}


@router.post('', status_code=201)
@router.put('/{ident}')
def save_student(body: StudentInput, request: Request, ident: str | None = None, user=Depends(administrator), db=Depends(db_session)):
    ws = lock_workspace(request, db)
    row = db.get(AdvisingStudent, ident) if ident else AdvisingStudent(id=str(uuid4()))
    if row is None:
        fail(404, 'not_found')
    if db.scalar(select(AdvisingStudent).where(func.lower(AdvisingStudent.code) == body.code.lower(), AdvisingStudent.id != row.id)):
        fail(409, 'duplicate_code')
    group = lambda ident: (r := db.get(Record, ident)) is not None and r.kind == 'groups'
    if body.group_id and not group(body.group_id):
        fail(422, 'invalid_reference')
    activities = [{'id': r.id, 'course_id': r.activity.course_id, 'group_ids': [g.group_id for g in r.activity.groups]}
                  for r in db.scalars(select(Record).where(Record.kind == 'courses'))]
    catalogue = {c.id: c.group_ids or [] for c in db.scalars(select(CourseCatalog))}
    home_courses = {a['course_id'] for a in activities if body.group_id in a['group_ids']} | {c for c, g in catalogue.items() if body.group_id in g}
    dropped = {c.course_id for c in body.changes if c.action == 'drop'}
    for c in body.changes:
        if c.course_id not in catalogue or (c.group_id and not group(c.group_id)):
            fail(422, 'invalid_reference')
        if c.action == 'drop' and c.course_id not in home_courses:
            fail(422, 'not_a_home_course')
        if c.action == 'add':
            if c.course_id in home_courses and c.course_id not in dropped:
                fail(422, 'already_taking_course')
            if not any(a['course_id'] == c.course_id and c.group_id in a['group_ids'] for a in activities):
                fail(422, 'no_sessions_for_group')
    row.code, row.name, row.group_id = body.code, body.name, body.group_id
    row.changes = [AdvisingChange(course_id=c.course_id, action=c.action, group_id=c.group_id) for c in body.changes]
    db.add(row)
    audit(db, ws, user, f'Updated advising student {body.code}' if ident else f'Added advising student {body.code}')
    db.commit()
    return {'id': row.id, 'version': ws.version}


@router.delete('/{ident}')
def delete_student(ident: str, request: Request, user=Depends(administrator), db=Depends(db_session)):
    ws = lock_workspace(request, db)
    row = db.get(AdvisingStudent, ident)
    if row is None:
        fail(404, 'not_found')
    db.delete(row)
    audit(db, ws, user, f'Removed advising student {row.code}')
    db.commit()
    return {'version': ws.version}
