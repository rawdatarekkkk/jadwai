import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from app.main import app
from app.models import (
    Audit,
    LoginBucket,
    PasswordReset,
    Session,
    WorkerHeartbeat,
    Workspace,
    utcnow,
)
from app.security import token_hash
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_workflows import login


def users(client):
    return {row["id"]: row for row in client.get("/api/users").json()}


def expected(row):
    return {"If-Match": f'"{row["version"]}"'}


def update(client, ident, **changes):
    row = users(client)[ident]
    return client.put(
        "/api/users/" + ident,
        headers=expected(row),
        json={**{key: row[key] for key in ["name", "role", "active"]}, **changes},
    )


def test_account_invitation_reset_single_use_and_revocation(environment):
    client, factory = environment
    login(client)
    created = client.post(
        "/api/users",
        json={"name": "New Viewer", "email": "NEW@example.test", "role": "viewer"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["user"]["email"] == "new@example.test"
    token = payload["reset"]["token"]
    with factory() as db:
        assert db.get(PasswordReset, token) is None
        assert db.get(PasswordReset, token_hash(token))
        assert all(
            token not in a.action and token not in str(a.params)
            for a in db.scalars(select(Audit))
        )
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "new-test-password-123"},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "other-test-password"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "new@example.test", "password": "new-test-password-123"},
        ).status_code
        == 200
    )
    assert client.get("/api/users").status_code == 403
    assert (
        client.post(
            "/api/users",
            json={"name": "No", "email": "no@example.test", "role": "administrator"},
        ).status_code
        == 403
    )
    assert client.get("/api/workspace").status_code == 200


def test_last_admin_and_stale_account(environment):
    client, _ = environment
    login(client)
    assert (
        update(client, "admin", active=False).json()["detail"] == "last_administrator"
    )
    assert update(client, "admin", role="viewer").status_code == 409
    row = users(client)["viewer"]
    assert (
        client.put(
            "/api/users/viewer",
            headers=expected(row),
            json={"name": "Renamed", "role": "viewer", "active": True},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/users/viewer",
            headers=expected(row),
            json={"name": "Overwritten", "role": "viewer", "active": False},
        ).json()["detail"]
        == "stale_account"
    )


def test_two_admins_cannot_simultaneously_remove_last_admin(environment):
    client, _ = environment
    login(client)
    assert update(client, "viewer", role="administrator").status_code == 200
    token1 = client.cookies.get("jadwai_session")
    login(client, "viewer@example.test")
    token2 = client.cookies.get("jadwai_session")
    snapshot = users(client)

    def demote(pair):
        ident, token = pair
        with TestClient(app) as other:
            other.cookies.set("jadwai_session", token, path="/api")
            return other.put(
                "/api/users/" + ident,
                headers={"X-Jadwai-Request": "1", **expected(snapshot[ident])},
                json={
                    "name": snapshot[ident]["name"],
                    "role": "viewer",
                    "active": True,
                },
            ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(demote, [("admin", token1), ("viewer", token2)])) == [
            200,
            409,
        ]


def test_deactivation_and_role_change_revoke_existing_sessions(environment):
    client, _ = environment
    login(client, "viewer@example.test")
    viewer_token = client.cookies.get("jadwai_session")
    login(client)
    assert update(client, "viewer", active=False).status_code == 200
    with TestClient(app) as old:
        old.cookies.set("jadwai_session", viewer_token, path="/api")
        assert old.get("/api/workspace").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "viewer@example.test", "password": "test-password-123"},
        ).status_code
        == 401
    )
    assert (
        update(client, "viewer", active=True, role="administrator").status_code == 200
    )
    login(client, "viewer@example.test")
    token = client.cookies.get("jadwai_session")
    login(client)
    assert update(client, "viewer", role="viewer").status_code == 200
    with TestClient(app) as old:
        old.cookies.set("jadwai_session", token, path="/api")
        assert old.get("/api/workspace").status_code == 401


def test_throttling_survives_connection_recycling(environment):
    client, factory = environment
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "admin@example.test", "password": "bad"},
            ).status_code
            == 401
        )
    factory.kw["bind"].dispose()
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": "test-password-123"},
        ).status_code
        == 429
    )
    with factory.begin() as db:
        for bucket in db.scalars(select(LoginBucket)):
            bucket.started_at = utcnow() - timedelta(minutes=16)
    assert login(client).status_code == 200


def test_reset_expiry_and_explicit_session_revocation(environment):
    client, factory = environment
    login(client)
    row = users(client)["viewer"]
    reset = client.post("/api/users/viewer/reset", headers=expected(row)).json()[
        "reset"
    ]
    with factory.begin() as db:
        db.get(PasswordReset, token_hash(reset["token"])).expires_at = (
            utcnow() - timedelta(seconds=1)
        )
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": reset["token"], "new_password": "new-password-123456"},
        ).json()["detail"]
        == "invalid_reset"
    )
    row = users(client)["admin"]
    assert (
        client.post(
            "/api/users/admin/revoke-sessions", headers=expected(row)
        ).status_code
        == 204
    )
    assert client.get("/api/workspace").status_code == 401


