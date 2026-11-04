import os
import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session as DB

from app.dependencies import (
    administrator,
    current_user,
    db_session,
    event,
    fail,
    info,
    workspace_lock,
)
from app.models import (
    Record,
    LoginBucket,
    PasswordReset,
    Session,
    User,
    WorkerHeartbeat,
    Workspace,
    utcnow,
)
from app.schemas import Login, NewUser, PasswordChange, ResetPassword, UserUpdate
from app.security import hash_password, token_hash, verify_password

router = APIRouter()
DUMMY_PASSWORD = hash_password("a-random-non-account-password")
WINDOW = timedelta(minutes=15)


def csrf(request):
    if request.headers.get("X-Jadwai-Request") != "1":
        fail(403, "invalid_request")


def limit(db, key, maximum):
    digest = token_hash(key)
    bucket = db.get(LoginBucket, digest)
    if not bucket:
        bucket = LoginBucket(key=digest, started_at=utcnow(), attempts=0)
        db.add(bucket)
    if bucket.started_at + WINDOW < utcnow():
        bucket.started_at, bucket.attempts = utcnow(), 0
    if bucket.attempts >= maximum:
        db.commit()
        fail(429, "too_many_attempts")
    bucket.attempts += 1
    return bucket


def session_cookie(response, request, token):
    response.set_cookie(
        "jadwai_session",
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https"
        or os.environ.get("JADWAI_COOKIE_SECURE", "").lower() == "true",
        max_age=28800,
        path="/api",
    )


def revoke(db, user_id):
    db.execute(delete(Session).where(Session.user_id == user_id))


def reset_token(db, user):
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    token = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(minutes=30)
    db.add(
        PasswordReset(token_hash=token_hash(token), user_id=user.id, expires_at=expires)
    )
    return {"token": token, "expires_at": expires}


@router.get("/api/health/live")
def live():
    return {"status": "alive"}


@router.get("/api/health")
def readiness(response: Response, db: DB = Depends(db_session)):
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    workspace = db.get(Workspace, 1)
    worker = db.get(WorkerHeartbeat, 1)
    fresh = bool(worker and utcnow() - worker.seen_at < timedelta(seconds=45))
    ready = version == "0026" and workspace is not None and fresh
    response.status_code = 200 if ready else 503
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ready" if ready else "not_ready",
        "database": True,
        "schema_current": version == "0026",
        "workspace": workspace is not None,
        "worker": fresh,
    }


@router.post("/api/auth/login")
def login(
    body: Login, request: Request, response: Response, db: DB = Depends(db_session)
):
    csrf(request)
    ws = workspace_lock(db)
    ip = request.client.host if request.client else "unknown"
    limit(db, "login-ip:" + ip, 30)
    email_bucket = limit(db, "login-email:" + body.email.casefold(), 5)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    valid = verify_password(body.password, user.password if user else DUMMY_PASSWORD)
    if not user or not user.active or not valid:
        event(db, ws, None, "login.failed")
        db.commit()
        fail(401, "invalid_credentials")
    email_bucket.attempts = 0
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=8),
        )
    )
    event(db, ws, user, "login.succeeded")
    db.commit()
    session_cookie(response, request, token)
    return info(user)


@router.get("/api/auth/me")
def me(user=Depends(current_user)):
    return info(user)


