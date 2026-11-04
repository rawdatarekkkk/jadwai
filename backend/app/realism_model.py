"""Solver-only policy encoding. The validator uses separate calculations."""
from collections import defaultdict
from ortools.sat.python import cp_model


def add_realism(model, calendar, choices, policy):
    periods=calendar['teaching_periods']
    occupied=defaultdict(list)
    activity_days=defaultdict(list)
    # One exact-start indicator is reused for every attending group and eligible teacher.
    for number,(activity,occurrence,start,teachers,rooms) in enumerate(choices):
        day_flags=[]
        for di,day in enumerate(calendar['days']):
            slots=[]
            for pi,period in enumerate(periods):
                if period['end']-period['start']!=activity['duration']:
                    continue
                present=model.new_bool_var(f'present_{number}_{di}_{pi}')
                model.add(start==di*1440+period['start']).only_enforce_if(present)
                model.add(start!=di*1440+period['start']).only_enforce_if(present.Not())
                slots.append(present)
                for group in activity['group_ids']:
                    occupied[('group',group,di,pi)].append(present)
                for teacher,selected in teachers.items():
                    teaches=model.new_bool_var(f'teaches_{number}_{teacher}_{di}_{pi}')
                    model.add(teaches<=present);model.add(teaches<=selected)
                    model.add(teaches>=present+selected-1)
                    occupied[('instructor',teacher,di,pi)].append(teaches)
            on_day=model.new_bool_var(f'day_{number}_{di}')
            model.add(on_day==sum(slots))
            day_flags.append(on_day)
        activity_days[activity['id']].append(day_flags)
    if policy.get('spread_activity_days'):
        for activity, flags_by_occurrence in activity_days.items():
            for di in range(len(calendar['days'])):
                model.add(sum(flags[di] for flags in flags_by_occurrence)<=1)
    keys={(kind,ident,di) for kind,ident,di,pi in occupied}
    gaps=[]
    for kind,ident,di in sorted(keys):
        used=[]
        for pi in range(len(periods)):
            values=occupied.get((kind,ident,di,pi),[])
            flag=model.new_bool_var(f'occupied_{kind}_{ident}_{di}_{pi}')
            if values:model.add_max_equality(flag,values)
            else:model.add(flag==0)
            used.append(flag)
        cap=policy.get('student_daily_hours' if kind=='group' else 'instructor_daily_hours')
        if cap is not None:
            model.add(sum(flag*(periods[pi]['end']-periods[pi]['start']) for pi,flag in enumerate(used))<=int(cap*60))
        consecutive=policy.get('max_consecutive_periods')
        if consecutive is not None:
            for pi in range(len(used)-consecutive):
                model.add(sum(used[pi:pi+consecutive+1])<=consecutive)
        daily_gaps=[]
        for pi in range(1,len(used)-1):
            before=model.new_bool_var(f'before_{kind}_{ident}_{di}_{pi}')
            after=model.new_bool_var(f'after_{kind}_{ident}_{di}_{pi}')
            model.add_max_equality(before,used[:pi]);model.add_max_equality(after,used[pi+1:])
            gap=model.new_bool_var(f'gap_{kind}_{ident}_{di}_{pi}')
            model.add(gap<=before);model.add(gap<=after);model.add(gap<=1-used[pi])
            model.add(gap>=before+after-used[pi]-1)
            daily_gaps.append(gap)
        if policy.get('max_idle_periods') is not None:
            model.add(sum(daily_gaps)<=policy['max_idle_periods'])
        gaps.extend(daily_gaps)
    return gaps if policy.get('compact_days') else []
