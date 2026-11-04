"""Shared semantic checks for manual rules and extracted rule candidates."""
from app.rule_semantics import TARGETS, TIME_TYPES

PARAMS = {
    'activity_room': ('room_ids',),
    'activities_not_same_day': ('activity_ids',),
    'instructor_max_daily_hours': ('hours',),
    'group_max_daily_hours': ('hours',),
    'instructor_max_days': ('days',),
}
REFERENCE_PARAMS = {'room_ids': 'rooms', 'activity_ids': 'courses'}


def rule_error(body, kind_of, calendar):
    """kind_of maps a record ID to its kind (None when missing)."""
    field, kind = TARGETS[body.type]
    targets = ('instructor_id', 'room_id', 'group_id', 'activity_id')
    if any(getattr(body, f) is not None for f in targets if f != field):
        return 'invalid_reference'
    if field and (not getattr(body, field) or kind_of(getattr(body, field)) != kind):
        return 'invalid_reference'
    params = body.params.model_dump()
    expected = PARAMS.get(body.type, ())
    if any(params[k] is None for k in expected) or any(v is not None for k, v in params.items() if k not in expected):
        return 'invalid_parameters'
    for key, ref_kind in REFERENCE_PARAMS.items():
        values = params[key] or []
        if len(set(values)) != len(values) or any(kind_of(v) != ref_kind for v in values):
            return 'invalid_reference'
    if body.type in TIME_TYPES:
        if body.start_hour is None or body.end_hour is None:
            return 'invalid_time_range'
        if (body.day is not None and body.day not in calendar['days']) or body.start_hour < calendar['start_hour'] or body.end_hour > calendar['end_hour']:
            return 'outside_calendar'
        if body.start_hour >= body.end_hour:
            return 'invalid_time_range'
    elif body.day is not None or body.start_hour is not None or body.end_hour is not None:
        return 'invalid_time_range'
    if body.strength != ('preferred' if body.type == 'preferred_period' else 'mandatory'):
        return 'invalid_strength'
    return None
