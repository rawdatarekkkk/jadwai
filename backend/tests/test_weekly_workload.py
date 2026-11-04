from copy import deepcopy
import math
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.schemas import Instructor
from app.models import Record, InstructorDetail
from app.solver import generate
from app.validation import validate_schedule
from app.statistics import build_statistics
from test_schedules import example, setup_data, start
from test_workflows import login, version
from app.schedule_worker import process_one


def fixture_snapshot():
    snap=example()
    for r in snap['records']:
        if r['kind']=='courses':r.update(duration=90,eligible_instructors=['t'])
        if r['kind']=='instructors':r.update(code=r['id'])
        r.setdefault('name',r['id']);r.setdefault('code',r['id'])
    snap.update(name='CS',term='Fall',input_version=1)
    return snap


def test_total_weekly_hours_and_independent_limit_check():
    snap=fixture_snapshot();snap['records'][0]['max_weekly_hours']=4.5
    result=generate(snap)
    assert result['status']=='completed'
    report=validate_schedule(snap,result['assignments']);assert report['passed']
    row=next(w for w in report['workload'] if w['instructor_id']=='t')
    assert row['assigned_minutes']==270 and row['assigned_hours']==4.5
    assert not row['exceeded'] and row['configured']
    assert 'weekly_workload_limits_missing' in report['limitations']  # u has no maximum
    too_low=deepcopy(snap);too_low['records'][0]['max_weekly_hours']=4
    assert generate(too_low)['status']=='infeasible'
    report=validate_schedule(too_low,result['assignments'])
    assert 'weekly_workload' in report['errors']
    assert next(w for w in report['workload'] if w['instructor_id']=='t')['exceeded']
    result['validation']=validate_schedule(snap,result['assignments'])
    stats=build_statistics(snap,result)
    teacher=next(t for t in stats['per_instructor'] if t['id']=='t')
    assert teacher['teaching_hours']==4.5 and teacher['max_weekly_hours']==4.5


def test_zero_load_reassigns_whole_activity_to_other_eligible_teacher():
    snap=fixture_snapshot();snap['records'][0]['max_weekly_hours']=0
    for a in snap['records']:
        if a['kind']=='courses':a['eligible_instructors']=['t','u']
    result=generate(snap)
    assert result['status']=='completed'
    assert all(a['instructor_id']=='u' for a in result['assignments'])
    assert validate_schedule(snap,result['assignments'])['passed']


def test_multigroup_session_counted_once_and_null_limit_is_unconfigured():
    snap=fixture_snapshot();snap['records'][0]['max_weekly_hours']=4.5
    snap['records'].append({'id':'g2','kind':'groups','name':'G2','size':1})
    for a in snap['records']:
        if a['kind']=='courses':a['group_ids']=['g','g2']
    result=generate(snap);assert result['status']=='completed'
    report=validate_schedule(snap,result['assignments'])
    assert report['passed'] and report['workload'][0]['assigned_hours']==4.5
    for teacher in snap['records']:
        if teacher['kind']=='instructors':teacher['max_weekly_hours']=None
    assert generate(snap)['status']=='completed'
    assert all(not w['configured'] for w in validate_schedule(snap,result['assignments'])['workload'])


@pytest.mark.parametrize('value',[-1,0.25,168.5,float('nan'),float('inf'),True,'3'])
def test_invalid_hours_rejected_in_input_and_snapshot(value):
    with pytest.raises(ValidationError):Instructor(name='T',code='T',department='CS',max_weekly_hours=value)
    snap=fixture_snapshot();rows=generate(snap)['assignments']
    snap['records'][0]['max_weekly_hours']=value
    assert generate(snap)['reason']=='invalid_workload_limit'
    assert 'invalid_workload_limit' in validate_schedule(snap,rows)['errors']


def test_persisted_limit_csv_and_stale_snapshot(environment):
    client,factory=environment;login(client);setup_data(client,factory)
    teacher=next(r for r in client.get('/api/workspace').json()['records'] if r['id']=='teacher')
    updated={k:v for k,v in teacher.items() if k not in ('id','kind')}
    updated['max_weekly_hours']=2
    assert client.put('/api/records/instructors/teacher',headers=version(client),json=updated).status_code==200
    with factory() as db:assert db.get(InstructorDetail,'teacher').max_weekly_minutes==120
    run_id=start(client).json()['id'];assert process_one(factory)
    run=client.get('/api/schedules/'+run_id).json();assert run['status']=='completed'
    assert next(w for w in run['result']['validation']['workload'] if w['instructor_id']=='teacher')['assigned_hours']==2
    updated['max_weekly_hours']=0
    assert client.put('/api/records/instructors/teacher',headers=version(client),json=updated).status_code==200
    old=client.get('/api/schedules/'+run_id).json();assert old['stale']
    assert next(r for r in old['snapshot']['records'] if r['id']=='teacher')['max_weekly_hours']==2
    run_id=start(client).json()['id'];assert process_one(factory)
    blocked=client.get('/api/schedules/'+run_id).json()
    assert blocked['status']=='completed'
    load=next(w for w in blocked['result']['validation']['workload'] if w['instructor_id']=='teacher')
    assert load['standard_weekly_hours']==12 and load['extra_hours']==0
    assert not load['exceeded']  # New runs use the standard-plus-extra policy, not legacy hard caps.
    csv='name,code,department,max_weekly_hours\nNew,N,CS,1.5\n'
    preview=client.post('/api/imports/instructors/preview',json={'csv':csv})
    assert preview.status_code==200 and preview.json()['valid']
    assert client.post('/api/imports/instructors/commit',headers=version(client),json={'csv':csv}).status_code==201
    assert any(r.get('max_weekly_hours')==1.5 for r in client.get('/api/workspace').json()['records'])
    updated['max_weekly_hours']=None
    assert client.put('/api/records/instructors/teacher',headers=version(client),json=updated).status_code==200
    assert 'max_weekly_hours' not in next(r for r in client.get('/api/workspace').json()['records'] if r['id']=='teacher')
    with factory() as db:
        db.get(InstructorDetail,'teacher').max_weekly_minutes=-1
        with pytest.raises(IntegrityError):db.commit()
