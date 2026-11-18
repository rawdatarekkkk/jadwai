"""One definition of what a rule means, shared by solver, validator, input checks and reports.

Time rules carry a day (or None for every teaching day) and a half-hour aligned interval.
Limit rules carry their parameters in `params` and no time interval.
"""
TIME_TYPES = ('teaching_allowed', 'teaching_preferred', 'unavailable', 'preferred_period', 'room_unavailable', 'group_unavailable', 'group_allowed', 'activity_allowed')
LIMIT_TYPES = ('lecture_before_tutorial', 'activity_room', 'activities_not_same_day', 'instructor_max_daily_hours', 'group_max_daily_hours', 'instructor_max_days')
TYPES = TIME_TYPES + LIMIT_TYPES
TARGETS = {
    'teaching_allowed': (None, None),
    'teaching_preferred': (None, None),
    'lecture_before_tutorial': (None, None),
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


def lecture_tutorial_pairs(records):
    """Same catalogue course and overlapping groups; legacy records use exact names.

    No global cross-course ordering. All weekly lectures finish before the first
    tutorial for each shared student group. Labs are not tutorials.
    """
    activities = [r for r in records if r['kind'] == 'courses']
    for lecture in activities:
        if lecture.get('activity_type') != 'lecture':
            continue
        for tutorial in activities:
            if tutorial.get('activity_type') != 'tutorial' or not set(lecture['group_ids']) & set(tutorial['group_ids']):
                continue
            a, b = lecture.get('course_id'), tutorial.get('course_id')
            same = a == b if a and b else bool(lecture.get('name') and lecture['name'].strip().casefold() == tutorial.get('name', '').strip().casefold())
            if same:
                yield lecture['id'], tutorial['id']


SOFT_TYPES = ('preferred_period', 'teaching_preferred')


def teaching_matches(rule, activity):
    return activity.get('activity_type') in param(rule, 'activity_types', [])


def preference_sets(snapshot, activity, teacher):
    """Instructor windows form one union; teaching preferences form another.

    Each applicable family contributes one penalty if the session misses its union.
    """
    instructor = [r for r in approved(snapshot, 'preferred_period') if r.get('instructor_id') == teacher]
    return ([instructor] if instructor else []) + teaching_window_sets(snapshot, activity, 'teaching_preferred')


def teaching_window_sets(snapshot, activity, kind):
    """Windows of one selector are alternatives; distinct selectors apply together."""
    families = {}
    for rule in approved(snapshot, kind):
        if teaching_matches(rule, activity):
            selector = tuple(sorted(param(rule, 'activity_types', [])))
            families.setdefault(selector, []).append(rule)
    return list(families.values())
