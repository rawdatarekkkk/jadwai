"""Personal timetables for students and instructors: published runs only, own sessions only."""
import csv
import io
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from app.dependencies import current_user, db_session, fail
from app.models import ExamRun, Record, ScheduleRun, Workspace

router = APIRouter()
SAFE_FIELDS = ('id', 'kind', 'name', 'code', 'year', 'major', 'activity_type')


def personal(db, user):
    if user.role == 'student':
        owner = db.get(Record, user.group_id) if user.group_id else None
        kind = 'groups'
    elif user.role == 'instructor':
        owner = db.get(Record, user.instructor_id) if user.instructor_id else None
        kind = 'instructors'
    else:
        fail(403, 'permission_denied')
    if not owner or owner.kind != kind:
        return None, None, []
    teaching = None
    row = db.scalar(select(ScheduleRun).where(ScheduleRun.published_at.isnot(None)))
    if row and row.result and row.result.get('validation', {}).get('passed'):
        records = {r['id']: r for r in row.snapshot['records']}
        if kind == 'groups':
            mine = {r['id'] for r in records.values() if r['kind'] == 'courses' and owner.id in r.get('group_ids', [])}
            assignments = [a for a in row.result['assignments'] if a['activity_id'] in mine]
        else:
            assignments = [a for a in row.result['assignments'] if a['instructor_id'] == owner.id]
        ids = {owner.id} | {a[k] for a in assignments for k in ('activity_id', 'room_id', 'instructor_id')}
        if kind == 'instructors':
            ids |= {g for a in assignments for g in records[a['activity_id']]['group_ids']}
        safe_records = []
        for ident in sorted(ids):
            if ident not in records:
                continue
            safe = {k: v for k, v in records[ident].items() if k in SAFE_FIELDS}
            if records[ident]['kind'] == 'courses':
                safe['group_ids'] = [owner.id] if kind == 'groups' else records[ident]['group_ids']
            safe_records.append(safe)
        teaching = {'id': row.id, 'name': row.name, 'status': 'completed', 'published_at': row.published_at, 'created_at': row.created_at,
                    'input_version': row.input_version, 'stale': row.input_version != db.get(Workspace, 1).version,
                    'snapshot': {'name': row.snapshot['name'], 'term': row.snapshot['term'], 'calendar': row.snapshot['calendar'], 'records': safe_records},
                    'result': {'assignments': assignments}}
    exams = []
    exam_run = db.scalar(select(ExamRun).where(ExamRun.published_at.isnot(None)))
    if exam_run and exam_run.result.get('status') == 'completed':
        for a in exam_run.result['assignments']:
            course = next((c for c in exam_run.snapshot['courses'] if c['id'] == a['course_id']), {})
            halls = a.get('halls') or []
            if kind == 'groups' and 'group:' + owner.id in course.get('participants', []):
                exams.append({**{k: a[k] for k in ('course_code', 'course_name', 'date', 'start_time', 'end_time')}, 'halls': [h['room_code'] for h in halls], 'role': 'student'})
            if kind == 'instructors':
                duties = [h['room_code'] for h in halls if h.get('invigilator_id') == owner.id]
                if duties:
                    exams.append({**{k: a[k] for k in ('course_code', 'course_name', 'date', 'start_time', 'end_time')}, 'halls': duties, 'role': 'invigilator'})
    return owner, teaching, sorted(exams, key=lambda e: (e['date'], e['start_time']))


@router.get('/api/me/schedule')
@router.get('/api/student/schedule')
def my_schedule(user=Depends(current_user), db=Depends(db_session)):
    owner, teaching, exams = personal(db, user)
    who = {'id': owner.id, **owner.data} if owner else None
    if who and owner.kind == 'instructors':
        who = {k: v for k, v in who.items() if k in ('id', 'name', 'code', 'department', 'position')}
    return {'group' if user.role == 'student' else 'instructor': who, 'run': teaching, 'exams': exams}


def csv_text(rows):
    stream = io.StringIO()
    writer = csv.writer(stream)
    safe = lambda v: "'" + str(v) if str(v).startswith(('=', '+', '-', '@', '\t', '\r')) else str(v)
    for row in rows:
        writer.writerow([safe(v) for v in row])
    return '﻿' + stream.getvalue()


def teaching_rows(snapshot, assignments):
    records = {r['id']: r for r in snapshot['records']}
    clock = lambda m: f'{m // 60:02d}:{m % 60:02d}'
    order = {d: i for i, d in enumerate(snapshot['calendar']['days'])}
    rows = [['Day', 'Start', 'End', 'Course', 'Type', 'Groups', 'Room', 'Instructor']]
    for a in sorted(assignments, key=lambda a: (order.get(a['day'], 9), a['start_minute'])):
        activity = records.get(a['activity_id'], {})
        rows.append([a['day'], clock(a['start_minute']), clock(a['end_minute']), activity.get('name', ''), activity.get('activity_type', ''),
                     '; '.join(records.get(g, {}).get('code', '') for g in activity.get('group_ids', [])),
                     records.get(a['room_id'], {}).get('code', ''), records.get(a['instructor_id'], {}).get('name', '')])
    return rows


@router.get('/api/me/schedule.csv')
def my_schedule_csv(user=Depends(current_user), db=Depends(db_session)):
    owner, teaching, exams = personal(db, user)
    if not teaching and not exams:
        fail(404, 'not_published')
    rows = teaching_rows(teaching['snapshot'], teaching['result']['assignments']) if teaching else [['Day', 'Start', 'End', 'Course', 'Type', 'Groups', 'Room', 'Instructor']]
    rows += [[], ['Exam date', 'Start', 'End', 'Course', 'Role', 'Halls']] + [[e['date'], e['start_time'], e['end_time'], e['course_name'], e['role'], '; '.join(e['halls'])] for e in exams]
    return Response(csv_text(rows), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="my-timetable.csv"'})


@router.get('/api/schedules/{ident}/export.csv')
def export_schedule_csv(ident: str, user=Depends(current_user), db=Depends(db_session)):
    if user.role != 'administrator':
        fail(403, 'permission_denied')
    row = db.get(ScheduleRun, ident)
    if not row or row.status != 'completed':
        fail(404, 'not_found')
    label = 'published' if row.published_at else 'draft'
    return Response(csv_text(teaching_rows(row.snapshot, row.result['assignments'])), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="JadwAI-timetable-{label}-{row.id[:8]}.csv"'})
