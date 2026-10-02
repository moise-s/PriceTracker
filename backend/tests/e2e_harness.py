"""Deterministic backend for the browser end-to-end suite (web/e2e). Never used in production.

It serves the real FastAPI app against a throwaway SQLite database and runs an in-process worker
whose HTTP transport replays the sanitised fixtures in ``tests/fakes.py`` — no request leaves the
machine. A small control API under ``/__e2e`` (mounted only here) lets each scenario reset state,
create accounts, inject per-market faults, slow the fake sites down and age observations.

    cd backend && uv run python -m tests.e2e_harness --port 8765 --origin http://localhost:4173
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import tempfile
import threading
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select

from pricetracker import settings as settings_module
from pricetracker.adapters.base import AdapterContext, MarketAdapter, SearchOutcome, SearchQuery
from pricetracker.adapters.registry import get_adapter
from pricetracker.db.base import utcnow
from pricetracker.db.session import get_engine, session_factory
from pricetracker.llm.service import build_snippet
from pricetracker.models import Base, Observation, Profile, User
from pricetracker.models.enums import ExtractionMethod, Role
from pricetracker.seed import seed_all
from pricetracker.services import accounts
from pricetracker.worker.executor import RunExecutor
from pricetracker.worker.queue import claim_next_run
from tests.conftest import make_settings
from tests.fakes import combined_handler

logger = logging.getLogger("e2e")

MARKET_HOSTS = {
    "angeloni": {"super.angeloni.com.br"},
    "bistek": {"www.bistek.com.br"},
    "fort": {"fortatacadista.com.br", "www.fortatacadista.com.br"},
    "imperatriz": {"api.zoombox.com.br", "9zli2drdqe.execute-api.us-east-1.amazonaws.com"},
}
Fault = Literal["blocked", "timeout", "broken", "needs_llm"]
CHALLENGE_PAGE = (
    "<html><head><title>Just a moment...</title></head>"
    '<body><div id="cf-chl-widget">Checking your browser</div></body></html>'
)


class State:
    faults: dict[str, Fault] = {}  # noqa: RUF012
    latency_seconds: float = 0.0


def fixture_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    market = next((slug for slug, hosts in MARKET_HOSTS.items() if host in hosts), None)
    fault = State.faults.get(market or "")
    if State.latency_seconds:
        time.sleep(State.latency_seconds)
    if fault == "blocked":
        return httpx.Response(403, text=CHALLENGE_PAGE)
    if fault == "timeout":
        raise httpx.ReadTimeout("simulated timeout", request=request)
    if fault == "broken" and request.url.path != "/robots.txt":
        return httpx.Response(200, text="<html><body><main>layout novo</main></body></html>")
    return combined_handler()(request)


class LayoutChangedAdapter(MarketAdapter):
    """A storefront whose markup changed: deterministic extraction yields nothing, but a
    sanitised text snippet is available for the (optional) LLM fallback."""

    version = "e2e"
    strategy = "layout-changed"

    def __init__(self, real: MarketAdapter) -> None:
        self.key = real.key
        self.allowed_domains = real.allowed_domains

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        snippet = build_snippet([f"{query.terms[0]} — preço indisponível no novo layout"], 2000)
        return SearchOutcome(
            method=ExtractionMethod.DOM,
            needs_llm=True,
            llm_snippet=snippet,
            llm_source_url=f"https://{self.allowed_domains[0]}/busca",
            notes=["layout da página mudou; extração determinística sem resultados"],
        )


def adapter_factory(key: str) -> MarketAdapter:
    real = get_adapter(key)
    return LayoutChangedAdapter(real) if State.faults.get(key) == "needs_llm" else real


# --- worker ------------------------------------------------------------------------------------


# Held by the worker while it claims/executes a run and by /reset while it rebuilds the schema.
DB_LOCK = threading.Lock()


async def _worker_loop(stop: threading.Event) -> None:
    factory = session_factory()
    while not stop.is_set():
        try:
            with DB_LOCK:
                with factory() as db:
                    run_id = claim_next_run(db, "e2e-worker")
                if run_id is not None:
                    executor = RunExecutor(
                        factory=factory,
                        settings=settings_module.get_settings(),
                        worker_id="e2e-worker",
                        adapter_factory=adapter_factory,
                        transport=httpx.MockTransport(fixture_handler),
                    )
                    await executor.execute(run_id)
        except Exception:  # keep the harness worker alive whatever a scenario does
            logger.exception("worker iteration failed")
            run_id = None
        if run_id is None:
            await asyncio.sleep(0.2)


def start_worker() -> threading.Event:
    stop = threading.Event()
    thread = threading.Thread(target=lambda: asyncio.run(_worker_loop(stop)), daemon=True)
    thread.start()
    return stop


# --- control API -------------------------------------------------------------------------------


class UserIn(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    admin: bool = False
    onboarded: bool = True


class FaultsIn(BaseModel):
    faults: dict[str, Fault] = {}
    latency_ms: int = 0


class AgeIn(BaseModel):
    days: int
    username: str | None = None
    # Scale the aged prices (e.g. 1.08 = they were 8% higher back then) so history shows a trend.
    price_factor: Decimal = Decimal("1")


def reset_database() -> None:
    with DB_LOCK:
        engine = get_engine()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with session_factory()() as db:
            seed_all(db)
        State.faults = {}
        State.latency_seconds = 0.0


def control_app() -> FastAPI:
    control = FastAPI(openapi_url=None, docs_url=None)

    @control.post("/reset")
    def reset() -> dict[str, bool]:
        reset_database()
        return {"ok": True}

    @control.post("/setup-code")
    def setup_code() -> dict[str, str]:
        with session_factory()() as db:
            return {"code": accounts.generate_setup_code(db)}

    @control.post("/users")
    def create_user(body: UserIn) -> dict[str, str]:
        with session_factory()() as db:
            account = accounts._create_user(
                db,
                username=body.username,
                display_name=body.display_name or body.username.title(),
                password=body.password,
                role=Role.ADMIN if body.admin else Role.USER,
            )
            if body.onboarded:
                profile = db.scalar(select(Profile).where(Profile.user_id == account.user.id))
                assert profile is not None
                profile.onboarding_completed_at = utcnow()
            db.commit()
            return {"id": str(account.user.id)}

    @control.post("/faults")
    def faults(body: FaultsIn) -> dict[str, Any]:
        State.faults = dict(body.faults)
        State.latency_seconds = body.latency_ms / 1000
        return {"faults": State.faults, "latency_ms": body.latency_ms}

    @control.post("/age-observations")
    def age(body: AgeIn) -> dict[str, int]:
        with session_factory()() as db:
            rows = db.scalars(select(Observation)).all()
            if body.username:
                user_id = db.scalar(select(User.id).where(User.username == body.username))
                rows = [row for row in rows if row.user_id == user_id]
            for row in rows:
                row.observed_at = row.observed_at - timedelta(days=body.days)
                for field in ("regular_price", "promo_price", "club_price", "unit_price"):
                    value = getattr(row, field)
                    if value is not None and body.price_factor != 1:
                        setattr(row, field, (value * body.price_factor).quantize(Decimal("0.01")))
            db.commit()
            return {"aged": len(rows)}

    return control


def build(origin: str, data_dir: Path) -> FastAPI:
    settings = make_settings(
        data_dir,
        environment="development",
        public_origin=origin,
        cookie_secure=False,
        setup_require_code=True,
        log_level="WARNING",
        http_max_retries=0,
        target_timeout_seconds=15.0,
    )
    settings_module.configure_settings(settings)
    from pricetracker.api.app import create_app

    app = create_app()
    reset_database()
    app.mount("/__e2e", control_app())
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--origin", default="http://localhost:4173")
    args = parser.parse_args()
    data_dir = Path(tempfile.mkdtemp(prefix="pricetracker-e2e-"))
    app = build(args.origin, data_dir)
    stop = start_worker()
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        stop.set()


if __name__ == "__main__":
    main()
