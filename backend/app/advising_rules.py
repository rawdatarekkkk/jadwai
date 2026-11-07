"""Pure advising-student helpers shared by the solver, validator and API (no database)."""
from collections import Counter

def personal_sessions(student, activities, catalogue_groups):
    """(activity ids, catalogue course ids) a student attends.

    activities: [{'id','course_id','group_ids'}]; catalogue_groups: {course_id: [group ids]}."""
    drops = {c['course_id'] for c in student['changes'] if c['action'] == 'drop'}
    adds = {(c['course_id'], c['group_id']) for c in student['changes'] if c['action'] == 'add'}
    home = student.get('group_id')
    sessions = {a['id'] for a in activities if home in a['group_ids'] and a.get('course_id') not in drops}
    sessions |= {a['id'] for a in activities for course, group in adds if a.get('course_id') == course and group in a['group_ids']}
    courses = {a.get('course_id') for a in activities if a['id'] in sessions and a.get('course_id')}
    courses |= {c for c, groups in catalogue_groups.items() if home in groups and c not in drops}
    courses |= {course for course, _ in adds}
    return sorted(sessions), sorted(courses)


def snapshot_students(rows):
    """Compact form stored in a teaching snapshot."""
    return [{'id': r['id'], 'code': r['code'], 'group_id': r['group_id'], 'activity_ids': r['activity_ids']} for r in rows]


def extra_seats(snapshot):
    """Students sitting in an activity outside their home group, per activity (for room sizes)."""
    groups = {r['id']: set(r.get('group_ids', [])) for r in snapshot['records'] if r['kind'] == 'courses'}
    return Counter(a for s in snapshot.get('students', []) for a in s['activity_ids'] if s.get('group_id') not in groups.get(a, set()))


def conflict_sets(snapshot):
    """Distinct personal session sets that a single group's own no-overlap rule does not already cover."""
    groups = {r['id']: set(r.get('group_ids', [])) for r in snapshot['records'] if r['kind'] == 'courses'}
    seen = {}
    for s in snapshot.get('students', []):
        ids = frozenset(a for a in s['activity_ids'] if a in groups)
        if len(ids) < 2 or set.intersection(*(groups[a] for a in ids)):
            continue
        seen.setdefault(ids, s['code'])
    return seen
