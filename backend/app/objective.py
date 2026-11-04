"""Declared scoring profiles. The solver minimises sum(weight × component); the worker
recomputes every component independently from the assignments and checks the total.

convenience-v1 components (all non-negative integers):
  preferences      sessions outside their instructor's preferred windows
  student_gaps     empty slots between a group's first and last session of a day
  instructor_gaps  the same for each instructor
  instructor_days  instructor-days with any teaching (fewer trips to campus)
  student_days     group-days with any class (fewer trips for students)
  edge_sessions    sessions in the first or last slot of the day
  group_peak       per group, the busiest day's occupied slots (balances the week)
  repeat_same_day  extra sessions of one activity on the same day (spreads lectures)
  long_day_minutes a group's teaching minutes beyond LONG_DAY_MINUTES in a day
"""
from app.calendar_slots import day_slots

CONVENIENCE_WEIGHTS = {'preferences': 20, 'repeat_same_day': 15, 'student_gaps': 10, 'instructor_gaps': 5,
                       'instructor_days': 3, 'student_days': 4, 'group_peak': 2, 'edge_sessions': 1, 'long_day_minutes': 1}
# A group's teaching beyond this many minutes in one day counts against convenience.
LONG_DAY_MINUTES = 270
PROFILES = ('convenience-v1', 'preferences-first-v1', 'weighted-v1')


def possible_gaps(snapshot):
    """Upper bound on gap slots; used to make preferences strictly dominate gaps."""
    activities = [r for r in snapshot['records'] if r['kind'] == 'courses']
    resources = {('i', t) for a in activities for t in a['eligible_instructors']} | {('g', g) for a in activities for g in a['group_ids']}
    return len(resources) * len(snapshot['calendar']['days']) * max(0, len(day_slots(snapshot['calendar'])) - 2)


def weights(snapshot, config):
    """Weights per component for the configured profile."""
    profile = config.get('objective_profile', 'convenience-v1')
    compact = bool(snapshot['calendar'].get('realism_policy', {}).get('compact_days'))
    if profile == 'convenience-v1':
        return dict(CONVENIENCE_WEIGHTS)
    if profile == 'weighted-v1':
        return {'preferences': config['preference_weight'], 'idle_periods': config['idle_weight']}
    return {'preferences': possible_gaps(snapshot) + 1 if compact else 1, 'idle_periods': 1}


def effective(snapshot, config):
    """Weights actually scored. Older profiles count idle periods only with compact days."""
    declared = weights(snapshot, config)
    if config.get('objective_profile', 'convenience-v1') != 'convenience-v1' and not snapshot['calendar'].get('realism_policy', {}).get('compact_days'):
        declared['idle_periods'] = 0
    return declared
