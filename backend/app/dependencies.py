from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from app.models import Audit, Session, SessionLocal, User, Workspace, utcnow
from app.security import token_hash


def db_session():
    with SessionLocal() as db:
        yield db


def fail(status, code):
    raise HTTPException(status_code=status, detail=code)


def workspace_lock(db, read=False):
    ws = db.scalar(
        select(Workspace).where(Workspace.id == 1).with_for_update(read=read)
    )
    if not ws:
        fail(503, "workspace_missing")
    return ws


def current_user(request: Request, db: DB = Depends(db_session)):
    # One lock order for all account/input writes prevents privilege-revocation
    # races and shared-lock upgrade deadlocks. Reads hold a shared lock.
    workspace_lock(db, read=request.method in ("GET", "HEAD", "OPTIONS"))
    session = db.get(Session, token_hash(request.cookies.get("jadwai_session", "")))
    if not session or session.expires_at < utcnow():
        fail(401, "session_expired")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        fail(401, "session_expired")
    if user.role in ("student", "instructor") and request.url.path not in (
        "/api/auth/me", "/api/auth/logout", "/api/auth/password", "/api/student/schedule",
    ) and not request.url.path.startswith("/api/me/"):
        fail(403, "permission_denied")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("X-Jadwai-Request") != "1":
            fail(403, "invalid_request")
        if user.role != "administrator" and request.url.path not in (
            "/api/auth/logout",
            "/api/auth/password",
        ):
            fail(403, "permission_denied")
    return user


def administrator(user=Depends(current_user)):
    if user.role != "administrator":
        fail(403, "permission_denied")
    return user


def lock_workspace(request, db):
    ws = workspace_lock(db)
    if request.headers.get("If-Match") != f'"{ws.version}"':
        fail(409, "stale_edit")
    return ws


def event(db, ws, user, code, target="", changes_inputs=False):
    if changes_inputs:
        ws.version += 1
    db.add(
        Audit(
            id=str(uuid4()),
            action=f"{code}: {target}"[:200],
            action_code=code,
            params={"target": target},
            actor=user.name if user else "System",
            input_version=ws.version,
        )
    )


def audit(db, ws, user, action):
    prefixes = {
        "Added ": "record.created",
        "Updated ": "record.updated",
        "Removed rule: ": "rule.deleted",
        "Removed ": "record.deleted",
        "Created rule: ": "rule.created",
        "Approve rule: ": "rule.approved",
        "Revoke rule: ": "rule.revoked",
    }
    for prefix, code in prefixes.items():
        if action.startswith(prefix):
            event(db, ws, user, code, action[len(prefix) :], changes_inputs=True)
            return
    event(db, ws, user, "legacy", action, changes_inputs=True)


def info(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "group_id": user.group_id,
        "instructor_id": user.instructor_id,
        "advising_student_id": user.advising_student_id,
        "active": user.active,
        "version": user.version,
    }
