"""Conservative input checks. Passing is not a proof of global feasibility."""
from collections import defaultdict

VERSION = 'manual-input-checks-v1'
from app import rule_semantics as rs
from app.calendar_slots import day_placements
SUPPORTED = set(rs.TYPES)


def inspect_inputs(snapshot):
    records={r['id']:r for r in snapshot['records']}; cal=snapshot['calendar']
    activities=[r for r in records.values() if r['kind']=='courses']
    rooms=[r for r in records.values() if r['kind']=='rooms']
    approved=[r for r in snapshot['rules'] if r['status']=='approved']
    locks=[r for r in snapshot.get('assignment_locks',[]) if r['status']=='approved']
    blockers=[];warnings=[];domains=[]; placements={}; load=defaultdict(int)
    def issue(code,message,activity=None,rule_ids=None,resource_id=None):
        blockers.append(dict(code=code,message=message,activity_id=activity,rule_ids=rule_ids or [],resource_id=resource_id))
    if not activities:issue('missing_activities','Add at least one teaching activity.')
    if not rooms:issue('missing_rooms','Add at least one room.')
    for rule in approved:
        if rule['type'] not in SUPPORTED:issue('unsupported_rule','An approved rule is unsupported.',rule_ids=[rule['id']])
    for teacher in records.values():
        if not cal.get('weekly_load_policy',{}).get('allow_overtime') and teacher['kind']=='instructors' and teacher.get('max_weekly_hours') is None:
            warnings.append(dict(code='weekly_limit_missing',resource_id=teacher['id'],message='Weekly teaching maximum is not configured; it will not be checked.'))
    for teacher in records.values():
        if teacher['kind']=='instructors' and not teacher.get('position') and any(teacher['id'] in a['eligible_instructors'] for a in activities):
            warnings.append(dict(code='instructor_position_missing',resource_id=teacher['id'],message='Set doctor or TA for this instructor; until then the lecture/tutorial split is not checked.'))
    for room in rooms:
        if not room.get('capacity') or not (room.get('room_types') or room.get('room_type')):
            warnings.append(dict(code='room_setup_missing',resource_id=room['id'],message='Room capacity/type is not configured; this room is excluded from generation.'))
    policy=cal.get('realism_policy',{})
    for key in ('student_daily_hours','instructor_daily_hours'):
        if policy.get(key) is None:warnings.append(dict(code=key+'_missing',message='This optional daily maximum is not configured.'))
    for activity in activities:
        ident=activity['id'];duration=activity['duration']; groups=activity['group_ids']
        if any(records.get(g,{}).get('kind')!='groups' for g in groups) or any(records.get(t,{}).get('kind')!='instructors' for t in activity['eligible_instructors']):
            issue('invalid_reference','An activity references a missing group or instructor.',ident);continue
        from app.positions import position_conflict
        wrong=[t for t in activity['eligible_instructors'] if position_conflict(activity['activity_type'],records[t])]
        if wrong:issue('instructor_position','Lectures need doctors; tutorials and labs need TAs.',ident,resource_id=wrong[0])
        size=sum(records[g]['size'] for g in groups)
        suitable=[r for r in rooms if (r.get('capacity') or 0)>=size and bool(set(r.get('room_types') or [r.get('room_type')]) & {'flexible','lab' if activity['activity_type']=='lab' else 'lecture'}) and set(activity.get('required_equipment',[]))<=set(r.get('equipment',[]))]
        for rule in approved:
            if rule['type']=='activity_room' and rule['activity_id']==ident:suitable=[r for r in suitable if r['id'] in rs.param(rule,'room_ids')]
        if not suitable:issue('no_suitable_room','No room matches this activity’s capacity, type, special-room features and room rules.',ident)
        slots=[(d,s,e) for d in cal['days'] for s,e,_ in day_placements(cal,duration)]
        window_sets=[[r for r in approved if r['type']=='activity_allowed' and r.get('activity_id')==ident]]+[[r for r in approved if r['type']=='group_allowed' and r.get('group_id')==g] for g in groups]
        overlaps=rs.overlaps
        usable=[]
        for d,s,e in slots:
            if not all(rs.within_windows(w,d,s,e) for w in window_sets):continue
            if any(r['type']=='group_unavailable' and r.get('group_id') in groups and overlaps(r,d,s,e) for r in approved):continue
            teachers=[t for t in activity['eligible_instructors'] if records[t].get('day_off') != d and (cal.get('weekly_load_policy',{}).get('allow_overtime') or records[t].get('max_weekly_hours') is None or records[t]['max_weekly_hours']*60>=duration*activity['sessions']) and not any(r['type']=='unavailable' and r.get('instructor_id')==t and overlaps(r,d,s,e) for r in approved)]
            available=[r['id'] for r in suitable if not any(rule['type']=='room_unavailable' and rule.get('room_id')==r['id'] and overlaps(rule,d,s,e) for rule in approved)]
            if teachers and available:usable.append((d,s,e,teachers,available))
        related=[r['id'] for r in approved if r.get('activity_id')==ident or ident in (rs.param(r,'activity_ids') or []) or r.get('group_id') in groups or r.get('instructor_id') in activity['eligible_instructors'] or r.get('room_id') in [room['id'] for room in suitable]]
        domains.append(dict(activity_id=ident,available_slots=len(usable),required_sessions=activity['sessions']))
        if not usable:issue('no_available_placement','No teaching slot survives this activity’s approved windows, closures, instructor eligibility and workload limits.',ident,related)
        elif len(usable)<activity['sessions']:
            issue('insufficient_slots','Fewer distinct teaching slots than required occurrences.',ident,related)
        elif policy.get('spread_activity_days') and len({p[0] for p in usable})<activity['sessions']:
            issue('insufficient_distinct_days','Separate-day policy requires more available days than this activity has.',ident,related)
        for occurrence in range(activity['sessions']):
            selected=[lock for lock in locks if lock['activity_id']==ident and lock['occurrence']==occurrence]
            # Teacher locks on any occurrence constrain the entire activity.
            teacher_locks=[lock for lock in locks if lock['activity_id']==ident and lock.get('instructor_id')]
            possible=[p for p in usable if all((not lock.get('day') or (p[0],p[1])==(lock['day'],lock['start_minute'])) and (not lock.get('room_id') or lock['room_id'] in p[4]) for lock in selected) and all(lock['instructor_id'] in p[3] for lock in teacher_locks)]
            placements[(ident,occurrence)]=possible
            if selected and not possible:issue('lock_contradiction','An approved lock cannot fit the current calendar, resources or approved rules.',ident,[lock['id'] for lock in selected]+related)
        for g in groups:load[g]+=duration*activity['sessions']
    day_minutes=sum(p['end']-p['start'] for p in cal.get('teaching_periods',[])) or (cal['end_hour']-cal['start_hour'])*60
    for g,minutes in load.items():
        cap=policy.get('student_daily_hours');available=len(cal['days'])*min(day_minutes,day_minutes if cap is None else cap*60)
        if minutes>available:issue('group_weekly_capacity','Required group teaching minutes exceed the week’s teaching capacity.',resource_id=g)
    from app.calendar_slots import end_for
    lock_end=lambda lock,activity:end_for(cal,activity['duration'],lock['start_minute']) or lock['start_minute']+activity['duration']
    fixed=[]
    for lock in locks:
        activity=records.get(lock['activity_id'])
        if not activity or lock['occurrence']>=activity.get('sessions',0):issue('invalid_lock','A lock references a missing occurrence.',lock['activity_id'],[lock['id']]);continue
        if lock.get('day'):
            resources={('group',g) for g in activity['group_ids']}
            if lock.get('room_id'):resources.add(('room',lock['room_id']))
            teacher_ids={l['instructor_id'] for l in locks if l['activity_id']==activity['id'] and l.get('instructor_id')}
            if len(teacher_ids)>1:issue('lock_teacher_conflict','Approved locks require different instructors for the same activity.',activity['id'],[lock['id']])
            resources|={('instructor',t) for t in teacher_ids}
            for other,other_end,other_resources in fixed:
                if (other['activity_id'],other['occurrence'])!=(lock['activity_id'],lock['occurrence']) and other['day']==lock['day'] and lock['start_minute']<other_end and other['start_minute']<lock_end(lock,activity) and resources&other_resources:
                    issue('locked_resource_collision','Two fixed sessions overlap for the same resource.',activity['id'],[other['id'],lock['id']])
            fixed.append((lock,lock_end(lock,activity),resources))
    return dict(version=VERSION,input_version=snapshot.get('input_version'),ready=not blockers,blockers=blockers,warnings=warnings,activity_domains=domains,
                definition='Necessary local checks only; passing does not prove global feasibility. Missing optional limits are warnings. Named teaching breaks do not count as teaching capacity.')
