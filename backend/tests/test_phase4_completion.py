from copy import deepcopy
from uuid import uuid4
import pytest
from app.solver import generate
from app.preflight import inspect_inputs
from app.validation import validate_schedule
from app.provenance import seal_snapshot,verify_snapshot,SolverSettings
from app.schedule_worker import process_one
from test_schedules import example,setup_data,start
from test_workflows import login,version


def window(typ,target,day='Monday',start=8,end=12):
    return dict(id=str(uuid4()),status='approved',type=typ,day=day,start_hour=start,end_hour=end,strength='mandatory',**target)


def test_permitted_windows_union_and_target_intersection():
    snap=example()
    snap['rules']=[window('activity_allowed',{'activity_id':'a'}),window('activity_allowed',{'activity_id':'a'},'Sunday'),window('group_allowed',{'group_id':'g'},'Monday')]
    result=generate(snap)
    assert result['status']=='completed'
    assert all(a['day']=='Monday' for a in result['assignments'])
    report=validate_schedule(snap,result['assignments'])
    assert report['passed']
    assert next(c for c in report['coverage'] if c['check']=='approved_allowed_windows')['applicable']==3
    bad=deepcopy(result['assignments']);bad[0]['day']='Sunday'
    report=validate_schedule(snap,bad)
    assert 'approved_allowed_windows' in report['errors']
    violation=next(v for v in report['violations'] if v['code']=='approved_allowed_windows')
    assert violation['sessions'][0]['activity_id'] and violation['rule_ids']


@pytest.mark.parametrize('cause', ['room','windows','lock','spread','group_load'])
def test_preflight_explains_proven_local_contradictions(cause):
    snap=example()
    if cause=='room':snap['records'][3]['capacity']=1
    elif cause=='windows':snap['rules']=[window('activity_allowed',{'activity_id':'a'},start=8,end=9),window('group_allowed',{'group_id':'g'},start=10,end=12)]
    elif cause=='lock':snap['assignment_locks']=[dict(id='l',status='approved',activity_id='a',occurrence=0,day='Sunday',start_minute=0)]
    elif cause=='spread':snap['calendar'].update(days=['Monday'],teaching_periods=[{'start':480,'end':540},{'start':540,'end':600}],realism_policy={'spread_activity_days':True})
    else:snap['calendar']['realism_policy']={'student_daily_hours':0.5}
    report=inspect_inputs(snap)
    assert not report['ready'] and report['blockers']
    assert any(b['activity_id'] or b['resource_id'] for b in report['blockers'])


def test_missing_optional_caps_are_warnings_not_blockers():
    report=inspect_inputs(example())
    assert report['ready'] and report['warnings']


def test_detailed_collision_names_both_sessions_and_resource():
    snap=example();rows=generate(snap)['assignments']
    rows[1].update(day=rows[0]['day'],start_minute=rows[0]['start_minute'],end_minute=rows[0]['end_minute'])
    report=validate_schedule(snap,rows)
    v=next(v for v in report['violations'] if v['code']=='resource_conflicts')
    assert len(v['sessions'])==2 and 'g' in v['resource_ids']
    assert next(c for c in report['coverage'] if c['check']=='resource_conflicts')['status']=='failed'


def test_custom_settings_and_weighted_objective_are_retained():
    snap=seal_snapshot(example(),SolverSettings(time_limit_seconds=1,search_workers=1,random_seed=7,objective_profile='weighted-v1',preference_weight=3,idle_weight=2).model_dump())
    assert verify_snapshot(snap)
    result=generate(snap)
    assert result['status']=='completed'
    d=result['solver_diagnostics']
    assert d['objective_definition']=='weighted-preferences-idle-v1'
    assert d['objective_weights']=={'preferences':3,'idle_periods':2}
    assert 'random_seed: 7' in d['parameters_text'] and 'num_search_workers: 1' in d['parameters_text']


