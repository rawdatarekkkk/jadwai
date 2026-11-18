"""Advance multipart builds using API credentials, independent of browser polling."""
import asyncio
import logging
from app.models import SessionLocal, Workspace
from app.schedules import continue_chain

logger = logging.getLogger(__name__)


def advance(factory=SessionLocal):
    with factory() as db:
        try:
            return continue_chain(db, db.get(Workspace, 1))
        finally:
            db.rollback()  # release the lock also when there is nothing to queue


async def coordinate(stop, factory=SessionLocal, interval=2):
    while not stop.is_set():
        try:
            await asyncio.to_thread(advance, factory)
        except Exception:
            logger.exception("Could not advance multipart build; will retry")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
