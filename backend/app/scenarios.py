"""Named scenarios, validated manual edits, comparison and publication of timetables.

Saved runs are never changed: an edit creates a new run from the same frozen snapshot
and is kept only if the independent validator passes. Publishing re-validates the run
against the *current* approved inputs under the exclusive workspace lock, and a partial
unique index guarantees one published teaching timetable and one published exam timetable.
"""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request
from pydantic import Field
from app.schemas import Name, Strict
from app.dependencies import administrator, db_session, event, fail, lock_workspace, workspace_lock
from app.models import ExamRun, ScheduleRun, utcnow

router = APIRouter()


class Rename(Strict):
    name: Name


class Change(Strict):
    activity_id: str
    occurrence: int = Field(ge=0, lt=10, strict=True)
    day: str | None = None
    start_minute: int | None = Field(default=None, ge=0, lt=1440, strict=True)
    room_id: str | None = None
    instructor_id: str | None = None


class Edit(Strict):
    request_key: UUID
    changes: list[Change] = Field(min_length=1, max_length=50)
    name: Name | None = None


def completed(row):
    return row and row.status == 'completed' and (row.result or {}).get('validation', {}).get('passed')


def schedule(db, ident):
    row = db.get(ScheduleRun, ident)
    if not row:
        fail(404, 'not_found')
    return row


@router.put('/api/schedules/{ident}/name')
def rename(ident: str, body: Rename, user=Depends(administrator), db=Depends(db_session)):
    ws = workspace_lock(db)
    row = schedule(db, ident)
    row.name = body.name
    event(db, ws, user, 'schedule.renamed', row.id)
    db.commit()
    return {'id': row.id, 'name': row.name}


@router.post('/api/schedules/{ident}/edits', status_code=201)
def edit(ident: str, body: Edit, request: Request, user=Depends(administrator), db=Depends(db_session)):
    from app.calendar_slots import end_for
    from app.statistics import build_statistics
    from app.validation import validate_schedule
    existing = db.query(ScheduleRun).filter(ScheduleRun.request_key == str(body.request_key)).one_or_none()
    if existing:
        if existing.parent_run_id != ident:
            fail(409, 'request_conflict')
        return {'id': existing.id}
    ws = workspace_lock(db)
    source = schedule(db, ident)
    if not completed(source):
        fail(409, 'invalid_transition')
    snapshot = source.snapshot
    activities = {r['id']: r for r in snapshot['records'] if r['kind'] == 'courses'}
    rows = [dict(a) for a in source.result['assignments']]
    for change in body.changes:
        target = next((a for a in rows if (a['activity_id'], a['occurrence']) == (change.activity_id, change.occurrence)), None)
        if not target:
            fail(422, 'invalid_edit')
        if (change.day is None) != (change.start_minute is None):
            fail(422, 'invalid_edit')
        if change.day is not None:
            end = end_for(snapshot['calendar'], activities[change.activity_id]['duration'], change.start_minute)
            if end is None:
                fail(422, 'invalid_edit')
            target.update(day=change.day, start_minute=change.start_minute, end_minute=end)
        if change.room_id is not None:
            target['room_id'] = change.room_id
        if change.instructor_id is not None:
            # One instructor teaches every weekly occurrence of an activity.
            for a in rows:
                if a['activity_id'] == change.activity_id:
                    a['instructor_id'] = change.instructor_id
    report = validate_schedule(snapshot, rows)
    if not report['passed']:
        fail(422, {'code': 'edit_breaks_rules', 'errors': report['errors'], 'violations': report.get('violations', [])[:20]})
    result = {'status': 'completed', 'assignments': rows, 'validation': report,
              'manual_edit': {'source_run_id': source.id, 'changes': [c.model_dump() for c in body.changes], 'edited_by': user.id},
              'objective_definition': 'manual-edit', 'provenance': (source.result or {}).get('provenance'),
              'lifecycle': {'queued_at': utcnow().isoformat(), 'finished_at': utcnow().isoformat()}}
    result['statistics'] = build_statistics(snapshot, result)
    row = ScheduleRun(id=str(uuid4()), workspace_id=1, created_by=user.id, input_version=source.input_version,
                      request_key=str(body.request_key), snapshot=snapshot, status='completed', result=result,
                      name=body.name or (source.name if (source.name or '').endswith(' (edited)') else f"{source.name or 'Draft'} (edited)"), parent_run_id=source.id)
    db.add(row)
    event(db, ws, user, 'schedule.edited', row.id)
    db.commit()
    return {'id': row.id}


