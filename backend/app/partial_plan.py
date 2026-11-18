"""Building one timetable in parts (for example one faculty or programme at a time).

A part run's snapshot carries a `plan`:
    {"scope": [{"programme": name, "year": n | None, "group": id (optional)}, ...], "base_run_id": id | None,
     "activity_ids": [activities this run places],
     "fixed": [assignments carried over unchanged from the base run]}

The solver places `activity_ids` around the fixed sessions, which keep their day, time,
instructor and room (a fixed session may only move to an identical room of the same
interchangeable pool). The result holds both, so every hard check runs on the combined
timetable. Activities outside the plan are simply not scheduled yet. A run is complete,
and can be published, once it covers every activity. No DB access here.
"""


def plan_of(snapshot):
    return snapshot.get('plan')


def covered(snapshot):
    """Ids of the activities this run must schedule, or None for all of them."""
    plan = plan_of(snapshot)
    if not plan:
        return None
    return set(plan['activity_ids']) | {row['activity_id'] for row in plan['fixed']}


def in_scope(snapshot, activities):
    """The activities a run schedules, from all activity records."""
    ids = covered(snapshot)
    return [a for a in activities if ids is None or a['id'] in ids]


def tas_that_must_teach(snapshot, records):
    """TAs that this run must give teaching.

    Whole timetable: every TA. A part: each TA not yet teaching in the fixed sessions
    whom the activities left for later parts could not all still cover (a matching,
    one TA per activity), so no part strands a TA with nothing left to teach."""
    from app.positions import tas_without_teaching, unassigned_tas
    records = list(records)
    courses = [r for r in records if r['kind'] == 'courses']
    waiting = {r['id'] for r in unassigned_tas([r for r in records if r['kind'] == 'instructors'], courses)}
    tas = [r for r in records if r['kind'] == 'instructors' and r.get('position') == 'ta' and r['id'] not in waiting]
    ids = covered(snapshot)
    if ids is None:
        return tas
    teaching = {row['instructor_id'] for row in plan_of(snapshot)['fixed']}
    idle = [ta for ta in tas if ta['id'] not in teaching]
    later = [r for r in records if r['kind'] == 'courses' and r['id'] not in ids]
    stranded = set(tas_without_teaching(idle, later))
    return [ta for ta in idle if ta['id'] in stranded]


def complete(snapshot):
    ids = covered(snapshot)
    return ids is None or ids >= {r['id'] for r in snapshot['records'] if r['kind'] == 'courses'}



def matches(group, scope):
    """Whether a group belongs to a scope item (a programme, one year of it, or one group)."""
    return any(group.get('major') == s['programme'] and s.get('year') in (None, group.get('year'))
               and s.get('group') in (None, group.get('id')) for s in scope)


def scope_activities(records, scope, done, rules=()):
    """Activities with at least one group in `scope`, minus those already scheduled."""
    groups = {r['id'] for r in records if r['kind'] == 'groups' and matches(r, scope)}
    selected = {r['id'] for r in records if r['kind'] == 'courses' and r['id'] not in done and groups & set(r['group_ids'])}
    if any(rule['status'] == 'approved' and rule['type'] == 'lecture_before_tutorial' for rule in rules):
        from app.rule_semantics import lecture_tutorial_pairs
        selected |= {lecture for lecture, tutorial in lecture_tutorial_pairs(records) if tutorial in selected and lecture not in done}
    return sorted(selected)


def progress(snapshot):
    """Sessions scheduled so far versus the whole timetable."""
    activities = [r for r in snapshot['records'] if r['kind'] == 'courses']
    ids = covered(snapshot)
    total = sum(a['sessions'] for a in activities)
    done = total if ids is None else sum(a['sessions'] for a in activities if a['id'] in ids)
    groups = {r['id']: r for r in snapshot['records'] if r['kind'] == 'groups'}
    left = {(groups[g].get('major') or '', groups[g].get('year') or 0) for a in activities if ids is not None and a['id'] not in ids for g in a['group_ids'] if g in groups}
    remaining = [{'programme': p, 'year': y or None} for p, y in sorted(left)]
    return {'scheduled_sessions': done, 'total_sessions': total, 'complete': done == total and (ids is None or complete(snapshot)),
            'remaining_programmes': remaining}
