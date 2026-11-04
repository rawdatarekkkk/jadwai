"""One definition of what a rule means, shared by solver, validator, input checks and reports.

Time rules carry a day (or None for every teaching day) and a half-hour aligned interval.
Limit rules carry their parameters in `params` and no time interval.
"""
TIME_TYPES = ('unavailable', 'preferred_period', 'room_unavailable', 'group_unavailable', 'group_allowed', 'activity_allowed')
LIMIT_TYPES = ('activity_room', 'activities_not_same_day', 'instructor_max_daily_hours', 'group_max_daily_hours', 'instructor_max_days')
TYPES = TIME_TYPES + LIMIT_TYPES
TARGETS = {
    'unavailable': ('instructor_id', 'instructors'),
    'preferred_period': ('instructor_id', 'instructors'),
    'room_unavailable': ('room_id', 'rooms'),
    'group_unavailable': ('group_id', 'groups'),
    'group_allowed': ('group_id', 'groups'),
    'activity_allowed': ('activity_id', 'courses'),
    'activity_room': ('activity_id', 'courses'),
    'activities_not_same_day': (None, None),
    'instructor_max_daily_hours': ('instructor_id', 'instructors'),
    'group_max_daily_hours': ('group_id', 'groups'),
    'instructor_max_days': ('instructor_id', 'instructors'),
}


def approved(snapshot, *types):
    return [r for r in snapshot['rules'] if r['status'] == 'approved' and r['type'] in types]


def on_day(rule, day):
    return rule.get('day') is None or rule['day'] == day


def bounds(rule):
    return round(rule['start_hour'] * 60), round(rule['end_hour'] * 60)


def covers(rule, day, start, end):
    """The session lies wholly inside the rule's interval on that day."""
    low, high = bounds(rule)
    return on_day(rule, day) and low <= start and end <= high


def overlaps(rule, day, start, end):
    low, high = bounds(rule)
    return on_day(rule, day) and start < high and low < end


def within_windows(windows, day, start, end):
    """Approved windows of one target are weekly alternatives; none means unrestricted."""
    return not windows or any(covers(r, day, start, end) for r in windows)


def param(rule, key, default=None):
    return (rule.get('params') or {}).get(key, default)
