from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from app.main import app
from app.models import Audit, Record, Session, Workspace, utcnow
from app.security import token_hash
from fastapi.testclient import TestClient
from sqlalchemy import select


def login(client, email="admin@example.test"):
    result = client.post(
        "/api/auth/login", json={"email": email, "password": "test-password-123"}
    )
    assert result.status_code == 200
    return result


def version(client):
    return {"If-Match": f'"{client.get("/api/workspace").json()["version"]}"'}


def test_authentication_logout_and_expiry(environment):
    client, factory = environment
    assert client.get("/api/workspace").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "admin@example.test", "password": "wrong"}
        ).status_code
        == 401
    )
    response = login(client)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    with factory() as db:
        token = client.cookies.get("jadwai_session")
        row = db.get(Session, token_hash(token))
        assert row.token_hash != token
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/workspace").status_code == 401
    login(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/workspace").status_code == 401


def test_viewer_and_csrf_block_changes(environment):
    client, _ = environment
    login(client, "viewer@example.test")
    assert client.get("/api/workspace").status_code == 200
    assert (
        client.post(
            "/api/records/groups",
            json={"name": "A", "code": "A", "size": 20},
            headers=version(client),
        ).status_code
        == 403
    )
    assert client.post("/api/auth/logout").status_code == 204
    login(client)
    del client.headers["X-Jadwai-Request"]
    assert (
        client.post(
            "/api/records/groups",
            json={"name": "A", "code": "A", "size": 20},
            headers=version(client),
        ).status_code
        == 403
    )


def test_crud_persists_versions_and_audit(environment):
    client, factory = environment
    login(client)
    create = client.post(
        "/api/records/groups",
        headers=version(client),
        json={"name": "Group A", "code": "A", "size": 20},
    )
    assert create.status_code == 201
    ident = create.json()["id"]
    assert create.json()["version"] == 2
    assert (
        client.put(
            f"/api/records/groups/{ident}",
            headers=version(client),
            json={"name": "Group A revised", "code": "A", "size": 25},
        ).status_code
        == 200
    )
    with factory() as db:
        assert db.get(Record, ident).data["size"] == 25
        assert (
            len(
                db.scalars(
                    select(Audit).where(Audit.action_code.like("record.%"))
                ).all()
            )
            == 2
        )
    assert (
        client.delete(
            f"/api/records/groups/{ident}", headers=version(client)
        ).status_code
        == 204
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "  ", "code": "A", "size": 20},
        {"name": "A", "code": "  ", "size": 20},
        {"name": "A", "code": "A", "size": 0},
        {"name": "A", "code": "A", "size": 20, "invented": True},
    ],
)
def test_invalid_records_do_not_change_version(environment, payload):
    client, factory = environment
    login(client)
    assert (
        client.post(
            "/api/records/groups", headers=version(client), json=payload
        ).status_code
        == 422
    )
    with factory() as db:
        assert db.get(Workspace, 1).version == 1
        assert not db.scalars(
            select(Audit).where(Audit.action_code.like("record.%"))
        ).all()


def test_simultaneous_edits_have_one_winner(environment):
    client, factory = environment
    login(client)
    cookie = client.cookies.get("jadwai_session")

    def create(code):
        with TestClient(app) as other:
            other.cookies.set("jadwai_session", cookie, path="/api")
            return other.post(
                "/api/records/groups",
                headers={"X-Jadwai-Request": "1", "If-Match": '"1"'},
                json={"name": code, "code": code, "size": 20},
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(create, ["A", "B"])) == [201, 409]
    with factory() as db:
        assert db.get(Workspace, 1).version == 2
        assert (
            len(
                db.scalars(
                    select(Audit).where(Audit.action_code.like("record.%"))
                ).all()
            )
            == 1
        )


def test_duplicate_codes_and_references(environment):
    client, _ = environment
    login(client)
    assert (
        client.post(
            "/api/records/instructors",
            headers=version(client),
            json={"name": "Other", "code": "test", "department": "CS"},
        ).status_code
        == 409
    )
    course = {
        "name": "Course",
        "code": "CS1",
        "activity_type": "lecture",
        "sessions": 2,
        "duration": 60,
        "eligible_instructors": ["missing"],
        "group_ids": ["missing"],
    }
    assert (
        client.post(
            "/api/records/courses", headers=version(client), json=course
        ).status_code
        == 422
    )


def test_approval_revocation_and_referential_integrity(environment):
    client, _ = environment
    login(client)
    body = {
        "title": "No Tuesday morning",
        "instructor_id": "teacher",
        "type": "unavailable",
        "day": "Tuesday",
        "start_hour": 8,
        "end_hour": 12,
        "strength": "mandatory",
    }
    response = client.post("/api/rules", headers=version(client), json=body)
    assert response.status_code == 201
    ident = response.json()["id"]
    assert client.get("/api/workspace").json()["rules"][0]["status"] == "draft"
    assert (
        client.post(f"/api/rules/{ident}/approve", headers=version(client)).status_code
        == 200
    )
    assert client.get("/api/workspace").json()["rules"][0]["approved_by"] == "admin"
    assert (
        client.delete(f"/api/rules/{ident}", headers=version(client)).status_code == 409
    )
    assert (
        client.delete(
            "/api/records/instructors/teacher", headers=version(client)
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/rules/{ident}/revoke", headers=version(client)).status_code
        == 200
    )
    assert (
        client.delete(f"/api/rules/{ident}", headers=version(client)).status_code == 204
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"start_hour": 12, "end_hour": 9},
        {"strength": "preferred"},
        {"instructor_id": "missing"},
        {"type": "invented"},
    ],
)
def test_invalid_rules(environment, updates):
    client, _ = environment
    login(client)
    body = {
        "title": "Test",
        "instructor_id": "teacher",
        "type": "unavailable",
        "day": "Tuesday",
        "start_hour": 8,
        "end_hour": 12,
        "strength": "mandatory",
    }
    assert (
        client.post(
            "/api/rules", headers=version(client), json={**body, **updates}
        ).status_code
        == 422
    )


def test_api_root_sends_browsers_to_the_website(environment):
    client, _ = environment
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 307 and response.headers['location'].startswith('http')
