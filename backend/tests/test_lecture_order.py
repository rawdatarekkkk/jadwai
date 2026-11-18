from copy import deepcopy
import pytest
from app.solver import generate
from app.validation import validate_schedule
from app.rule_parser import parse
from app.schemas import RuleInput
from app.partial_plan import scope_activities
from test_schedules import example


def snapshot():
    s = example()
    s['records'][4].update(name='Databases', course_id='db')
    s['records'][5].update(name='Databases', course_id='db')
    s['rules'] = [{'id': 'order', 'status': 'approved', 'type': 'lecture_before_tutorial'}]
    return s


@pytest.mark.parametrize('text', ['a lecture should be before a tutorial in any schedule', 'lectures must finish before tutorials', 'lectures before tutorials', 'المحاضرة قبل السكشن'])
def test_plain_text_global_rule(text):
    result = parse(text, {'records': [], 'calendar': snapshot()['calendar']})
    assert result['decision'] == 'ready'
    body = RuleInput.model_validate(result['proposals'][0]['data'])
    assert body.type == 'lecture_before_tutorial' and body.strength == 'mandatory'
    assert body.group_id is None and body.activity_id is None


def rows(lecture_day='Sunday', tutorial_day='Monday'):
    return [dict(activity_id=a, occurrence=o, day=d, start_minute=start, end_minute=end, instructor_id='t', room_id='r')
            for a,o,d,start,end in [('a',0,lecture_day,480,540),('a',1,lecture_day,540,600),('b',0,tutorial_day,480,570)]]


def test_solver_and_independent_validator_enforce_week_order():
    s = snapshot()
    valid, invalid = rows(), rows('Monday', 'Sunday')
    assert validate_schedule(s,valid)['passed']
    assert generate(s,fixed_assignments=valid)['status'] == 'completed'
    assert 'approved_lecture_before_tutorial' in validate_schedule(s,invalid)['errors']
    assert generate(s,fixed_assignments=invalid)['status'] == 'infeasible'
    result = generate(s)
    assert result['status'] == 'completed'
    assert validate_schedule(s,result['assignments'])['passed']


def test_same_day_end_boundary_and_custom_week_order():
    s = snapshot(); valid=rows('Sunday','Sunday');valid[-1].update(start_minute=600,end_minute=690)
    assert validate_schedule(s,valid)['passed']
    assert generate(s,fixed_assignments=valid)['status'] == 'completed'
    s['calendar']['days'] = ['Monday','Sunday']
    assert 'approved_lecture_before_tutorial' in validate_schedule(s,rows())['errors']


def test_other_courses_and_unapproved_rules_are_unaffected():
    s = snapshot(); s['records'][5]['course_id'] = 'different'
    assert validate_schedule(s,rows('Monday','Sunday'))['passed']
    s=snapshot();s['rules'][0]['status']='draft'
    assert validate_schedule(s,rows('Monday','Sunday'))['passed']


def test_partial_schedule_keeps_fixed_lecture_order():
    s=snapshot();s['plan']={'activity_ids':['b'],'fixed':rows()[:2]}
    assert generate(s,fixed_assignments=rows())['status'] == 'completed'
    s['plan']['fixed']=rows('Monday','Sunday')[:2]
    assert generate(s,fixed_assignments=rows('Monday','Sunday'))['status']=='infeasible'


def test_shared_lecture_dependency_is_added_to_partial_scope():
    s=snapshot();s['records'].append({'id':'h','kind':'groups','major':'CS','year':2,'size':5})
    s['records'][4]['group_ids']=['g','h'];s['records'][5]['group_ids']=['h']
    assert scope_activities(s['records'],[{'programme':'CS','year':2}],set(),s['rules']) == ['a','b']


def test_rule_create_and_approve(environment):
    from test_workflows import login,version
    client,_=environment;login(client)
    proposal=parse('a lecture should be before a tutorial in any schedule',{'records':[],'calendar':snapshot()['calendar']})['proposals'][0]['data']
    created=client.post('/api/rules',json=proposal,headers=version(client))
    assert created.status_code==201,created.text
    approved=client.post('/api/rules/'+created.json()['id']+'/approve',headers=version(client))
    assert approved.status_code==200,approved.text
