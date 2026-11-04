"""Shared semantic checks for manual rules and extracted rule candidates."""
TARGETS = {
    'unavailable': ('instructor_id', 'instructors'),
    'preferred_period': ('instructor_id', 'instructors'),
    'room_unavailable': ('room_id', 'rooms'),
    'group_unavailable': ('group_id', 'groups'),
    'group_allowed': ('group_id', 'groups'),
    'activity_allowed': ('activity_id', 'courses'),
}


def rule_error(body, target_kind, calendar):
    field, kind = TARGETS[body.type]
    if not getattr(body, field) or any(getattr(body, f) is not None for f in
            ('instructor_id', 'room_id', 'group_id', 'activity_id') if f != field):
        return 'invalid_reference'
    if target_kind != kind:
        return 'invalid_reference'
    if (body.day not in calendar['days'] or body.start_hour < calendar['start_hour']
            or body.end_hour > calendar['end_hour']):
        return 'outside_calendar'
    if body.start_hour >= body.end_hour:
        return 'invalid_time_range'
    if body.strength != ('preferred' if body.type == 'preferred_period' else 'mandatory'):
        return 'invalid_strength'
    return None
