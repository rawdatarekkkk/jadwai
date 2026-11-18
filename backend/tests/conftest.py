import os
from uuid import uuid4

import pytest
from app.main import app, db_session
from app.models import Record, User, Workspace
from app.security import hash_password
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def environment():
    url = os.environ.get("DATABASE_ADMIN_URL") or os.environ["DATABASE_URL"]
    owner = create_engine(url)
    schema = "test_" + uuid4().hex
    with owner.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(Workspace(id=1, name="Test", term="Fall 2026", version=1))
        db.add(
            User(
                id="admin",
                email="admin@example.test",
                name="Admin",
                password=hash_password("test-password-123"),
                role="administrator",
            )
        )
        db.add(
            User(
                id="viewer",
                email="viewer@example.test",
                name="Viewer",
                password=hash_password("test-password-123"),
                role="viewer",
            )
        )
        db.add(
            Record(
                id="teacher",
                kind="instructors",
                data={"name": "Dr. Test", "code": "TEST", "department": "CS"},
            )
        )

    def dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[db_session] = dependency
    app.state.chain_factory = factory
    app.state.chain_enabled = False
    try:
        with TestClient(app) as client:
            client.headers["X-Jadwai-Request"] = "1"
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        del app.state.chain_factory
        del app.state.chain_enabled
        engine.dispose()
        with owner.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        owner.dispose()


