"""Solver-only slot occupancy model: daily policy limits and convenience terms.

The validator recomputes everything here from assignments in realism_validation.py
and convenience.py; it never reads these variables.
"""
from collections import defaultdict
from app.calendar_slots import day_slots, slots_in
from app.objective import LONG_DAY_MINUTES


def add_realism(model, calendar, choices, policy, convenience=False):
    """Returns component name -> list of non-negative integer expressions to minimise."""
    slots = day_slots(calendar)
    days = range(len(calendar['days']))
    occupied = defaultdict(list)
    activity_days = defaultdict(list)
    edge = []
    # One exact-placement indicator per occurrence and possible start, reused for
    # every attending group and every eligible teacher.
    for number, (activity, occurrence, start, teachers, rooms, ends) in enumerate(choices):
        flags_by_day, everything = [], []
        for di in days:
            present_today = []
            for s, e in sorted(ends.items()):
                if s // 1440 != di:
                    continue
                present = model.new_bool_var(f'present_{number}_{s}')
                model.add(start == s).only_enforce_if(present)
                model.add(start != s).only_enforce_if(present.Not())
                present_today.append(present)
                covered = slots_in(calendar, s - di * 1440, e - di * 1440)
                if convenience and covered and (covered[0] == 0 or covered[-1] == len(slots) - 1):
                    edge.append(present)
                teaching = []
                for teacher, selected in teachers.items():
                    teaches = model.new_bool_var(f'teaches_{number}_{s}_{teacher}')
                    model.add_bool_and([present, selected]).only_enforce_if(teaches)
                    model.add_bool_or([present.Not(), selected.Not()]).only_enforce_if(teaches.Not())
                    teaching.append((teacher, teaches))
                for si in covered:
                    for group in activity['group_ids']:
                        occupied[('group', group, di, si)].append(present)
                    for teacher, teaches in teaching:
                        occupied[('instructor', teacher, di, si)].append(teaches)
            on_day = model.new_bool_var(f'day_{number}_{di}')
            model.add(on_day == sum(present_today))
            flags_by_day.append(on_day)
            everything += present_today
        model.add(sum(everything) == 1)
        activity_days[activity['id']].append(flags_by_day)
    if policy.get('spread_activity_days'):
        for flags_by_occurrence in activity_days.values():
            for di in days:
                model.add(sum(flags[di] for flags in flags_by_occurrence) <= 1)
    resources = {(kind, ident) for kind, ident, _, _ in occupied}
    components = defaultdict(list)
    consecutive = policy.get('max_consecutive_periods')
    want_gaps = convenience or policy.get('compact_days') or policy.get('max_idle_periods') is not None
    for kind, ident in sorted(resources):
        cap = policy.get('student_daily_hours' if kind == 'group' else 'instructor_daily_hours')
        loads = []
        for di in days:
            used = []
            for si in range(len(slots)):
                values = occupied.get((kind, ident, di, si), [])
                flag = model.new_bool_var(f'occupied_{kind}_{ident}_{di}_{si}')
                if values:
                    model.add_max_equality(flag, values)
                else:
                    model.add(flag == 0)
                used.append(flag)
            if cap is not None:
                model.add(sum(flag * (slots[si][1] - slots[si][0]) for si, flag in enumerate(used)) <= int(cap * 60))
            if consecutive is not None:
                for si in range(len(used) - consecutive):
                    model.add(sum(used[si:si + consecutive + 1]) <= consecutive)
            if want_gaps:
                # Running "any session earlier/later today" flags keep this linear in slots.
                earlier, later = [None] * len(used), [None] * len(used)
                for si in range(1, len(used)):
                    earlier[si] = model.new_bool_var(f'before_{kind}_{ident}_{di}_{si}')
                    model.add_max_equality(earlier[si], [used[si - 1]] + ([earlier[si - 1]] if si > 1 else []))
                for si in range(len(used) - 2, -1, -1):
                    later[si] = model.new_bool_var(f'after_{kind}_{ident}_{di}_{si}')
                    model.add_max_equality(later[si], [used[si + 1]] + ([later[si + 1]] if si < len(used) - 2 else []))
                daily_gaps = []
                for si in range(1, len(used) - 1):
                    before, after = earlier[si], later[si]
                    gap = model.new_bool_var(f'gap_{kind}_{ident}_{di}_{si}')
                    model.add(gap <= before)
                    model.add(gap <= after)
                    model.add(gap <= 1 - used[si])
                    model.add(gap >= before + after - used[si] - 1)
                    daily_gaps.append(gap)
                if policy.get('max_idle_periods') is not None:
                    model.add(sum(daily_gaps) <= policy['max_idle_periods'])
                components['student_gaps' if kind == 'group' else 'instructor_gaps'] += daily_gaps
            if convenience and kind == 'instructor':
                works = model.new_bool_var(f'works_{ident}_{di}')
                model.add_max_equality(works, used)
                components['instructor_days'].append(works)
            if convenience and kind == 'group':
                load = model.new_int_var(0, len(slots), f'load_{ident}_{di}')
                model.add(load == sum(used))
                loads.append(load)
                day_minutes = sum(e - s for s, e in slots)
                excess = model.new_int_var(0, day_minutes, f'long_{ident}_{di}')
                model.add_max_equality(excess, [sum(flag * (slots[si][1] - slots[si][0]) for si, flag in enumerate(used)) - LONG_DAY_MINUTES, 0])
                components['long_day_minutes'].append(excess)
                attends = model.new_bool_var(f'attends_{ident}_{di}')
                model.add_max_equality(attends, used)
                components['student_days'].append(attends)
        if loads:
            peak = model.new_int_var(0, len(slots), f'peak_{ident}')
            model.add_max_equality(peak, loads)
            components['group_peak'].append(peak)
    components['edge_sessions'] = edge
    if convenience:
        # Two sessions of one activity on the same day: count every extra one.
        for flags_by_occurrence in activity_days.values():
            if len(flags_by_occurrence) < 2:
                continue
            for di in days:
                any_today = model.new_bool_var('')
                model.add_max_equality(any_today, [flags[di] for flags in flags_by_occurrence])
                components['repeat_same_day'].append(sum(flags[di] for flags in flags_by_occurrence) - any_today)
    components['idle_periods'] = components['student_gaps'] + components['instructor_gaps']
    return dict(components)
