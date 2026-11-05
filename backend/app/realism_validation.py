"""Independent observed daily workload, slot gaps and convenience components."""
from collections import defaultdict, Counter
from app.calendar_slots import day_slots, slots_in


def occupancy(snapshot, assignments):
    """(kind, id, day) -> set of occupied slot indices, recomputed from assignments."""
    calendar = snapshot['calendar']
    records = {r['id']: r for r in snapshot['records']}
    used = defaultdict(set)
    for row in assignments:
        activity = records.get(row['activity_id'])
        if not activity or activity['kind'] != 'courses':
            continue
        covered = slots_in(calendar, row['start_minute'], row['end_minute'])
        for key in [('instructor', row['instructor_id'])] + [('group', g) for g in activity['group_ids']]:
            used[(*key, row['day'])].update(covered)
    return used


def gaps(slots):
    positions = sorted(slots)
    return positions[-1] - positions[0] + 1 - len(positions) if positions else 0


def convenience_components(snapshot, assignments):
    """Every convenience-v1 component except preferences (see objective.py)."""
    count = len(day_slots(snapshot['calendar']))
    used = occupancy(snapshot, assignments)
    peaks = defaultdict(int)
    for (kind, ident, _), slots in used.items():
        if kind == 'group':
            peaks[ident] = max(peaks[ident], len(slots))
    edge = 0
    for row in assignments:
        covered = slots_in(snapshot['calendar'], row['start_minute'], row['end_minute'])
        edge += bool(covered) and (covered[0] == 0 or covered[-1] == count - 1)
    from app.objective import LONG_DAY_MINUTES, WORKLOAD_STEPS, WORKLOAD_UNIT
    records = {r['id']: r for r in snapshot['records']}
    taught = Counter()
    for row in assignments:
        taught[row['instructor_id']] += records[row['activity_id']]['duration']
    slots = day_slots(snapshot['calendar'])
    per_day = Counter((row['activity_id'], row['day']) for row in assignments)
    return {
        'repeat_same_day': sum(n - 1 for n in per_day.values()),
        'workload_balance': sum(cost * (max(0, minutes - threshold) // WORKLOAD_UNIT) for minutes in taught.values() for threshold, cost in WORKLOAD_STEPS),
        'long_day_minutes': sum(max(0, sum(slots[i][1] - slots[i][0] for i in s) - LONG_DAY_MINUTES) for (k, _, _), s in used.items() if k == 'group'),
        'student_gaps': sum(gaps(s) for (k, _, _), s in used.items() if k == 'group'),
        'instructor_gaps': sum(gaps(s) for (k, _, _), s in used.items() if k == 'instructor'),
        'instructor_days': sum(1 for (k, _, _), s in used.items() if k == 'instructor' and s),
        'student_days': sum(1 for (k, _, _), s in used.items() if k == 'group' and s),
        'group_peak': sum(peaks.values()),
        'edge_sessions': edge,
    }


def check_realism(snapshot, assignments):
    calendar=snapshot['calendar'];policy=calendar.get('realism_policy',{})
    if not policy or not any(v is not None and v is not False for v in policy.values()):return None,set()
    if not calendar.get('teaching_periods'):return None,{'invalid_realism_policy'}
    slots=day_slots(calendar);records={r['id']:r for r in snapshot['records']}
    errors=set();activity_days=Counter()
    for row in assignments:
        if records.get(row['activity_id'],{}).get('kind')=='courses':activity_days[(row['activity_id'],row['day'])]+=1
    if policy.get('spread_activity_days') and any(n>1 for n in activity_days.values()):errors.add('activity_day_distribution')
    rows=[]
    for (kind,ident,day),occupied in sorted(occupancy(snapshot,assignments).items()):
        positions=sorted(occupied)
        minutes=sum(slots[i][1]-slots[i][0] for i in positions)
        longest=run=0;previous=-2
        for p in positions:
            run=run+1 if p==previous+1 else 1
            longest=max(longest,run);previous=p
        cap=policy.get('student_daily_hours' if kind=='group' else 'instructor_daily_hours')
        idle=gaps(occupied)
        if cap is not None and minutes>round(cap*60):errors.add('group_daily_load' if kind=='group' else 'instructor_daily_load')
        if policy.get('max_consecutive_periods') is not None and longest>policy['max_consecutive_periods']:errors.add('consecutive_periods')
        if policy.get('max_idle_periods') is not None and idle>policy['max_idle_periods']:errors.add('idle_periods')
        rows.append({'kind':kind,'id':ident,'day':day,'teaching_hours':minutes/60,'idle_periods':idle,'max_consecutive_periods':longest,'daily_limit_hours':cap})
    return {'policy':policy,'daily_resources':rows,'idle_periods':sum(r['idle_periods'] for r in rows),
            'definition':'Idle periods are unoccupied teaching periods between the first and last session; fixed breaks are excluded. Consecutive periods are adjacent teaching periods.'},errors
