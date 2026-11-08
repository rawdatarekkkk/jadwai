"""Independent timetable checks: no dependency on the solver/model builder."""
from collections import Counter, defaultdict
from app import rule_semantics as rs
from app.calendar_slots import placement_for

CHECKS = ["complete_assignment", "calendar", "instructor_eligibility", "instructor_position", "ta_teaching", "instructor_day_off", "instructor_continuity", "room_suitability", "resource_conflicts", "approved_unavailability", "approved_room_unavailability", "approved_group_unavailability", "configured_weekly_workload", "approved_assignment_locks", "approved_allowed_windows", "approved_room_rules", "approved_daily_limits", "approved_teaching_days", "approved_separate_days", "advising_student_conflicts"]


def validate_schedule(snapshot, assignments):
    if any(r["status"] == "approved" and r["type"] not in rs.TYPES for r in snapshot["rules"]):
        return report({"unsupported_rule"})
    from app.schemas import RealismPolicy
    try:
        RealismPolicy.model_validate(snapshot["calendar"].get("realism_policy", {}))
    except ValueError:
        return report({"invalid_realism_policy"})
    records = {r["id"]: r for r in snapshot["records"]}
    activities = {k: r for k, r in records.items() if r["kind"] == "courses"}
    calendar = snapshot["calendar"]
    if not activities or not any(r["kind"] == "rooms" for r in records.values()):
        return report({"input_data"})
    # Check types before hashing keys, comparisons or dictionary lookups. Python
    # booleans compare equal to integers, so occurrence/minutes require exact int.
    if not isinstance(assignments, list):
        return report({"invalid_assignment"})
    for row in assignments:
        if not isinstance(row, dict) or any(type(row.get(k)) is not str for k in ("activity_id", "instructor_id", "room_id", "day")) or any(type(row.get(k)) is not int for k in ("occurrence", "start_minute", "end_minute")):
            return report({"invalid_assignment"})
    errors = set()
    from app.partial_plan import covered, tas_that_must_teach
    scope = covered(snapshot)  # a part run covers only some activities
    expected = Counter((a["id"], n) for a in activities.values() if scope is None or a["id"] in scope for n in range(a["sessions"]))
    actual = Counter((a.get("activity_id"), a.get("occurrence")) for a in assignments)
    if actual != expected:
        errors.add("complete_assignment")
    teachers = {}
    occupied = []
    # Students joining an activity from outside its groups need seats too.
    joining = Counter(a for s in snapshot.get("students", []) for a in s["activity_ids"] if a in activities and s.get("group_id") not in activities[a]["group_ids"])
    for row in assignments:
        activity = activities.get(row.get("activity_id"))
        if not activity:
            errors.add("complete_assignment")
            continue
        teacher = row.get("instructor_id")
        if teacher not in activity["eligible_instructors"] or records.get(teacher, {}).get("kind") != "instructors":
            errors.add("instructor_eligibility")
        from app.positions import position_conflict
        if position_conflict(activity["activity_type"], records.get(teacher)):
            errors.add("instructor_position")
        if activity["id"] in teachers and teachers[activity["id"]] != teacher:
            errors.add("instructor_continuity")
        teachers[activity["id"]] = teacher
        start, end, day = row.get("start_minute"), row.get("end_minute"), row.get("day")
        if records.get(teacher, {}).get("day_off") == day:
            errors.add("instructor_day_off")
        if day not in calendar["days"] or placement_for(calendar, activity["duration"], start, end) is None:
            errors.add("calendar")
            continue
        room = records.get(row.get("room_id"), {})
        size = sum(records.get(g, {}).get("size", 10**9) for g in activity["group_ids"]) + joining[activity["id"]]
        required_type = "lab" if activity["activity_type"] == "lab" else "lecture"
        if room.get("kind") != "rooms" or (room.get("capacity") or 0) < size or not set(room.get("room_types") or [room.get("room_type")]) & {required_type, "flexible"} or not set(activity.get("required_equipment", [])) <= set(room.get("equipment", [])):
            errors.add("room_suitability")
        targets = [('activity_allowed', 'activity_id', activity['id'])] + [('group_allowed', 'group_id', g) for g in activity['group_ids']]
        for typ, field, ident in targets:
            windows = [r for r in rs.approved(snapshot, typ) if r.get(field)==ident]
            if not rs.within_windows(windows, day, start, end):
                errors.add('approved_allowed_windows')
        if any(row.get("room_id") not in rs.param(r, "room_ids") for r in rs.approved(snapshot, "activity_room") if r["activity_id"] == activity["id"]):
            errors.add("approved_room_rules")
        resources = {("teacher", teacher), ("room", row.get("room_id")), *(("group", g) for g in activity["group_ids"])}
        for other_day, other_start, other_end, other_resources in occupied:
            if day == other_day and start < other_end and other_start < end and resources & other_resources:
                errors.add("resource_conflicts")
        occupied.append((day, start, end, resources))
        for rule in rs.approved(snapshot, "room_unavailable", "group_unavailable", "unavailable"):
            if not rs.overlaps(rule, day, start, end):
                continue
            if rule["type"] == "room_unavailable" and rule.get("room_id") == row.get("room_id"):
                errors.add("approved_room_unavailability")
            if rule["type"] == "group_unavailable" and rule.get("group_id") in activity["group_ids"]:
                errors.add("approved_group_unavailability")
            if rule["type"] == "unavailable" and rule["instructor_id"] == teacher:
                errors.add("approved_unavailability")
    errors |= limit_rule_errors(snapshot, activities, assignments)
    errors |= advising_errors(snapshot, activities, assignments)
    teaching = {a["instructor_id"] for a in assignments}
    if any(r["id"] not in teaching for r in tas_that_must_teach(snapshot, records.values())):
        errors.add("ta_teaching")
    # Independently sum assigned teaching minutes (breaks inside a session excluded).
    workload = []
    for teacher in records.values():
        if teacher["kind"] != "instructors":
            continue
        minutes = sum(activities[a["activity_id"]]["duration"] for a in assignments if a["instructor_id"] == teacher["id"] and a["activity_id"] in activities)
        overtime_policy = calendar.get("weekly_load_policy", {}).get("allow_overtime", False)
        limit = None if overtime_policy else teacher.get("max_weekly_hours")
        if limit is not None and (type(limit) not in (int, float) or not 0 <= limit <= 168 or limit * 2 != int(limit * 2)):
            errors.add("invalid_workload_limit")
            continue
        limit_minutes = None if limit is None else int(limit * 60)
        exceeded = limit_minutes is not None and minutes > limit_minutes
        if exceeded:
            errors.add("weekly_workload")
        workload.append({"instructor_id": teacher["id"], "assigned_minutes": minutes, "assigned_hours": minutes / 60,
                         "max_weekly_hours": limit, "configured": limit is not None or overtime_policy, "exceeded": exceeded,
                         "regular_hours": min(minutes / 60, 12) if overtime_policy else None, "extra_hours": max(0, minutes / 60 - 12) if overtime_policy else None, "standard_weekly_hours": 12 if overtime_policy else None})
    checked_locks=[]
    for lock in snapshot.get('assignment_locks',[]):
        if lock.get('status')!='approved' or (scope is not None and lock.get('activity_id') not in scope):continue
        matches=[a for a in assignments if a['activity_id']==lock.get('activity_id') and a['occurrence']==lock.get('occurrence')]
        fields=[k for k in ('instructor_id','room_id','day','start_minute') if lock.get(k) is not None]
        activity = activities.get(lock.get('activity_id'))
        shape = (activity is not None and type(lock.get('occurrence')) is int and 0 <= lock['occurrence'] < activity['sessions']
                 and (lock.get('day') is None) == (lock.get('start_minute') is None)
                 and (lock.get('start_minute') is None or type(lock['start_minute']) is int)
                 and all(type(lock[k]) is str for k in ('instructor_id', 'room_id', 'day') if lock.get(k) is not None))
        valid=shape and len(matches)==1 and bool(fields) and all(matches[0][k]==lock[k] for k in fields)
        if not valid:errors.add('assignment_lock')
        checked_locks.append({'lock_id':lock.get('id'),'activity_id':lock.get('activity_id'),'occurrence':lock.get('occurrence'),'fields':fields,'passed':valid})
    from app.realism_validation import check_realism
    realism, realism_errors = check_realism(snapshot, assignments)
    errors.update(realism_errors)
    result = report(errors, workload, realism, checked_locks)
    from app.validation_details import details
    result.update(details(snapshot, assignments, result))
    return result


