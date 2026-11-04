from copy import deepcopy
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.models import ScheduleRun, WorkerHeartbeat, utcnow
from app.solver import generate
from app.validation import validate_schedule, CHECKS
from app.schedule_worker import process_one, recover_interrupted
from test_workflows import login, version


def example():
    return {"calendar": {"days": ["Sunday", "Monday"], "start_hour": 8, "end_hour": 12, "period_minutes": 30, "timezone": "Africa/Cairo"}, "rules": [], "records": [
        {"id": "t", "kind": "instructors", "name": "Teacher"},
        {"id": "u", "kind": "instructors", "name": "Other teacher"},
        {"id": "g", "kind": "groups", "size": 20},
        {"id": "r", "kind": "rooms", "capacity": 25, "room_type": "lecture", "equipment": ["projector"]},
        {"id": "a", "kind": "courses", "sessions": 2, "duration": 60, "activity_type": "lecture", "eligible_instructors": ["t", "u"], "group_ids": ["g"], "required_equipment": ["projector"]},
        {"id": "b", "kind": "courses", "sessions": 1, "duration": 90, "activity_type": "tutorial", "eligible_instructors": ["t"], "group_ids": ["g"]},
    ]}


def test_solver_assigns_all_occurrences_with_consistent_teacher_and_preferences():
    snap = example()
    snap["rules"] = [{"status": "approved", "type": "unavailable", "instructor_id": "t", "day": "Sunday", "start_hour": 8, "end_hour": 12}, {"status": "approved", "type": "preferred_period", "instructor_id": "u", "day": "Monday", "start_hour": 8, "end_hour": 12}]
    result = generate(snap)
    assert result["status"] == "completed"
    assert len(result["assignments"]) == 3
    assert validate_schedule(snap, result["assignments"])["passed"]
    assert result["preference_penalty"] == 0
    assert all(r["day"] == "Monday" for r in result["assignments"])


def test_infeasible_unknown_and_cancelled_are_distinct():
    snap = example()
    snap["calendar"].update(days=["Sunday"], end_hour=9)
    assert generate(snap)["status"] == "infeasible"
    assert generate(example(), time_limit=0)["status"] == "unknown"
    cancel = Event(); cancel.set()
    assert generate(example(), cancel)["status"] == "cancelled"


def test_room_equipment_capacity_and_draft_rules():
    snap = example()
    snap["records"][3]["equipment"] = []
    assert generate(snap)["reason"] == "no_suitable_room"
    snap = example()
    snap["rules"] = [{"status": "draft", "type": "unavailable", "instructor_id": "t", "day": "Monday", "start_hour": 8, "end_hour": 12}]
    assert generate(snap)["status"] == "completed"


def test_independent_validator_rejects_seeded_corruption():
    snap = example()
    assignments = generate(snap)["assignments"]
    assert validate_schedule(snap, assignments)["checks"] == CHECKS
    assert not validate_schedule(snap, assignments[:-1])["passed"]
    bad = deepcopy(assignments); bad[0]["room_id"] = "missing"
    assert "room_suitability" in validate_schedule(snap, bad)["errors"]
    bad = deepcopy(assignments); bad[0]["instructor_id"] = "missing"
    assert "instructor_eligibility" in validate_schedule(snap, bad)["errors"]
    bad = deepcopy(assignments); bad[0]["start_minute"] = 0
    assert "calendar" in validate_schedule(snap, bad)["errors"]
    bad = deepcopy(assignments)
    for r in bad: r.update(day="Sunday", start_minute=480, end_minute=480 + next(a["duration"] for a in snap["records"] if a["id"] == r["activity_id"]))
    assert "resource_conflicts" in validate_schedule(snap, bad)["errors"]
    snap["rules"] = [{"status": "approved", "type": "unavailable", "instructor_id": assignments[0]["instructor_id"], "day": assignments[0]["day"], "start_hour": 8, "end_hour": 12}]
    assert "approved_unavailability" in validate_schedule(snap, assignments)["errors"]


