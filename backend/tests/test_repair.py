"""Impossible teaching timetables: the diagnosis finds what must give way and proves the fix."""
from app.repair import diagnose
from app.solver import generate
from app.validation import validate_schedule


def campus(days=("Sunday", "Monday")):
    return {"name": "T", "term": "T", "input_version": 1, "assignment_locks": [], "rules": [], "students": [],
            "calendar": {"days": list(days), "start_hour": 8, "end_hour": 12, "period_minutes": 60, "timezone": "Africa/Cairo", "realism_policy": {}},
            "records": [
                {"id": "t", "kind": "instructors", "name": "Dr. T", "position": "doctor"},
                {"id": "u", "kind": "instructors", "name": "Dr. U", "position": "doctor"},
                {"id": "g", "kind": "groups", "name": "Group G", "code": "G", "size": 20},
                {"id": "r", "kind": "rooms", "name": "Room R", "code": "R", "capacity": 30, "room_type": "lecture"},
                {"id": "s", "kind": "rooms", "name": "Room S", "code": "S", "capacity": 30, "room_type": "lecture"},
                {"id": "a", "kind": "courses", "name": "Algebra", "code": "A", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["g"]},
                {"id": "b", "kind": "courses", "name": "Biology", "code": "B", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["u"], "group_ids": ["g"]},
            ]}


def impossible(snap):
    assert generate(snap)["status"] in ("infeasible", "blocked")
    return diagnose(snap, budget=60, step=10)


def proven(result):
    assert result["status"] == "fixable" and result["verified"], result
    return result["suggestions"]


def rule(ident, type_, **fields):
    return {"id": ident, "status": "approved", "type": type_, "title": ident, **fields}


def test_two_sessions_locked_to_the_same_time_get_a_new_slot():
    snap = campus()
    snap["assignment_locks"] = [{"id": "l1", "status": "approved", "activity_id": "a", "occurrence": 0, "day": "Sunday", "start_minute": 480},
                                {"id": "l2", "status": "approved", "activity_id": "b", "occurrence": 0, "day": "Sunday", "start_minute": 480}]
    result = impossible(snap)
    [fix] = proven(result)
    assert fix["kind"] == "move_session" and "Move it to" in fix["message"]
    # One lock stays; the released session moves to a slot that is free for group G.
    lock = next(l for l in snap["assignment_locks"] if l["id"] == fix["target"])
    moved = next(a for a in result["assignments"] if a["activity_id"] == lock["activity_id"])
    assert (moved["day"], moved["start_minute"]) != ("Sunday", 480)


def test_only_instructor_unavailable_all_week():
    snap = campus()
    snap["rules"] = [rule("t-away", "unavailable", instructor_id="t", day=None, start_hour=8, end_hour=12)]
    [fix] = proven(impossible(snap))
    assert fix["target"] == "t-away" and "Dr. T is unavailable every day 08:00–12:00, but 1 session(s) need that time" in fix["message"]
    assert fix["sessions"] and "Algebra" in fix["sessions"][0]


def test_day_off_against_the_groups_only_free_day():
    snap = campus()
    snap["records"][0]["day_off"] = "Sunday"
    snap["rules"] = [rule("g-busy-monday", "group_unavailable", group_id="g", day="Monday", start_hour=8, end_hour=12)]
    fixes = proven(impossible(snap))
    # One of the two must give way, and only one is needed.
    assert len(fixes) == 1 and fixes[0]["kind"] in ("day_off", "rule")


def test_daily_hours_limit_too_low_for_the_load():
    snap = campus(days=("Sunday",))
    snap["records"] += [{"id": f"c{i}", "kind": "courses", "name": f"Course {i}", "code": f"C{i}", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["u"], "group_ids": ["g"]} for i in range(2)]
    snap["calendar"]["realism_policy"] = {"student_daily_hours": 2}
    [fix] = proven(impossible(snap))
    assert fix["kind"] == "policy" and "needs 4 h for Group G on Sunday" in fix["message"]


def test_courses_that_cannot_be_on_separate_days():
    snap = campus(days=("Sunday",))
    snap["rules"] = [rule("apart", "activities_not_same_day", params={"activity_ids": ["a", "b"]}, day=None, start_hour=None, end_hour=None)]
    [fix] = proven(impossible(snap))
    assert fix["target"] == "apart" and "separate days" in fix["message"]


def test_too_many_sessions_for_the_week_needs_a_data_change():
    snap = campus(days=("Sunday",))
    snap["records"] += [{"id": f"c{i}", "kind": "courses", "name": f"Course {i}", "code": f"C{i}", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["u"], "group_ids": ["g"]} for i in range(3)]
    result = impossible(snap)  # 5 hours of teaching for one group in a 4-hour day
    assert result["status"] == "data_change_needed" and "rooms, eligible instructors or sessions must change" in result["message"]


def test_a_feasible_timetable_needs_no_fix():
    snap = campus()
    assert validate_schedule(snap, generate(snap)["assignments"])["passed"]
    result = diagnose(snap, budget=30, step=10)
    assert result["status"] == "fixable" and result["suggestions"] == []


def test_too_many_sessions_names_the_overloaded_group():
    snap = campus(days=("Sunday",))
    snap["records"] += [{"id": f"c{i}", "kind": "courses", "name": f"Course {i}", "code": f"C{i}", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["u"], "group_ids": ["g"]} for i in range(3)]
    assert any("group teaching minutes exceed" in f for f in diagnose(snap, budget=30, step=10)["findings"])


def test_worker_saves_the_fix_with_an_impossible_run(environment, monkeypatch):
    from uuid import uuid4
    from app.models import ScheduleRun
    from app.schedule_worker import process_one
    from test_schedules import setup_data
    from test_workflows import login, version
    client, factory = environment
    login(client); setup_data(client, factory)
    teacher = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses')['eligible_instructors'][0]
    # The course's only instructor is away all week.
    cal = client.get('/api/workspace').json()['calendar']
    made = client.post('/api/rules', headers=version(client), json={'title': 'Away all week', 'type': 'unavailable', 'strength': 'mandatory', 'instructor_id': teacher, 'day': None, 'start_hour': cal['start_hour'], 'end_hour': cal['end_hour']})
    assert made.status_code == 201, made.text
    rule = made.json()
    assert client.post(f"/api/rules/{rule['id']}/approve", headers=version(client)).status_code == 200
    ident = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())}).json()['id']
    assert process_one(factory)
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['status'] in ('infeasible', 'blocked')
    repair = run['result']['repair']
    assert repair['status'] == 'fixable' and repair['verified'] and 'assignments' not in repair
    assert [s['target'] for s in repair['suggestions']] == [rule['id']]
