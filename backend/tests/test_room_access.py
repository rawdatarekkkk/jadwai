"""Special rooms: only the chosen programmes or courses may use them."""
from app.room_access import room_allows
from app.solver import generate
from app.validation import validate_schedule
from test_workflows import login, version


def campus(reserved=None):
    lab = {"id": "dslab", "kind": "rooms", "name": "Data Science Lab", "code": "DSL", "capacity": 30, "room_types": ["lab"], "equipment": ["Data Science Lab"], **(reserved or {})}
    return {"calendar": {"days": ["Sunday"], "start_hour": 8, "end_hour": 10, "period_minutes": 60, "timezone": "Africa/Cairo"}, "rules": [], "records": [
        {"id": "t", "kind": "instructors", "name": "TA", "position": "ta"},
        {"id": "ds", "kind": "groups", "name": "DS G1", "code": "DS1", "size": 20, "year": 3, "major": "Data Science"},
        {"id": "ba", "kind": "groups", "name": "BA G1", "code": "BA1", "size": 20, "year": 3, "major": "Business Administration"},
        lab,
        {"id": "ml", "kind": "courses", "course_id": "c-ml", "name": "Machine Learning", "code": "ML", "sessions": 1, "duration": 60, "activity_type": "lab", "eligible_instructors": ["t"], "group_ids": ["ds"]},
        {"id": "xl", "kind": "courses", "course_id": "c-xl", "name": "Excel", "code": "XL", "sessions": 1, "duration": 60, "activity_type": "lab", "eligible_instructors": ["t"], "group_ids": ["ba"]},
    ]}


def test_open_room_admits_everyone_and_a_reserved_room_only_its_users():
    records = {r["id"]: r for r in campus()["records"]}
    lab = dict(records["dslab"])
    assert room_allows(lab, records["xl"], records)
    lab["reserved_majors"] = ["Data Science"]
    assert room_allows(lab, records["ml"], records) and not room_allows(lab, records["xl"], records)
    lab = {**lab, "reserved_majors": [], "reserved_course_ids": ["c-xl"]}
    assert room_allows(lab, records["xl"], records) and not room_allows(lab, records["ml"], records)


def test_solver_never_places_others_in_a_reserved_room_and_the_validator_catches_it():
    snap = campus({"reserved_majors": ["Data Science"]})
    # Only one lab exists and it is reserved for Data Science: Business Administration's lab has nowhere to go.
    result = generate(snap)
    assert result["status"] == "infeasible" and result["reason"] == "no_suitable_room" and result["activity_id"] == "xl"
    rows = [{"activity_id": "ml", "occurrence": 0, "instructor_id": "t", "room_id": "dslab", "day": "Sunday", "start_minute": 480, "end_minute": 540},
            {"activity_id": "xl", "occurrence": 0, "instructor_id": "t", "room_id": "dslab", "day": "Sunday", "start_minute": 540, "end_minute": 600}]
    assert "room_suitability" in validate_schedule(snap, rows)["errors"]
    assert validate_schedule(campus(), rows)["passed"]


def test_rooms_can_be_reserved_through_the_api(environment):
    client, factory = environment
    login(client)
    client.post('/api/records/groups', headers=version(client), json={'name': 'DS G1', 'code': 'DS1', 'size': 20, 'year': 3, 'major': 'Data Science'}).raise_for_status()
    body = {'name': 'Data Science Lab', 'code': 'DSL', 'capacity': 30, 'room_types': ['lab'], 'equipment': ['Data Science Lab'], 'reserved_majors': ['data science']}
    made = client.post('/api/records/rooms', headers=version(client), json=body)
    assert made.status_code == 201, made.text
    room = next(r for r in client.get('/api/workspace').json()['records'] if r['kind'] == 'rooms' and r['code'] == 'DSL')
    assert room['reserved_majors'] == ['Data Science'] and room['reserved_course_ids'] == []  # spelling follows the groups
    assert client.post('/api/records/rooms', headers=version(client), json={**body, 'code': 'DSL2', 'reserved_majors': ['Nope']}).json()['detail'] == 'unknown_programme'