def test_password_change_checks_current_password_and_ends_sessions(environment):
    client, _ = environment
    login(client, "viewer@example.test")
    assert (
        client.post(
            "/api/auth/password",
            json={"current_password": "bad", "new_password": "new-viewer-password"},
        ).json()["detail"]
        == "incorrect_password"
    )
    assert (
        client.post(
            "/api/auth/password",
            json={
                "current_password": "test-password-123",
                "new_password": "new-viewer-password",
            },
        ).status_code
        == 204
    )
    assert client.get("/api/workspace").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "viewer@example.test", "password": "test-password-123"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "viewer@example.test", "password": "new-viewer-password"},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "sql", ["UPDATE audit SET actor='changed'", "DELETE FROM audit", "TRUNCATE audit"]
)
def test_audit_is_append_only_even_for_owner(environment, sql):
    client, factory = environment
    login(client)
    with factory() as db:
        with pytest.raises(DBAPIError):
            db.execute(text(sql))
            db.commit()
        db.rollback()
        assert db.scalars(select(Audit)).all()


def test_accounts_do_not_change_academic_input_version_and_audit_is_structured(
    environment,
):
    client, factory = environment
    login(client)
    assert update(client, "viewer", name="مشاهد").status_code == 200
    with factory() as db:
        assert db.get(Workspace, 1).version == 1
        row = db.scalar(select(Audit).where(Audit.action_code == "account.updated"))
        assert row.params == {"target": "مشاهد"}


def test_worker_cleans_only_expired_credentials_and_health_reflects_freshness(
    environment, monkeypatch
):
    client, factory = environment
    login(client)
    with factory.begin() as db:
        db.add(
            Session(
                token_hash="expired",
                user_id="admin",
                expires_at=utcnow() - timedelta(minutes=1),
            )
        )
        db.add(
            PasswordReset(
                token_hash="expired",
                user_id="admin",
                expires_at=utcnow() - timedelta(minutes=1),
            )
        )
        db.add(
            LoginBucket(
                key="expired", started_at=utcnow() - timedelta(minutes=16), attempts=5
            )
        )
    assert client.get("/api/health").status_code == 503
    spec = importlib.util.spec_from_file_location(
        "worker_module", Path("../worker/main.py")
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    worker.heartbeat()
    assert client.get("/api/health").status_code == 200
    with factory() as db:
        assert db.get(Session, "expired") is None
        assert db.get(PasswordReset, "expired") is None
        assert db.get(LoginBucket, "expired") is None
    assert client.get("/api/workspace").status_code == 200
    with factory.begin() as db:
        db.get(WorkerHeartbeat, 1).seen_at = utcnow() - timedelta(minutes=2)
    assert client.get("/api/health").json()["worker"] is False


def test_runtime_role_has_no_schema_or_audit_mutation_privileges(environment):
    client, factory = environment
    login(client)
    engine = factory.kw["bind"]
    role = "probe_" + __import__("uuid").uuid4().hex
    with engine.begin() as db:
        schema = db.scalar(text("SELECT current_schema()"))
        db.execute(text(f"CREATE ROLE {role}"))
        db.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {role}"))
        db.execute(text(f"GRANT SELECT,INSERT ON audit TO {role}"))
    try:
        for statement in [
            "UPDATE audit SET actor='changed'",
            "DELETE FROM audit",
            "TRUNCATE audit",
            "CREATE TABLE unauthorized(id integer)",
        ]:
            with engine.connect() as db:
                db.execute(text(f"SET LOCAL ROLE {role}"))
                with pytest.raises(DBAPIError):
                    db.execute(text(statement))
                db.rollback()
    finally:
        with engine.begin() as db:
            db.execute(text(f"REVOKE ALL ON audit FROM {role}"))
            db.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM {role}"))
            db.execute(text(f"DROP ROLE {role}"))


def test_calendar_is_versioned_and_rejects_rules_outside_teaching_hours(environment):
    client, factory = environment
    login(client)
    ws = client.get("/api/workspace").json()
    body = {
        "name": "CS Updated",
        "term": "Spring 2027",
        **ws["calendar"],
        "start_date": "2027-02-01",
        "end_date": "2027-06-01",
        "days": ["Sunday", "Monday"],
    }
    assert (
        client.put("/api/workspace", headers={"If-Match": '"1"'}, json=body).status_code
        == 200
    )
    assert client.get("/api/workspace").json()["calendar"]["start_date"] == "2027-02-01"
    assert (
        client.put("/api/workspace", headers={"If-Match": '"1"'}, json=body).status_code
        == 409
    )
    rule = {
        "title": "Outside teaching day",
        "instructor_id": "teacher",
        "type": "unavailable",
        "day": "Tuesday",
        "start_hour": 8,
        "end_hour": 12,
        "strength": "mandatory",
    }
    assert (
        client.post("/api/rules", headers={"If-Match": '"2"'}, json=rule).json()[
            "detail"
        ]
        == "outside_calendar"
    )
    rule["day"] = "Sunday"
    assert (
        client.post("/api/rules", headers={"If-Match": '"2"'}, json=rule).status_code
        == 201
    )
    assert (
        client.put(
            "/api/workspace",
            headers={"If-Match": '"3"'},
            json={**body, "start_hour": 10},
        ).json()["detail"]
        == "calendar_conflict"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"days": []},
        {"days": ["Sunday", "Sunday"]},
        {"start_hour": 18, "end_hour": 8},
        {"timezone": "Not/A_Zone"},
        {"start_date": "2027-06-01", "end_date": "2027-02-01"},
    ],
)
def test_invalid_calendar_does_not_change_inputs(environment, changes):
    client, _ = environment
    login(client)
    ws = client.get("/api/workspace").json()
    body = {"name": ws["name"], "term": ws["term"], **ws["calendar"], **changes}
    assert (
        client.put("/api/workspace", headers={"If-Match": '"1"'}, json=body).status_code
        == 422
    )
    assert client.get("/api/workspace").json()["version"] == 1
