from copy import deepcopy
from itertools import product
from random import Random
from threading import Event
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.solver import generate
from app.validation import validate_schedule
from app.schedule_worker import process_one
from test_schedules import example, setup_data, start
from test_workflows import login, version

@pytest.mark.parametrize('field,value', [('occurrence',False),('occurrence',-1),('occurrence','0'),('activity_id',[]),('room_id',{}),('instructor_id',[]),('day',[]),('start_minute',True),('end_minute',float('nan'))])
def test_malformed_assignment_fails_closed(field,value):
    snap=example(); assignments=generate(snap)['assignments']; assignments[0][field]=value
    assert not validate_schedule(snap,assignments)['passed']

@pytest.mark.parametrize('assignments',[None,{},'schedule',[None],[42],[[]],[{'activity_id':'a'}]])
def test_invalid_shapes_fail_closed(assignments):
    assert not validate_schedule(example(),assignments)['passed']

def test_empty_snapshot_cannot_pass():
    snap=example();snap['records']=[]
    assert not validate_schedule(snap,[])['passed']

def test_exact_end_and_adjacent_sessions():
    snap=example();snap['calendar'].update(days=['Sunday'],end_hour=10)
    snap['records']=[r for r in snap['records'] if r['id']!='b']
    rows=[dict(activity_id='a',occurrence=n,instructor_id='t',room_id='r',day='Sunday',start_minute=480+n*60,end_minute=540+n*60) for n in range(2)]
    assert validate_schedule(snap,rows)['passed']
    rows[1]['start_minute']-=30;rows[1]['end_minute']-=30
    assert 'resource_conflicts' in validate_schedule(snap,rows)['errors']

def test_capacity_type_and_flexible_room_boundaries():
    snap=example();snap['records'][3]['capacity']=20
    assert generate(snap)['status']=='completed'
    snap['records'][3]['capacity']=19
    assert generate(snap)['reason']=='no_suitable_room'
    snap=example();snap['records'][3]['room_type']='lab'
    assert generate(snap)['reason']=='no_suitable_room'
    snap['records'][3]['room_type']='flexible'
    assert generate(snap)['status']=='completed'

def test_teacher_continuity_cannot_be_relaxed():
    snap=example();snap['records']=[r for r in snap['records'] if r['id']!='b']
    snap['calendar'].update(days=['Sunday','Monday'],end_hour=9)
    snap['rules']=[dict(status='approved',type='unavailable',instructor_id=t,day=d,start_hour=8,end_hour=9) for t,d in [('t','Sunday'),('u','Monday')]]
    assert generate(snap)['status']=='infeasible'

def test_limits_do_not_claim_infeasibility(monkeypatch):
    from app import solver
    monkeypatch.setattr(solver,'MAX_CANDIDATES',1)
    assert generate(example())['status']=='blocked'
    snap=example();snap['records'][4]['sessions']=161
    assert generate(snap)['status']=='blocked'

