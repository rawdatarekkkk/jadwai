"""Conservative input checks. Passing is not a proof of global feasibility."""
from collections import defaultdict

VERSION = 'manual-input-checks-v1'
from app import rule_semantics as rs
from app.calendar_slots import day_placements
SUPPORTED = set(rs.TYPES)
AR = {
    'missing_activities': 'أضف نشاط تدريس واحدًا على الأقل.',
    'missing_rooms': 'أضف قاعة واحدة على الأقل.',
    'unsupported_rule': 'يوجد قيد معتمد غير مدعوم.',
    'invalid_reference': 'نشاط يشير إلى مجموعة أو مدرس غير موجود.',
    'instructor_position': 'المحاضرات للدكاترة؛ السكاشن والمعامل للمعيدين.',
    'no_suitable_room': 'لا توجد قاعة تناسب سعة هذا النشاط ونوعه وتجهيزاته الخاصة وقواعد القاعات.',
    'no_available_placement': 'لا يبقى موعد تدريس لهذا النشاط بعد النوافذ المعتمدة والإغلاقات وأهلية المدرسين وحدود العبء.',
    'insufficient_slots': 'عدد المواعيد المتاحة أقل من عدد الحصص المطلوبة.',
    'insufficient_distinct_days': 'سياسة الأيام المختلفة تحتاج أيامًا متاحة أكثر مما لدى هذا النشاط.',
    'lock_contradiction': 'حصة مثبتة معتمدة لا تتوافق مع التقويم أو الموارد أو القواعد المعتمدة.',
    'group_weekly_capacity': 'دقائق التدريس المطلوبة للمجموعة أكثر مما يتسع له أسبوع التدريس.',
    'invalid_lock': 'حصة مثبتة تشير إلى حصة غير موجودة.',
    'lock_teacher_conflict': 'حصص مثبتة معتمدة تطلب مدرسين مختلفين لنفس النشاط.',
    'locked_resource_collision': 'حصتان مثبتتان تتداخلان على نفس المورد.',
}


