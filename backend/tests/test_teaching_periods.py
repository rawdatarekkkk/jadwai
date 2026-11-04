from copy import deepcopy
from app.reference_periods import PERIODS
from app.solver import generate
from app.validation import validate_schedule
from app.schemas import CalendarInput
from test_schedules import example
from test_workflows import login,version
import pytest


def test_five_periods_are_exact_and_breaks_are_never_scheduled():
    assert len(PERIODS) == 5
    snap=example();snap['calendar'].update(teaching_periods=PERIODS,end_hour=22)
    for a in snap['records']:
        if a['kind']=='courses':a['duration']=90
    result=generate(snap)
    assert result['status']=='completed'
    assert validate_schedule(snap,result['assignments'])['passed']
    assert all({'start':a['start_minute'],'end':a['end_minute']} in PERIODS for a in result['assignments'])
    bad=deepcopy(result['assignments']);bad[0].update(start_minute=600,end_minute=690)
    assert 'calendar' in validate_schedule(snap,bad)['errors']
    evening=deepcopy(result['assignments']);evening[0].update(start_minute=1065,end_minute=1155)
    assert 'calendar' in validate_schedule(snap,evening)['errors']

@pytest.mark.parametrize('periods',[[{'start':600,'end':510}],[{'start':510,'end':600},{'start':590,'end':680}],[{'start':450,'end':540}],[{'start':True,'end':600}]])
def test_invalid_period_definitions_are_rejected(periods):
    with pytest.raises(ValueError):CalendarInput(name='CS',term='Fall',timezone='Africa/Cairo',days=['Sunday'],start_hour=8,end_hour=22,period_minutes=30,teaching_periods=periods)

def test_incompatible_duration_has_no_placement():
    snap=example();snap['calendar'].update(teaching_periods=PERIODS,end_hour=22)
    assert generate(snap)['status']=='infeasible'
