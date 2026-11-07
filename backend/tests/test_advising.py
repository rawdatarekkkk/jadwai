from app.advising_rules import personal_sessions
from app.exam_planning import generate_exam_draft
from app.solver import generate
from app.validation import validate_schedule
from test_workflows import login, version


def two_groups():
    """Two groups with one lecture each; both teachers prefer 08:00-09:00."""
    return {'calendar': {'days': ['Sunday'], 'start_hour': 8, 'end_hour': 10, 'period_minutes': 30, 'timezone': 'Africa/Cairo'},
            'rules': [{'status': 'approved', 'type': 'preferred_period', 'instructor_id': t, 'day': 'Sunday', 'start_hour': 8, 'end_hour': 9} for t in ('t1', 't2')],
            'records': [
                {'id': 't1', 'kind': 'instructors', 'name': 'T1'}, {'id': 't2', 'kind': 'instructors', 'name': 'T2'},
                {'id': 'g1', 'kind': 'groups', 'size': 20}, {'id': 'g2', 'kind': 'groups', 'size': 20},
                {'id': 'r1', 'kind': 'rooms', 'capacity': 25, 'room_type': 'lecture'}, {'id': 'r2', 'kind': 'rooms', 'capacity': 25, 'room_type': 'lecture'},
                {'id': 'math', 'kind': 'courses', 'sessions': 1, 'duration': 60, 'activity_type': 'lecture', 'eligible_instructors': ['t1'], 'group_ids': ['g1']},
                {'id': 'physics', 'kind': 'courses', 'sessions': 1, 'duration': 60, 'activity_type': 'lecture', 'eligible_instructors': ['t2'], 'group_ids': ['g2']}]}


def test_personal_sessions_follow_drops_and_added_groups():
    activities = [{'id': 'm1', 'course_id': 'M', 'group_ids': ['g1']}, {'id': 'p1', 'course_id': 'P', 'group_ids': ['g1']},
                  {'id': 'p2', 'course_id': 'P', 'group_ids': ['g2']}, {'id': 'x2', 'course_id': 'X', 'group_ids': ['g2']}]
    student = {'group_id': 'g1', 'changes': [{'action': 'drop', 'course_id': 'P', 'group_id': None}, {'action': 'add', 'course_id': 'X', 'group_id': 'g2'}]}
    assert personal_sessions(student, activities, {'E': ['g1']}) == (['m1', 'x2'], ['E', 'M', 'X'])


def test_an_advising_students_sessions_never_overlap():
    snapshot = two_groups()
    together = generate(snapshot)
    assert {a['start_minute'] for a in together['assignments']} == {480}  # both preferred at 08:00
    snapshot['students'] = [{'id': 's', 'code': 'S1', 'group_id': 'g1', 'activity_ids': ['math', 'physics']}]
    result = generate(snapshot)
    assert result['status'] == 'completed'
    assert len({a['start_minute'] for a in result['assignments']}) == 2
    assert validate_schedule(snapshot, result['assignments'])['passed']
    assert 'advising_student_conflicts' in validate_schedule(snapshot, together['assignments'])['errors']


def test_joining_students_need_seats():
    snapshot = two_groups()
    next(r for r in snapshot['records'] if r['id'] == 'g2')['size'] = 25
    snapshot['students'] = [{'id': 's', 'code': 'S1', 'group_id': 'g1', 'activity_ids': ['math', 'physics']}]
    assert generate(snapshot)['reason'] == 'no_suitable_room'


def test_an_advising_student_is_an_exam_cohort():
    courses = [{'id': c, 'code': c, 'name': c, 'participants': [cohort], 'programs': []} for c, cohort in [('A', 'year1'), ('B', 'year2')]]
    snapshot = {'dates': ['2026-10-20', '2026-10-21'], 'max_exams_per_cohort_day': 1, 'missing_cohort_codes': [], 'courses': courses, 'time_limit_seconds': 10}
    for c in courses:
        c['participants'].append('student:S1')
    result = generate_exam_draft(snapshot)
    assert result['status'] == 'completed' and result['validation']['passed']
    assert len({a['date'] for a in result['assignments']}) == 2  # one exam per day for the student