@pytest.mark.parametrize('seed',range(30))
def test_random_instances_agree_with_exhaustive_oracle(seed):
    rng=Random(seed);snap=example()
    snap['calendar'].update(days=['Sunday'],end_hour=10,period_minutes=60)
    snap['records']=[r for r in snap['records'] if r['id']!='b']
    activity=snap['records'][-1];activity.update(sessions=rng.randint(1,3),duration=60)
    blocked={t:set(rng.sample([480,540],rng.randint(0,2))) for t in ['t','u']}
    snap['rules']=[dict(status='approved',type='unavailable',instructor_id=t,day='Sunday',start_hour=m//60,end_hour=m//60+1) for t,ms in blocked.items() for m in ms]
    feasible=any(len(set(times))==len(times) and all(m not in blocked[t] for m in times) for t in ['t','u'] for times in product([480,540],repeat=activity['sessions']))
    result=generate(snap)
    assert (result['status']=='completed')==feasible
    if feasible:assert validate_schedule(snap,result['assignments'])['passed']

@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_generation_creates_exactly_one_job(environment,same_key):
    client,factory=environment;login(client);setup_data(client,factory)
    cookies=dict(client.cookies);headers={'X-Jadwai-Request':'1',**version(client)};key=str(uuid4())
    def submit(_):
        with TestClient(app) as c:
            c.cookies.update(cookies)
            r=c.post('/api/schedules',headers=headers,json={'request_key':key if same_key else str(uuid4())})
            return r.status_code,r.json()
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(submit,range(8)))
    if same_key:
        assert all(status==202 for status,_ in results)
        assert len({r['id'] for _,r in results})==1
    else:
        assert [s for s,_ in results].count(202)==1
        assert [s for s,_ in results].count(409)==7
    assert len(client.get('/api/schedules').json())==1

def test_multiple_workers_claim_once(environment,monkeypatch):
    from app import schedule_worker
    client,factory=environment;login(client);setup_data(client,factory);start(client)
    entered=Event();release=Event();original=schedule_worker.generate
    def delayed(*args):
        entered.set();assert release.wait(5);return original(*args)
    monkeypatch.setattr(schedule_worker,'generate',delayed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(process_one,factory);assert entered.wait(5)
        second=pool.submit(process_one,factory);assert second.result(timeout=5) is False
        release.set();assert first.result(timeout=10)
    assert client.get('/api/schedules').json()[0]['status']=='completed'

@pytest.mark.parametrize('seed',range(20))
def test_multi_resource_instances_against_exhaustive_oracle(seed):
    rng=Random(seed);snap=example()
    snap['calendar'].update(days=['Sunday'],end_hour=10,period_minutes=60)
    snap['records'][3]['required_equipment']=[]
    snap['records'].append(dict(snap['records'][3],id='s'))
    snap['records'].append(dict(snap['records'][2],id='h'))
    activities=[r for r in snap['records'] if r['kind']=='courses']
    for a in activities:a.update(sessions=1,duration=60,eligible_instructors=rng.sample(['t','u'],rng.randint(1,2)),required_equipment=[])
    shared=rng.choice([True,False]);activities[1]['group_ids']=['g' if shared else 'h']
    blocked={t:set(rng.sample([480,540],rng.randint(0,2))) for t in ['t','u']}
    snap['rules']=[dict(status='approved',type='unavailable',instructor_id=t,day='Sunday',start_hour=m//60,end_hour=m//60+1) for t,ms in blocked.items() for m in ms]
    options=[[(t,r,m) for t in a['eligible_instructors'] for r in ['r','s'] for m in [480,540] if m not in blocked[t]] for a in activities]
    feasible=any(x[2]!=y[2] or (x[0]!=y[0] and x[1]!=y[1] and not shared) for x,y in product(*options))
    result=generate(snap)
    assert (result['status']=='completed')==feasible
    if feasible:assert validate_schedule(snap,result['assignments'])['passed']

def test_real_candidate_limit_is_bounded():
    snap=example();snap['calendar'].update(days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],start_hour=0,end_hour=24)
    base=snap['records'][4];snap['records']=[r for r in snap['records'] if r['kind']!='courses']
    snap['records'] += [dict(base,id=f'a{i}',sessions=10,duration=30) for i in range(16)]
    snap['records'] += [dict(snap['records'][3],id=f'r{i}') for i in range(4)]
    result=generate(snap)
    assert result['status']=='blocked' and result['reason']=='instance_too_large'


def test_large_demo_semester_97_sessions_passes_independent_validation():
    from app.stress_seed import planned_records
    records, teachers = planned_records(30)
    assert len(records)==120 and len(teachers)==24
    snap=example()
    snap['calendar'].update(days=['Sunday','Monday','Tuesday','Wednesday','Thursday'],end_hour=18)
    snap['records'][4]['sessions']=4
    snap['records'][5]['sessions']=3
    snap['records']+=records
    for i,teacher in enumerate(teachers):
        preferred=i%2==1
        snap['rules'].append(dict(status='approved',type='preferred_period' if preferred else 'unavailable',instructor_id=teacher,day=snap['calendar']['days'][i%5],start_hour=10 if preferred else 8,end_hour=14 if preferred else 10))
    result=generate(snap)
    assert result['status']=='completed'
    assert len(result['assignments'])==97
    assert validate_schedule(snap,result['assignments'])['passed']