def limit_rule_errors(snapshot, activities, assignments):
    """Daily-hour, teaching-day and same-day limits, recomputed from the assignments."""
    errors = set()
    minutes = defaultdict(int)
    days_taught = defaultdict(set)
    activity_days = defaultdict(set)
    for a in assignments:
        activity = activities.get(a["activity_id"])
        if not activity:
            continue
        minutes[("instructor", a["instructor_id"], a["day"])] += activity["duration"]
        for g in activity["group_ids"]:
            minutes[("group", g, a["day"])] += activity["duration"]
        days_taught[a["instructor_id"]].add(a["day"])
        activity_days[a["activity_id"]].add(a["day"])
    for rule in rs.approved(snapshot, "instructor_max_daily_hours", "group_max_daily_hours"):
        kind, ident = ("instructor", rule["instructor_id"]) if rule["type"] == "instructor_max_daily_hours" else ("group", rule["group_id"])
        if any(m > round(rs.param(rule, "hours") * 60) for (k, i, _), m in minutes.items() if (k, i) == (kind, ident)):
            errors.add("approved_daily_limits")
    for rule in rs.approved(snapshot, "instructor_max_days"):
        if len(days_taught[rule["instructor_id"]]) > rs.param(rule, "days"):
            errors.add("approved_teaching_days")
    for rule in rs.approved(snapshot, "activities_not_same_day"):
        ids = rs.param(rule, "activity_ids")
        if any(activity_days[x] & activity_days[y] for i, x in enumerate(ids) for y in ids[i + 1:]):
            errors.add("approved_separate_days")
    return errors


