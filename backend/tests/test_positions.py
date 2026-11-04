from app.solver import generate
from app.validation import validate_schedule
from app.preflight import inspect_inputs
from test_schedules import example
from test_workflows import login, version


def classified():
    snapshot = example()
    for record in snapshot['records']:
        if record['kind'] == 'instructors':
            record['position'] = 'doctor'
    return snapshot


def test_doctor_lectures_and_ta_tutorials_are_checked_everywhere():
    snapshot = classified()
    # Activity 'b' is a tutorial taught only by 't', a doctor.
    assert generate(snapshot)['reason'] == 'instructor_position'
    assert any(b['code'] == 'instructor_position' for b in inspect_inputs(snapshot)['blockers'])
    next(r for r in snapshot['records'] if r['id'] == 'b')['activity_type'] = 'lecture'
    result = generate(snapshot)
    assert result['status'] == 'completed'
    assert validate_schedule(snapshot, result['assignments'])['passed']
    next(r for r in snapshot['records'] if r['id'] == 't')['position'] = 'ta'
    assert 'instructor_position' in validate_schedule(snapshot, result['assignments'])['errors']


def test_unclassified_instructors_are_warned_not_blocked():
    snapshot = example()
    report = inspect_inputs(snapshot)
    assert any(w['code'] == 'instructor_position_missing' for w in report['warnings'])
    assert generate(snapshot)['status'] == 'completed'


def test_position_saved_and_enforced_by_api(environment):
    client, _ = environment
    login(client)
    base = {'department': 'CS', 'day_off': 'Friday'}
    doctor = client.post('/api/records/instructors', headers=version(client), json={**base, 'name': 'Dr. A', 'code': 'DRA', 'position': 'doctor'}).json()['id']
    ta = client.post('/api/records/instructors', headers=version(client), json={**base, 'name': 'TA B', 'code': 'TAB', 'position': 'ta'}).json()['id']
    group = client.post('/api/records/groups', headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20}).json()['id']
    activity = {'name': 'Course', 'code': 'C1', 'sessions': 1, 'duration': 60, 'group_ids': [group]}
    assert client.post('/api/records/courses', headers=version(client), json={**activity, 'activity_type': 'lab', 'eligible_instructors': [doctor]}).json()['detail'] == 'instructor_position'
    assert client.post('/api/records/courses', headers=version(client), json={**activity, 'activity_type': 'lab', 'eligible_instructors': [ta]}).status_code == 201
    course = {'name': 'Course', 'code': 'CC', 'group_ids': [group], 'eligibility': {'lecture': [ta], 'tutorial': [], 'lab': []}}
    assert client.post('/api/course-catalog', headers=version(client), json=course).json()['detail'] == 'instructor_position'
    course['eligibility'] = {'lecture': [doctor], 'tutorial': [ta], 'lab': [ta]}
    assert client.post('/api/course-catalog', headers=version(client), json=course).status_code == 201
    # A TA already eligible for labs cannot be reclassified as a doctor.
    response = client.put(f'/api/records/instructors/{ta}', headers=version(client), json={**base, 'name': 'TA B', 'code': 'TAB', 'position': 'doctor'})
    assert response.status_code == 409 and response.json()['detail'] == 'position_in_use'
    saved = next(r for r in client.get('/api/workspace').json()['records'] if r['id'] == doctor)
    assert saved['position'] == 'doctor'


def test_instructor_account_links_to_instructor(environment):
    client, _ = environment
    login(client)
    assert client.post('/api/users', json={'name': 'T', 'email': 't@example.test', 'role': 'instructor'}).status_code == 422
    assert client.post('/api/users', json={'name': 'T', 'email': 't@example.test', 'role': 'viewer', 'instructor_id': 'teacher'}).status_code == 422
    created = client.post('/api/users', json={'name': 'T', 'email': 't@example.test', 'role': 'instructor', 'instructor_id': 'teacher'})
    assert created.status_code == 201 and created.json()['user']['instructor_id'] == 'teacher'
    assert client.delete('/api/records/instructors/teacher', headers=version(client)).json()['detail'] == 'record_in_use'
