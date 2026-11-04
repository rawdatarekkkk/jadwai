"""Independent observed daily workload and teaching-period gap calculations."""
from collections import defaultdict, Counter


def check_realism(snapshot, assignments):
    calendar=snapshot['calendar'];policy=calendar.get('realism_policy',{})
    if not policy or not any(v is not None and v is not False for v in policy.values()):return None,set()
    records={r['id']:r for r in snapshot['records']}
    periods=calendar.get('teaching_periods',[])
    if not periods:return None,{'invalid_realism_policy'}
    daily=defaultdict(list);activity_days=Counter();errors=set()
    for row in assignments:
        activity=records.get(row['activity_id'])
        if not activity or activity['kind']!='courses':continue
        position=next((i for i,p in enumerate(periods) if (p['start'],p['end'])==(row['start_minute'],row['end_minute'])),None)
        if position is None:continue  # main calendar validation reports the defect
        activity_days[(activity['id'],row['day'])]+=1
        resources=[('instructor',row['instructor_id'])]+[('group',g) for g in activity['group_ids']]
        for key in resources:daily[(*key,row['day'])].append((position,row['end_minute']-row['start_minute']))
    if policy.get('spread_activity_days') and any(n>1 for n in activity_days.values()):errors.add('activity_day_distribution')
    rows=[]
    for (kind,ident,day),sessions in sorted(daily.items()):
        positions=sorted(set(p for p,_ in sessions))
        minutes=sum(m for _,m in sessions)
        gaps=(positions[-1]-positions[0]+1-len(positions)) if positions else 0
        longest=run=0;previous=-2
        for p in positions:
            run=run+1 if p==previous+1 else 1
            longest=max(longest,run);previous=p
        cap=policy.get('student_daily_hours' if kind=='group' else 'instructor_daily_hours')
        if cap is not None and minutes>round(cap*60):errors.add('group_daily_load' if kind=='group' else 'instructor_daily_load')
        if policy.get('max_consecutive_periods') is not None and longest>policy['max_consecutive_periods']:errors.add('consecutive_periods')
        if policy.get('max_idle_periods') is not None and gaps>policy['max_idle_periods']:errors.add('idle_periods')
        rows.append({'kind':kind,'id':ident,'day':day,'teaching_hours':minutes/60,'idle_periods':gaps,'max_consecutive_periods':longest,'daily_limit_hours':cap})
    return {'policy':policy,'daily_resources':rows,'idle_periods':sum(r['idle_periods'] for r in rows),
            'definition':'Idle periods are unoccupied teaching periods between the first and last session; fixed breaks are excluded. Consecutive periods are adjacent teaching periods.'},errors
