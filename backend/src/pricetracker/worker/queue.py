"""Durable job queue on the ``runs`` table.

Claiming is a single atomic ``UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP
LOCKED)`` on PostgreSQL, so several workers never take the same run. SQLite (dev
only) serialises writers, which gives the same guarantee for one process.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.models import Run, RunEvent, RunTarget
from pricetracker.models.enums import RunStatus, TargetStatus


def claim_next_run(db: Session, worker_id: str) -> uuid.UUID | None:
    candidate = (
        select(Run.id).where(Run.status == RunStatus.QUEUED.value).order_by(Run.created_at).limit(1)
    )
    if db.get_bind().dialect.name == "postgresql":
        candidate = candidate.with_for_update(skip_locked=True)
    now = utcnow()
    stmt = (
        update(Run)
        .where(Run.id == candidate.scalar_subquery(), Run.status == RunStatus.QUEUED.value)
        .values(
            status=RunStatus.RUNNING.value,
            worker_id=worker_id,
            heartbeat_at=now,
            attempt=Run.attempt + 1,
        )
        .returning(Run.id)
    )
    run_id = db.execute(stmt).scalar_one_or_none()
    db.commit()
    return run_id


def recover_stale_runs(db: Session, stale_after_seconds: float) -> list[uuid.UUID]:
    """Requeue runs whose worker stopped heart-beating (crash, container restart)."""
    cutoff = utcnow() - timedelta(seconds=stale_after_seconds)
    stale = list(
        db.scalars(
            select(Run.id).where(
                Run.status == RunStatus.RUNNING.value,
                (Run.heartbeat_at.is_(None)) | (Run.heartbeat_at < cutoff),
            )
        )
    )
    for run_id in stale:
        release_run(db, run_id, reason="worker parou de responder; retomando do ponto em que parou")
    return stale


def release_run(db: Session, run_id: uuid.UUID, reason: str) -> None:
    """Put a running run back in the queue without losing finished targets."""
    db.execute(
        update(RunTarget)
        .where(RunTarget.run_id == run_id, RunTarget.status == TargetStatus.RUNNING.value)
        .values(status=TargetStatus.PENDING.value)
    )
    db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == RunStatus.RUNNING.value)
        .values(status=RunStatus.QUEUED.value, worker_id=None)
    )
    db.add(RunEvent(run_id=run_id, level="warning", event="requeued", message=reason[:300]))
    db.commit()


def touch_heartbeat(db: Session, run_id: uuid.UUID) -> bool:
    """Update the heartbeat and return True when cancellation was requested."""
    run = db.get(Run, run_id)
    if run is None:
        return True
    run.heartbeat_at = utcnow()
    cancel = run.cancel_requested_at is not None
    db.commit()
    return cancel
