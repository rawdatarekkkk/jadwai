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


def test_scope_can_name_one_group():
    records = campus()["records"] + [{"id": "ga2", "kind": "groups", "size": 20, "major": "A", "year": 2},
        {"id": "a2", "kind": "courses", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["ga2"]},
        {"id": "both", "kind": "courses", "sessions": 1, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t"], "group_ids": ["ga", "ga2"]}]
    assert scope_activities(records, [{"programme": "A", "year": 2, "group": "ga2"}], set()) == ["a2", "both"]  # a shared lecture comes along
    assert scope_activities(records, [{"programme": "A", "year": 1, "group": "ga2"}], set()) == []  # the group must belong to that year


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


def test_a_part_can_be_published_into_the_published_timetable(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    other = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups' and r['code'] == 'H')
    assert client.post('/api/records/courses', headers=version(client), json={"name": "Other", "code": "O", "activity_type": "lecture", "sessions": 1, "duration": 60, "eligible_instructors": ["teacher"], "group_ids": [other['id']]}).status_code == 201
    full = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())})
    assert process_one(factory)
    full = client.get(f"/api/schedules/{full.json()['id']}").json()
    merge = lambda ident: client.post(f'/api/schedules/{ident}/publish-merged', headers=version(client), json={'request_key': str(uuid4())})
    part = scoped(client, ['B'])
    assert process_one(factory)
    part = client.get(f"/api/schedules/{part.json()['id']}").json()
    assert part['status'] == 'completed', part['result']
    assert merge(part['id']).json()['detail'] == 'nothing_published'
    assert client.post(f"/api/schedules/{full['id']}/publish", headers=version(client)).status_code == 200
    assert merge(full['id']).json()['detail'] == 'not_a_part'
    # Made without the published week, this part clashes with it: refused, with the clash named.
    clash = merge(part['id'])
    if clash.status_code == 409:
        assert clash.json()['detail']['code'] == 'merge_validation_failed' and 'resource_conflicts' in clash.json()['detail']['errors']
    # Re-planned inside the published timetable, B's course is placed around everyone else: complete, and published directly.
    again = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4()), 'scope': [{'programme': 'B', 'year': 1}],
                                                                         'base_run_id': full['id'], 'replace': True})
    assert again.status_code == 202, again.text
    assert process_one(factory)
    again = client.get(f"/api/schedules/{again.json()['id']}").json()
    assert again['status'] == 'completed' and again['progress']['complete'], again['result']
    o = next(r['id'] for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses' and r['code'] == 'O')
    kept = [a for a in full['result']['assignments'] if a['activity_id'] != o]
    assert [a for a in again['result']['assignments'] if a['activity_id'] != o] == kept  # everyone else untouched
    # Merging it works too (same result); publishing it directly also works.
    done = merge(again['id'])
    assert done.status_code == 201, done.text
    merged = client.get(f"/api/schedules/{done.json()['id']}").json()
    assert merged['published_at'] and merged['result']['validation']['passed'] and merged['result']['merge']['part_run_id'] == again['id']
    assert client.get(f"/api/schedules/{full['id']}").json()['published_at'] is None  # replaced by the merged version
    assert client.post(f"/api/schedules/{again['id']}/publish", headers=version(client)).status_code == 200


def test_a_group_replanned_after_new_data_still_makes_a_whole_publishable_timetable(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    full = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())})
    assert process_one(factory)
    full = full.json()['id']
    assert client.post(f"/api/schedules/{full}/publish", headers=version(client)).status_code == 200
    # Added after publishing: a new group with its own course (like ACSI2-G20 and its labs).
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    other = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups' and r['code'] == 'H')
    assert client.post('/api/records/courses', headers=version(client), json={"name": "New", "code": "NEW", "activity_type": "lecture", "sessions": 1, "duration": 60,
                                                                               "eligible_instructors": ["teacher"], "group_ids": [other['id']]}).status_code == 201
    # Re-planning group A inside the published timetable places the new course too.
    again = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4()), 'scope': [{'programme': 'A', 'year': 1}], 'base_run_id': full, 'replace': True})
    assert again.status_code == 202, again.text
    assert process_one(factory)
    again = client.get(f"/api/schedules/{again.json()['id']}").json()
    new = next(r['id'] for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'courses' and r['code'] == 'NEW')
    assert again['status'] == 'completed' and again['progress']['complete'], again['result']
    assert new in {a['activity_id'] for a in again['result']['assignments']}
    assert client.post(f"/api/schedules/{again['id']}/publish", headers=version(client)).status_code == 200


