from copy import deepcopy
from app.exam_planning import generate_exam_draft, validate_exam_draft
from app.models import CourseCatalog
from test_workflows import login, version

DATES = ['2026-10-20', '2026-10-21', '2026-10-22']  # Tuesday-Thursday


def sample(tas=2):
    courses = [{'id': c, 'code': c, 'name': c, 'participants': [cohort], 'programs': [], 'students': students}
               for c, cohort, students in [('BIG', 'year1', 260), ('A', 'year1', 80), ('B', 'year2', 90), ('C', 'year2', 70)]]
    return {'dates': DATES, 'max_exams_per_cohort_day': 1, 'missing_cohort_codes': [], 'courses': courses,
            'halls': [{'id': 'h1', 'code': 'H1', 'name': 'Hall 1', 'capacity': 150}, {'id': 'h2', 'code': 'H2', 'name': 'Hall 2', 'capacity': 120}],
            'invigilators': [{'id': f't{i}', 'code': f'T{i}', 'name': f'TA {i}', 'day_off': None, 'unavailable': []} for i in range(tas)],
            'time_limit_seconds': 10}


def test_large_exam_is_split_and_every_hall_has_a_free_invigilator():
    snap = sample()
    snap['invigilators'][0]['day_off'] = 'Tuesday'
    result = generate_exam_draft(snap)
    assert result['status'] == 'completed', result
    big = next(a for a in result['assignments'] if a['course_id'] == 'BIG')
    assert {h['room_id'] for h in big['halls']} == {'h1', 'h2'}
    assert all(sum(h['capacity'] for h in a['halls']) >= a['students'] for a in result['assignments'])
    assert all(not (a['date'] == '2026-10-20' and any(h['invigilator_id'] == 't0' for h in a['halls'])) for a in result['assignments'])
    # The same cohort does not sit exams on consecutive days when it can be avoided.
    assert result['convenience']['back_to_back_days'] == 0


def test_validator_catches_hall_and_invigilator_mistakes():
    snap = sample()
    result = generate_exam_draft(snap)
    rows = deepcopy(result['assignments'])
    big = next(a for a in rows if a['course_id'] == 'BIG')
    big['halls'] = big['halls'][:1]
    assert 'hall_capacity' in validate_exam_draft(snap, rows)['errors']
    rows = deepcopy(result['assignments'])
    a, b = rows[0], rows[1]
    b.update(date=a['date'], start_time=a['start_time'], end_time=a['end_time'])
    b['halls'] = deepcopy(a['halls'])
    errors = validate_exam_draft(snap, rows)['errors']
    assert 'hall_double_booking' in errors and 'invigilator_conflict' in errors
    rows = deepcopy(result['assignments'])
    snap['invigilators'][0]['unavailable'] = [{'day': None, 'start_hour': 8, 'end_hour': 18}]
    assert any(h['invigilator_id'] == 't0' for a in rows for h in a['halls'])
    assert 'invigilator_availability' in validate_exam_draft(snap, rows)['errors']


def test_blocked_when_halls_students_or_tas_are_missing():
    snap = sample(); snap['halls'] = []
    assert generate_exam_draft(snap)['reason'] == 'no_exam_halls'
    snap = sample(); snap['courses'][1]['students'] = None
    assert generate_exam_draft(snap)['reason'] == 'missing_student_counts'
    snap = sample(); snap['courses'][0]['students'] = 300
    assert generate_exam_draft(snap)['reason'] == 'hall_capacity'
    snap = sample(tas=0)
    assert generate_exam_draft(snap)['reason'] == 'no_invigilators'
    # One TA cannot staff two halls at once, so the 260-student exam has no slot.
    assert generate_exam_draft(sample(tas=1))['status'] == 'infeasible'