@router.post("/api/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    row = db.get(Session, token_hash(request.cookies.get("jadwai_session", "")))
    if row:
        db.delete(row)
    event(db, db.get(Workspace, 1), user, "logout")
    db.commit()
    response.delete_cookie("jadwai_session", path="/api")


@router.post("/api/auth/password", status_code=204)
def change_password(
    body: PasswordChange,
    response: Response,
    user=Depends(current_user),
    db: DB = Depends(db_session),
):
    ws = db.get(Workspace, 1)
    limit(db, "change-password:" + user.id, 5)
    if not verify_password(body.current_password, user.password):
        db.commit()
        fail(400, "incorrect_password")
    user.password = hash_password(body.new_password)
    user.version += 1
    revoke(db, user.id)
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    event(db, ws, user, "password.changed")
    db.commit()
    response.delete_cookie("jadwai_session", path="/api")


@router.post("/api/auth/reset-password", status_code=204)
def consume_reset(
    body: ResetPassword,
    request: Request,
    response: Response,
    db: DB = Depends(db_session),
):
    csrf(request)
    ws = workspace_lock(db)
    limit(db, "reset-ip:" + (request.client.host if request.client else "unknown"), 30)
    row = db.get(PasswordReset, token_hash(body.token))
    user = db.get(User, row.user_id) if row else None
    if not row or row.expires_at < utcnow() or not user or not user.active:
        db.commit()
        fail(400, "invalid_reset")
    user.password = hash_password(body.new_password)
    user.version += 1
    revoke(db, user.id)
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    event(db, ws, user, "password.reset")
    db.commit()
    response.delete_cookie("jadwai_session", path="/api")


@router.get("/api/users")
def list_users(user=Depends(administrator), db: DB = Depends(db_session)):
    return [info(row) for row in db.scalars(select(User).order_by(User.name, User.id))]


def student_group(db, body):
    if body.role != "student":
        if body.group_id:
            fail(422, "invalid_input")
        return None
    group = db.get(Record, body.group_id) if body.group_id else None
    if not group or group.kind != "groups":
        fail(422, "invalid_input")
    return group.id


@router.post("/api/users", status_code=201)
def create_user(
    body: NewUser, user=Depends(administrator), db: DB = Depends(db_session)
):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        fail(409, "duplicate_email")
    row = User(
        id=str(uuid4()),
        email=body.email.lower(),
        name=body.name,
        role=body.role,
        group_id=student_group(db, body),
        active=True,
        version=1,
        password=hash_password(secrets.token_urlsafe(40)),
    )
    db.add(row)
    db.flush()
    token = reset_token(db, row)
    event(db, db.get(Workspace, 1), user, "account.created", row.name)
    db.commit()
    return {"user": info(row), "reset": token}


def target_user(db, ident, request):
    row = db.get(User, ident)
    if not row:
        fail(404, "not_found")
    if request.headers.get("If-Match") != f'"{row.version}"':
        fail(409, "stale_account")
    return row


@router.put("/api/users/{ident}")
def update_user(
    ident: str,
    body: UserUpdate,
    request: Request,
    user=Depends(administrator),
    db: DB = Depends(db_session),
):
    row = target_user(db, ident, request)
    if (
        row.active
        and row.role == "administrator"
        and (not body.active or body.role != "administrator")
    ):
        count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.active.is_(True), User.role == "administrator")
        )
        if count <= 1:
            fail(409, "last_administrator")
    group_id = student_group(db, body)
    permissions_changed = row.role != body.role or row.active != body.active or row.group_id != group_id
    row.group_id = group_id
    row.name, row.role, row.active = body.name, body.role, body.active
    row.version += 1
    if permissions_changed:
        revoke(db, row.id)
        db.execute(delete(PasswordReset).where(PasswordReset.user_id == row.id))
    event(db, db.get(Workspace, 1), user, "account.updated", row.name)
    db.commit()
    return info(row)


@router.post("/api/users/{ident}/reset")
def issue_reset(
    ident: str,
    request: Request,
    user=Depends(administrator),
    db: DB = Depends(db_session),
):
    row = target_user(db, ident, request)
    if not row.active:
        fail(409, "account_inactive")
    revoke(db, row.id)
    token = reset_token(db, row)
    row.version += 1
    event(db, db.get(Workspace, 1), user, "password.reset_issued", row.name)
    db.commit()
    return {"reset": token, "version": row.version}


@router.post("/api/users/{ident}/revoke-sessions", status_code=204)
def revoke_sessions(
    ident: str,
    request: Request,
    user=Depends(administrator),
    db: DB = Depends(db_session),
):
    row = target_user(db, ident, request)
    revoke(db, row.id)
    row.version += 1
    event(db, db.get(Workspace, 1), user, "sessions.revoked", row.name)
    db.commit()