def test_one_request_builds_a_timetable_in_chained_parts(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    other = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups' and r['code'] == 'H')
    assert client.post('/api/records/courses', headers=version(client), json={"name": "Other", "code": "O", "activity_type": "lecture", "sessions": 1, "duration": 60,
                                                                               "eligible_instructors": ["teacher"], "group_ids": [other['id']]}).status_code == 201
    first = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4()), 'scope': [{'programme': 'A', 'year': 1}],
                                                                         'then': [[{'programme': 'B', 'year': 1}]]}).json()
    assert first['name'] == 'Whole university · part 1/2'
    assert process_one(factory)
    # No browser requests: the coordinator queues the next part on its own.
    from app.chain_coordinator import advance
    # Another finished draft created while no browser was watching must not hide the chain.
    with factory.begin() as db:
        from app.models import ScheduleRun
        source = db.get(ScheduleRun, first['id'])
        db.add(ScheduleRun(id=str(uuid4()), workspace_id=1, created_by='admin', input_version=source.input_version,
                           request_key=str(uuid4()), status='completed', snapshot={k: v for k, v in source.snapshot.items() if k != 'chain'}, result=source.result))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: advance(factory), range(2)))
    assert sum(r is not None for r in attempts) == 1
    second_id = next(r.id for r in attempts if r is not None)
    assert advance(factory) is None  # another coordinator cannot queue a duplicate
    runs = client.get('/api/schedules').json()
    second = next(r for r in runs if r['id'] == second_id)
    assert second['id'] == second_id
    assert second['status'] == 'queued' and second['name'] == 'Whole university · part 2/2' and second['parent_run_id'] == first['id']
    assert process_one(factory)
    second = client.get(f"/api/schedules/{second['id']}").json()
    assert second['status'] == 'completed' and second['progress']['complete'], second['result']
    assert client.post(f"/api/schedules/{second['id']}/publish", headers=version(client)).status_code == 200
    assert not process_one(factory)  # nothing more queued


def test_a_chain_stops_and_says_why_when_the_data_changed_during_the_build(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    first = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4()), 'scope': [{'programme': 'A', 'year': 1}],
                                                                         'then': [[{'programme': 'B', 'year': 1}]]}).json()
    assert process_one(factory)
    client.post('/api/records/groups', headers=version(client), json={'name': 'K', 'code': 'K', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    runs = client.get('/api/schedules').json()
    assert [r['id'] for r in runs] == [first['id']]
    assert runs[0]['result']['chain_stopped'] == 'stale_schedule'
    answer = client.post('/api/assistant', headers=version(client), json={'text': 'status', 'previous': {}}).json()
    assert 'stopped after part 1 of 2' in ' '.join(answer['text']) and answer['choices'][0]['text'] == 'generate the whole university timetable'


def test_the_chat_publishes_the_timetable_it_generated_from_any_page(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    hello = client.post('/api/assistant', headers=version(client), json={'text': 'generate the timetable'}).json()
    run = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())}).json()
    # The chat confirms it started this run: from now on "it" means this timetable.
    client.post(f"/api/assistant/chats/{hello['chat_id']}/messages/{hello['message_id']}/done", headers=version(client),
                json={'note': ['Started.'], 'subject_kind': 'schedules', 'subject_id': run['id']}).raise_for_status()
    waiting = client.post('/api/assistant', headers=version(client), json={'text': 'publish the schedule', 'chat_id': hello['chat_id'], 'screen': {'page': 'dashboard'}}).json()
    assert 'still being generated' in waiting['text'][0] and waiting['action']['run_id'] == run['id'] and waiting['show_run'] == run['id']
    assert process_one(factory)
    ready = client.post('/api/assistant', headers=version(client), json={'text': 'publish this schedule', 'chat_id': hello['chat_id'], 'screen': {'page': 'dashboard'}}).json()
    assert ready['text'][0].startswith("Publish the timetable we've been talking about")
    assert ready['action'] == {'type': 'publish', 'what': 'teaching', 'run_id': run['id'], 'label': 'Publish'} and ready['show_run'] == run['id']


