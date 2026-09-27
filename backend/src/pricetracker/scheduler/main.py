"""Scheduler process: turns due recurring schedules into queued runs.

Each occurrence gets an idempotency key ``schedule:<id>:<occurrence UTC>`` backed by
a unique constraint, so two schedulers (or a restart mid-tick) never create the
same run twice. Schedules are claimed with ``FOR UPDATE SKIP LOCKED`` on
PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.db.session import init_engine, session_factory
from pricetracker.logs import configure_logging
from pricetracker.models import Schedule, User
from pricetracker.models.enums import RunTrigger, ScheduleFrequency
from pricetracker.services import runs as run_service
from pricetracker.services.errors import ServiceError
from pricetracker.settings import get_settings

logger = logging.getLogger("pricetracker.scheduler")


def next_occurrence(schedule: Schedule, after: datetime) -> datetime:
    """Next occurrence strictly after ``after`` (UTC), computed in the schedule's timezone."""
    tz = ZoneInfo(schedule.timezone or "America/Sao_Paulo")
    hour, minute = (int(part) for part in (schedule.time_local or "07:00").split(":"))
    local_after = after.astimezone(tz)
    candidate_day = local_after.date()
    for offset in range(0, 15):
        day = candidate_day + timedelta(days=offset)
        if schedule.frequency == ScheduleFrequency.WEEKLY.value and schedule.weekday is not None:
            if day.weekday() != schedule.weekday:
                continue
        candidate = datetime.combine(day, time(hour, minute), tzinfo=tz)
        if candidate > local_after:
            return candidate.astimezone(ZoneInfo("UTC"))
    raise ValueError("could not compute next occurrence")


def enqueue_due(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    due = list(
        db.scalars(
            select(Schedule.id).where(Schedule.enabled.is_(True), Schedule.next_run_at <= now)
        )
    )
    created = 0
    for schedule_id in due:
        schedule = db.get(Schedule, schedule_id)
        if schedule is None or schedule.next_run_at is None or schedule.next_run_at > now:
            continue
        occurrence = schedule.next_run_at
        user = db.get(User, schedule.user_id)
        key = f"schedule:{schedule.id}:{occurrence.isoformat()}"
        run_id = None
        if user is not None and user.is_active:
            try:
                run = run_service.create_run(
                    db,
                    user,
                    list_id=schedule.list_id,
                    store_ids=[uuid.UUID(s) for s in schedule.store_ids] or None,
                    trigger=RunTrigger.SCHEDULE,
                    schedule_id=schedule.id,
                    idempotency_key=key,
                    allow_concurrent=True,
                )
                run_id = run.id
                created += 1
            except (ServiceError, IntegrityError) as exc:
                db.rollback()
                logger.warning(
                    "schedule %s occurrence %s skipped: %s", schedule_id, occurrence, exc
                )
        schedule = db.get(Schedule, schedule_id)
        if schedule is None:
            continue
        if run_id is not None:
            schedule.last_run_id = run_id
            schedule.last_run_at = now
        schedule.next_run_at = next_occurrence(schedule, max(now, occurrence))
        db.commit()
    return created


async def run_scheduler(stop: asyncio.Event) -> None:
    settings = get_settings()
    init_engine(settings)
    factory = session_factory()
    logger.info("scheduler ready")
    while not stop.is_set():
        try:
            with factory() as db:
                count = enqueue_due(db)
            if count:
                logger.info("enqueued %d scheduled run(s)", count)
        except Exception:
            logger.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_poll_seconds)
        except TimeoutError:
            pass


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    loop = asyncio.new_event_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        loop.run_until_complete(run_scheduler(stop))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
