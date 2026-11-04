"""Idempotently create synthetic data. Existing inputs and passwords are never overwritten."""

import os
from uuid import uuid4

from app.models import Audit, Record, Rule, SessionLocal, User, Workspace
from app.security import hash_password


def seed():
    password = os.environ.get("JADWAI_ADMIN_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set JADWAI_ADMIN_PASSWORD to at least 12 characters.")
    with SessionLocal.begin() as db:
        if db.get(Workspace, 1):
            print("Workspace already exists; seed left all existing data unchanged.")
            return
        db.add(Workspace(id=1, name="Computer Science", term="Fall 2026", version=1))
        db.add(
            User(
                id=str(uuid4()),
                email=os.environ.get(
                    "JADWAI_ADMIN_EMAIL", "admin@jadwai.local"
                ).lower(),
                name="Workspace Admin",
                password=hash_password(password),
                role="administrator",
            )
        )

        def record(kind, **data):
            ident = str(uuid4())
            db.add(Record(id=ident, kind=kind, data=data))
            return ident

        ahmed = record(
            "instructors",
            name="Dr. Ahmed Hassan",
            code="AH",
            department="Computer Science",
        )
        nour = record(
            "instructors",
            name="Dr. Nour Ibrahim",
            code="NI",
            department="Computer Science",
        )
        salma = record(
            "instructors",
            name="Dr. Salma Ali",
            code="SA",
            department="Computer Science",
        )
        omar = record(
            "instructors", name="Omar Mahmoud", code="OM", department="Computer Science"
        )
        a = record("groups", name="Year 2 · Group A", code="Y2-A", size=32)
        b = record("groups", name="Year 2 · Group B", code="Y2-B", size=30)
        c = record("groups", name="Year 3 · Group A", code="Y3-A", size=28)
        record(
            "rooms",
            name="The Cedar Hall",
            code="C-201",
            capacity=80,
            room_type="lecture",
        )
        record(
            "rooms",
            name="The Olive Room",
            code="C-204",
            capacity=40,
            room_type="lecture",
        )
        record(
            "rooms", name="Computing Lab", code="L-102", capacity=36, room_type="lab"
        )
        db.flush()
        record(
            "courses",
            name="Data Structures",
            code="CS201-LEC",
            activity_type="lecture",
            sessions=2,
            duration=60,
            eligible_instructors=[ahmed, nour],
            group_ids=[a, b],
        )
        record(
            "courses",
            name="Data Structures Lab",
            code="CS201-LAB",
            activity_type="lab",
            sessions=1,
            duration=120,
            eligible_instructors=[omar],
            group_ids=[a],
        )
        record(
            "courses",
            name="Database Systems",
            code="CS302-LEC",
            activity_type="lecture",
            sessions=2,
            duration=60,
            eligible_instructors=[salma, nour],
            group_ids=[c],
        )
        record(
            "courses",
            name="Software Engineering",
            code="CS303-LEC",
            activity_type="lecture",
            sessions=2,
            duration=60,
            eligible_instructors=[ahmed, salma],
            group_ids=[c],
        )
        db.add(
            Rule(
                id=str(uuid4()),
                data={
                    "title": "Keep Tuesday mornings free for Dr. Ahmed",
                    "instructor_id": ahmed,
                    "type": "unavailable",
                    "day": "Tuesday",
                    "start_hour": 8,
                    "end_hour": 12,
                    "strength": "mandatory",
                },
                status="draft",
            )
        )
        db.add(
            Audit(
                id=str(uuid4()),
                action="Created workspace with synthetic starter data",
                action_code="workspace.created",
                params={},
                actor="Workspace Admin",
                input_version=1,
            )
        )
    print("Synthetic workspace created. Sign in using the account configured in .env.")


if __name__ == "__main__":
    seed()
