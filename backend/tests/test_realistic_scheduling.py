from copy import deepcopy
import pytest
from app.calendar_slots import day_placements
from app.provenance import CONFIG
from app.realism_validation import convenience_components
from app.solver import generate
from app.validation import validate_schedule
from app.validation_details import preference_penalty
from test_schedules import example
from test_workflows import login, version

PERIODS = [{'start': s, 'end': e} for s, e in [(510, 600), (615, 705), (720, 810), (825, 915), (945, 1035)]]


def periods_snapshot():
    snap = example()
    snap['calendar'].update(days=['Sunday', 'Monday', 'Tuesday'], end_hour=18, teaching_periods=deepcopy(PERIODS))
    for r in snap['records']:
        if r['kind'] == 'courses':
            r['duration'] = 90
    return snap


def rule(**fields):
    return {'id': fields.pop('id', 'r'), 'status': 'approved', 'title': 'Rule', 'strength': 'mandatory', 'day': None, 'start_hour': None, 'end_hour': None, 'params': {}, **fields}


def test_three_hour_lab_spans_two_periods_but_never_a_long_break():
    cal = {'teaching_periods': PERIODS, 'start_hour': 8, 'end_hour': 18, 'period_minutes': 30}
    # 8:30-11:45 and 12:00-15:15 have 15-minute breaks inside; 13:45-17:15 spans a 30-minute break.
    assert [(s, e) for s, e, _ in day_placements(cal, 180)] == [(510, 705), (615, 810), (720, 915), (825, 1035)]
    snap = periods_snapshot()
    lab = next(r for r in snap['records'] if r['id'] == 'b')
    lab.update(duration=180)
    result = generate(snap)
    assert result['status'] == 'completed'
    session = next(a for a in result['assignments'] if a['activity_id'] == 'b')
    assert (session['start_minute'], session['end_minute']) in [(510, 705), (615, 810), (720, 915), (825, 1035)]
    assert validate_schedule(snap, result['assignments'])['passed']
    bad = deepcopy(result['assignments'])
    next(a for a in bad if a['activity_id'] == 'b')['end_minute'] = session['start_minute'] + 180
    assert 'calendar' in validate_schedule(snap, bad)['errors']


def test_half_hour_and_every_day_rules():
    snap = periods_snapshot()
    # Group unavailable until 10:30 every day: 10:15-11:45 overlaps it, so nothing starts before 12:00.
    snap['rules'] = [rule(type='group_unavailable', group_id='g', start_hour=8, end_hour=10.5)]
    result = generate(snap)
    assert result['status'] == 'completed'
    assert all(a['start_minute'] >= 720 for a in result['assignments'])
    assert validate_schedule(snap, result['assignments'])['passed']
    moved = deepcopy(result['assignments'])
    moved[0].update(start_minute=510, end_minute=600)
    assert 'approved_group_unavailability' in validate_schedule(snap, moved)['errors']


@pytest.mark.parametrize('limit,error', [
    (lambda: rule(type='activity_room', activity_id='a', params={'room_ids': ['r']}), 'approved_room_rules'),
    (lambda: rule(type='activities_not_same_day', params={'activity_ids': ['a', 'b']}), 'approved_separate_days'),
    (lambda: rule(type='instructor_max_daily_hours', instructor_id='t', params={'hours': 1.5}), 'approved_daily_limits'),
    (lambda: rule(type='group_max_daily_hours', group_id='g', params={'hours': 1.5}), 'approved_daily_limits'),
    (lambda: rule(type='instructor_max_days', instructor_id='t', params={'days': 1}), 'approved_teaching_days'),
])
def test_limit_rules_are_solved_and_independently_checked(limit, error):
    snap = periods_snapshot()
    snap['records'].append({'id': 'r2', 'kind': 'rooms', 'name': 'R2', 'code': 'R2', 'capacity': 25, 'room_type': 'lecture', 'equipment': ['projector']})
    for record in snap['records']:
        if record['id'] == 'a':
            record['eligible_instructors'] = ['t']
    snap['rules'] = [limit()]
    result = generate(snap)
    assert result['status'] == 'completed', result
    assert validate_schedule(snap, result['assignments'])['passed']
    # Pile everything onto one day in the second room to break each limit.
    broken = deepcopy(result['assignments'])
    for i, a in enumerate(broken):
        a.update(day='Sunday', start_minute=PERIODS[i]['start'], end_minute=PERIODS[i]['end'], room_id='r2', instructor_id='t')
    if error == 'approved_teaching_days':
        broken[0]['day'] = 'Monday'
    assert error in validate_schedule(snap, broken)['errors']


