"""Bounded CP-SAT interval scheduling from frozen JSON-safe input snapshots.

Factoring time, room and instructor decisions avoids a Boolean variable for
 every time × room × teacher combination. Resource conflicts use NoOverlap.
Times are absolute minutes from the start of the teaching week (day index × 1440).
"""
from collections import defaultdict
import hashlib
from ortools.sat.python import cp_model

from app.provenance import CONFIG
from app.calendar_slots import day_placements
from app import rule_semantics as rs

MAX_SESSIONS = 600
MAX_CANDIDATES = 3000000


def check_rules(snapshot, by_id, cal):
    """Reason the approved rules cannot be used, or None."""
    for rule in rs.approved(snapshot, *rs.TYPES):
        field, kind = rs.TARGETS[rule['type']]
        if field and by_id.get(rule.get(field), {}).get('kind') != kind:
            return 'invalid_rule'
        if rule['type'] in rs.TIME_TYPES and rule.get('day') is not None and rule['day'] not in cal['days']:
            return 'invalid_rule'
        for key, ref_kind in (('room_ids', 'rooms'), ('activity_ids', 'courses')):
            if any(by_id.get(v, {}).get('kind') != ref_kind for v in rs.param(rule, key) or []):
                return 'invalid_rule'
    if any(r['status'] == 'approved' and r['type'] not in rs.TYPES for r in snapshot['rules']):
        return 'unsupported_rule'
    return None


def check_locks(locks, by_id, cal):
    for lock in locks:
        activity=by_id.get(lock.get('activity_id'))
        if not activity or activity['kind']!='courses' or type(lock.get('occurrence')) is not int or not 0<=lock['occurrence']<activity['sessions'] or not any(lock.get(k) is not None for k in ('instructor_id','room_id','day')):
            return False
        if lock.get('instructor_id') is not None and lock['instructor_id'] not in activity['eligible_instructors']:
            return False
        if lock.get('room_id') is not None and by_id.get(lock['room_id'],{}).get('kind')!='rooms':
            return False
        if (lock.get('day') is None)!=(lock.get('start_minute') is None) or (lock.get('day') is not None and (lock['day'] not in cal['days'] or type(lock['start_minute']) is not int)):
            return False
    return True


def room_pools(rooms, snapshot, locks, enabled=True):
    """room id -> sorted ids of rooms it is interchangeable with (pools of 2+ only).

    Rooms are interchangeable when capacity, types and features match and no rule or
    lock names them; the solver then only counts how many of a pool are busy."""
    if not enabled:
        return {}
    named = {lock.get('room_id') for lock in locks}
    named |= {r['room_id'] for r in rs.approved(snapshot, 'room_unavailable')}
    named |= {room for r in rs.approved(snapshot, 'activity_room') for room in rs.param(r, 'room_ids')}
    classes = defaultdict(list)
    for r in rooms:
        if r['id'] not in named:
            classes[(r.get('capacity'), tuple(sorted(r.get('room_types') or [r.get('room_type') or ''])), tuple(sorted(r.get('equipment') or [])))].append(r['id'])
    return {ident: sorted(members) for members in classes.values() if len(members) > 1 for ident in members}


def assign_pool_rooms(sessions, members):
    """Give each pooled session a concrete room. Sessions are intervals and at most
    len(members) overlap at any time, so earliest-start-first assignment always succeeds."""
    free_at = {room: -1 for room in members}
    for start, end, row in sorted(sessions, key=lambda x: (x[0], x[1])):
        room = min((r for r in members if free_at[r] <= start), key=lambda r: (free_at[r], r))
        free_at[room] = end
        row['room_id'] = room


