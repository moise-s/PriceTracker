"""Worker process: claims queued runs and executes them one at a time.

On start it requeues runs abandoned by a previous worker (crash or container
restart). On SIGTERM/SIGINT it stops claiming, cancels the in-flight run tasks and
puts that run back in the queue, so a restart resumes it without losing finished
targets.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import uuid
from pathlib import Path

from pricetracker.db.session import init_engine, session_factory
from pricetracker.logs import configure_logging
from pricetracker.settings import get_settings
from pricetracker.worker.executor import RunExecutor
from pricetracker.worker.queue import claim_next_run, recover_stale_runs, release_run

logger = logging.getLogger("pricetracker.worker")
HEARTBEAT_FILE = Path(
    os.environ.get(
        "PRICETRACKER_WORKER_HEARTBEAT_FILE",
        "/tmp/pricetracker-worker.alive",  # noqa: S108
    )
)


def _touch() -> None:
    try:
        HEARTBEAT_FILE.write_text(str(int(asyncio.get_event_loop().time())))
    except OSError:
        pass


async def run_worker(stop: asyncio.Event | None = None, once: bool = False) -> None:
    settings = get_settings()
    init_engine(settings)
    factory = session_factory()
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    stop = stop or asyncio.Event()
    with factory() as db:
        recovered = recover_stale_runs(db, settings.worker_stale_after_seconds)
    if recovered:
        logger.warning("requeued %d abandoned run(s)", len(recovered))
    logger.info("worker %s ready", worker_id)
    while not stop.is_set():
        _touch()
        with factory() as db:
            run_id = claim_next_run(db, worker_id)
            if run_id is None:
                recover_stale_runs(db, settings.worker_stale_after_seconds)
        if run_id is None:
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
            except TimeoutError:
                pass
            continue
        executor = RunExecutor(factory=factory, settings=settings, worker_id=worker_id)
        task = asyncio.create_task(executor.execute(run_id))
        stopper = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            stopper.cancel()
            try:
                status = task.result()
                logger.info("run %s finished: %s", run_id, status.value)
            except Exception:
                logger.exception("run %s crashed", run_id)
                with factory() as db:
                    release_run(db, run_id, reason="erro inesperado no worker; retomando")
        else:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception) as exc:
                logger.info("in-flight run stopped: %s", type(exc).__name__)
            with factory() as db:
                release_run(db, run_id, reason="worker desligado; busca devolvida à fila")
        if once:
            return


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    loop = asyncio.new_event_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        loop.run_until_complete(run_worker(stop))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