def inspect_inputs(snapshot):
    records={r['id']:r for r in snapshot['records']}; cal=snapshot['calendar']
    from app.partial_plan import in_scope
    all_activities=[r for r in records.values() if r['kind']=='courses']
    activities=in_scope(snapshot, all_activities)  # a part run checks only its own activities
    rooms=[r for r in records.values() if r['kind']=='rooms']
    approved=[r for r in snapshot['rules'] if r['status']=='approved']
    locks=[r for r in snapshot.get('assignment_locks',[]) if r['status']=='approved']
    blockers=[];warnings=[];domains=[]; placements={}; load=defaultdict(int)
    def issue(code,message,activity=None,rule_ids=None,resource_id=None,ar=None):
        # Every message is sent in English and Arabic; the page shows the interface language.
        blockers.append(dict(code=code,message=message,message_ar=ar or AR.get(code,message),activity_id=activity,rule_ids=rule_ids or [],resource_id=resource_id))
    if not activities:issue('missing_activities','Add at least one teaching activity.')
    if not rooms:issue('missing_rooms','Add at least one room.')
    for rule in approved:
        if rule['type'] not in SUPPORTED:issue('unsupported_rule','An approved rule is unsupported.',rule_ids=[rule['id']])
    for teacher in records.values():
        if not cal.get('weekly_load_policy',{}).get('allow_overtime') and teacher['kind']=='instructors' and teacher.get('max_weekly_hours') is None:
            warnings.append(dict(code='weekly_limit_missing',resource_id=teacher['id'],message='Weekly teaching maximum is not configured; it will not be checked.',message_ar='لم يُحدد الحد الأسبوعي للتدريس؛ لن يُفحص.'))
    for teacher in records.values():
        if teacher['kind']=='instructors' and not teacher.get('position') and any(teacher['id'] in a['eligible_instructors'] for a in activities):
            warnings.append(dict(code='instructor_position_missing',resource_id=teacher['id'],message='Set doctor or TA for this instructor; until then the lecture/tutorial split is not checked.',message_ar='حدّد دكتور أو معيد لهذا المدرس؛ حتى ذلك لا يُفحص تقسيم المحاضرات والسكاشن.'))
    for room in rooms:
        if not room.get('capacity') or not (room.get('room_types') or room.get('room_type')):
            warnings.append(dict(code='room_setup_missing',resource_id=room['id'],message='Room capacity/type is not configured; this room is excluded from generation.',message_ar='سعة القاعة أو نوعها غير محدد؛ تُستبعد هذه القاعة من الإنشاء.'))
    policy=cal.get('realism_policy',{})
    for key in ('student_daily_hours','instructor_daily_hours'):
        if policy.get(key) is None:warnings.append(dict(code=key+'_missing',message='This optional daily maximum is not configured.',message_ar='هذا الحد اليومي الاختياري غير محدد.'))
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
    from app.positions import tas_without_teaching
    valid=[a for a in all_activities if all(records.get(t,{}).get('kind')=='instructors' for t in a['eligible_instructors'])]
    for ta in tas_without_teaching([r for r in records.values() if r['kind']=='instructors'],valid):
        issue('ta_without_teaching',f"{records[ta]['name']} cannot be given any session. Every TA must teach: add this TA to a course's tutorials or labs, or add more activities to the pool.",resource_id=ta,
              ar=f"لا يمكن إعطاء {records[ta]['name']} أي حصة. يجب أن يدرّس كل معيد: أضفه إلى سكاشن أو معامل مقرر، أو أضف أنشطة أكثر.")
    day_minutes=sum(p['end']-p['start'] for p in cal.get('teaching_periods',[])) or (cal['end_hour']-cal['start_hour'])*60
    overloaded_pools(records, activities, cal, day_minutes, policy, issue)
    room_week(rooms, activities, cal, day_minutes, issue)
    periods=cal.get('teaching_periods') or []
    if periods:
        # Most periods a group can attend in a day: the daily-hours cap, and a free period
        # after every run of max_consecutive_periods (periods taken as equal length).
        length=day_minutes/len(periods); per_day=len(periods)
        if policy.get('max_consecutive_periods'):per_day-=len(periods)//(policy['max_consecutive_periods']+1)
        if policy.get('student_daily_hours') is not None:per_day=min(per_day,int(policy['student_daily_hours']*60//length))
        tight=len(cal['days'])*per_day*length
    for g,minutes in load.items():
        cap=policy.get('student_daily_hours');available=len(cal['days'])*min(day_minutes,day_minutes if cap is None else cap*60)
        if minutes>available:issue('group_weekly_capacity','Required group teaching minutes exceed the week’s teaching capacity.',resource_id=g)
        elif periods and minutes>0.9*tight:
            warnings.append(dict(code='group_week_nearly_full',resource_id=g,message=f"{records[g].get('name',g)} needs {round(minutes/60,1)} of the {round(tight/60,1)} teaching hours its week can hold under the daily limits. Generation may take long or fail; consider fewer sessions or relaxing the daily or consecutive-period limits.",
                message_ar=f"تحتاج {records[g].get('name',g)} إلى {round(minutes/60,1)} من {round(tight/60,1)} ساعة تدريس يتسع لها أسبوعها ضمن الحدود اليومية. قد يطول الإنشاء أو يفشل؛ قلّل الحصص أو خفّف حد الساعات اليومية أو الفترات المتتالية."))
    by_activity={a['id']:a for a in activities}
    for student in snapshot.get('students',[]):
        if not student['activity_ids']:
            warnings.append(dict(code='advising_student_empty',resource_id=student['id'],message=f"Advising student {student['code']} attends no sessions.",message_ar=f"طالب الإرشاد {student['code']} لا يحضر أي حصة."))
        minutes=sum(by_activity[a]['duration']*by_activity[a]['sessions'] for a in student['activity_ids'] if a in by_activity)
        if minutes>len(cal['days'])*day_minutes:issue('advising_student_capacity',f"Advising student {student['code']} has more teaching than the week can hold.",resource_id=student['id'],ar=f"لدى طالب الإرشاد {student['code']} تدريس أكثر مما يتسع له الأسبوع.")
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


def overloaded_pools(records, activities, cal, day_minutes, policy, issue):
    """Activities that only a set of instructors may teach need at most their combined week.

    For each eligibility list, every activity whose instructors all come from that list
    must be taught by them; if those minutes exceed the list's teaching week (days off
    and an instructor daily maximum respected), no timetable exists."""
    cap = policy.get('instructor_daily_hours')
    per_day = day_minutes if cap is None else min(day_minutes, round(cap * 60))
    week = lambda t: per_day * sum(1 for d in cal['days'] if records[t].get('day_off') != d)
    valid = [a for a in activities if a['eligible_instructors'] and all(records.get(t, {}).get('kind') == 'instructors' for t in a['eligible_instructors'])]
    reported = set()
    for pool in sorted({frozenset(a['eligible_instructors']) for a in valid}, key=len):
        mine = [a for a in valid if pool >= set(a['eligible_instructors'])]
        need = sum(a['duration'] * a['sessions'] for a in mine)
        have = sum(week(t) for t in pool)
        if need > have and not reported & {a['id'] for a in mine}:
            reported |= {a['id'] for a in mine}
            names = ', '.join(sorted(records[t].get('name', t) for t in pool))
            codes = ', '.join(sorted({(a.get('code') or a.get('name') or a['id']).split('-A')[0] for a in mine})[:5])
            issue('instructor_pool_overloaded', f"{codes}: {round(need / 60, 1)} weekly hours can only be taught by {names}, who have {round(have / 60, 1)} teaching hours a week between them. Add instructors to these activities or reduce their sessions.",
                  mine[0]['id'], resource_id=sorted(pool)[0],
                  ar=f"{codes}: {round(need / 60, 1)} ساعة أسبوعيًا لا يدرّسها إلا {names}، ومجموع وقتهم {round(have / 60, 1)} ساعة تدريس في الأسبوع. أضف مدرسين لهذه الأنشطة أو قلّل حصصها.")


def room_week(rooms, activities, cal, day_minutes, issue):
    """Weekly teaching minutes needing a lab or a lecture room against what those rooms hold.

    Each session occupies one room for at least its teaching minutes; flexible rooms count
    for both kinds, so the kinds are also checked together."""
    usable = [r for r in rooms if r.get('capacity') and (r.get('room_types') or r.get('room_type'))]
    kinds = lambda r: set(r.get('room_types') or [r.get('room_type')])
    week = len(cal['days']) * day_minutes
    need = {'lab': 0, 'lecture': 0}
    for a in activities:
        need['lab' if a['activity_type'] == 'lab' else 'lecture'] += a['duration'] * a['sessions']
    for kind, label, label_ar in (('lab', 'labs', 'المعامل'), ('lecture', 'lecture and tutorial rooms', 'قاعات المحاضرات والسكاشن')):
        have = week * sum(1 for r in usable if kinds(r) & {kind, 'flexible'})
        if need[kind] > have:
            issue('room_week_capacity', f"Sessions needing {label} take {round(need[kind] / 60)} hours a week, but those rooms hold {round(have / 60)}. Add rooms or reduce sessions.",
                  ar=f"الحصص التي تحتاج {label_ar} تأخذ {round(need[kind] / 60)} ساعة أسبوعيًا، وهذه القاعات تتسع لـ {round(have / 60)} فقط. أضف قاعات أو قلّل الحصص.")
    have = week * sum(1 for r in usable if kinds(r) & {'lab', 'lecture', 'flexible'})
    if need['lab'] + need['lecture'] > have and all(need[k] <= week * sum(1 for r in usable if kinds(r) & {k, 'flexible'}) for k in need):
        issue('room_week_capacity', f"Sessions take {round((need['lab'] + need['lecture']) / 60)} room-hours a week, but the rooms hold {round(have / 60)}. Add rooms or reduce sessions.",
              ar=f"تأخذ الحصص {round((need['lab'] + need['lecture']) / 60)} ساعة قاعة أسبوعيًا، والقاعات تتسع لـ {round(have / 60)} فقط. أضف قاعات أو قلّل الحصص.")
