from test_schedules import example
from app.solver import generate
from app.validation import validate_schedule
from app.preflight import inspect_inputs


def test_twelve_hours_plus_extra_is_allowed_and_counted():
    snapshot = example()
    snapshot['calendar'].update(days=['Saturday','Sunday','Monday','Tuesday','Wednesday','Thursday'], start_hour=8,end_hour=18,weekly_load_policy={'regular_hours':12,'allow_overtime':True})
    snapshot['records'] = [r for r in snapshot['records'] if r['id']!='b']
    activity = next(r for r in snapshot['records'] if r['id']=='a')
    activity.update(sessions=9,duration=90,eligible_instructors=['t'])
    teacher = next(r for r in snapshot['records'] if r['id']=='t')
    teacher['max_weekly_hours']=12
    assert not inspect_inputs(snapshot)['blockers']
    result = generate(snapshot)
    assert result['status']=='completed'
    report = validate_schedule(snapshot,result['assignments'])
    assert report['passed']
    load = next(w for w in report['workload'] if w['instructor_id']=='t')
    assert load['assigned_hours']==13.5
    assert load['regular_hours']==12 and load['extra_hours']==1.5
    assert not load['exceeded']
    rows=result['assignments'][:8]
    snapshot['records'][-1]['sessions']=8
    load=next(w for w in validate_schedule(snapshot,rows)['workload'] if w['instructor_id']=='t')
    assert load['assigned_hours']==12 and load['extra_hours']==0
