from copy import deepcopy
import pytest
from app.proposal_validation import validate_proposal

CALENDAR = {'days': ['Saturday', 'Sunday'], 'start_hour': 9, 'end_hour': 17}
RECORDS = {'teacher': 'instructors', 'room': 'rooms', 'group': 'groups', 'activity': 'courses'}


def envelope():
    return {'decision': 'ready', 'proposals': [{'kind': 'rule', 'data': {
        'title': 'Saturday unavailable', 'type': 'unavailable', 'instructor_id': 'teacher',
        'day': 'Saturday', 'start_hour': 9, 'end_hour': 11, 'strength': 'mandatory',
    }}], 'clarifications': [], 'unsupported': []}


def check(value):
    return validate_proposal(value, records=RECORDS, calendar=CALENDAR)


def test_valid_saturday_candidate_is_only_eligible_for_human_review():
    value = envelope(); before = deepcopy(value)
    result = check(value)
    assert result.valid and result.eligible_for_review and result.requires_human_approval
    assert value == before


@pytest.mark.parametrize('field,value,code', [
    ('instructor_id', 'invented', 'invalid_reference'),
    ('instructor_id', 'room', 'invalid_reference'),
    ('day', 'Friday', 'outside_calendar'),
    ('start_hour', 8, 'outside_calendar'),
    ('end_hour', 9, 'invalid_time_range'),
    ('strength', 'preferred', 'invalid_strength'),
])
def test_semantic_errors_block_review(field, value, code):
    output = envelope(); output['proposals'][0]['data'][field] = value
    result = check(output)
    assert not result.valid and not result.eligible_for_review
    assert result.errors == ('proposals.0.' + code,)


@pytest.mark.parametrize('value', ['9', True, 9.0])
def test_hours_are_not_coerced(value):
    output = envelope(); output['proposals'][0]['data']['start_hour'] = value
    assert check(output).errors == ('proposal_syntax',)


@pytest.mark.parametrize('kind,field,target,strength', [
    ('preferred_period','instructor_id','teacher','preferred'),
    ('room_unavailable','room_id','room','mandatory'),
    ('group_unavailable','group_id','group','mandatory'),
    ('group_allowed','group_id','group','mandatory'),
    ('activity_allowed','activity_id','activity','mandatory'),
])
def test_other_manual_rule_types(kind, field, target, strength):
    output = envelope(); data = output['proposals'][0]['data']; data.pop('instructor_id')
    data.update(type=kind, strength=strength); data[field] = target
    assert check(output).eligible_for_review


def test_ambiguous_response_is_valid_but_cannot_be_approved_as_ready():
    output = envelope(); output.update(decision='clarify', clarifications=['which_time'])
    result = check(output)
    assert result.valid and not result.eligible_for_review
    output['decision'] = 'ready'
    assert check(output).errors == ('decision_consistency',)


def test_duplicate_rule_and_extra_target_rejected():
    output = envelope(); output['proposals'].append(deepcopy(output['proposals'][0]))
    assert check(output).errors == ('proposals.1.duplicate_rule',)
    output = envelope(); output['proposals'][0]['data']['room_id'] = 'room'
    assert check(output).errors == ('proposals.0.invalid_reference',)


def test_unknown_fields_and_unimplemented_proposals_are_not_silently_dropped():
    output = envelope(); output['approved'] = True
    assert check(output).errors == ('proposal_syntax',)
    output = envelope(); output['proposals'][0]['kind'] = 'instructor_weekly_limit'
    assert check(output).errors == ('proposal_syntax',)


def test_empty_ready_and_duplicate_codes_are_invalid():
    output = envelope(); output['proposals'] = []
    assert check(output).errors == ('decision_consistency',)
    output.update(decision='clarify', clarifications=['time', 'time'])
    assert check(output).errors == ('clarifications_codes',)
