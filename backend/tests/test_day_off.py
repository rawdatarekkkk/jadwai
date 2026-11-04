from test_schedules import example
from app.solver import generate
from app.validation import validate_schedule
from app.preflight import inspect_inputs
from test_workflows import login, version


def test_day_off_enforced_and_independently_checked():
    snapshot = example()
    for teacher in snapshot['records'][:2]:
        teacher['day_off'] = 'Sunday'
    result = generate(snapshot)
    assert result['status'] == 'completed'
    assert all(a['day'] == 'Monday' for a in result['assignments'])
    assert validate_schedule(snapshot, result['assignments'])['passed']
    result['assignments'][0]['day'] = 'Sunday'
    assert 'instructor_day_off' in validate_schedule(snapshot, result['assignments'])['errors']
    snapshot['calendar']['days'] = ['Sunday']
    assert inspect_inputs(snapshot)['blockers']
    assert generate(snapshot)['status'] == 'infeasible'


def test_day_off_saved_and_validated(environment):
    client, _ = environment
    login(client)
    body = {'name': 'New Teacher', 'code': 'NEW', 'department': 'CS', 'day_off': 'Friday'}
    assert client.post('/api/records/instructors', headers=version(client), json=body).status_code == 201
    teacher = next(r for r in client.get('/api/workspace').json()['records'] if r['code'] == 'NEW')
    assert teacher['day_off'] == 'Friday'
    body.update(code='INVALID', day_off='Funday')
    assert client.post('/api/records/instructors', headers=version(client), json=body).status_code == 422
