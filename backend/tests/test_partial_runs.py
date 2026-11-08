"""Building one timetable in parts: each part keeps the earlier parts' sessions fixed."""
from uuid import uuid4
from app.partial_plan import progress, scope_activities, tas_that_must_teach
from app.solver import assign_pool_rooms, generate
from app.validation import validate_schedule
from app.schedule_worker import process_one
from test_schedules import setup_data
from test_workflows import login, version


def campus():
    """Two programmes sharing one teacher and one room; a TA teaches only in B."""
    records = [
        {"id": "t", "kind": "instructors", "name": "Shared teacher", "position": "doctor"},
        {"id": "ta", "kind": "instructors", "name": "B's TA", "position": "ta"},
        {"id": "ga", "kind": "groups", "size": 20, "major": "A"},
        {"id": "gb", "kind": "groups", "size": 20, "major": "B"},
        {"id": "r", "kind": "rooms", "capacity": 30, "room_type": "lecture"},
        {"id": "a1", "kind": "courses", "sessions": 2, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["ga"]},
        {"id": "b1", "kind": "courses", "sessions": 2, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["gb"]},
        {"id": "b2", "kind": "courses", "sessions": 1, "duration": 60, "activity_type": "tutorial", "eligible_instructors": ["ta"], "group_ids": ["gb"]},
    ]
    return {"calendar": {"days": ["Sunday", "Monday"], "start_hour": 8, "end_hour": 11, "period_minutes": 60, "timezone": "Africa/Cairo"}, "rules": [], "records": records}


def part(snapshot, programmes, fixed=()):
    scope = [{"programme": p, "year": None} for p in programmes]
    ids = scope_activities(snapshot["records"], scope, {r["activity_id"] for r in fixed})
    return {**snapshot, "plan": {"scope": scope, "base_run_id": None, "activity_ids": ids, "fixed": list(fixed)}}


def test_parts_add_up_to_one_valid_timetable_without_moving_earlier_sessions():
    first = part(campus(), ["A"])
    assert first["plan"]["activity_ids"] == ["a1"]
    one = generate(first)
    assert one["status"] == "completed" and len(one["assignments"]) == 2
    # Part A alone is valid: B is simply not scheduled yet, and B's TA is not required yet.
    report = validate_schedule(first, one["assignments"])
    assert report["passed"], report["errors"]
    assert progress(first) == {"scheduled_sessions": 2, "total_sessions": 5, "complete": False, "remaining_programmes": [{"programme": "B", "year": None}]}
    second = part(campus(), ["B"], one["assignments"])
    two = generate(second)
    assert two["status"] == "completed"
    kept = {(r["activity_id"], r["occurrence"]): r for r in two["assignments"]}
    assert all(kept[(r["activity_id"], r["occurrence"])] == r for r in one["assignments"])
    # The shared teacher and room are never double-booked across parts.
    assert validate_schedule(second, two["assignments"])["passed"]
    assert validate_schedule(campus(), two["assignments"])["passed"]
    assert progress(second)["complete"]


def test_a_part_that_cannot_fit_around_fixed_sessions_is_infeasible():
    snapshot = campus()
    snapshot["calendar"]["days"] = ["Sunday"]  # three hours: A's two plus B's two lectures cannot all fit
    one = generate(part(snapshot, ["A"]))
    assert one["status"] == "completed"
    assert generate(part(snapshot, ["B"], one["assignments"]))["status"] == "infeasible"


def test_validator_rejects_a_part_missing_its_own_sessions_and_the_last_part_needs_every_ta():
    first = part(campus(), ["A"])
    one = generate(first)
    assert "complete_assignment" in validate_schedule(first, one["assignments"][:1])["errors"]
    # Without a plan the same rows are an incomplete full timetable.
    assert "complete_assignment" in validate_schedule(campus(), one["assignments"])["errors"]
    assert [t["id"] for t in tas_that_must_teach(first, first["records"])] == []
    assert [t["id"] for t in tas_that_must_teach(campus(), campus()["records"])] == ["ta"]


def test_scope_can_name_one_year_of_a_programme():
    records = campus()["records"] + [{"id": "ga2", "kind": "groups", "size": 20, "major": "A", "year": 2},
        {"id": "a2", "kind": "courses", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["ga2"]}]
    assert scope_activities(records, [{"programme": "A", "year": 2}], set()) == ["a2"]
    assert scope_activities(records, [{"programme": "A", "year": None}], {"a1"}) == ["a2"]


