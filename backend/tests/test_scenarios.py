from uuid import uuid4
from app.schedule_worker import process_one
from test_schedules import setup_data, start
from test_workflows import login, version


def generated(client, factory):
    login(client)
    setup_data(client, factory)
    client.post('/api/records/rooms', headers=version(client), json={'name': 'R2', 'code': 'R2', 'capacity': 30, 'room_type': 'lecture'})
    ident = start(client).json()['id']
    assert process_one(factory)
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['status'] == 'completed', run['result']
    return run


def test_rename_edit_compare_and_reject_rule_breaking_edits(environment):
    client, factory = environment
    run = generated(client, factory)
    assert client.put(f"/api/schedules/{run['id']}/name", json={'name': 'Plan A'}).json()['name'] == 'Plan A'
    first, second = run['result']['assignments']
    rooms = [r['id'] for r in run['snapshot']['records'] if r['kind'] == 'rooms']
    other_room = next(r for r in rooms if r != first['room_id'])
    key = str(uuid4())
    edited = client.post(f"/api/schedules/{run['id']}/edits", json={'request_key': key, 'changes': [{'activity_id': first['activity_id'], 'occurrence': first['occurrence'], 'room_id': other_room}]})
    assert edited.status_code == 201, edited.text
    new = client.get(f"/api/schedules/{edited.json()['id']}").json()
    assert new['parent_run_id'] == run['id'] and new['name'] == 'Plan A (edited)' and new['result']['validation']['passed']
    assert client.post(f"/api/schedules/{run['id']}/edits", json={'request_key': key, 'changes': [{'activity_id': first['activity_id'], 'occurrence': 0, 'room_id': other_room}]}).json()['id'] == new['id']
    comparison = client.get(f"/api/schedule-comparisons?a={run['id']}&b={new['id']}").json()
    assert [m['changed'] for m in comparison['moved_sessions']] == [['room_id']]
    # Putting both sessions of the same group at the same time is refused.
    clash = client.post(f"/api/schedules/{run['id']}/edits", json={'request_key': str(uuid4()), 'changes': [
        {'activity_id': second['activity_id'], 'occurrence': second['occurrence'], 'day': first['day'], 'start_minute': first['start_minute']}]})
    assert clash.status_code == 422 and 'resource_conflicts' in clash.json()['detail']['errors']
    assert client.get(f"/api/schedules/{run['id']}").json()['result']['assignments'] == run['result']['assignments']


def test_publish_requires_current_valid_inputs_and_keeps_one_published(environment):
    client, factory = environment
    run = generated(client, factory)
    published = client.post(f"/api/schedules/{run['id']}/publish", headers=version(client))
    assert published.status_code == 200, published.text
    second = start(client).json()['id']
    assert process_one(factory)
    assert client.post(f"/api/schedules/{second}/publish", headers=version(client)).status_code == 200
    runs = {r['id']: r for r in client.get('/api/schedules').json()}
    assert runs[second]['published_at'] and not runs[run['id']]['published_at']
    # Any input change makes the draft stale; it can no longer be published.
    client.post('/api/records/groups', headers=version(client), json={'name': 'New', 'code': 'NEW', 'size': 5})
    assert client.post(f"/api/schedules/{run['id']}/publish", headers=version(client)).json()['detail'] == 'stale_schedule'
    assert client.post(f"/api/schedules/{second}/unpublish", headers=version(client)).status_code == 200
    client.post('/api/auth/logout'); login(client, 'viewer@example.test')
    assert client.post(f"/api/schedules/{second}/publish", headers=version(client)).status_code == 403