def test_convenience_profile_scores_match_independent_recount():
    snap = periods_snapshot()
    snap['provenance'] = {'solver_config': {**CONFIG, 'objective_profile': 'convenience-v1'}}
    result = generate(snap)
    assert result['status'] == 'completed'
    observed = {'preferences': preference_penalty(snap, result['assignments'])['total'], **convenience_components(snap, result['assignments'])}
    assert all(result['objective_components'][k] == observed[k] for k in result['objective_components'])
    weights = result['solver_diagnostics']['objective_weights']
    assert result['solver_diagnostics']['objective_value'] == sum(weights[k] * observed[k] for k in weights)
    # Both sessions of the lecture and the tutorial share one group: a compact day has no gaps.
    assert observed['student_gaps'] == 0


def test_rules_api_accepts_new_vocabulary(environment):
    client, factory = environment
    login(client)
    group = client.post('/api/records/groups', headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20}).json()['id']
    room = client.post('/api/records/rooms', headers=version(client), json={'name': 'Lab', 'code': 'LAB', 'capacity': 30, 'room_type': 'lab', 'equipment': ['Data Science Lab']}).json()['id']
    lab = client.post('/api/records/courses', headers=version(client), json={'name': 'ML', 'code': 'ML', 'activity_type': 'lab', 'sessions': 1, 'duration': 60, 'eligible_instructors': ['teacher'], 'group_ids': [group], 'required_equipment': ['Data Science Lab']}).json()['id']
    base = {'title': 'Rule', 'strength': 'mandatory'}
    good = [
        {**base, 'type': 'group_unavailable', 'group_id': group, 'start_hour': 8.5, 'end_hour': 10},
        {**base, 'type': 'activity_room', 'activity_id': lab, 'params': {'room_ids': [room]}},
        {**base, 'type': 'group_max_daily_hours', 'group_id': group, 'params': {'hours': 4.5}},
        {**base, 'type': 'instructor_max_days', 'instructor_id': 'teacher', 'params': {'days': 3}},
    ]
    for body in good:
        response = client.post('/api/rules', headers=version(client), json=body)
        assert response.status_code == 201, (body, response.text)
    bad = [
        ({**base, 'type': 'group_unavailable', 'group_id': group, 'start_hour': 8.25, 'end_hour': 10}, 422),
        ({**base, 'type': 'activity_room', 'activity_id': lab, 'params': {'room_ids': [group]}}, 'invalid_reference'),
        ({**base, 'type': 'instructor_max_days', 'instructor_id': 'teacher', 'params': {'hours': 3}}, 'invalid_parameters'),
        ({**base, 'type': 'group_max_daily_hours', 'group_id': group, 'day': 'Sunday', 'params': {'hours': 4}}, 'invalid_time_range'),
    ]
    for body, expected in bad:
        response = client.post('/api/rules', headers=version(client), json=body)
        assert response.status_code == 422
        if isinstance(expected, str):
            assert response.json()['detail'] == expected
    rules = client.get('/api/workspace').json()['rules']
    assert {r['type'] for r in rules} == {'group_unavailable', 'activity_room', 'group_max_daily_hours', 'instructor_max_days'}
    assert next(r for r in rules if r['type'] == 'group_unavailable')['start_hour'] == 8.5
    for r in rules:
        assert client.post(f"/api/rules/{r['id']}/approve", headers=version(client)).status_code == 200
    preflight = client.get('/api/schedules/preflight/current').json()
    assert not any(b['code'] == 'unsupported_rule' for b in preflight['blockers'])
