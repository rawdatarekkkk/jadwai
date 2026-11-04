from app.models import User
from app.security import hash_password
from app.schedule_worker import process_one
from test_workflows import login, version
from test_schedules import setup_data, start


def test_student_scoped_access(environment):
    client, factory = environment
    login(client)
    setup_data(client, factory)
    group = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups')
    for group_id in (None, 'teacher'):
        assert client.post('/api/users', json={'name':'Student','email':'s@example.test','role':'student','group_id':group_id}).status_code == 422
    response = client.post('/api/users', json={'name':'Student','email':'s@example.test','role':'student','group_id':group['id']})
    assert response.status_code == 201
    ident = response.json()['user']['id']
    with factory.begin() as db:
        db.get(User, ident).password = hash_password('test-password-123')
    other = client.post('/api/records/groups', headers=version(client), json={'name':'Other group','code':'OTHER','size':10}).json()
    assert client.post('/api/records/courses', headers=version(client), json={'name':'Private other course','code':'OTHER-C','activity_type':'lecture','sessions':1,'duration':60,'eligible_instructors':['teacher'],'group_ids':[other['id']]}).status_code == 201
    run_id = start(client).json()['id']
    assert process_one(factory)
    login(client, 's@example.test')
    for path in ('/api/workspace', '/api/users', '/api/schedules', f'/api/schedules/{run_id}', f'/api/schedules/{run_id}/statistics'):
        assert client.get(path).status_code == 403
    assert client.post('/api/schedules', json={'request_key':'00000000-0000-0000-0000-000000000001'}).status_code == 403
    data = client.get('/api/student/schedule?group_id=other').json()
    assert data['group']['id'] == group['id']
    run = data['run']
    assert run['id'] == run_id and len(run['result']['assignments']) == 2
    assert 'Private other course' not in str(run)
    assert 'statistics' not in run['result'] and 'rules' not in run['snapshot']
    for record in run['snapshot']['records']:
        if record['kind'] == 'courses':
            assert record['group_ids'] == [group['id']]
            assert 'eligible_instructors' not in record
        if record['kind'] == 'groups':
            assert record['id'] == group['id']
    login(client)
    account = next(u for u in client.get('/api/users').json() if u['id'] == ident)
    assert client.put(f'/api/users/{ident}', headers={'If-Match':f'"{account["version"]}"'}, json={'name':'Student','role':'viewer','active':True}).status_code == 200
    assert client.get('/api/student/schedule').status_code == 403


def test_student_empty(environment):
    client, factory = environment
    with factory.begin() as db:
        db.add(User(id='student',email='s@example.test',name='Student',role='student',password=hash_password('test-password-123')))
    login(client, 's@example.test')
    assert client.get('/api/student/schedule').json() == {'group':None,'run':None}