def generate(snapshot, cancel=None, on_solver=None, time_limit=None, *, fixed_assignments=None, hints=None):
    config = snapshot.get("provenance", {}).get("solver_config", CONFIG)
    if time_limit is None: time_limit = config["time_limit_seconds"]
    profile = config.get('objective_profile', 'convenience-v1')
    if profile == 'convenience-v1' and fixed_assignments is None and hints is None:
        # The convenience model is much larger. Find a valid timetable with the plain
        # model first and start the convenience search from it.
        # The warm start skips daily policies (their occupancy model is the expensive
        # part); the main search enforces them, repairing the hint where needed.
        quick = {**snapshot, 'calendar': {**snapshot['calendar'], 'realism_policy': {}},
                 'provenance': {**snapshot.get('provenance', {}), 'solver_config': {**config, 'objective_profile': 'preferences-first-v1'}}}
        budget = time_limit * 0.5
        started = __import__('time').monotonic()
        # Register the warm-start solver too, so Cancel can stop it; its progress
        # figures use another scoring scale, so they are not reported.
        register = (lambda solver: on_solver(solver) and None) if on_solver else None
        first = generate(quick, cancel, register, budget)
        if cancel and cancel.is_set():
            return {'status':'cancelled','assignments':[]}
        if first['status'] != 'completed':
            return first
        remaining = max(0.5, time_limit - (__import__('time').monotonic() - started)) if time_limit else 0
        result = generate(snapshot, cancel, on_solver, remaining, hints=first['assignments'])
        if result.get('solver_diagnostics'):
            result['solver_diagnostics'].update(requested_time_limit_seconds=time_limit, warm_start={
                'profile': 'preferences-first-v1', 'raw_status': first['solver_diagnostics']['raw_status'], 'solver_seconds': first['solver_diagnostics']['solver_seconds']})
        return result
    from app.schemas import RealismPolicy
    try:
        policy=RealismPolicy.model_validate(snapshot['calendar'].get('realism_policy',{}))
    except ValueError:
        return {'status':'blocked','reason':'invalid_realism_policy','assignments':[]}
    active_policy=policy != RealismPolicy()
    if active_policy and not snapshot['calendar'].get('teaching_periods'):
        return {'status':'blocked','reason':'invalid_realism_policy','assignments':[]}
    model = cp_model.CpModel()
    records = snapshot['records']
    by_id = {r['id']: r for r in records}
    activities = [r for r in records if r['kind']=='courses']
    rooms = [r for r in records if r['kind']=='rooms']
    cal = snapshot['calendar']
    days = cal['days']
    if not activities or not rooms:
        return {'status':'blocked','reason':'missing_data','assignments':[]}
    if sum(a['sessions'] for a in activities)>MAX_SESSIONS:
        return {'status':'blocked','reason':'instance_too_large','assignments':[]}
    reason = check_rules(snapshot, by_id, cal)
    if reason:
        return {'status':'blocked','reason':reason,'assignments':[]}
    locks=[lock for lock in snapshot.get('assignment_locks',[]) if lock.get('status')=='approved']
    if not check_locks(locks, by_id, cal):
        return {'status':'blocked','reason':'invalid_lock','assignments':[]}
    for record in records:
        if not cal.get("weekly_load_policy", {}).get("allow_overtime") and record["kind"] == "instructors" and record.get("max_weekly_hours") is not None:
            hours = record["max_weekly_hours"]
            if type(hours) not in (int, float) or not 0 <= hours <= 168 or hours * 2 != int(hours * 2):
                return {"status":"blocked", "reason":"invalid_workload_limit", "assignments":[]}
    from app.positions import position_conflict, tas_without_teaching
    if any(position_conflict(a['activity_type'], by_id.get(t)) for a in activities for t in a['eligible_instructors']):
        return {'status':'blocked','reason':'instructor_position','assignments':[]}
    tas = [r for r in records if r['kind'] == 'instructors' and r.get('position') == 'ta']
    if tas_without_teaching(tas, activities):
        return {'status':'blocked','reason':'ta_without_teaching','assignments':[]}
    rules_of = lambda *types: rs.approved(snapshot, *types)
    room_limits = {r['activity_id']: set(rs.param(r, 'room_ids')) for r in rules_of('activity_room')}
    pool_of = room_pools(rooms, snapshot, locks, enabled=fixed_assignments is None)
    resources = defaultdict(list)
    from app.advising_rules import conflict_sets, extra_seats
    # Advising students: none of a student's own sessions may overlap.
    personal = defaultdict(list)
    for n, ids in enumerate(conflict_sets(snapshot)):
        for a in ids:
            personal[a].append(n)
    seats = extra_seats(snapshot)
    workload_terms = defaultdict(list)
    day_of = {}  # (activity id, occurrence) -> per-day Booleans
    choices, penalties = [], []
    count = 0
    for activity in activities:
        if cancel and cancel.is_set():
            return {'status':'cancelled','assignments':[]}
        size = sum(by_id[g]['size'] for g in activity['group_ids']) + seats[activity['id']]
        room_type = 'lab' if activity['activity_type']=='lab' else 'lecture'
        suitable = [r for r in rooms if (r.get('capacity') or 0)>=size and bool(set(r.get('room_types') or [r.get('room_type')]) & {room_type,'flexible'}) and set(activity.get('required_equipment',[]))<=set(r.get('equipment',[]))]
        for allowed_rooms in [room_limits[activity['id']]] if activity['id'] in room_limits else []:
            suitable = [r for r in suitable if r['id'] in allowed_rooms]
        if not suitable:
            return {'status':'infeasible','reason':'no_suitable_room','activity_id':activity['id'],'assignments':[]}
        duration = activity['duration']
        ends = {di*1440+s: di*1440+e for di in range(len(days)) for s, e, _ in day_placements(cal, duration)}
        local = lambda s: (days[s//1440], s%1440, ends[s]-(s//1440)*1440)
        # Windows for one target form a weekly union. Each activity/group target
        # is a separate mandatory restriction, so targets intersect.
        window_sets = [[r for r in rules_of('activity_allowed') if r.get('activity_id')==activity['id']]]
        window_sets += [[r for r in rules_of('group_allowed') if r.get('group_id')==g] for g in activity['group_ids']]
        group_blocks = [r for r in rules_of('group_unavailable') if r['group_id'] in activity['group_ids']]
        starts = [s for s in ends if all(rs.within_windows(w, *local(s)) for w in window_sets) and not any(rs.overlaps(r, *local(s)) for r in group_blocks)]
        if not starts:return {'status':'infeasible','reason':'no_available_placement','activity_id':activity['id'],'assignments':[]}
        allowed, preferred = {}, {}
        for teacher in activity['eligible_instructors']:
            mine = [r for r in snapshot['rules'] if r['status']=='approved' and r.get('instructor_id')==teacher]
            mandatory = [r for r in mine if r['type']=='unavailable']
            windows = [r for r in mine if r['type']=='preferred_period']
            allowed[teacher] = [s for s in starts if local(s)[0] != by_id[teacher].get('day_off') and not any(rs.overlaps(r, *local(s)) for r in mandatory)]
            if windows:
                preferred[teacher] = [s for s in starts if rs.within_windows(windows, *local(s))]
        if not any(allowed.values()):
            return {'status':'infeasible','reason':'no_available_placement','activity_id':activity['id'],'assignments':[]}
        count += sum(len(values) for values in allowed.values())*len(suitable)*activity['sessions']
        if count>MAX_CANDIDATES:
            return {'status':'blocked','reason':'instance_too_large','assignments':[]}
        teachers = {t:model.new_bool_var(f'teacher_{activity["id"]}_{t}') for t in allowed}
        model.add_exactly_one(teachers.values())
        for ident, selected in teachers.items():
            workload_terms[ident].append(selected * activity["duration"] * activity["sessions"])
        # Ordering occurrences by start breaks symmetry, but a time lock names an
        # occurrence number, so ordering could reject valid locked timetables.
        time_locked = any(lock['activity_id']==activity['id'] and lock.get('day') is not None for lock in locks)
        lengths = {ends[s]-s for s in starts}
        previous = None
        for occurrence in range(activity['sessions']):
            if cancel and cancel.is_set():
                return {'status':'cancelled','assignments':[]}
            prefix = f'{activity["id"]}_{occurrence}'
            start = model.new_int_var_from_domain(cp_model.Domain.from_values(starts),'start_'+prefix)
            end = model.new_int_var_from_domain(cp_model.Domain.from_values(sorted({ends[s] for s in starts})),'end_'+prefix)
            if len(lengths) == 1:
                length = next(iter(lengths))
                model.add(end == start + length)
            else:
                # Sessions spanning a break are longer in elapsed time than in teaching time.
                length = model.new_int_var_from_domain(cp_model.Domain.from_values(sorted(lengths)), 'length_'+prefix)
                model.add(length == end - start)
                model.add_allowed_assignments([start, end], [(s, ends[s]) for s in starts])
            interval = model.new_interval_var(start,length,end,'session_'+prefix)
            if previous is not None and not time_locked:
                model.add(previous<start)
            previous = start
            flags = []
            for di in range(len(days)):
                todays = [s for s in starts if s//1440 == di]
                flag = model.new_bool_var(f'on_{prefix}_{di}')
                if todays:
                    model.add_linear_expression_in_domain(start, cp_model.Domain.from_values(todays)).only_enforce_if(flag)
                else:
                    model.add(flag == 0)
                flags.append(flag)
            model.add_exactly_one(flags)
            day_of[(activity['id'], occurrence)] = flags
            for group in activity['group_ids']:
                resources[('group',group)].append(interval)
            for n in personal[activity['id']]:
                resources[('student',n)].append(interval)
            for teacher,selected in teachers.items():
                if not allowed[teacher]:
                    model.add(selected==0)
                else:
                    model.add_linear_expression_in_domain(start,cp_model.Domain.from_values(allowed[teacher])).only_enforce_if(selected)
                resources[('teacher',teacher)].append(model.new_optional_interval_var(start,length,end,selected,'teacher_session_'+prefix+'_'+teacher))
                if teacher in preferred:
                    fits = model.new_bool_var('preferred_'+prefix+'_'+teacher)
                    if preferred[teacher]:
                        domain = cp_model.Domain.from_values(preferred[teacher])
                        model.add_linear_expression_in_domain(start,domain).only_enforce_if(fits)
                        model.add_linear_expression_in_domain(start,domain.complement()).only_enforce_if(fits.Not())
                    else:
                        model.add(fits==0)
                    penalty = model.new_bool_var('penalty_'+prefix+'_'+teacher)
                    model.add(penalty>=selected-fits)
                    model.add(penalty<=selected)
                    model.add(penalty<=1-fits)
                    penalties.append(penalty)
            room_vars = {}
            for room in suitable:
                pool = pool_of.get(room['id'])
                if pool:
                    # Interchangeable rooms: one choice per pool, capacity checked below.
                    if pool[0] not in room_vars:
                        selected = model.new_bool_var('pool_'+prefix+'_'+pool[0])
                        room_vars[pool[0]] = selected
                        resources[('pool', pool[0])].append(model.new_optional_interval_var(start,length,end,selected,'pool_session_'+prefix+'_'+pool[0]))
                    continue
                selected = model.new_bool_var('room_'+prefix+'_'+room['id'])
                room_vars[room['id']] = selected
                blocks = [r for r in rules_of('room_unavailable') if r['room_id'] == room['id']]
                if blocks:
                    allowed_starts = [s for s in starts if not any(rs.overlaps(r, *local(s)) for r in blocks)]
                    if allowed_starts:
                        model.add_linear_expression_in_domain(start, cp_model.Domain.from_values(allowed_starts)).only_enforce_if(selected)
                    else:
                        model.add(selected == 0)
                resources[('room',room['id'])].append(model.new_optional_interval_var(start,length,end,selected,'room_session_'+prefix+'_'+room['id']))
            model.add_exactly_one(room_vars.values())
            for lock in locks:
                if lock['activity_id']!=activity['id'] or lock['occurrence']!=occurrence:continue
                if lock.get('instructor_id') is not None:model.add(teachers[lock['instructor_id']]==1)
                if lock.get('room_id') is not None:
                    if lock['room_id'] in room_vars:model.add(room_vars[lock['room_id']]==1)
                    else:model.add(False)
                if lock.get('day') is not None:model.add(start==days.index(lock['day'])*1440+lock['start_minute'])
            choices.append((activity,occurrence,start,teachers,room_vars,{s: ends[s] for s in starts}))
            hint = (hints or {}) and next((h for h in hints if (h['activity_id'], h['occurrence']) == (activity['id'], occurrence)), None)
            if hint:
                model.add_hint(start, days.index(hint['day'])*1440+hint['start_minute'])
                # The instructor choice is shared by every occurrence; hint it once.
                if occurrence == 0:
                    for ident, var in teachers.items(): model.add_hint(var, int(ident == hint['instructor_id']))
                hinted = (pool_of.get(hint['room_id']) or [hint['room_id']])[0]
                for ident, var in room_vars.items(): model.add_hint(var, int(ident == hinted))
    # Test-only differential hook: constrain every decision by equality, never hints.
    # No HTTP endpoint accepts this argument.
    if fixed_assignments is not None:
        fixed={(r['activity_id'],r['occurrence']):r for r in fixed_assignments}
        expected={(a['id'],o) for a,o,*_ in choices}
        if len(fixed)!=len(fixed_assignments) or set(fixed)!=expected:
            raise ValueError('Fixed assignments must cover every occurrence exactly once')
        for activity,occurrence,start,teachers,room_vars,ends in choices:
            row=fixed[activity['id'],occurrence]
            absolute = days.index(row['day'])*1440+row['start_minute'] if row.get('day') in days and type(row.get('start_minute')) is int else None
            if absolute not in ends or row.get('instructor_id') not in teachers or row.get('room_id') not in room_vars or row.get('end_minute')!=ends[absolute]-(absolute//1440)*1440:
                model.add(False)
                continue
            model.add(start==absolute)
            for ident,var in teachers.items():model.add(var==int(ident==row['instructor_id']))
            for ident,var in room_vars.items():model.add(var==int(ident==row['room_id']))
    pool_sizes = {pool[0]: len(pool) for pool in pool_of.values()}
    for key, intervals in resources.items():
        if key[0] == 'pool':
            if len(intervals) > pool_sizes[key[1]]:
                model.add_cumulative(intervals, [1] * len(intervals), pool_sizes[key[1]])
        elif len(intervals)>1:
            model.add_no_overlap(intervals)
    for record in records:
        if not cal.get("weekly_load_policy", {}).get("allow_overtime") and record["kind"] == "instructors" and record.get("max_weekly_hours") is not None:
            model.add(sum(workload_terms[record["id"]]) <= int(record["max_weekly_hours"] * 60))
    # Every TA teaches: each must be selected for at least one activity.
    for ta in tas:
        model.add(sum(workload_terms[ta['id']]) >= 1)
    add_limit_rules(model, snapshot, choices, day_of, len(days))
    components = {'preferences': penalties}
    if active_policy or profile == 'convenience-v1':
        from app.realism_model import add_realism
        components.update(add_realism(model, cal, choices, policy.model_dump(), convenience=profile == 'convenience-v1'))
    if profile == 'convenience-v1':
        components['workload_balance'] = workload_balance(model, workload_terms)
    from app.objective import weights as profile_weights, effective
    weights, scored = profile_weights(snapshot, config), effective(snapshot, config)
    model.minimize(sum(weight * sum(components.get(name, [])) for name, weight in scored.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config["search_workers"]
    solver.parameters.random_seed = config["random_seed"]
    progress_handler = on_solver(solver) if on_solver else None
    class Progress(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            progress_handler({'best_objective':self.objective_value,'best_bound':self.best_objective_bound,'solver_seconds':self.wall_time})
    status = solver.solve(model, Progress() if callable(progress_handler) else None)
    solved = status in (cp_model.OPTIMAL,cp_model.FEASIBLE)
    definition = {'convenience-v1': 'convenience-v1', 'weighted-v1': 'weighted-preferences-idle-v1'}.get(profile, 'preferences-then-idle-periods-v1' if active_policy else 'preferred-periods-v1')
    diagnostics = {'raw_status': solver.status_name(status), 'ortools_version': __import__('ortools').__version__,
                   'parameters_text': str(solver.parameters), 'solver_seconds': solver.wall_time,
                   'objective_definition': definition,
                   'objective_weights': weights,
                   'model_sha256':hashlib.sha256(str(model.proto).encode('utf-8')).hexdigest(),
                   'model_validation_error':model.validate(),
                   'objective_value':solver.objective_value if solved else None,
                   'best_objective_bound':solver.best_objective_bound if solved else None}
    if cancel and cancel.is_set():
        return {'status':'cancelled','assignments':[],'solver_diagnostics':diagnostics}
    if solved:
        assignments = []
        pooled = defaultdict(list)
        for activity,occurrence,start,teachers,room_vars,ends in choices:
            minute = solver.value(start)
            base = (minute//1440)*1440
            chosen = next(r for r,v in room_vars.items() if solver.value(v))
            row = {'activity_id':activity['id'],'occurrence':occurrence,'instructor_id':next(t for t,v in teachers.items() if solver.value(v)),'room_id':chosen,'day':days[minute//1440],'start_minute':minute-base,'end_minute':ends[minute]-base}
            if chosen in pool_sizes:
                pooled[chosen].append((minute, ends[minute], row))
            assignments.append(row)
        for key, sessions in pooled.items():
            assign_pool_rooms(sessions, next(pool for pool in pool_of.values() if pool[0] == key))
        observed = {name: int(sum(solver.value(v) for v in components.get(name, []))) for name in weights if scored[name]}
        # Score the returned solution itself: CP-SAT's reported value can sit slightly
        # above it when presolve leaves slack on objective variables.
        diagnostics.update(solver_reported_objective=diagnostics['objective_value'],
                           objective_value=sum(scored[name] * value for name, value in observed.items()))
        return {'status':'completed','solver_diagnostics':{**diagnostics,'objective_components':observed},'assignments':assignments,'preference_penalty':int(sum(solver.value(v) for v in penalties)),'idle_period_penalty':observed.get('idle_periods') if policy.compact_days and profile != 'convenience-v1' else None,'objective_components':observed,'objective_definition':definition,'optimal':status==cp_model.OPTIMAL,'solver_seconds':round(solver.wall_time,3)}
    return {'solver_diagnostics':diagnostics,'status':'infeasible' if status==cp_model.INFEASIBLE else 'unknown' if status==cp_model.UNKNOWN else 'failed','reason':'conflicting_requirements' if status==cp_model.INFEASIBLE else 'search_limit' if status==cp_model.UNKNOWN else 'model_invalid' if status==cp_model.MODEL_INVALID else 'solver_error','assignments':[]}


def workload_balance(model, workload_terms):
    """Stepped cost of each instructor's weekly teaching minutes (see objective.py)."""
    from app.objective import WORKLOAD_STEPS, WORKLOAD_UNIT
    costs = []
    for teacher, terms in workload_terms.items():
        load = model.new_int_var(0, 10080 * 7, f'load_{teacher}')
        model.add(load == sum(terms))
        for threshold, cost in WORKLOAD_STEPS:
            above = model.new_int_var(0, 10080 * 7, f'above_{teacher}_{threshold}')
            model.add_max_equality(above, [load - threshold, 0])
            units = model.new_int_var(0, 10080 * 7, f'units_{teacher}_{threshold}')
            model.add_division_equality(units, above, WORKLOAD_UNIT)
            costs.append(cost * units)
    return costs


def add_limit_rules(model, snapshot, choices, day_of, day_count):
    """Daily-hour, teaching-day and same-day limits from approved limit rules."""
    def teaching_on(teacher, di):
        """(minutes, Boolean) per occurrence that `teacher` may teach on day di."""
        terms = []
        for activity, occurrence, _, teachers, _, _ in choices:
            if teacher in teachers:
                both = model.new_bool_var(f'teach_{teacher}_{activity["id"]}_{occurrence}_{di}')
                model.add_multiplication_equality(both, [teachers[teacher], day_of[(activity['id'], occurrence)][di]])
                terms.append((activity['duration'], both))
        return terms
    for rule in rs.approved(snapshot, 'instructor_max_daily_hours'):
        for di in range(day_count):
            model.add(sum(m * b for m, b in teaching_on(rule['instructor_id'], di)) <= round(rs.param(rule, 'hours') * 60))
    for rule in rs.approved(snapshot, 'group_max_daily_hours'):
        for di in range(day_count):
            model.add(sum(a['duration'] * day_of[(a['id'], o)][di] for a, o, *_ in choices if rule['group_id'] in a['group_ids']) <= round(rs.param(rule, 'hours') * 60))
    for rule in rs.approved(snapshot, 'instructor_max_days'):
        working = []
        for di in range(day_count):
            works = model.new_bool_var(f'works_{rule["id"]}_{di}')
            terms = [b for _, b in teaching_on(rule['instructor_id'], di)]
            if terms:
                model.add_max_equality(works, terms)
            else:
                model.add(works == 0)
            working.append(works)
        model.add(sum(working) <= rs.param(rule, 'days'))
    for rule in rs.approved(snapshot, 'activities_not_same_day'):
        for di in range(day_count):
            present = []
            for ident in rs.param(rule, 'activity_ids'):
                flag = model.new_bool_var(f'meets_{rule["id"]}_{ident}_{di}')
                model.add_max_equality(flag, [day_of[(a['id'], o)][di] for a, o, *_ in choices if a['id'] == ident])
                present.append(flag)
            model.add(sum(present) <= 1)
