from uuid import uuid4
import pytest
from app.rule_parser import parse
from app.proposal_validation import validate_proposal
from test_workflows import login, version

CALENDAR = {'days': ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'], 'start_hour': 8, 'end_hour': 18}
RECORDS = [
    {'id': 'ahmed', 'kind': 'instructors', 'data': {'name': 'Dr. Ahmed Hassan', 'code': 'AH', 'position': 'doctor'}},
    {'id': 'mona', 'kind': 'instructors', 'data': {'name': 'Mona Adel', 'code': 'MA', 'position': 'ta'}},
    {'id': 'sara', 'kind': 'instructors', 'data': {'name': 'د. سارة علي', 'code': 'SA', 'position': 'doctor'}},
    {'id': 'ahmed2', 'kind': 'instructors', 'data': {'name': 'Ahmed Samir', 'code': 'AS', 'position': 'ta'}},
    {'id': 'g1', 'kind': 'groups', 'data': {'name': 'CS Year 1 G1', 'code': 'CS1-G1', 'year': 1, 'size': 30}},
    {'id': 'g2', 'kind': 'groups', 'data': {'name': 'CS Year 1 G2', 'code': 'CS1-G2', 'year': 1, 'size': 30}},
    {'id': 'g3', 'kind': 'groups', 'data': {'name': 'CS Year 2 G1', 'code': 'CS2-G1', 'year': 2, 'size': 30}},
    {'id': 'dslab', 'kind': 'rooms', 'data': {'name': 'Data Science Lab', 'code': 'DSL'}},
    {'id': 'h1', 'kind': 'rooms', 'data': {'name': 'Hall 1', 'code': 'H1'}},
    {'id': 'ml-lec', 'kind': 'courses', 'data': {'name': 'Machine Learning', 'code': 'ML-L', 'activity_type': 'lecture'}},
    {'id': 'ml-lab', 'kind': 'courses', 'data': {'name': 'Machine Learning', 'code': 'ML-B', 'activity_type': 'lab'}},
    {'id': 'db-lec', 'kind': 'courses', 'data': {'name': 'Databases', 'code': 'DB-L', 'activity_type': 'lecture'}},
]
CONTEXT = {'records': RECORDS, 'calendar': CALENDAR}


def rules(text):
    output = parse(text, CONTEXT)
    check = validate_proposal(output, records={r['id']: r['kind'] for r in RECORDS}, calendar=CALENDAR)
    assert check.valid, (output, check.errors)
    return output, [p['data'] for p in output['proposals']]


def test_english_unavailability_with_half_hour_time():
    output, found = rules("Dr. Ahmed Hassan can't teach on Sunday before 10:30")
    assert output['decision'] == 'ready'
    assert found == [{**found[0], 'type': 'unavailable', 'instructor_id': 'ahmed', 'day': 'Sunday', 'start_hour': 8, 'end_hour': 10.5}]


def test_egyptian_arabic_and_arabic_digits():
    output, found = rules('سارة علي مش فاضية يوم الاثنين بعد ٢')
    assert output['decision'] == 'ready'
    assert [(r['type'], r['instructor_id'], r['day'], r['start_hour'], r['end_hour']) for r in found] == [('unavailable', 'sara', 'Monday', 14, 18)]


def test_preference_every_day():
    _, found = rules('Mona Adel prefers to teach in the mornings every day')
    assert [(r['type'], r['day'], r['start_hour'], r['end_hour'], r['strength']) for r in found] == [('preferred_period', None, 8, 12, 'preferred')]


def test_year_targets_every_group_of_that_year():
    _, found = rules('No classes for year 1 on Thursday after 2pm')
    assert sorted((r['type'], r['group_id']) for r in found) == [('group_unavailable', 'g1'), ('group_unavailable', 'g2')]
    assert {(r['day'], r['start_hour'], r['end_hour']) for r in found} == {('Thursday', 14, 18)}


def test_generic_words_in_group_names_are_not_ambiguous():
    output, found = rules('No classes for year 2 on Monday after 3pm')
    assert output['decision'] == 'ready' and [r['group_id'] for r in found] == ['g3']


def test_ambiguous_first_name_asks_for_clarification():
    output = parse('Ahmed cannot teach on Sunday', CONTEXT)
    assert output['decision'] == 'clarify' and output['clarifications'] == ['ambiguous_name:ahmed']


def test_special_room_requirement_uses_activity_type():
    _, found = rules('The Machine Learning lab must be in the Data Science Lab')
    assert [(r['type'], r['activity_id'], r['params']['room_ids']) for r in found] == [('activity_room', 'ml-lab', ['dslab'])]


@pytest.mark.parametrize('text,expected', [
    ('Mona Adel should teach at most 4.5 hours per day', ('instructor_max_daily_hours', 'hours', 4.5)),
    ('CS1-G1 no more than 6 hours a day', ('group_max_daily_hours', 'hours', 6)),
    ('Dr. Ahmed Hassan only 3 days a week', ('instructor_max_days', 'days', 3)),
    ('الدكتورة سارة علي ٣ أيام في الأسبوع', ('instructor_max_days', 'days', 3)),
])
def test_limit_rules(text, expected):
    _, found = rules(text)
    assert [(r['type'], r['params'][expected[1]]) for r in found] == [(expected[0], expected[2])]


def test_activities_on_different_days():
    _, found = rules('Machine Learning lecture and Databases should not be on the same day')
    assert found[0]['type'] == 'activities_not_same_day' and set(found[0]['params']['activity_ids']) == {'ml-lec', 'db-lec'}


def test_only_on_a_day_becomes_unavailability_elsewhere():
    _, found = rules('Mona Adel teaches only on Monday')
    assert sorted(r['day'] for r in found) == sorted(d for d in CALENDAR['days'] if d != 'Monday')
    assert all(r['type'] == 'unavailable' and (r['start_hour'], r['end_hour']) == (8, 18) for r in found)


def test_unrecognised_and_missing_target():
    assert parse('make it nice', CONTEXT)['decision'] == 'unsupported'
    assert parse('nobody can teach on Sunday', CONTEXT)['clarifications'] == ['missing_target']


def test_interpret_endpoint_stores_reviewable_proposal(environment):
    client, _ = environment
    login(client)
    response = client.post('/api/proposals/interpret', headers=version(client), json={'request_key': str(uuid4()), 'text': 'Dr. Test cannot teach on Monday before 10'})
    assert response.status_code == 201, response.text
    record = response.json()['record']
    assert record['origin'] == 'builtin_parser' and record['output']['decision'] == 'ready'
    proposal_id = response.json()['id']
    review = client.post(f'/api/proposals/{proposal_id}/review', headers=version(client), json={'request_key': str(uuid4()), 'action': 'create_drafts', 'rationale': 'Matches the request'})
    assert review.status_code == 201, review.text
    rules = client.get('/api/workspace').json()['rules']
    assert [(r['type'], r['day'], r['end_hour'], r['status']) for r in rules] == [('unavailable', 'Monday', 10, 'draft')]
