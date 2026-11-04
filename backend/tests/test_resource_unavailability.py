from copy import deepcopy
import pytest
from sqlalchemy.exc import IntegrityError
from app.models import Rule
from app.solver import generate
from app.validation import validate_schedule
from test_schedules import example, setup_data, start
from test_workflows import login, version
from app.schedule_worker import process_one


@pytest.mark.parametrize('kind,target,check', [('room','r','approved_room_unavailability'),('group','g','approved_group_unavailability')])
def test_approved_resource_blocks_enforced_and_independently_checked(kind,target,check):
    snap=example()
    snap['rules']=[{'id':'block','status':'approved','type':kind+'_unavailable',kind+'_id':target,'day':'Sunday','start_hour':8,'end_hour':12}]
    result=generate(snap)
    assert result['status']=='completed'
    assert all(a['day']=='Monday' for a in result['assignments'])
    assert validate_schedule(snap,result['assignments'])['passed']
    bad=deepcopy(result['assignments']);bad[0]['day']='Sunday'
    assert check in validate_schedule(snap,bad)['errors']
    snap['rules'][0]['status']='draft'
    assert check not in validate_schedule(snap,bad)['errors']
    # Overlapping blocks must not conflict with each other.
    snap['rules'][0]['status']='approved'
    snap['rules'].append({**snap['rules'][0],'id':'overlap','start_hour':9,'end_hour':11})
    assert generate(snap)['status']=='completed'
    snap['calendar']['days']=['Sunday']
    assert generate(snap)['status']=='infeasible'


@pytest.mark.parametrize('kind,target', [('room','r'),('group','g')])
def test_resource_block_end_boundary_is_exclusive(kind,target):
    snap=example();snap['calendar']['days']=['Sunday']
    snap['records']=[r for r in snap['records'] if r['id']!='b']
    snap['records'][-1]['sessions']=1
    snap['rules']=[{'id':'b','status':'approved','type':kind+'_unavailable',kind+'_id':target,'day':'Sunday','start_hour':8,'end_hour':9}]
    row={'activity_id':'a','occurrence':0,'room_id':'r','instructor_id':'t','day':'Sunday','start_minute':540,'end_minute':600}
    assert validate_schedule(snap,[row])['passed']
    assert generate(snap)['status']=='completed'


def test_resource_rule_lifecycle_targets_and_persistence(environment):
    client,factory=environment;login(client);setup_data(client,factory)
    records=client.get('/api/workspace').json()['records']
    ids={k:next(r['id'] for r in records if r['kind']==k) for k in ('groups','rooms','instructors')}
    for kind,record_kind in [('room','rooms'),('group','groups')]:
        body={'title':kind+' closed Sunday','type':kind+'_unavailable',kind+'_id':ids[record_kind],'day':'Sunday','start_hour':8,'end_hour':18,'strength':'mandatory'}
        for extra in ({'instructor_id':ids['instructors']},{kind+'_id':ids['instructors']},{'strength':'preferred'}):
            assert client.post('/api/rules',headers=version(client),json={**body,**extra}).status_code==422
        made=client.post('/api/rules',headers=version(client),json=body)
        assert made.status_code==201
        rule=next(r for r in client.get('/api/workspace').json()['rules'] if r['title']==body['title'])
        assert rule['status']=='draft'
        assert client.delete('/api/records/'+record_kind+'/'+ids[record_kind],headers=version(client)).status_code==409
        assert client.post('/api/rules/'+rule['id']+'/approve',headers=version(client)).status_code==200
    run_id=start(client).json()['id'];assert process_one(factory)
    run=client.get('/api/schedules/'+run_id).json()
    assert run['status']=='completed' and run['result']['validation']['passed']
    assert all(a['day']!='Sunday' for a in run['result']['assignments'])
    assert run['result']['statistics']['input_summary']['approved_unavailability_rules']==2
    with factory.begin() as db:
        db.add(Rule(id='bad',data={'title':'wrong target','type':'room_unavailable','instructor_id':ids['instructors'],'day':'Sunday','start_hour':8,'end_hour':9,'strength':'mandatory'}))
        with pytest.raises(IntegrityError):db.flush()
        db.rollback()


def test_closed_room_does_not_block_other_rooms():
    snap=example();snap['calendar'].update(days=['Sunday'],end_hour=9)
    snap['records']=[r for r in snap['records'] if r['id']!='b']
    next(r for r in snap['records'] if r['id']=='a')['sessions']=1
    snap['records'].append({**next(r for r in snap['records'] if r['id']=='r'),'id':'other-room'})
    snap['rules']=[{'id':'closed','type':'room_unavailable','status':'approved','room_id':'r','day':'Sunday','start_hour':8,'end_hour':9}]
    result=generate(snap)
    assert result['status']=='completed'
    assert result['assignments'][0]['room_id']=='other-room'
    assert validate_schedule(snap,result['assignments'])['passed']


def test_unsupported_approved_rule_blocks_solver_and_validator():
    snap=example();rows=generate(snap)['assignments']
    snap['rules']=[{'id':'unsupported','status':'approved','type':'unimplemented'}]
    assert generate(snap)['reason']=='unsupported_rule'
    assert 'unsupported_rule' in validate_schedule(snap,rows)['errors']
