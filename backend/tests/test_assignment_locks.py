from copy import deepcopy
from uuid import uuid4
import pytest
from app.solver import generate
from app.validation import validate_schedule
from app.schedule_worker import process_one
from test_schedules import example, setup_data, start
from test_workflows import login, version


def test_full_lock_and_independent_corruption():
    snap = example()
    snap['assignment_locks'] = [dict(id='lock', status='approved', activity_id='a', occurrence=0,
                                   instructor_id='u', room_id='r', day='Monday', start_minute=480)]
    result = generate(snap)
    assert result['status'] == 'completed'
    assert validate_schedule(snap, result['assignments'])['passed']
    assert all(a['instructor_id'] == 'u' for a in result['assignments'] if a['activity_id']=='a')
    for field, value in [('instructor_id','t'), ('room_id','other'), ('day','Sunday'), ('start_minute',510)]:
        bad = deepcopy(result['assignments'])
        next(a for a in bad if a['activity_id']=='a' and a['occurrence']==0)[field] = value
        assert 'assignment_lock' in validate_schedule(snap, bad)['errors']
    snap['assignment_locks'][0]['occurrence'] = False
    assert 'assignment_lock' in validate_schedule(snap, result['assignments'])['errors']
    assert generate(snap)['reason'] == 'invalid_lock'


def test_time_locks_out_of_occurrence_order_are_feasible():
    # Locks copied from different runs can put a later occurrence on an earlier day.
    snap = example()
    snap['assignment_locks'] = [dict(id='late', status='approved', activity_id='a', occurrence=0, day='Monday', start_minute=480),
                                dict(id='early', status='approved', activity_id='a', occurrence=1, day='Sunday', start_minute=480)]
    result = generate(snap)
    assert result['status'] == 'completed'
    assert validate_schedule(snap, result['assignments'])['passed']
    placed = {a['occurrence']: (a['day'], a['start_minute']) for a in result['assignments'] if a['activity_id']=='a'}
    assert placed == {0: ('Monday', 480), 1: ('Sunday', 480)}


def test_draft_ignored_and_contradictory_locks_infeasible():
    snap=example()
    snap['assignment_locks']=[dict(id='1',status='draft',activity_id='missing',occurrence=0,room_id='missing')]
    assert generate(snap)['status']=='completed'
    snap['assignment_locks']=[dict(id=str(n),status='approved',activity_id='a',occurrence=0,instructor_id=t) for n,t in enumerate(['t','u'])]
    assert generate(snap)['status']=='infeasible'


def test_lock_lifecycle_snapshot_and_permissions(environment):
    client,factory=environment
    login(client);setup_data(client,factory)
    source=start(client).json()['id']; assert process_one(factory)
    run=client.get('/api/schedules/'+source).json()
    a=run['result']['assignments'][0]
    body=dict(request_key=str(uuid4()),source_run_id=source,activity_id=a['activity_id'],occurrence=a['occurrence'],keep_instructor=True,keep_time=True,keep_room=True)
    headers=version(client)
    response=client.post('/api/locks',headers=headers,json=body)
    assert response.status_code==201,response.text
    lock=response.json(); ident=lock['id']; assert lock['status']=='draft'
    assert client.post('/api/locks',headers=headers,json=body).json()['id']==ident
    assert client.post('/api/locks',headers=version(client),json={**body,'keep_room':False}).status_code==409
    draft=start(client).json()['id']; assert process_one(factory)
    assert client.get('/api/schedules/'+draft).json()['snapshot']['assignment_locks']==[]
    assert client.post('/api/locks/'+ident+'/approve',headers=version(client)).status_code==200
    assert client.delete('/api/locks/'+ident,headers=version(client)).status_code==409
    locked=start(client).json()['id']; assert process_one(factory)
    saved=client.get('/api/schedules/'+locked).json()
    assert saved['result']['validation']['passed']
    assert saved['result']['validation']['assignment_locks'][0]['passed']
    fixed=next(x for x in saved['result']['assignments'] if x['activity_id']==a['activity_id'] and x['occurrence']==a['occurrence'])
    assert all(fixed[k]==a[k] for k in ('instructor_id','room_id','day','start_minute'))
    assert client.post('/api/locks/'+ident+'/revoke',headers=version(client)).status_code==200
    assert client.delete('/api/locks/'+ident,headers=version(client)).status_code==204
    login(client,'viewer@example.test')
    assert client.post('/api/locks',headers=version(client),json={**body,'request_key':str(uuid4())}).status_code==403
