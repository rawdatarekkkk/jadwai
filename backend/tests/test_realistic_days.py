from copy import deepcopy
import pytest
from app.solver import generate
from app.validation import validate_schedule
from app.statistics import build_statistics
from app.schedule_worker import process_one
from test_weekly_workload import fixture_snapshot
from test_workflows import login, version
from test_schedules import setup_data, start

POLICY={'student_daily_hours':6.0,'instructor_daily_hours':6.0,'spread_activity_days':True,'max_consecutive_periods':3,'max_idle_periods':1,'compact_days':True}
PERIODS=[{'start':s,'end':e} for s,e in [(510,600),(615,705),(720,810),(825,915),(945,1035)]]


def sample():
    snap=fixture_snapshot();snap['calendar'].update(days=['Sunday','Monday','Tuesday'],end_hour=18,teaching_periods=deepcopy(PERIODS),realism_policy=deepcopy(POLICY))
    return snap


def rows(positions):
    return [{'activity_id':'a' if i<2 else 'b','occurrence':i if i<2 else 0,'instructor_id':'t','room_id':'r','day':'Sunday','start_minute':PERIODS[pi]['start'],'end_minute':PERIODS[pi]['end']} for i,pi in enumerate(positions)]


def test_realistic_policy_spreads_sessions_and_does_not_mutate_snapshot():
    snap=sample();before=deepcopy(snap)
    result=generate(snap)
    assert result['status']=='completed' and snap==before
    report=validate_schedule(snap,result['assignments']);assert report['passed']
    assert len({a['day'] for a in result['assignments'] if a['activity_id']=='a'})==2
    assert all(r['teaching_hours']<=6 and r['idle_periods']<=1 and r['max_consecutive_periods']<=3 for r in report['realism']['daily_resources'])
    assert result['idle_period_penalty']==report['realism']['idle_periods']
    assert result['objective_definition']=='preferences-then-idle-periods-v1'


def test_independent_daily_cap_distribution_consecutive_and_gap_checks():
    snap=sample();snap['calendar']['realism_policy'].update(student_daily_hours=3,instructor_daily_hours=3,max_consecutive_periods=2)
    report=validate_schedule(snap,rows([0,1,2]))
    assert {'group_daily_load','instructor_daily_load','activity_day_distribution','consecutive_periods'}<=set(report['errors'])
    snap['calendar']['realism_policy'].update(spread_activity_days=False,student_daily_hours=6,instructor_daily_hours=6,max_consecutive_periods=3)
    report=validate_schedule(snap,rows([0,3,4]))
    assert 'idle_periods' in report['errors']
    assert all(r['idle_periods']==2 for r in report['realism']['daily_resources'])
    report=validate_schedule(snap,rows([0,1,2]))
    assert report['passed'] and all(r['idle_periods']==0 for r in report['realism']['daily_resources'])  # clock breaks are excluded


def test_daily_capacity_failure_and_preference_penalty_remain_honest():
    snap=sample();snap['calendar']['realism_policy']['student_daily_hours']=0
    assert generate(snap)['status']=='infeasible'
    snap=sample()
    snap['rules']=[{'id':'p','title':'Sunday first period','type':'preferred_period','status':'approved','instructor_id':'t','day':'Sunday','start_hour':8,'end_hour':10}]
    result=generate(snap);assert result['status']=='completed'
    result['validation']=validate_schedule(snap,result['assignments'])
    assert result['validation']['passed']
    assert result['preference_penalty']==build_statistics(snap,result)['preferences']['unsatisfied_sessions']==2


@pytest.mark.parametrize('policy',[{'student_daily_hours':-1},{'max_idle_periods':-1},{'max_consecutive_periods':0},{'unknown':True}])
def test_invalid_policy_fails_safely(policy):
    snap=sample();assignments=generate(snap)['assignments'];snap['calendar']['realism_policy']=policy
    assert generate(snap)['reason']=='invalid_realism_policy'
    assert 'invalid_realism_policy' in validate_schedule(snap,assignments)['errors']


def test_calendar_policy_is_versioned_and_snapshotted(environment):
    client,factory=environment;login(client);setup_data(client,factory)
    old=start(client).json()['id'];assert process_one(factory)
    ws=client.get('/api/workspace').json()
    body={'name':ws['name'],'term':ws['term'],**ws['calendar']}
    body.update(teaching_periods=[{'start':s,'end':s+60} for s in range(480,720,60)],start_hour=8,end_hour=12,realism_policy={**POLICY,'student_daily_hours':1.0,'instructor_daily_hours':1.0})
    assert client.put('/api/workspace',headers=version(client),json=body).status_code==200
    assert client.get('/api/schedules/'+old).json()['stale']
    new=start(client).json()['id'];assert process_one(factory)
    run=client.get('/api/schedules/'+new).json()
    assert run['status']=='completed' and run['result']['validation']['passed']
    assert run['snapshot']['calendar']['realism_policy']['student_daily_hours']==1
    assert all(r['teaching_hours']<=1 for r in run['result']['validation']['realism']['daily_resources'])