def test_api_allowed_rule_and_settings_idempotency(environment):
    client,factory=environment
    login(client);setup_data(client,factory)
    ws=client.get('/api/workspace').json();activity=next(r for r in ws['records'] if r['kind']=='courses')
    body=dict(title='Monday only',activity_id=activity['id'],type='activity_allowed',day='Monday',start_hour=8,end_hour=12,strength='mandatory')
    response=client.post('/api/rules',headers=version(client),json=body)
    assert response.status_code==201,response.text
    assert client.post('/api/rules/'+response.json()['id']+'/approve',headers=version(client)).status_code==200
    preparation=client.get('/api/schedules/preflight/current').json()
    assert preparation['ready']
    key=str(uuid4());settings={'time_limit_seconds':2,'search_workers':1,'random_seed':9}
    created=client.post('/api/schedules',headers=version(client),json={'request_key':key,'settings':settings})
    assert created.status_code==202,created.text
    retry=client.post('/api/schedules',headers=version(client),json={'request_key':key,'settings':{**settings,'random_seed':10}})
    assert retry.status_code==409
    assert process_one(factory)
    saved=client.get('/api/schedules/'+created.json()['id']).json()
    assert saved['snapshot']['snapshot_schema_version']==2
    assert saved['result']['validation']['passed']
    assert all(a['day']=='Monday' for a in saved['result']['assignments'])
    assert saved['result']['provenance']['lifecycle']['finished_at']
    login(client,'viewer@example.test')
    assert client.get('/api/schedules/preflight/current').status_code==403


def test_invalid_settings_and_rule_target_rejected(environment):
    client,factory=environment
    login(client);setup_data(client,factory)
    assert client.post('/api/schedules',headers=version(client),json={'request_key':str(uuid4()),'settings':{'time_limit_seconds':61}}).status_code==422
    assert client.post('/api/rules',headers=version(client),json=dict(title='Bad',type='activity_allowed',instructor_id='teacher',day='Monday',start_hour=8,end_hour=12,strength='mandatory')).status_code==422


def test_historical_input_selection_keeps_source_and_staleness(environment):
    client,factory=environment
    login(client);setup_data(client,factory)
    source=start(client).json()['id'];assert process_one(factory)
    saved=client.get('/api/schedules/'+source).json()
    assert client.post('/api/records/groups',headers=version(client),json={'name':'Extra','code':'EXTRA','size':10}).status_code==201
    response=client.post('/api/schedules',headers=version(client),json={'request_key':str(uuid4()),'source_run_id':source})
    assert response.status_code==202,response.text
    assert response.json()['stale']
    assert response.json()['snapshot']['records']==saved['snapshot']['records']
    assert response.json()['snapshot']['provenance']['source_run_id']==source
    assert process_one(factory)
    assert client.get('/api/schedules/'+response.json()['id']).json()['result']['validation']['passed']


def test_solution_progress_is_score_only_before_validation():
    updates=[]
    result=generate(example(),on_solver=lambda solver:updates.append)
    assert result['status']=='completed' and updates
    assert all(set(p)=={'best_objective','best_bound','solver_seconds'} for p in updates)
    assert result['solver_diagnostics']['model_sha256']
    assert result['solver_diagnostics']['model_validation_error']==''


def test_global_infeasibility_is_not_hidden_by_passing_local_checks():
    snap=example()
    snap['calendar'].update(days=['Sunday'],end_hour=11)
    snap['records'].append(dict(id='h',kind='groups',size=20))
    snap['records'][-2].update(duration=60,sessions=2,group_ids=['h'])
    assert inspect_inputs(snap)['ready']
    result=generate(snap)
    assert result['status']=='infeasible'
    assert result['solver_diagnostics']['raw_status']=='INFEASIBLE'


def test_model_invalid_remains_distinct_from_unknown_and_infeasible():
    def invalid_parameters(solver):
        solver.parameters.num_search_workers=-1
    result=generate(example(),on_solver=invalid_parameters)
    assert result['status']=='failed' and result['reason']=='model_invalid'
    assert result['solver_diagnostics']['raw_status']=='MODEL_INVALID'