def test_an_older_chat_still_knows_the_timetable_it_generated(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    hello = client.post('/api/assistant', headers=version(client), json={'text': 'generate the whole university timetable'}).json()
    run = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())}).json()
    assert (hello['action'] or {}).get('type') == 'generate', hello['text']
    # Confirmed before chats remembered their timetable: no subject was sent.
    client.post(f"/api/assistant/chats/{hello['chat_id']}/messages/{hello['message_id']}/done", headers=version(client), json={'note': ['Started.']}).raise_for_status()
    assert process_one(factory)
    shown = client.post('/api/assistant', headers=version(client), json={'text': 'show the draft', 'chat_id': hello['chat_id'], 'screen': {'page': 'dashboard'}}).json()
    assert shown['text'][0].startswith('The timetable we generated in this chat:') and shown['action']['run_id'] == run['id'] and shown['auto_open']


def test_one_groups_week_from_a_whole_draft_is_published_into_the_published_timetable(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    records = client.get('/api/workspace').json()['records']
    group = next(r for r in records if r['kind'] == 'groups')
    assert client.put(f"/api/records/groups/{group['id']}", headers=version(client), json={'name': 'G', 'code': 'G', 'size': 20, 'major': 'A', 'year': 1}).status_code == 200
    full = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())}).json()['id']
    assert process_one(factory)
    assert client.post(f"/api/schedules/{full}/publish", headers=version(client)).status_code == 200
    published = client.get(f"/api/schedules/{full}").json()['result']['assignments']
    # Added after publishing: a group with its own lab, taught by its own instructor in its own lab room.
    # The draft is a fresh whole solve, so a course sharing the teacher or room R could land on a time the
    # published week already uses, and the merge would then (correctly) be refused with merge_validation_failed
    # (see test_a_part_can_be_published_into_the_published_timetable). Here nothing is shared, so it always passes.
    client.post('/api/records/groups', headers=version(client), json={'name': 'H', 'code': 'H', 'size': 20, 'major': 'B', 'year': 1}).raise_for_status()
    other = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'groups' and r['code'] == 'H')
    lab_teacher = client.post('/api/records/instructors', headers=version(client), json={'name': 'Lab Teacher', 'code': 'LT', 'department': 'CS'}).json()['id']
    assert client.post('/api/records/rooms', headers=version(client), json={'name': 'Lab', 'code': 'LAB', 'capacity': 30, 'room_type': 'lab'}).status_code == 201
    assert client.post('/api/records/courses', headers=version(client), json={"name": "New", "code": "NEW", "activity_type": "lab", "sessions": 1, "duration": 60,
                                                                               "eligible_instructors": [lab_teacher], "group_ids": [other['id']]}).status_code == 201
    draft = client.post('/api/schedules', headers=version(client), json={'request_key': str(uuid4())}).json()['id']
    assert process_one(factory)
    # JAI, asked to publish H's week only, offers that and says nothing else changes.
    answer = client.post('/api/assistant', headers=version(client), json={'text': "publish this group's schedule", 'previous': {}, 'screen': {'page': 'timetable', 'run_id': draft, 'group': other['id']}}).json()
    assert answer['action'] == {'type': 'publish_merged', 'run_id': draft, 'groups': [other['id']], 'label': 'Publish H'}, answer['text']
    assert answer['text'][0].startswith("Publish H's week (1 sessions) from this draft into the published timetable?")
    merged = client.post(f"/api/schedules/{draft}/publish-merged", headers=version(client), json={'request_key': str(uuid4()), 'groups': [other['id']]})
    assert merged.status_code == 201, merged.text
    now = client.get(f"/api/schedules/{merged.json()['id']}").json()
    assert now['published_at'] and now['result']['merge']['scope'] == [{'group': other['id']}]
    kept = {(a['activity_id'], a['occurrence']): (a['day'], a['start_minute']) for a in published}
    assert all((a['day'], a['start_minute']) == kept[(a['activity_id'], a['occurrence'])] for a in now['result']['assignments'] if (a['activity_id'], a['occurrence']) in kept)
    assert len(now['result']['assignments']) == len(published) + 1