def setup_data(client, factory):
    with factory.begin() as db:
        db.add(WorkerHeartbeat(id=1, seen_at=utcnow()))
    for kind, body in [("groups", {"name": "G", "code": "G", "size": 20}), ("rooms", {"name": "R", "code": "R", "capacity": 30, "room_type": "lecture"})]:
        assert client.post(f"/api/records/{kind}", headers=version(client), json=body).status_code == 201
    group = next(r for r in client.get('/api/workspace').json()['records'] if r['kind']=='groups')
    assert client.post('/api/records/courses', headers=version(client), json={"name": "Course", "code": "C", "activity_type": "lecture", "sessions": 2, "duration": 60, "eligible_instructors": ["teacher"], "group_ids": [group['id']]}).status_code == 201


def start(client, key=None):
    return client.post('/api/schedules', headers=version(client), json={"request_key": key or str(uuid4())})


def test_persisted_job_idempotency_staleness_and_access(environment):
    client, factory = environment
    assert client.get('/api/schedules').status_code == 401
    login(client); setup_data(client, factory)
    key = str(uuid4())
    created = start(client, key)
    assert created.status_code == 202
    ident = created.json()['id']
    assert start(client, key).json()['id'] == ident
    assert start(client).status_code == 409
    assert process_one(factory)
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['status'] == 'completed'
    assert run['result']['validation']['passed']
    assert not run['result']['validation']['publication_ready']
    frozen = run['snapshot']
    assert client.post('/api/records/groups', headers=version(client), json={'name':'New','code':'NEW','size':10}).status_code == 201
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['stale'] and run['snapshot'] == frozen
    assert client.post('/api/schedules', headers={'If-Match':'"1"'}, json={'request_key':str(uuid4())}).status_code == 409
    # A retry of the same run remains idempotent after input changes.
    assert start(client, key).json()['id'] == ident
    login(client, 'viewer@example.test')
    assert client.get('/api/schedules').status_code == 403
    assert start(client).status_code == 403


def test_cancellation_and_interrupted_worker(environment):
    from datetime import timedelta
    client, factory = environment
    login(client); setup_data(client, factory)
    ident = start(client).json()['id']
    assert client.post(f'/api/schedules/{ident}/cancel').json()['status'] == 'cancelled'
    assert not process_one(factory)
    ident = start(client).json()['id']
    with factory.begin() as db:
        row = db.get(ScheduleRun, ident)
        row.status = 'running'; row.updated_at = utcnow() - timedelta(seconds=100)
    recover_interrupted(factory)
    assert client.get(f'/api/schedules/{ident}').json()['result']['reason'] == 'worker_interrupted'


def test_snapshot_is_immutable_in_database(environment):
    client, factory = environment
    login(client); setup_data(client, factory)
    ident = start(client).json()['id']
    with factory() as db:
        row = db.get(ScheduleRun, ident)
        row.snapshot = {}
        with pytest.raises(DBAPIError): db.commit()


def test_missing_worker_and_data_fail_cleanly(environment):
    client, factory = environment
    login(client)
    assert start(client).json()['detail'] == 'worker_unavailable'
    with factory.begin() as db: db.add(WorkerHeartbeat(id=1, seen_at=utcnow()))
    assert start(client).json()['detail'] == 'schedule_missing_data'


def test_running_cancellation_discards_even_a_complete_candidate(environment, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app import schedule_worker
    client, factory = environment
    login(client); setup_data(client, factory)
    ident = start(client).json()['id']
    entered = Event()
    def delayed(snapshot, cancelled, on_solver):
        candidate = generate(snapshot)
        entered.set()
        assert cancelled.wait(5)
        return candidate
    monkeypatch.setattr(schedule_worker, 'generate', delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(process_one, factory)
        assert entered.wait(5)
        response = client.post(f'/api/schedules/{ident}/cancel')
        assert response.json()['cancel_requested']
        assert future.result(timeout=10)
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['status'] == 'cancelled'
    assert run['result']['assignments'] == []
    assert 'optimal' not in run['result']


def test_validator_failure_never_becomes_a_completed_draft(environment, monkeypatch):
    from app import schedule_worker
    client, factory = environment
    login(client); setup_data(client, factory)
    ident = start(client).json()['id']
    monkeypatch.setattr(schedule_worker, 'generate', lambda *args: {'status':'completed','assignments':[]})
    assert process_one(factory)
    run = client.get(f'/api/schedules/{ident}').json()
    assert run['status'] == 'failed'
    assert run['result']['reason'] == 'validation_failed'
    assert run['result']['assignments'] == []