def test_advising_students_through_the_api_and_portal(environment):
    client, factory = environment
    login(client)
    teacher = client.post('/api/records/instructors', headers=version(client), json={'name': 'Dr. A', 'code': 'DRA', 'department': 'CS', 'day_off': 'Friday', 'position': 'doctor'}).json()['id']
    g1 = client.post('/api/records/groups', headers=version(client), json={'name': 'G1', 'code': 'G1', 'size': 20}).json()['id']
    g2 = client.post('/api/records/groups', headers=version(client), json={'name': 'G2', 'code': 'G2', 'size': 20}).json()['id']
    eligibility = {'lecture': [teacher], 'tutorial': [], 'lab': []}
    courses = {}
    for code, group in [('MATH', g1), ('PHYS', g2)]:
        courses[code] = client.post('/api/course-catalog', headers=version(client), json={'name': code, 'code': code, 'eligibility': eligibility, 'group_ids': [group]}).json()['id']
        assert client.post('/api/records/courses', headers=version(client), json={'name': code, 'code': code + '-L', 'sessions': 1, 'duration': 60, 'activity_type': 'lecture', 'eligible_instructors': [teacher], 'group_ids': [group], 'course_id': courses[code]}).status_code == 201
    body = {'code': 'S-1', 'name': 'Retaking student', 'group_id': g1, 'changes': [{'action': 'add', 'course_id': courses['PHYS'], 'group_id': g1}]}
    assert client.post('/api/advising-students', headers=version(client), json=body).json()['detail'] == 'no_sessions_for_group'
    body['changes'] = [{'action': 'add', 'course_id': courses['MATH'], 'group_id': g1}]
    assert client.post('/api/advising-students', headers=version(client), json=body).json()['detail'] == 'already_taking_course'
    body['changes'] = [{'action': 'add', 'course_id': courses['PHYS'], 'group_id': g2}]
    before = version(client)['If-Match']
    created = client.post('/api/advising-students', headers=version(client), json=body)
    assert created.status_code == 201 and version(client)['If-Match'] != before
    student = client.get('/api/advising-students').json()['students'][0]
    assert len(student['activity_ids']) == 2 and set(student['course_ids']) == set(courses.values())
    preflight = client.get('/api/schedules/preflight/current').json()
    assert not any(b['code'].startswith('advising') for b in preflight['blockers'])
    account = client.post('/api/users', json={'email': 's1@example.test', 'name': 'S1', 'role': 'student', 'advising_student_id': student['id']})
    assert account.status_code == 201, account.text
    assert client.post('/api/users', json={'email': 's2@example.test', 'name': 'S2', 'role': 'instructor', 'advising_student_id': student['id']}).status_code == 422


def test_an_advising_student_over_the_daily_maximum_is_named_never_double_booked():
    # Two groups' exams on one date: only an advising student links them.
    courses = [{'id': c, 'code': c, 'name': c, 'participants': [cohort, 'student:S1'], 'programs': []} for c, cohort in [('A', 'year1'), ('B', 'year2')]]
    snapshot = {'dates': ['2026-10-20'], 'max_exams_per_cohort_day': 1, 'missing_cohort_codes': [], 'courses': courses, 'time_limit_seconds': 10}
    result = generate_exam_draft(snapshot)
    assert result['status'] == 'completed' and result['validation']['passed']
    assert len({a['start_time'] for a in result['assignments']}) == 2
    assert result['convenience']['advising_exceptions'] == [{'student': 'S1', 'date': '2026-10-20', 'exams': 2}]
    assert result['recommendations'][0]['action'] == 'advising_exceptions'
    # A student group keeps the hard daily maximum.
    for c in courses:
        c['participants'] = ['year1']
    assert generate_exam_draft(snapshot)['reason'] == 'not_enough_days'