@router.get('/api/schedule-comparisons')
def compare(a: str, b: str, user=Depends(administrator), db=Depends(db_session)):
    from app.realism_validation import convenience_components
    from app.validation_details import preference_penalty
    left, right = schedule(db, a), schedule(db, b)
    if not completed(left) or not completed(right):
        fail(409, 'invalid_transition')
    key = lambda x: (x['activity_id'], x['occurrence'])
    before = {key(x): x for x in left.result['assignments']}
    after = {key(x): x for x in right.result['assignments']}
    fields = ('day', 'start_minute', 'end_minute', 'room_id', 'instructor_id')
    moved = [{'activity_id': k[0], 'occurrence': k[1], 'before': {f: before[k][f] for f in fields}, 'after': {f: after[k][f] for f in fields},
              'changed': [f for f in fields if before[k][f] != after[k][f]]}
             for k in sorted(before.keys() & after.keys()) if any(before[k][f] != after[k][f] for f in fields)]
    def metrics(row):
        rows = row.result['assignments']
        return {'preferences': preference_penalty(row.snapshot, rows)['total'], **convenience_components(row.snapshot, rows),
                'same_inputs': row.input_version}
    return {'a': {'id': left.id, 'name': left.name, 'metrics': metrics(left)}, 'b': {'id': right.id, 'name': right.name, 'metrics': metrics(right)},
            'moved_sessions': moved, 'only_in_a': len(before.keys() - after.keys()), 'only_in_b': len(after.keys() - before.keys()),
            'note': 'Lower is better for every metric. Runs made from different inputs are not directly comparable.'}


def publish_row(db, ws, user, model, row, kind):
    """Unpublish the current one and publish `row` in one transaction."""
    for other in db.query(model).filter(model.published_at.isnot(None), model.id != row.id):
        other.published_at = None
    db.flush()
    row.published_at = utcnow()
    event(db, ws, user, f'{kind}.published', row.id)
    db.commit()
    return {'id': row.id, 'published_at': row.published_at}


@router.post('/api/schedules/{ident}/publish')
def publish(ident: str, request: Request, user=Depends(administrator), db=Depends(db_session)):
    from app.schedules import snapshot_of
    from app.validation import validate_schedule
    ws = lock_workspace(request, db)
    row = schedule(db, ident)
    if not completed(row):
        fail(409, 'invalid_transition')
    if row.input_version != ws.version:
        fail(409, 'stale_schedule')
    from app.partial_plan import complete
    if not complete(row.snapshot):
        fail(409, 'schedule_incomplete')  # a part of the timetable; schedule the remaining programmes first
    current = snapshot_of(db, ws)
    report = validate_schedule(current, row.result['assignments'])
    if not report['passed']:
        fail(409, {'code': 'publication_validation_failed', 'errors': report['errors']})
    return publish_row(db, ws, user, ScheduleRun, row, 'schedule')


class MergeInput(Strict):
    request_key: UUID
    # Publish only these groups' sessions from the draft (a whole timetable or a part); everyone else keeps the published week.
    groups: list[str] = Field(default_factory=list, max_length=50)


