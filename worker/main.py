"""Heartbeat, expiring-session cleanup and reconnecting Phase 2 worker."""

import logging
import signal
import threading
from datetime import timedelta

from app.models import (
    LoginBucket,
    PasswordReset,
    Session,
    SessionLocal,
    WorkerHeartbeat,
    utcnow,
)
from sqlalchemy import delete
from app.schedule_worker import process_one
from sqlalchemy.exc import DBAPIError

stop = threading.Event()
logger = logging.getLogger("jadwai.worker")


def heartbeat():
    with SessionLocal.begin() as db:
        now = utcnow()
        row = db.get(WorkerHeartbeat, 1)
        if row:
            row.seen_at = now
        else:
            db.add(WorkerHeartbeat(id=1, seen_at=now))
        db.execute(delete(Session).where(Session.expires_at < now))
        db.execute(delete(PasswordReset).where(PasswordReset.expires_at < now))
        db.execute(
            delete(LoginBucket).where(
                LoginBucket.started_at < now - timedelta(minutes=15)
            )
        )


def run():
    delay = 1
    logger.info("Worker started; schedule generation, heartbeat and session maintenance.")
    while not stop.is_set():
        try:
            heartbeat()
            delay = 1
            process_one(shutdown=stop)
            stop.wait(1)
        except DBAPIError:
            logger.warning("Database unavailable; reconnecting in %s seconds.", delay)
            stop.wait(delay)
            delay = min(delay * 2, 15)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run()
