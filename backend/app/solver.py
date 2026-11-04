"""Bounded CP-SAT interval scheduling from frozen JSON-safe input snapshots.

Factoring time, room and instructor decisions avoids a Boolean variable for
 every time × room × teacher combination. Resource conflicts use NoOverlap.
"""
from collections import defaultdict
import hashlib
from ortools.sat.python import cp_model

from app.provenance import CONFIG

MAX_CANDIDATES = 50000


def generate(snapshot, cancel=None, on_solver=None, time_limit=None, *, fixed_assignments=None):
    config = snapshot.get("provenance", {}).get("solver_config", CONFIG)
    if time_limit is None: time_limit = config["time_limit_seconds"]
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
    if not activities or not rooms:
        return {'status':'blocked','reason':'missing_data','assignments':[]}
    if sum(a['sessions'] for a in activities)>160:
        return {'status':'blocked','reason':'instance_too_large','assignments':[]}
    resources = defaultdict(list)
    for rule in snapshot['rules']:
        if rule['status'] != 'approved':
            continue
        if rule['type'] not in ('unavailable', 'preferred_period', 'room_unavailable', 'group_unavailable', 'group_allowed', 'activity_allowed'):
            return {'status':'blocked','reason':'unsupported_rule','assignments':[]}
        if rule['type'] in ('room_unavailable', 'group_unavailable'):
            kind = 'room' if rule['type'] == 'room_unavailable' else 'group'
            ident = rule.get(kind + '_id')
            if ident not in by_id or by_id[ident]['kind'] != ('rooms' if kind == 'room' else 'groups') or rule['day'] not in cal['days']:
                return {'status':'blocked','reason':'invalid_rule','assignments':[]}
    locks=[lock for lock in snapshot.get('assignment_locks',[]) if lock.get('status')=='approved']
    for lock in locks:
        activity=by_id.get(lock.get('activity_id'))
        if not activity or activity['kind']!='courses' or type(lock.get('occurrence')) is not int or not 0<=lock['occurrence']<activity['sessions'] or not any(lock.get(k) is not None for k in ('instructor_id','room_id','day')):
            return {'status':'blocked','reason':'invalid_lock','assignments':[]}
        if lock.get('instructor_id') is not None and lock['instructor_id'] not in activity['eligible_instructors']:
            return {'status':'blocked','reason':'invalid_lock','assignments':[]}
        if lock.get('room_id') is not None and by_id.get(lock['room_id'],{}).get('kind')!='rooms':
            return {'status':'blocked','reason':'invalid_lock','assignments':[]}
        if (lock.get('day') is None)!=(lock.get('start_minute') is None) or (lock.get('day') is not None and (lock['day'] not in cal['days'] or type(lock['start_minute']) is not int)):
            return {'status':'blocked','reason':'invalid_lock','assignments':[]}
    resource_blocks = [rule for rule in snapshot['rules'] if rule['status']=='approved' and rule['type'] in ('room_unavailable','group_unavailable')]
    workload_terms = defaultdict(list)
    for record in records:
        if not cal.get("weekly_load_policy", {}).get("allow_overtime") and record["kind"] == "instructors" and record.get("max_weekly_hours") is not None:
            hours = record["max_weekly_hours"]
            if type(hours) not in (int, float) or not 0 <= hours <= 168 or hours * 2 != int(hours * 2):
                return {"status":"blocked", "reason":"invalid_workload_limit", "assignments":[]}
    choices, penalties = [], []
    count = 0
    for activity in activities:
        if cancel and cancel.is_set():
            return {'status':'cancelled','assignments':[]}
        size = sum(by_id[g]['size'] for g in activity['group_ids'])
        room_type = 'lab' if activity['activity_type']=='lab' else 'lecture'
        suitable = [r for r in rooms if (r.get('capacity') or 0)>=size and bool(set(r.get('room_types') or [r.get('room_type')]) & {room_type,'flexible'}) and set(activity.get('required_equipment',[]))<=set(r.get('equipment',[]))]
        if not suitable:
            return {'status':'infeasible','reason':'no_suitable_room','activity_id':activity['id'],'assignments':[]}
        duration = activity['duration']
        if cal.get('teaching_periods'):
            starts = [di*1440+p['start'] for di in range(len(cal['days'])) for p in cal['teaching_periods'] if p['end']-p['start']==duration]
        else:
            starts = [di*1440+minute for di in range(len(cal['days'])) for minute in range(cal['start_hour']*60,cal['end_hour']*60-duration+1,cal['period_minutes'])]
        # Windows for one target form a weekly union. Each activity/group target
        # is a separate mandatory restriction, so targets intersect.
        window_sets = [[r for r in snapshot['rules'] if r['status']=='approved' and r['type']=='activity_allowed' and r.get('activity_id')==activity['id']]]
        window_sets += [[r for r in snapshot['rules'] if r['status']=='approved' and r['type']=='group_allowed' and r.get('group_id')==g] for g in activity['group_ids']]
        for windows in window_sets:
            if windows: starts=[s for s in starts if any(r['day']==cal['days'][s//1440] and r['start_hour']*60<=s%1440 and s%1440+duration<=r['end_hour']*60 for r in windows)]
        if not starts:return {'status':'infeasible','reason':'no_available_placement','activity_id':activity['id'],'assignments':[]}
        allowed, preferred = {}, {}
        for teacher in activity['eligible_instructors']:
            rules = [r for r in snapshot['rules'] if r['status']=='approved' and r.get('instructor_id')==teacher]
            mandatory = [r for r in rules if r['type']=='unavailable']
            windows = [r for r in rules if r['type']=='preferred_period']
            allowed[teacher] = [s for s in starts if cal['days'][s//1440] != by_id[teacher].get('day_off') and not any(r['day']==cal['days'][s//1440] and s%1440 < r['end_hour']*60 and r['start_hour']*60 < s%1440+duration for r in mandatory)]
            if windows:
                preferred[teacher] = [s for s in starts if any(r['day']==cal['days'][s//1440] and s%1440 >= r['start_hour']*60 and s%1440+duration <= r['end_hour']*60 for r in windows)]
        if not any(allowed.values()):
            return {'status':'infeasible','reason':'no_available_placement','activity_id':activity['id'],'assignments':[]}
        count += sum(len(values) for values in allowed.values())*len(suitable)*activity['sessions']
        if count>MAX_CANDIDATES:
            return {'status':'blocked','reason':'instance_too_large','assignments':[]}
        teachers = {t:model.new_bool_var(f'teacher_{activity["id"]}_{t}') for t in allowed}
        model.add_exactly_one(teachers.values())
        for ident, selected in teachers.items():
            workload_terms[ident].append(selected * activity["duration"] * activity["sessions"])
        previous = None
        for occurrence in range(activity['sessions']):
            if cancel and cancel.is_set():
                return {'status':'cancelled','assignments':[]}
            prefix = f'{activity["id"]}_{occurrence}'
            start = model.new_int_var_from_domain(cp_model.Domain.from_values(starts),'start_'+prefix)
            end = model.new_int_var(min(starts)+duration,max(starts)+duration,'end_'+prefix)
            interval = model.new_interval_var(start,duration,end,'session_'+prefix)
            if previous is not None:
                model.add(previous<start)
            previous = start
            for group in activity['group_ids']:
                resources[('group',group)].append(interval)
            for rule in resource_blocks:
                block_start = cal['days'].index(rule['day']) * 1440 + rule['start_hour'] * 60
                block_end = cal['days'].index(rule['day']) * 1440 + rule['end_hour'] * 60
                if rule['type'] == 'group_unavailable' and rule['group_id'] in activity['group_ids']:
                    domain = cp_model.Domain.from_values([s for s in starts if s + duration <= block_start or s >= block_end])
                    model.add_linear_expression_in_domain(start, domain)
            for teacher,selected in teachers.items():
                if not allowed[teacher]:
                    model.add(selected==0)
                else:
                    model.add_linear_expression_in_domain(start,cp_model.Domain.from_values(allowed[teacher])).only_enforce_if(selected)
                resources[('teacher',teacher)].append(model.new_optional_interval_var(start,duration,end,selected,'teacher_session_'+prefix+'_'+teacher))
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
                selected = model.new_bool_var('room_'+prefix+'_'+room['id'])
                room_vars[room['id']] = selected
                for rule in resource_blocks:
                    if rule['type'] == 'room_unavailable' and rule['room_id'] == room['id']:
                        block_start = cal['days'].index(rule['day']) * 1440 + rule['start_hour'] * 60
                        block_end = cal['days'].index(rule['day']) * 1440 + rule['end_hour'] * 60
                        allowed_starts = [s for s in starts if s + duration <= block_start or s >= block_end]
                        if allowed_starts:
                            model.add_linear_expression_in_domain(start, cp_model.Domain.from_values(allowed_starts)).only_enforce_if(selected)
                        else:
                            model.add(selected == 0)
                resources[('room',room['id'])].append(model.new_optional_interval_var(start,duration,end,selected,'room_session_'+prefix+'_'+room['id']))
            model.add_exactly_one(room_vars.values())
            for lock in locks:
                if lock['activity_id']!=activity['id'] or lock['occurrence']!=occurrence:continue
                if lock.get('instructor_id') is not None:model.add(teachers[lock['instructor_id']]==1)
                if lock.get('room_id') is not None:
                    if lock['room_id'] in room_vars:model.add(room_vars[lock['room_id']]==1)
                    else:model.add(False)
                if lock.get('day') is not None:model.add(start==cal['days'].index(lock['day'])*1440+lock['start_minute'])
            choices.append((activity,occurrence,start,teachers,room_vars))
    # Test-only differential hook: constrain every decision by equality, never hints.
    # No HTTP endpoint accepts this argument.
    if fixed_assignments is not None:
        fixed={(r['activity_id'],r['occurrence']):r for r in fixed_assignments}
        expected={(a['id'],o) for a,o,_,_,_ in choices}
        if len(fixed)!=len(fixed_assignments) or set(fixed)!=expected:
            raise ValueError('Fixed assignments must cover every occurrence exactly once')
        for activity,occurrence,start,teachers,room_vars in choices:
            row=fixed[activity['id'],occurrence]
            if row.get('day') not in cal['days'] or row.get('instructor_id') not in teachers or row.get('room_id') not in room_vars or row.get('end_minute')!=row.get('start_minute',-1)+activity['duration']:
                model.add(False)
                continue
            model.add(start==cal['days'].index(row['day'])*1440+row['start_minute'])
            for ident,var in teachers.items():model.add(var==int(ident==row['instructor_id']))
            for ident,var in room_vars.items():model.add(var==int(ident==row['room_id']))
    for intervals in resources.values():
        if len(intervals)>1:
            model.add_no_overlap(intervals)
    for record in records:
        if not cal.get("weekly_load_policy", {}).get("allow_overtime") and record["kind"] == "instructors" and record.get("max_weekly_hours") is not None:
            model.add(sum(workload_terms[record["id"]]) <= int(record["max_weekly_hours"] * 60))
    gaps=[]
    if active_policy:
        from app.realism_model import add_realism
        gaps=add_realism(model,cal,choices,policy.model_dump())
    # First minimise unmet instructor preferences, then free teaching periods
    # inside an instructor/group day. This is an explicit lexicographic objective.
    weighted = config.get("objective_profile") == "weighted-v1"
    primary_weight = config.get("preference_weight",10) if weighted else len(gaps)+1
    idle_weight = config.get("idle_weight",1) if weighted else 1
    model.minimize(sum(penalties)*primary_weight+sum(gaps)*idle_weight)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = config["search_workers"]
    solver.parameters.random_seed = config["random_seed"]
    progress_handler = on_solver(solver) if on_solver else None
    class Progress(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            progress_handler({'best_objective':self.objective_value,'best_bound':self.best_objective_bound,'solver_seconds':self.wall_time})
    status = solver.solve(model, Progress() if callable(progress_handler) else None)
    diagnostics = {'raw_status': solver.status_name(status), 'ortools_version': __import__('ortools').__version__,
                   'parameters_text': str(solver.parameters), 'solver_seconds': solver.wall_time,
                   'objective_definition': 'weighted-preferences-idle-v1' if weighted else 'preferences-then-idle-periods-v1' if active_policy else 'preferred-periods-v1',
                   'objective_weights': {'preferences':primary_weight,'idle_periods':idle_weight},
                   'model_sha256':hashlib.sha256(str(model.proto).encode('utf-8')).hexdigest(),
                   'model_validation_error':model.validate(),
                   'objective_value':solver.objective_value if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None,
                   'best_objective_bound':solver.best_objective_bound if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None}
    if cancel and cancel.is_set():
        return {'status':'cancelled','assignments':[],'solver_diagnostics':diagnostics}
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        assignments = []
        for activity,occurrence,start,teachers,room_vars in choices:
            minute = solver.value(start)
            assignments.append({'activity_id':activity['id'],'occurrence':occurrence,'instructor_id':next(t for t,v in teachers.items() if solver.value(v)),'room_id':next(r for r,v in room_vars.items() if solver.value(v)),'day':cal['days'][minute//1440],'start_minute':minute%1440,'end_minute':minute%1440+activity['duration']})
        return {'status':'completed','solver_diagnostics':diagnostics,'assignments':assignments,'preference_penalty':sum(solver.value(v) for v in penalties),'idle_period_penalty':sum(solver.value(v) for v in gaps) if policy.compact_days else None,'objective_definition':diagnostics['objective_definition'],'optimal':status==cp_model.OPTIMAL,'solver_seconds':round(solver.wall_time,3)}
    return {'solver_diagnostics':diagnostics,'status':'infeasible' if status==cp_model.INFEASIBLE else 'unknown' if status==cp_model.UNKNOWN else 'failed','reason':'conflicting_requirements' if status==cp_model.INFEASIBLE else 'search_limit' if status==cp_model.UNKNOWN else 'model_invalid' if status==cp_model.MODEL_INVALID else 'solver_error','assignments':[]}
