"""Versioned schedule statistics, computed from the exact saved input snapshot."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
import json
from app import rule_semantics as rs


def percentage(numerator, denominator):
    return round(100*numerator/denominator,2) if denominator else None


def scope_groups(snapshot, scope):
    """Group ids a report is limited to, or None for the whole timetable.

    scope: {'group': id} or {'year': '3' | 'unassigned', 'major': name | '__unassigned'},
    the same choices as the Timetable page filters."""
    if not scope:
        return None
    groups=[r for r in snapshot['records'] if r['kind']=='groups']
    if scope.get('group'):
        return {g['id'] for g in groups if g['id']==scope['group']}
    year, major = scope.get('year'), scope.get('major')
    return {g['id'] for g in groups
            if (not year or (str(g['year']) if g.get('year') else 'unassigned')==year)
            and (not major or (g.get('major') or '__unassigned')==major)}


def scope_label(snapshot, scope):
    if not scope:
        return None
    records={r['id']:r for r in snapshot['records']}
    if scope.get('group'):
        g=records[scope['group']]
        return ' / '.join(x for x in [f"Year {g['year']}" if g.get('year') else '', g.get('major') or '', g.get('name') or g.get('code') or ''] if x)
    return ' / '.join(x for x in [('Unassigned year' if scope.get('year')=='unassigned' else f"Year {scope['year']}") if scope.get('year') else '',
                                  ('Unassigned major' if scope.get('major')=='__unassigned' else scope.get('major') or '')] if x)


def build_statistics(snapshot, result, scope=None):
    records={r['id']:r for r in snapshot['records']}
    activities={k:r for k,r in records.items() if r['kind']=='courses'}
    chosen=scope_groups(snapshot, scope)
    all_assignments=result.get('assignments',[])
    if chosen is not None:
        # A group or programme report: the sessions those groups attend.
        activities={k:r for k,r in activities.items() if chosen & set(r['group_ids'])}
    rooms={k:r for k,r in records.items() if r['kind']=='rooms' and r.get('capacity') and (r.get('room_types') or r.get('room_type'))}
    instructors={k:r for k,r in records.items() if r['kind']=='instructors'}
    groups={k:r for k,r in records.items() if r['kind']=='groups'}
    assignments=[a for a in all_assignments if a['activity_id'] in activities]
    completed=result.get('status')=='completed' and result.get('validation',{}).get('passed',False)
    expected=sum(a['sessions'] for a in activities.values())
    cal=snapshot['calendar']
    day_minutes=sum(p['end']-p['start'] for p in cal.get('teaching_periods',[])) if cal.get('teaching_periods') else (cal['end_hour']-cal['start_hour'])*60
    weekly_minutes=day_minutes*len(cal['days'])
    duration=sum(activities[a['activity_id']]['duration'] for a in assignments)
    room_minutes=Counter(); teacher_minutes=Counter(); group_minutes=Counter(); daily=Counter()
    used_seat_minutes=0; available_seat_minutes=0
    # Who actually attends: group members, minus advising students who dropped the course,
    # plus advising students joining from other groups.
    students=snapshot.get('students',[])
    attending={ident:sum(groups[g]['size'] for g in act['group_ids'])
               -sum(1 for st in students if st.get('group_id') in act['group_ids'] and ident not in st['activity_ids'])
               +sum(1 for st in students if st.get('group_id') not in act['group_ids'] and ident in st['activity_ids'])
               for ident,act in activities.items()}
    for a in assignments:
        activity=activities[a['activity_id']]; minutes=activity['duration']
        room_minutes[a['room_id']]+=minutes;teacher_minutes[a['instructor_id']]+=minutes;daily[a['day']]+=1
        for g in activity['group_ids']:group_minutes[g]+=minutes
        used_seat_minutes+=attending[a['activity_id']]*minutes
        available_seat_minutes+=rooms[a['room_id']]['capacity']*minutes
    conflicts={'room_overlap_pairs':0,'instructor_overlap_pairs':0,'group_overlap_pairs':0}
    for i,a in enumerate(assignments):
        for b in assignments[i+1:]:
            if a['day']!=b['day'] or a['start_minute']>=b['end_minute'] or b['start_minute']>=a['end_minute']:continue
            conflicts['room_overlap_pairs']+=int(a['room_id']==b['room_id'])
            conflicts['instructor_overlap_pairs']+=int(a['instructor_id']==b['instructor_id'])
            conflicts['group_overlap_pairs']+=int(bool(set(activities[a['activity_id']]['group_ids']) & set(activities[b['activity_id']]['group_ids'])))
    preferences=[r for r in snapshot['rules'] if r['status']=='approved' and r['type']=='preferred_period']
    if chosen is not None:
        preferences=[r for r in preferences if r['instructor_id'] in teacher_minutes]
        instructors={k:r for k,r in instructors.items() if k in teacher_minutes}
    per_rule=[]
    for rule in preferences:
        relevant=[a for a in assignments if a['instructor_id']==rule['instructor_id']]
        satisfied=sum(rs.covers(rule,a['day'],a['start_minute'],a['end_minute']) for a in relevant)
        per_rule.append({'id':rule['id'],'title':rule['title'],'instructor':records[rule['instructor_id']]['name'],'applicable_sessions':len(relevant),'satisfied_sessions':satisfied,'unsatisfied_sessions':len(relevant)-satisfied,'satisfaction_percent':percentage(satisfied,len(relevant)),'status':'not_applicable' if not relevant else 'fully_satisfied' if satisfied==len(relevant) else 'partially_satisfied' if satisfied else 'unsatisfied'})
    applicable=0; preferred_satisfied=0
    for a in assignments:
        windows=[r for r in preferences if r['instructor_id']==a['instructor_id']]
        if not windows:continue
        applicable+=1
        preferred_satisfied+=int(rs.within_windows(windows,a['day'],a['start_minute'],a['end_minute']))
    return {'provenance':result.get('provenance'), 'solver_diagnostics':result.get('solver_diagnostics'), 'report_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'status':result.get('status'),'input_version':snapshot['input_version'],
        'input_summary':{'activities':len(activities),'instructors':len(instructors),'rooms':len(rooms),'student_groups':len(groups),'approved_rules':len(snapshot['rules']),'approved_unavailability_rules':sum(r['type'] in ('unavailable','room_unavailable','group_unavailable') for r in snapshot['rules']),'approved_preference_rules':len(preferences)},
        'coverage':{'expected_sessions':expected,'scheduled_sessions':len(assignments),'unscheduled_sessions':expected-len(assignments),'assignment_percent':percentage(len(assignments),expected)},
        'validation':{'coverage':result.get('validation',{}).get('coverage'),'violations':result.get('validation',{}).get('violations'),'conflict_basis':result.get('validation',{}).get('conflict_basis'),'preference_evaluation':result.get('validation',{}).get('preference_evaluation'),'passed':result.get('validation',{}).get('passed',False),'checks':result.get('validation',{}).get('checks',[]),'workload':result.get('validation',{}).get('workload'),'realism':result.get('validation',{}).get('realism'),'assignment_locks':result.get('validation',{}).get('assignment_locks'),'errors':result.get('validation',{}).get('errors',[]),'conflicts':conflicts if completed else None,'publication_ready':False},
        'preferences':{'approved_rules':len(preferences),'fully_satisfied_rules':sum(r['status']=='fully_satisfied' for r in per_rule),'partially_satisfied_rules':sum(r['status']=='partially_satisfied' for r in per_rule),'unsatisfied_rules':sum(r['status']=='unsatisfied' for r in per_rule),'not_applicable_rules':sum(r['status']=='not_applicable' for r in per_rule),'applicable_sessions':applicable,'satisfied_sessions':preferred_satisfied,'unsatisfied_sessions':applicable-preferred_satisfied,'satisfaction_percent':percentage(preferred_satisfied,applicable),'per_rule':per_rule},
        'utilization':{'scheduled_teaching_minutes':duration,'available_teaching_minutes_per_room':weekly_minutes,'room_time_percent':percentage(duration,len(rooms)*weekly_minutes) if completed else None,'occupied_room_seat_percent':percentage(used_seat_minutes,available_seat_minutes) if completed else None,'group_week_percent':percentage(sum(group_minutes[g] for g in (chosen if chosen is not None else groups)),len(chosen if chosen is not None else groups)*weekly_minutes) if completed else None,'rooms_used':len(room_minutes),'rooms_total':len(rooms),'instructors_used':len(teacher_minutes),'instructors_total':len(instructors),'groups_used':len(set(group_minutes)&(chosen if chosen is not None else set(groups))),'groups_total':len(chosen if chosen is not None else groups)},
        'scope':{'label':scope_label(snapshot,scope),**(scope or {})} if scope else None,
        'convenience':convenience(snapshot,assignments) if completed and chosen is None else None,
        'week':week_quality(snapshot,all_assignments,assignments,chosen if chosen is not None else set(groups)) if completed else None,
        'advising':advising(snapshot,all_assignments,chosen),  # their sessions may be with other groups
        'per_day':[{'day':d,'sessions':daily[d]} for d in cal['days']],
        'per_room':[{'id':ident,'name':r['name'],'code':r['code'],'teaching_minutes':room_minutes[ident],'time_utilization_percent':percentage(room_minutes[ident],weekly_minutes) if completed else None} for ident,r in rooms.items()],
        'per_instructor':[{'id':ident,'name':r['name'],'code':r['code'],'teaching_minutes':teacher_minutes[ident], 'teaching_hours':teacher_minutes[ident]/60, 'standard_weekly_hours':12 if snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') else None, 'extra_hours':max(0,teacher_minutes[ident]/60-12) if snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') else None, 'max_weekly_hours':None if snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') else r.get('max_weekly_hours'), 'weekly_limit_configured':not snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') and r.get('max_weekly_hours') is not None, 'weekly_limit_exceeded':not snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') and r.get('max_weekly_hours') is not None and teacher_minutes[ident] > r['max_weekly_hours']*60} for ident,r in instructors.items()],
        'per_group':[{'id':ident,'name':r['name'],'code':r['code'],'year':r.get('year'),'major':r.get('major'),'teaching_minutes':group_minutes[ident]} for ident,r in groups.items() if chosen is None or ident in chosen],
        'solver':{'seconds':result.get('solver_seconds'),'optimal_for_supported_objective':result.get('optimal'),'preference_penalty':result.get('preference_penalty'),'idle_period_penalty':result.get('idle_period_penalty'),'objective_definition':result.get('objective_definition')},
        'definitions':{'room_time_percent':'Scheduled session minutes / (configured saved rooms × available weekly teaching minutes). Breaks in named periods are excluded. Low usage is not proof of poor timetable quality.','occupied_room_seat_percent':'Attending students × session minutes / assigned-room capacity × session minutes; unused room periods excluded. Attending students are the groups\' sizes, minus advising students who dropped the course, plus advising students joining it.','convenience':'Recomputed from the assignments; lower is better. Gaps are free teaching periods between sessions on one day; days count each person-day with teaching; edge sessions use the first or last period of the day.','preference_satisfaction':'Each assigned session with approved preferred windows for its instructor is counted once; satisfied if it fits entirely within at least one window. Per-rule counts separately evaluate each window.','conflicts':'Counts overlapping assignment pairs independently for shared room, instructor and any student group. A pair can appear in several categories; categories must not be added as a unique-conflict count.'},
        'limitations':['Draft only; not publication-ready.',('Standard weekly load is 12 teaching hours; hours above 12 are extra time and do not invalidate a schedule.' if snapshot['calendar'].get('weekly_load_policy',{}).get('allow_overtime') else 'Weekly workload limits: configured instructor maxima are checked. Unconfigured maxima are not covered; daily policy and approved assignment-lock coverage are reported separately.'),'Teaching load uses elapsed teaching hours: one 90-minute session is 1.5 hours, counted once per instructor, not once per attending group. Breaks are excluded.','No overall efficiency/fairness score or educational improvement is claimed.']}


def html_report(run_id, snapshot, stats, stale):
    e=lambda value:escape(str(value))
    def table(rows):
        if not rows:return '<p>None recorded.</p>'
        # Leave out columns with no value in any row (for example limits that are not configured).
        keys=[k for k in rows[0] if any(row.get(k) is not None for row in rows)]
        return '<table><thead><tr>'+''.join('<th>'+e(k.replace('_',' ').title())+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e('-' if row.get(k) is None else row[k])+'</td>' for k in keys)+'</tr>' for row in rows)+'</tbody></table>'
    def pairs(values):return table([{'metric':k.replace('_',' ').title(),'value':v} for k,v in values.items() if v is not None])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JadwAI schedule statistics</title><style>body{font:15px/1.55 system-ui,sans-serif;color:#284737;background:#faf9f3;max-width:1100px;margin:40px auto;padding:0 24px}h1{font-family:Georgia,serif;font-size:38px}h2{margin-top:36px}table{width:100%;border-collapse:collapse;background:white;font-size:13px;overflow-wrap:anywhere}th,td{padding:10px;text-align:left;border:1px solid #d7dfcf}th{background:#eaf0e2}.warning{padding:15px;background:#fff0d5}small{color:#63725f}@media print{body{margin:0}thead{display:table-header-group}tr{break-inside:avoid}}</style><h1>JadwAI · Schedule statistics</h1><p>'+e(snapshot['name'])+' · '+e(snapshot['term'])+' · '+e((stats.get('scope') or {}).get('label') or 'Full schedule')+'</p><p><b>DRAFT — UNPUBLISHED</b> · Status: '+e(stats['status'])+' · Input version '+e(stats['input_version'])+'</p><small>Run '+e(run_id)+' · Report '+e(stats['generated_at'])+' · Timezone '+e(snapshot['calendar']['timezone'])+'</small>'+('<p class="warning">Inputs have changed since this schedule was generated. Statistics describe its saved snapshot.</p>' if stale else '')+'<h2>Saved inputs</h2>'+pairs(stats['input_summary'])+'<h2>Assignment coverage</h2>'+pairs(stats['coverage'])+'<h2>Conflict and validation checks</h2>'+pairs({'supported_validation_passed':stats['validation']['passed'],**(stats['validation']['conflicts'] or {})})+'<p>Checks: '+e(', '.join(stats['validation']['checks']))+'</p>'+(('<h2>Preferences</h2>'+pairs({k:v for k,v in stats['preferences'].items() if k!='per_rule'})+table(stats['preferences']['per_rule'])) if stats['preferences']['applicable_sessions'] else '')+('<h2>Week quality</h2>'+pairs(stats['week']) if stats.get('week') else '')+'<h2>Room and resource usage</h2>'+pairs(stats['utilization'])+'<h2>Daily distribution</h2>'+table(stats['per_day'])+'<h2>Rooms</h2>'+table(stats['per_room'])+'<h2>Instructor teaching time</h2>'+table(stats['per_instructor'])+'<h2>Student-group teaching time</h2>'+table(stats['per_group'])+'<h2>Daily timetable policy</h2>'+ (pairs(stats['validation']['realism']['policy'])+table(stats['validation']['realism']['daily_resources']) if stats['validation'].get('realism') else '<p>Not checked for this saved report.</p>')+'<h2>Solver</h2>'+pairs(stats['solver'])+'<h2>Metric definitions</h2>'+''.join('<p><b>'+e(k)+'</b>: '+e(v)+'</p>' for k,v in stats['definitions'].items())+'<h2>Limitations</h2><ul>'+''.join('<li>'+e(v)+'</li>' for v in stats['limitations'])+'</ul></html>'


def convenience(snapshot, assignments):
    from app.realism_validation import convenience_components
    return convenience_components(snapshot, assignments)


def week_quality(snapshot, all_assignments, assignments, chosen):
    """Student-week figures for the chosen groups, from the saved assignments."""
    from app.realism_validation import occupancy, gaps
    from app.calendar_slots import day_slots, slots_in
    used = {k: v for k, v in occupancy(snapshot, all_assignments).items() if k[0] == 'group' and k[1] in chosen}
    slots = day_slots(snapshot['calendar'])
    hours = [sum(slots[i][1] - slots[i][0] for i in s) / 60 for s in used.values()]
    edge = sum(1 for a in assignments if (lambda c: bool(c) and (c[0] == 0 or c[-1] == len(slots) - 1))(slots_in(snapshot['calendar'], a['start_minute'], a['end_minute'])))
    return {'groups': len(chosen), 'student_gaps': sum(gaps(s) for s in used.values()), 'student_days': len(used),
            'days_per_group': round(len(used) / len(chosen), 1) if chosen else 0, 'longest_day_hours': max(hours, default=0), 'edge_sessions': edge}


def advising(snapshot, assignments, chosen=None):
    """Advising students (those based in the chosen groups) and how many have two of their own sessions overlapping."""
    times = {}
    for a in assignments:
        times.setdefault(a['activity_id'], []).append((a['day'], a['start_minute'], a['end_minute']))
    clashes = 0
    students = [s for s in snapshot.get('students', []) if chosen is None or s.get('group_id') in chosen]
    for student in students:
        mine = sorted(t for ident in student['activity_ids'] for t in times.get(ident, []))
        clashes += any(x[0] == y[0] and y[1] < x[2] for x, y in zip(mine, mine[1:]))
    return {'students': len(students), 'students_with_clashes': clashes}
