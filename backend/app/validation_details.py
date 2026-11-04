"""Independent observed violations and coverage; no solver/model imports."""
from collections import Counter


def details(snapshot, rows, report):
    records={r.get('id','legacy-rule'):r for r in snapshot['records']}; rules=[r for r in snapshot['rules'] if r['status']=='approved']
    violations=[]; cal=snapshot['calendar']; activities=[r for r in records.values() if r['kind']=='courses']
    def add(code, sessions=(), resource_ids=(), rule_ids=(), message=''):
        violations.append(dict(code=code,message=message or code.replace('_',' '),sessions=[{k:a.get(k) for k in ('activity_id','occurrence','instructor_id','room_id','day','start_minute','end_minute')} for a in sessions],resource_ids=list(resource_ids),rule_ids=list(rule_ids)))
    counts=Counter((a['activity_id'],a['occurrence']) for a in rows)
    for activity in activities:
        for n in range(activity['sessions']):
            count=counts[(activity['id'],n)]
            if count!=1:add('complete_assignment',[{'activity_id':activity['id'],'occurrence':n}],message=f'Expected one assignment; found {count}.')
    for n,a in enumerate(rows):
        activity=records.get(a['activity_id'],{})
        if activity.get('kind')!='courses':add('complete_assignment',[a]);continue
        groups=activity['group_ids'];start,end,day=a['start_minute'],a['end_minute'],a['day']
        teacher=a['instructor_id'];room=records.get(a['room_id'],{})
        if records.get(teacher,{}).get('day_off') == day:add('instructor_day_off',[a],[teacher],message='Session falls on the instructor’s day off.')
        if a['occurrence'] not in range(activity['sessions']):add('complete_assignment',[a])
        if teacher not in activity['eligible_instructors'] or records.get(teacher,{}).get('kind')!='instructors':add('instructor_eligibility',[a],[teacher])
        if any(b['activity_id']==a['activity_id'] and b['instructor_id']!=teacher for b in rows[:n]):add('instructor_continuity',[a],[teacher])
        periods=cal.get('teaching_periods',[])
        valid=any((p['start'],p['end'])==(start,end) for p in periods) if periods else (start-cal['start_hour']*60)%cal['period_minutes']==0
        if day not in cal['days'] or start<cal['start_hour']*60 or end>cal['end_hour']*60 or end-start!=activity['duration'] or not valid:add('calendar',[a])
        size=sum(records.get(g,{}).get('size',10**9) for g in groups)
        if room.get('kind')!='rooms' or (room.get('capacity') or 0)<size or not set(room.get('room_types') or [room.get('room_type')]) & {'flexible','lab' if activity['activity_type']=='lab' else 'lecture'} or not set(activity.get('required_equipment',[]))<=set(room.get('equipment',[])):add('room_suitability',[a],[a['room_id']])
        for b in rows[:n]:
            if b['day']!=day or start>=b['end_minute'] or b['start_minute']>=end:continue
            other=records.get(b['activity_id'],{})
            shared=set(groups)&set(other.get('group_ids',[]))
            if teacher==b['instructor_id']:shared.add(teacher)
            if a['room_id']==b['room_id']:shared.add(a['room_id'])
            if shared:add('resource_conflicts',[b,a],sorted(shared))
        for r in rules:
            if r['day']!=day or not (start<r['end_hour']*60 and r['start_hour']*60<end):continue
            key={'unavailable':('instructor_id',[teacher],'approved_unavailability'),'room_unavailable':('room_id',[a['room_id']],'approved_room_unavailability'),'group_unavailable':('group_id',groups,'approved_group_unavailability')}.get(r['type'])
            if key and r.get(key[0]) in key[1]:add(key[2],[a],[r[key[0]]],[r.get('id','legacy-rule')])
        for typ,field,ident in [('activity_allowed','activity_id',activity['id'])]+[('group_allowed','group_id',g) for g in groups]:
            windows=[r for r in rules if r['type']==typ and r.get(field)==ident]
            if windows and not any(r['day']==day and r['start_hour']*60<=start and end<=r['end_hour']*60 for r in windows):add('approved_allowed_windows',[a],[ident],[r.get('id','legacy-rule') for r in windows])
    for w in report.get('workload') or []:
        if w['exceeded']:add('weekly_workload',[a for a in rows if a['instructor_id']==w['instructor_id']],[w['instructor_id']])
    realism=report.get('realism') or {};policy=realism.get('policy',{})
    for day in realism.get('daily_resources',[]):
        sessions=[a for a in rows if a['day']==day['day'] and (a['instructor_id']==day['id'] if day['kind']=='instructor' else day['id'] in records.get(a['activity_id'],{}).get('group_ids',[]))]
        if day['daily_limit_hours'] is not None and day['teaching_hours']>day['daily_limit_hours']:add('instructor_daily_load' if day['kind']=='instructor' else 'group_daily_load',sessions,[day['id']])
        if policy.get('max_consecutive_periods') is not None and day['max_consecutive_periods']>policy['max_consecutive_periods']:add('consecutive_periods',sessions,[day['id']])
        if policy.get('max_idle_periods') is not None and day['idle_periods']>policy['max_idle_periods']:add('idle_periods',sessions,[day['id']])
    if policy.get('spread_activity_days'):
        for activity in activities:
            for d in cal['days']:
                same=[a for a in rows if a['activity_id']==activity['id'] and a['day']==d]
                if len(same)>1:add('activity_day_distribution',same)
    for lock in report.get('assignment_locks') or []:
        if not lock['passed']:add('assignment_lock',[a for a in rows if a['activity_id']==lock['activity_id'] and a['occurrence']==lock['occurrence']],rule_ids=[lock['lock_id']])
    for code in report['errors']:
        if not any(v['code']==code for v in violations):add(code,message='Validation failed; see saved input and check coverage.')
    aliases={'configured_weekly_workload':{'weekly_workload','invalid_workload_limit'},'approved_assignment_locks':{'assignment_lock'},'configured_daily_load':{'instructor_daily_load','group_daily_load'},'configured_consecutive_periods':{'consecutive_periods'},'configured_idle_periods':{'idle_periods'}}
    coverage=[]
    for check in report['checks']:
        applicable=len(rows);basis='assigned sessions'
        if check=='complete_assignment':applicable=sum(a['sessions'] for a in activities);basis='required occurrences'
        elif check=='instructor_day_off':applicable=sum(bool(r.get('day_off')) for r in records.values() if r['kind']=='instructors');basis='instructors with a configured day off'
        elif check=='instructor_position':applicable=sum(bool(records.get(a['instructor_id'],{}).get('position')) for a in rows);basis='sessions taught by an instructor classified as doctor or TA'
        elif check=='resource_conflicts':applicable=len(rows)*(len(rows)-1)//2;basis='assignment pairs; exact room/instructor/group IDs, half-open time intervals'
        elif check=='configured_weekly_workload':applicable=sum(w['configured'] for w in report.get('workload') or []);basis='instructors with 12-hour standard load and extra-time accounting' if cal.get('weekly_load_policy',{}).get('allow_overtime') else 'instructors with configured weekly maxima'
        elif check=='approved_assignment_locks':applicable=len(report.get('assignment_locks') or []);basis='approved locks'
        elif check in ('approved_unavailability','approved_room_unavailability','approved_group_unavailability','approved_allowed_windows'):
            types={'approved_unavailability':{'unavailable'},'approved_room_unavailability':{'room_unavailable'},'approved_group_unavailability':{'group_unavailable'},'approved_allowed_windows':{'activity_allowed','group_allowed'}}[check]
            applicable=sum(r['type'] in types for r in rules);basis='approved rules'
        elif check.startswith('configured_') or check=='activity_day_distribution':applicable=len(realism.get('daily_resources',[])) if check!='activity_day_distribution' else len(activities);basis='observed resource-days' if check!='activity_day_distribution' else 'activities'
        failure=bool(set(report['errors'])&aliases.get(check,{check}))
        coverage.append(dict(check=check,required=True,applicable=applicable,basis=basis,status='failed' if failure else 'passed' if applicable else 'not_applicable'))
    for limitation in report['limitations']:
        if limitation in ('weekly_workload_limits_missing','daily_limits_not_configured'):coverage.append(dict(check=limitation,required=False,applicable=None,basis='unconfigured policy',status='not_configured'))
    return dict(violations=violations,coverage=coverage,conflict_basis='Exact group IDs represent disjoint cohorts. Any shared instructor, room or group is a conflict when half-open intervals overlap; adjacency and fixed breaks are allowed.')


def preference_penalty(snapshot, rows):
    """Recalculate one penalty per session outside its instructor's union of windows."""
    count=0;observed=[]
    for a in rows:
        windows=[r for r in snapshot['rules'] if r['status']=='approved' and r['type']=='preferred_period' and r.get('instructor_id')==a['instructor_id']]
        if not windows:continue
        satisfied=any(r['day']==a['day'] and r['start_hour']*60<=a['start_minute'] and a['end_minute']<=r['end_hour']*60 for r in windows)
        count+=not satisfied
        observed.append(dict(activity_id=a['activity_id'],occurrence=a['occurrence'],rule_ids=[r.get('id','legacy-rule') for r in windows],penalty=0 if satisfied else 1))
    return dict(definition='one-per-session-outside-instructor-window-union-v1',total=count,sessions=observed)
