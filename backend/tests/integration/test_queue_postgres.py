"""Queue guarantees that only PostgreSQL can prove (row locks, SKIP LOCKED, concurrent workers)."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import pytest
from sqlalchemy import select

from pricetracker.db.session import session_factory
from pricetracker.models import Run
from pricetracker.models.enums import RunStatus
from pricetracker.worker.queue import claim_next_run
from tests.conftest import create_user

pytestmark = pytest.mark.postgres


def _queue_runs(db: Any, count: int) -> list[uuid.UUID]:
    user = create_user(db, "fila")
    runs = [Run(user_id=user.id) for _ in range(count)]
    db.add_all(runs)
    db.commit()
    return [run.id for run in runs]


def test_claim_skips_a_run_locked_by_another_worker_instead_of_waiting(
    db: Any, settings: Any
) -> None:
    (run_id,) = _queue_runs(db, 1)
    factory = session_factory()
    holder = factory()
    holder.execute(select(Run).where(Run.id == run_id).with_for_update()).scalar_one()
    try:
        with factory() as other:
            started = time.monotonic()
            assert claim_next_run(other, "worker-b") is None
            assert time.monotonic() - started < 2
    finally:
        holder.rollback()
        holder.close()
    with factory() as other:
        assert claim_next_run(other, "worker-b") == run_id


def test_concurrent_workers_claim_each_run_exactly_once(db: Any, settings: Any) -> None:
    ids = _queue_runs(db, 12)
    factory = session_factory()
    claimed: list[uuid.UUID] = []
    guard = threading.Lock()

    def worker(name: str) -> None:
        while True:
            with factory() as session:
                run_id = claim_next_run(session, name)
            if run_id is None:
                return
            with guard:
                claimed.append(run_id)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(claimed) == sorted(ids)
    with factory() as session:
        statuses = set(session.scalars(select(Run.status)))
    assert statuses == {RunStatus.RUNNING.value}