@router.post('/api/schedules/{ident}/publish-merged', status_code=201)
def publish_merged(ident: str, body: MergeInput, request: Request, user=Depends(administrator), db=Depends(db_session)):
    """Publish a part (a programme, year or group) into the published timetable.

    The part's sessions replace those same activities in the published timetable; the combined
    week is checked against the current inputs (rooms, instructors, students, rules, coverage)
    and published as a new version only if it passes. Other groups keep their published week."""
    from app.provenance import CONFIG, seal_snapshot
    from app.schedules import snapshot_of
    from app.statistics import build_statistics
    from app.validation import validate_schedule
    existing = db.query(ScheduleRun).filter(ScheduleRun.request_key == str(body.request_key)).one_or_none()
    if existing:
        if (existing.result or {}).get('merge', {}).get('part_run_id') != ident:
            fail(409, 'request_conflict')
        return {'id': existing.id, 'published_at': existing.published_at}
    ws = lock_workspace(request, db)
    part = schedule(db, ident)
    if not completed(part):
        fail(409, 'invalid_transition')
    plan = (part.snapshot or {}).get('plan')
    if not plan and not body.groups:
        fail(409, 'not_a_part')  # a complete timetable: publish it directly
    if part.input_version != ws.version:
        fail(409, 'stale_schedule')
    published = db.query(ScheduleRun).filter(ScheduleRun.published_at.isnot(None)).one_or_none()
    if not completed(published):
        fail(409, 'nothing_published')
    if body.groups:
        # The groups' own sessions (lectures they share move for the other groups too), and sessions the published
        # timetable does not have yet (added since it was published): without them it would be incomplete.
        acts = {r['id']: r for r in part.snapshot['records'] if r['kind'] == 'courses'}
        chosen = set(body.groups)
        if not chosen & {r['id'] for r in part.snapshot['records'] if r['kind'] == 'groups'}:
            fail(422, 'invalid_scope')
        have = {a['activity_id'] for a in published.result['assignments']}
        placed = {a['activity_id'] for a in part.result['assignments']
                  if chosen & set(acts.get(a['activity_id'], {}).get('group_ids') or []) or a['activity_id'] not in have}
        scope = [{'group': g} for g in body.groups]
    else:
        placed, scope = set(plan['activity_ids']), plan.get('scope')
    merged = [dict(a) for a in published.result['assignments'] if a['activity_id'] not in placed] + \
             [dict(a) for a in part.result['assignments'] if a['activity_id'] in placed]
    config = ((published.snapshot or {}).get('provenance') or {}).get('solver_config') or CONFIG
    snapshot = seal_snapshot(snapshot_of(db, ws), config)
    report = validate_schedule(snapshot, merged)
    if not report['passed']:
        fail(409, {'code': 'merge_validation_failed', 'errors': report['errors'], 'violations': report.get('violations', [])[:20]})
    result = {'status': 'completed', 'assignments': merged, 'validation': report,
              'merge': {'published_run_id': published.id, 'part_run_id': part.id, 'scope': scope, 'replaced_activities': len(placed), 'merged_by': user.id},
              'objective_definition': 'merged-part', 'provenance': (published.result or {}).get('provenance'),
              'lifecycle': {'queued_at': utcnow().isoformat(), 'finished_at': utcnow().isoformat()}}
    result['statistics'] = build_statistics(snapshot, result)
    row = ScheduleRun(id=str(uuid4()), workspace_id=1, created_by=user.id, input_version=ws.version, request_key=str(body.request_key),
                      snapshot=snapshot, status='completed', result=result, parent_run_id=published.id,
                      name=f"{published.name or 'Published timetable'} + {part.name or 'part'}"[:100])
    db.add(row)
    db.flush()
    event(db, ws, user, 'schedule.merged', row.id)
    return publish_row(db, ws, user, ScheduleRun, row, 'schedule')


@router.post('/api/schedules/{ident}/unpublish')
def unpublish(ident: str, request: Request, user=Depends(administrator), db=Depends(db_session)):
    ws = lock_workspace(request, db)
    row = schedule(db, ident)
    if not row.published_at:
        fail(409, 'invalid_transition')
    row.published_at = None
    event(db, ws, user, 'schedule.unpublished', row.id)
    db.commit()
    return {'id': row.id, 'published_at': None}


def exam(db, ident):
    row = db.get(ExamRun, ident)
    if not row:
        fail(404, 'not_found')
    return row


@router.put('/api/exam-schedules/{ident}/name')
def rename_exam(ident: str, body: Rename, user=Depends(administrator), db=Depends(db_session)):
    ws = workspace_lock(db)
    row = exam(db, ident)
    row.name = body.name
    event(db, ws, user, 'exam.renamed', row.id)
    db.commit()
    return {'id': row.id, 'name': row.name}


@router.post('/api/exam-schedules/{ident}/publish')
def publish_exam(ident: str, request: Request, user=Depends(administrator), db=Depends(db_session)):
    from app.exam_planning import validate_exam_draft
    ws = lock_workspace(request, db)
    row = exam(db, ident)
    if row.result.get('status') != 'completed' or not validate_exam_draft(row.snapshot, row.result['assignments'])['passed']:
        fail(409, 'invalid_transition')
    if 'halls' not in row.snapshot:
        fail(409, 'exam_without_halls')
    if row.input_version != ws.version:
        fail(409, 'stale_schedule')
    return publish_row(db, ws, user, ExamRun, row, 'exam')


@router.post('/api/exam-schedules/{ident}/unpublish')
def unpublish_exam(ident: str, request: Request, user=Depends(administrator), db=Depends(db_session)):
    ws = lock_workspace(request, db)
    row = exam(db, ident)
    if not row.published_at:
        fail(409, 'invalid_transition')
    row.published_at = None
    event(db, ws, user, 'exam.unpublished', row.id)
    db.commit()
    return {'id': row.id, 'published_at': None}