def advising_errors(snapshot, activities, assignments):
    """No two sessions of one advising student may overlap."""
    sessions = defaultdict(list)
    for a in assignments:
        sessions[a.get("activity_id")].append((a.get("day"), a.get("start_minute"), a.get("end_minute")))
    for student in snapshot.get("students", []):
        mine = sorted(t for ident in student["activity_ids"] if ident in activities for t in sessions[ident])
        if any(x[0] == y[0] and y[1] < x[2] for x, y in zip(mine, mine[1:])):
            return {"advising_student_conflicts"}
    return set()


def report(errors, workload=None, realism=None, checked_locks=None):
    return {"passed": not errors, "checks": CHECKS + ([key for key, active in [("configured_daily_load", any(realism["policy"].get(k) is not None for k in ("student_daily_hours", "instructor_daily_hours"))), ("activity_day_distribution", realism["policy"].get("spread_activity_days")), ("configured_consecutive_periods", realism["policy"].get("max_consecutive_periods") is not None), ("configured_idle_periods", realism["policy"].get("max_idle_periods") is not None)] if active] if realism is not None else []), "errors": sorted(errors), "publication_ready": False,
            "workload": workload, "realism": realism, "assignment_locks": checked_locks,
            "coverage": [{"check":key,"required":True,"applicable":None,"basis":"input structure failed before evaluation","status":"not_evaluated"} for key in CHECKS],
            "violations": [{"code":code,"message":code.replace("_"," "),"sessions":[],"resource_ids":[],"rule_ids":[]} for code in sorted(errors)],
            "limitations": (["weekly_workload_limits_missing"] if workload is None or any(not row["configured"] for row in workload) else []) + (["daily_limits_not_configured"] if realism is None or any(realism["policy"].get(k) is None for k in ("student_daily_hours", "instructor_daily_hours")) else []) + ["draft_only"]}