def test_a_part_must_use_a_ta_that_later_parts_could_not_cover():
    snapshot = campus()
    # Two TAs both able to teach A's and B's tutorial: one must teach in part A, or part B
    # (one tutorial) would leave one of them idle for good.
    snapshot["records"] += [{"id": "ta2", "kind": "instructors", "name": "Second TA", "position": "ta"},
        {"id": "a2", "kind": "courses", "sessions": 1, "duration": 60, "activity_type": "tutorial", "eligible_instructors": ["ta", "ta2"], "group_ids": ["ga"]}]
    snapshot["records"][7]["eligible_instructors"] = ["ta", "ta2"]
    first = part(snapshot, ["A"])
    assert len(tas_that_must_teach(first, first["records"])) == 1
    one = generate(first)
    assert one["status"] == "completed"
    two = generate(part(snapshot, ["B"], one["assignments"]))
    assert two["status"] == "completed" and {r["instructor_id"] for r in two["assignments"]} >= {"ta", "ta2"}


def test_carried_over_sessions_keep_their_room_inside_a_pool():
    rows = [{"room_id": "p1"}, {"room_id": "p1"}]
    # The new session starts first; the kept one needs room p2 later and keeps it.
    assign_pool_rooms([(0, 60, rows[0], None), (30, 90, rows[1], "p2")], ["p1", "p2"])
    assert rows[1]["room_id"] == "p2" and rows[0]["room_id"] == "p1"


def scoped(client, programmes, base=None):
    body = {"request_key": str(uuid4()), "scope": [{"programme": p, "year": 1} for p in programmes]}
    if base:
        body["base_run_id"] = base
    return client.post('/api/schedules', headers=version(client), json=body)


def test_api_builds_in_parts_and_publishes_only_the_complete_timetable(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    other = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups' and r['code'] == 'H')
    assert client.post('/api/records/courses', headers=version(client), json={"name": "Other", "code": "O", "activity_type": "lecture", "sessions": 1, "duration": 60, "eligible_instructors": ["teacher"], "group_ids": [other['id']]}).status_code == 201
    assert scoped(client, ['Nope']).json()['detail'] == 'invalid_scope'
    assert client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4()), 'scope': [{'programme': 'A', 'year': 4}]}).json()['detail'] == 'invalid_scope'
    first = scoped(client, ['A'])
    assert first.status_code == 202, first.text
    assert process_one(factory)
    run = client.get(f"/api/schedules/{first.json()['id']}").json()
    assert run['status'] == 'completed', run['result']
    assert run['progress'] == {'scheduled_sessions': 2, 'total_sessions': 3, 'complete': False, 'remaining_programmes': [{'programme': 'B', 'year': 1}], 'scope': [{'programme': 'A', 'year': 1}], 'base_run_id': None}
    assert client.post(f"/api/schedules/{run['id']}/publish", headers=version(client)).json()['detail'] == 'schedule_incomplete'
    assert scoped(client, ['A'], run['id']).json()['detail'] == 'scope_empty'
    last = scoped(client, ['B'], run['id'])
    assert last.status_code == 202, last.text
    assert process_one(factory)
    done = client.get(f"/api/schedules/{last.json()['id']}").json()
    assert done['status'] == 'completed' and done['progress']['complete'], done['result']
    assert client.post(f"/api/schedules/{done['id']}/publish", headers=version(client)).status_code == 200


def test_preflight_names_a_course_its_instructors_cannot_fit_and_a_part_ignores_other_parts():
    from app.preflight import inspect_inputs
    snapshot = campus()
    # B's TA alone must give 7 one-hour tutorials, but has 2 days x 3 hours = 6 hours.
    snapshot["records"][7]["sessions"] = 7
    report = inspect_inputs(snapshot)
    assert [b["activity_id"] for b in report["blockers"] if b["code"] == "instructor_pool_overloaded"] == ["b2"]
    assert inspect_inputs(part(snapshot, ["A"]))["ready"]  # part A does not include b2


def test_preflight_warns_when_a_group_week_is_nearly_full():
    from app.preflight import inspect_inputs
    snapshot = campus()
    snapshot["calendar"].update(teaching_periods=[{"start": 480, "end": 540}, {"start": 540, "end": 600}, {"start": 600, "end": 660}],
                                realism_policy={"max_consecutive_periods": 2})
    # Two of three periods a day are usable (a free one after every two): 4 hours a week. Group B needs 4.
    snapshot["records"][6]["sessions"] = 3
    warned = [w["resource_id"] for w in inspect_inputs(snapshot)["warnings"] if w["code"] == "group_week_nearly_full"]
    assert warned == ["gb"]


def test_preflight_blocks_more_teaching_than_the_rooms_hold():
    from app.preflight import inspect_inputs
    snapshot = campus()  # one room, 2 days x 3 hours = 6 room-hours
    snapshot["records"][6]["sessions"] = 5  # 2 + 5 + 1 = 8 hours of lectures and tutorials
    codes = [b["code"] for b in inspect_inputs(snapshot)["blockers"]]
    assert "room_week_capacity" in codes
    assert "room_week_capacity" not in [b["code"] for b in inspect_inputs(campus())["blockers"]]