def test_exam_api_assigns_halls_and_tas(environment):
    client, factory = environment
    login(client)
    group = client.post('/api/records/groups', headers=version(client), json={'name': 'CS1', 'code': 'CS1', 'size': 140}).json()['id']
    client.post('/api/records/rooms', headers=version(client), json={'name': 'Exam Hall A', 'code': 'EHA', 'capacity': 100, 'room_types': ['exam_hall']})
    client.post('/api/records/rooms', headers=version(client), json={'name': 'Exam Hall B', 'code': 'EHB', 'capacity': 60, 'room_types': ['exam_hall', 'lecture']})
    client.post('/api/records/instructors', headers=version(client), json={'name': 'TA One', 'code': 'TA1', 'department': 'CS', 'position': 'ta'})
    client.post('/api/records/instructors', headers=version(client), json={'name': 'TA Two', 'code': 'TA2', 'department': 'CS', 'position': 'ta'})
    with factory.begin() as db:
        db.add(CourseCatalog(id='alg', name='Algorithms', code='ALG', eligibility={'lecture': [], 'tutorial': [], 'lab': []}, group_ids=[group], source_info={}))
        db.add(CourseCatalog(id='hist', name='History', code='HIS', eligibility={'lecture': [], 'tutorial': [], 'lab': []}, group_ids=[], expected_students=40, source_info={'program_semesters': [{'faculty_section': 'ARTS', 'program_or_cohort': 'History', 'semester': 1}]}))
    response = client.post('/api/exam-schedules', headers=version(client), json={'start_date': '2026-10-20', 'end_date': '2026-10-22', 'time_limit_seconds': 5})
    assert response.status_code == 201, response.text
    run = response.json()
    assert run['result']['status'] == 'completed', run['result']
    alg = next(a for a in run['result']['assignments'] if a['course_code'] == 'ALG')
    assert alg['students'] == 140 and {h['room_code'] for h in alg['halls']} == {'EHA', 'EHB'}
    assert all(h['invigilator_name'] in ('TA One', 'TA Two') for h in alg['halls'])
    exported = client.get('/api/exam-schedules/' + run['id'] + '/export').text
    assert 'EHA' in exported and ('TA One' in exported or 'TA Two' in exported)
    rules = client.put('/api/exam-schedules/cohort-rules', headers=version(client), json={'broad_programs': ['Computer Science Core'], 'tracks': {}, 'aliases': {}})
    assert rules.status_code == 200 and rules.json()['broad_programs'] == ['computersciencecore']
    assert client.put(f"/api/exam-schedules/{run['id']}/name", json={'name': 'Midterms v1'}).json()['name'] == 'Midterms v1'
    # Changing the cohort lists above changed the inputs, so this draft is stale now.
    assert client.post(f"/api/exam-schedules/{run['id']}/publish", headers=version(client)).json()['detail'] == 'stale_schedule'
    fresh = client.post('/api/exam-schedules', headers=version(client), json={'start_date': '2026-10-20', 'end_date': '2026-10-22', 'time_limit_seconds': 5}).json()
    assert client.post(f"/api/exam-schedules/{fresh['id']}/publish", headers=version(client)).status_code == 200
    assert next(r for r in client.get('/api/exam-schedules').json() if r['id'] == fresh['id'])['published_at']

    # Instructors see the exams of the courses they teach as well as invigilation duties.
    from app.models import User
    from app.security import hash_password
    teacher = next(r for r in client.get('/api/workspace').json()['records'] if r['code'] == 'TA1')
    with factory.begin() as db:
        db.get(CourseCatalog, 'alg').eligibility = {'lecture': [], 'tutorial': [teacher['id']], 'lab': []}
        db.add(User(id='ta-user', email='ta1@example.test', name='TA One', role='instructor', instructor_id=teacher['id'], password=hash_password('test-password-123')))
    login(client, 'ta1@example.test')
    roles = {(e['course_code'], e['role']) for e in client.get('/api/me/schedule').json()['exams']}
    assert ('ALG', 'course') in roles
