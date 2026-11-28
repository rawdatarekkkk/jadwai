"""Exam timetables from each course's exam plan: quiz rounds, midterms, and finals with
second-chance midterms in the reserved first slot."""
from app.exam_planning import DEFAULT_STARTS, generate_exam_draft, starts_of, validate_exam_draft
from test_exam_halls import sample
from test_workflows import login, version


def items(snap, plan):
    """plan: course id -> [(type, minutes, students or None)]."""
    rows = []
    for c in snap['courses']:
        for kind, minutes, students in plan.get(c['id'], []):
            rows.append({**c, 'id': f"{c['id']}:{kind}", 'course_id': c['id'], 'exam_type': kind, 'duration_minutes': minutes,
                         'label': kind, 'students': students or c['students']})
    snap['courses'] = rows
    return snap


def finals(tas=8):
    snap = items(sample(tas=tas), {'BIG': [('final', 180, None), ('makeup', 120, 26)], 'A': [('final', 180, None), ('makeup', 120, 8)],
                                    'B': [('final', 180, None)], 'C': [('final', 180, None)]})
    snap['starts'] = {'final': DEFAULT_STARTS['final'], 'makeup': DEFAULT_STARTS['makeup']}
    snap['dates'] = ['2026-10-20', '2026-10-21', '2026-10-22', '2026-10-24', '2026-10-25']
    return snap


def test_finals_keep_the_first_slot_for_second_chance_midterms():
    result = generate_exam_draft(finals())
    assert result['status'] == 'completed', result
    rows = result['assignments']
    assert all(a['start_time'] == '09:00' and a['end_time'] == '11:00' for a in rows if a['exam_type'] == 'makeup')
    assert all(a['start_time'] in ('11:30', '15:00') and a['duration_minutes'] == 180 for a in rows if a['exam_type'] == 'final')
    # A course's final and its second chance (the same students) are never at the same time,
    # and with one exam a day they fall on different days.
    for course in ('BIG', 'A'):
        mine = [a for a in rows if a['course_id'] == course]
        assert len(mine) == 2 and mine[0]['date'] != mine[1]['date']
    makeup = next(a for a in rows if a['exam_id'] == 'BIG:makeup')
    assert makeup['students'] == 26 and result['validation']['passed']


def test_quizzes_take_their_own_length_and_start_times():
    snap = items(sample(tas=6), {c: [('quiz', 30, None)] for c in ('BIG', 'A', 'B', 'C')})
    snap['starts'] = {'quiz': ['09:00', '10:15']}
    result = generate_exam_draft(snap)
    assert result['status'] == 'completed', result
    assert {(a['start_time'], a['end_time']) for a in result['assignments']} <= {('09:00', '09:30'), ('10:15', '10:45')}


def test_starts_follow_the_exam_type_and_older_snapshots_use_slots():
    assert starts_of({'starts': {'final': ['11:30']}}, {'exam_type': 'final', 'duration_minutes': 180}) == [690]
    assert starts_of({}, {'duration_minutes': 120}) == [540, 675, 810]  # the three fixed 2-hour slots
    assert starts_of({}, {'duration_minutes': 180}) == []                # no fixed slot is 3 hours long


def test_validator_rejects_a_wrong_start_length_or_overlap():
    snap = finals()
    snap.pop('halls'); snap.pop('invigilators')
    rows = [{'exam_id': c['id'], 'course_id': c['course_id'], 'course_code': c['code'], 'course_name': c['name'], 'date': d, 'start_time': s, 'end_time': e,
             'duration_minutes': c['duration_minutes'], 'programs': []}
            for c, (d, s, e) in zip(snap['courses'], [('2026-10-21', '11:30', '14:30'), ('2026-10-20', '09:00', '11:00'), ('2026-10-24', '11:30', '14:30'),
                                                       ('2026-10-22', '09:00', '11:00'), ('2026-10-20', '15:00', '18:00'), ('2026-10-21', '11:30', '14:30')])]
    assert validate_exam_draft(snap, rows)['passed'], validate_exam_draft(snap, rows)['errors']
    swapped = [dict(r) for r in rows]  # BIG's second chance after its final
    swapped[1].update(date='2026-10-25')
    assert 'second_chance_after_final' in validate_exam_draft(snap, swapped)['errors']
    rows[0]['start_time'], rows[0]['end_time'] = '09:00', '12:00'  # a final in the reserved first slot
    assert 'exam_times' in validate_exam_draft(snap, rows)['errors']
    rows[0]['start_time'], rows[0]['end_time'] = '11:30', '14:30'
    rows[4]['date'], rows[4]['start_time'], rows[4]['end_time'] = '2026-10-21', '11:30', '14:30'  # B and C (year2) at the same time
    assert 'cohort_slot_conflicts' in validate_exam_draft(snap, rows)['errors']


def test_api_builds_each_timetable_from_the_course_plans(environment):
    from app.models import CourseCatalog
    client, factory = environment
    login(client)
    with factory.begin() as db:
        db.add(CourseCatalog(id='c1', name='Programming', code='CS101', source_info={'program_semesters': [{'faculty_section': 'INFORMATICS', 'program_or_cohort': 'CS', 'semester': 1}]},
                             eligibility={'lecture': [], 'tutorial': [], 'lab': []}, group_ids=[], expected_students=50, quiz_count=2, second_chance=True))
        db.add(CourseCatalog(id='c2', name='Math', code='MA101', source_info={'program_semesters': [{'faculty_section': 'INFORMATICS', 'program_or_cohort': 'CS', 'semester': 1}]},
                             eligibility={'lecture': [], 'tutorial': [], 'lab': []}, group_ids=[], expected_students=40, quiz_count=3, second_chance=False))
    make = lambda body: client.post('/api/exam-schedules', headers=version(client), json={'use_halls': False, **body})
    final = make({'kind': 'final'}).json()
    assert sorted(c['id'] for c in final['snapshot']['courses']) == ['c1:final', 'c1:makeup', 'c2:final']
    assert next(c for c in final['snapshot']['courses'] if c['id'] == 'c1:makeup')['students'] == 5  # 10% of 50
    assert final['snapshot']['starts'] == {'final': ['11:30', '15:00'], 'makeup': ['09:00']}
    quiz3 = make({'kind': 'quiz', 'quiz_number': 3, 'quiz_minutes': 15}).json()
    assert [c['id'] for c in quiz3['snapshot']['courses']] == ['c2:quiz3']  # CS101 has only two quizzes
    skipped = make({'kind': 'final', 'skip': ['c1:makeup'], 'makeup_students': {}}).json()
    assert sorted(c['id'] for c in skipped['snapshot']['courses']) == ['c1:final', 'c2:final']
    assert make({'kind': 'final', 'starts': {'final': ['09:00']}}).json()['detail'] == 'final_overlaps_second_chance'


def test_solver_puts_every_second_chance_before_its_final():
    from app.exam_planning import generate_exam_draft
    snap = finals()
    result = generate_exam_draft(snap)
    assert result['status'] == 'completed' and result['validation']['passed']
    at = {(a['course_id'], a['exam_type']): (a['date'], a['start_time']) for a in result['assignments']}
    for (course, kind), when in at.items():
        if kind == 'makeup':
            assert when < at[course, 'final']
