"""Executes one run: adapters -> deterministic matching -> optional LLM -> persistence.

Every target ends in exactly one typed state. Nothing is swallowed: an exception
in one target becomes that target's ``adapter_error``/``blocked``/``timeout`` and the
run continues; the run's final status is derived from the counts.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pricetracker.adapters.base import (
    AdapterContext,
    MarketAdapter,
    SearchOutcome,
    SearchQuery,
    StoreContext,
)
from pricetracker.adapters.cache import document_cache, robots_loader, robots_saver
from pricetracker.adapters.errors import AdapterError
from pricetracker.adapters.http import (
    Blocked,
    FetchError,
    FetchTimeout,
    NotAllowedHost,
    PoliteClient,
    UpstreamError,
)
from pricetracker.adapters.registry import get_adapter
from pricetracker.db.base import utcnow
from pricetracker.domain.listing import Listing, listing_to_dict
from pricetracker.domain.matching import MatchResult, MatchSpec, Pins, select_best
from pricetracker.domain.pricing import OfferPricing, unit_price_for
from pricetracker.domain.quality import assess_outlier
from pricetracker.llm.providers import LlmError
from pricetracker.llm.service import LlmService
from pricetracker.logs import bound, log_event
from pricetracker.models import (
    AdapterVersion,
    Candidate,
    Market,
    Observation,
    Product,
    ProductMarketPin,
    Run,
    RunEvent,
    RunTarget,
    Store,
)
from pricetracker.models.enums import (
    Availability,
    PinDecision,
    ReviewStatus,
    RunStatus,
    TargetStatus,
)
from pricetracker.services.catalog import product_match_spec
from pricetracker.services.runs import final_status, target_counts
from pricetracker.settings import Settings
from pricetracker.worker.queue import touch_heartbeat

logger = logging.getLogger(__name__)

MAX_CANDIDATES_STORED = 20


@dataclass(frozen=True)
class TargetPlan:
    id: uuid.UUID
    product_id: uuid.UUID
    store_id: uuid.UUID
    market_id: uuid.UUID


@dataclass(frozen=True)
class MarketPlan:
    id: uuid.UUID
    slug: str
    adapter_key: str
    allowed_domains: tuple[str, ...]


@dataclass
class TargetResult:
    status: TargetStatus
    method: str | None = None
    error_type: str | None = None
    error_detail: str | None = None
    listings: list[Listing] = field(default_factory=list)
    evaluations: list[tuple[Listing, MatchResult]] = field(default_factory=list)
    best_index: int | None = None
    llm_needed: bool = False
    llm_used: bool = False
    query_used: str | None = None
    notes: list[str] = field(default_factory=list)
    duration_ms: int = 0
    requests: int = 0


@dataclass
class RunPlan:
    run_id: uuid.UUID
    user_id: uuid.UUID
    targets: list[TargetPlan]
    specs: dict[uuid.UUID, MatchSpec]
    stores: dict[uuid.UUID, StoreContext]
    markets: dict[uuid.UUID, MarketPlan]
    pins: dict[tuple[uuid.UUID, uuid.UUID], Pins]
    preferred: dict[tuple[uuid.UUID, uuid.UUID], tuple[str, ...]]
    cancel_requested: bool
    allow_llm: bool
    debug: bool


def _scope_key(market_id: uuid.UUID, store: StoreContext) -> str:
    return f"{market_id}:{json.dumps(store.price_context, sort_keys=True)}"


class RunExecutor:
    def __init__(
        self,
        *,
        factory: sessionmaker[Session],
        settings: Settings,
        worker_id: str,
        adapter_factory: Callable[[str], MarketAdapter] = get_adapter,
        transport: httpx.AsyncBaseTransport | None = None,
        llm_factory: Callable[[Session], LlmService] | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self.factory = factory
        self.settings = settings
        self.worker_id = worker_id
        self.adapter_factory = adapter_factory
        self.transport = transport
        self.llm_factory = llm_factory or (lambda db: LlmService(db, settings))
        self.sleep = sleep
        self._cancelled = asyncio.Event()
        self._scope_results: dict[tuple[str, uuid.UUID], asyncio.Future[TargetResult]] = {}

    # --- loading -------------------------------------------------------------------

    def _load(self, run_id: uuid.UUID) -> RunPlan | None:
        with self.factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                return None
            targets = list(
                db.scalars(
                    select(RunTarget).where(
                        RunTarget.run_id == run_id,
                        RunTarget.status.in_(
                            [TargetStatus.PENDING.value, TargetStatus.RUNNING.value]
                        ),
                    )
                )
            )
            product_ids = {t.product_id for t in targets}
            store_ids = {t.store_id for t in targets}
            products = {
                p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))
            }
            stores = {s.id: s for s in db.scalars(select(Store).where(Store.id.in_(store_ids)))}
            markets = {
                m.id: m
                for m in db.scalars(
                    select(Market).where(Market.id.in_({s.market_id for s in stores.values()}))
                )
            }
            pins: dict[tuple[uuid.UUID, uuid.UUID], Pins] = {}
            preferred: dict[tuple[uuid.UUID, uuid.UUID], list[str]] = {}
            for pin in db.scalars(
                select(ProductMarketPin).where(
                    ProductMarketPin.user_id == run.user_id,
                    ProductMarketPin.product_id.in_(product_ids),
                )
            ):
                key = (pin.product_id, pin.market_id)
                current = pins.get(key, Pins())
                if pin.decision == PinDecision.ACCEPT.value:
                    pins[key] = Pins(current.accepted | {pin.listing_key}, current.rejected)
                    if pin.url is not None:
                        preferred.setdefault(key, []).append(pin.url)
                else:
                    pins[key] = Pins(current.accepted, current.rejected | {pin.listing_key})
            recent = db.execute(
                select(Observation.product_id, Observation.market_id, Observation.url)
                .where(
                    Observation.user_id == run.user_id,
                    Observation.product_id.in_(product_ids),
                    Observation.url.is_not(None),
                    Observation.observed_at > utcnow() - timedelta(days=60),
                )
                .order_by(Observation.observed_at.desc())
                .limit(500)
            ).all()
            for product_id, market_id, url in recent:
                if url is None:
                    continue
                bucket = preferred.setdefault((product_id, market_id), [])
                if url not in bucket and len(bucket) < 3:
                    bucket.append(url)
            plan = RunPlan(
                run_id=run.id,
                user_id=run.user_id,
                targets=[TargetPlan(t.id, t.product_id, t.store_id, t.market_id) for t in targets],
                specs={pid: product_match_spec(p) for pid, p in products.items()},
                stores={
                    sid: StoreContext(
                        store_id=str(s.id),
                        slug=s.slug,
                        name=s.name,
                        external_id=s.external_id,
                        price_context=dict(s.price_context or {}),
                        postal_code=s.postal_code,
                        city=s.city,
                    )
                    for sid, s in stores.items()
                },
                markets={
                    mid: MarketPlan(m.id, m.slug, m.adapter_key, tuple(m.allowed_domains or []))
                    for mid, m in markets.items()
                },
                pins=pins,
                preferred={k: tuple(v) for k, v in preferred.items()},
                cancel_requested=run.cancel_requested_at is not None,
                allow_llm=bool((run.params or {}).get("allow_llm", True)),
                debug=bool((run.params or {}).get("debug", False)),
            )
            if run.started_at is None:
                run.started_at = utcnow()
            run.status = RunStatus.RUNNING.value
            run.heartbeat_at = utcnow()
            db.add(
                RunEvent(
                    run_id=run.id,
                    event="started",
                    message=f"Coleta iniciada ({len(targets)} alvo(s) pendentes).",
                )
            )
            db.commit()
            return plan

    # --- execution --------------------------------------------------------------------

    async def execute(self, run_id: uuid.UUID) -> RunStatus:
        plan = self._load(run_id)
        if plan is None:
            return RunStatus.FAILED
        with bound(run_id=str(run_id)):
            if plan.cancel_requested:
                self._cancelled.set()
            heartbeat = asyncio.create_task(self._heartbeat(run_id))
            clients: dict[uuid.UUID, PoliteClient] = {}
            adapters: dict[uuid.UUID, MarketAdapter] = {}
            try:
                global_limit = asyncio.Semaphore(max(1, self.settings.worker_concurrency))
                market_limits = {mid: asyncio.Semaphore(2) for mid in plan.markets}
                for mid, market in plan.markets.items():
                    adapters[mid] = self.adapter_factory(market.adapter_key)
                    domains = market.allowed_domains or adapters[mid].allowed_domains
                    clients[mid] = PoliteClient(
                        allowed_domains=domains,
                        settings=self.settings,
                        transport=self.transport,
                        robots_loader=robots_loader(self.factory),
                        robots_saver=robots_saver(self.factory, self.settings),
                        sleep=self.sleep,
                    )
                cache = document_cache(self.factory)

                async def run_target(target: TargetPlan) -> None:
                    async with global_limit, market_limits[target.market_id]:
                        await self._process(
                            plan,
                            target,
                            adapters[target.market_id],
                            clients[target.market_id],
                            cache,
                        )

                await asyncio.gather(*(run_target(t) for t in plan.targets))
            finally:
                heartbeat.cancel()
                for client in clients.values():
                    await client.aclose()
            return self._finalize(run_id)

    async def _heartbeat(self, run_id: uuid.UUID) -> None:
        while True:
            await asyncio.sleep(self.settings.worker_heartbeat_seconds)
            try:
                with self.factory() as db:
                    if touch_heartbeat(db, run_id):
                        self._cancelled.set()
            except Exception:  # pragma: no cover - heartbeat must never kill a run
                logger.exception("heartbeat failed")

    def _mark_running(self, target_id: uuid.UUID) -> bool:
        with self.factory() as db:
            target = db.get(RunTarget, target_id)
            if target is None:
                return False
            run = db.get(Run, target.run_id)
            if run is not None and run.cancel_requested_at is not None:
                self._cancelled.set()
            if self._cancelled.is_set():
                target.status = TargetStatus.CANCELLED.value
                target.finished_at = utcnow()
                db.commit()
                return False
            target.status = TargetStatus.RUNNING.value
            target.attempts += 1
            target.started_at = utcnow()
            db.commit()
            return True

    async def _process(
        self,
        plan: RunPlan,
        target: TargetPlan,
        adapter: MarketAdapter,
        client: PoliteClient,
        cache: Any,
    ) -> None:
        if not self._mark_running(target.id):
            return
        store = plan.stores[target.store_id]
        spec = plan.specs[target.product_id]
        market = plan.markets[target.market_id]
        with bound(target_id=str(target.id), market=market.slug):
            scope = (_scope_key(target.market_id, store), target.product_id)
            future = self._scope_results.get(scope)
            if future is None:
                future = asyncio.get_running_loop().create_future()
                self._scope_results[scope] = future
                try:
                    result = await self._search_and_match(
                        plan, target, adapter, client, cache, store, spec
                    )
                except Exception as exc:  # defensive: a bug must not abort the run
                    logger.exception("unexpected executor error")
                    result = TargetResult(
                        TargetStatus.ADAPTER_ERROR,
                        error_type="internal_error",
                        error_detail=str(exc)[:300],
                    )
                future.set_result(result)
            else:
                shared = await asyncio.shield(future)
                result = TargetResult(
                    **{
                        **shared.__dict__,
                        "notes": [*shared.notes, "mesmo contexto de preço de outra filial"],
                    }
                )
            try:
                self._persist(plan, target, adapter, market, spec, result)
            except Exception:
                logger.exception("failed to persist target result")
                self._persist_failure(plan, target, "falha interna ao gravar o resultado")

    async def _search_and_match(
        self,
        plan: RunPlan,
        target: TargetPlan,
        adapter: MarketAdapter,
        client: PoliteClient,
        cache: Any,
        store: StoreContext,
        spec: MatchSpec,
    ) -> TargetResult:
        started = time.monotonic()
        before = client.request_count
        key = (target.product_id, target.market_id)
        pins = plan.pins.get(key, Pins())
        query = SearchQuery(
            product_name=spec.search_terms[0],
            terms=list(spec.search_terms),
            spec=spec,
            preferred_urls=plan.preferred.get(key, ()),
        )
        ctx = AdapterContext(client=client, store=store, cache=cache, debug=plan.debug)
        result: TargetResult
        try:
            outcome = await asyncio.wait_for(
                adapter.search(ctx, query), timeout=self.settings.target_timeout_seconds
            )
        except Blocked as exc:
            result = TargetResult(
                TargetStatus.BLOCKED, error_type=exc.error_type, error_detail=str(exc)
            )
        except (FetchTimeout, TimeoutError) as exc:
            result = TargetResult(
                TargetStatus.TIMEOUT,
                error_type="timeout",
                error_detail=str(exc) or "tempo esgotado",
            )
        except (UpstreamError, NotAllowedHost) as exc:
            result = TargetResult(
                TargetStatus.ADAPTER_ERROR, error_type=exc.error_type, error_detail=str(exc)
            )
        except FetchError as exc:
            result = TargetResult(
                TargetStatus.ADAPTER_ERROR, error_type=exc.error_type, error_detail=str(exc)
            )
        except AdapterError as exc:
            result = TargetResult(
                TargetStatus.ADAPTER_ERROR, error_type=exc.error_type, error_detail=str(exc)
            )
        except Exception as exc:
            logger.error("adapter crashed: %s", traceback.format_exc(limit=5))
            result = TargetResult(
                TargetStatus.ADAPTER_ERROR,
                error_type="adapter_crash",
                error_detail=f"{type(exc).__name__}: {exc}"[:300],
            )
        else:
            result = await self._classify(
                plan, target, market_domains(adapter, client), outcome, spec, pins
            )
        result.duration_ms = int((time.monotonic() - started) * 1000)
        result.requests = client.request_count - before
        return result

    async def _classify(
        self,
        plan: RunPlan,
        target: TargetPlan,
        domains: list[str],
        outcome: SearchOutcome,
        spec: MatchSpec,
        pins: Pins,
    ) -> TargetResult:
        listings = list(outcome.listings)
        result = TargetResult(
            TargetStatus.NOT_FOUND,
            method=outcome.method.value if outcome.method else None,
            query_used=outcome.query_used,
            notes=list(outcome.notes),
        )
        if not listings and outcome.needs_llm:
            result.llm_needed = True
            llm_listings, error = await self._llm_fallback(plan, target, domains, outcome)
            if llm_listings is None:
                result.status = TargetStatus.NEEDS_LLM
                result.error_type = error[0]
                result.error_detail = error[1]
                return result
            listings = llm_listings
            result.llm_used = True
            result.method = "llm"
            result.notes = list(outcome.notes)
        evaluations, best = select_best(listings, spec, pins)
        result.listings = listings
        result.evaluations = evaluations
        result.best_index = best
        if best is not None:
            result.status = TargetStatus.FOUND
            result.method = listings[best].method.value
            return result
        accepted = [(listing, match) for listing, match in evaluations if match.accepted]
        if accepted:
            if all(listing.availability == Availability.OUT_OF_STOCK for listing, _ in accepted):
                result.status = TargetStatus.UNAVAILABLE
            else:
                result.status = TargetStatus.NO_PRICE
            return result
        priced = [listing for listing in listings if listing.price is not None]
        out_of_stock = [
            listing for listing in listings if listing.availability == Availability.OUT_OF_STOCK
        ]
        if len(listings) >= 3 and not priced and not out_of_stock:
            result.status = TargetStatus.ADAPTER_ERROR
            result.error_type = "no_prices_extracted"
            result.error_detail = (
                f"nenhum preço extraído de {len(listings)} resultados; possível mudança no site"
            )
            return result
        result.status = TargetStatus.NOT_FOUND
        coverage = [n for n in outcome.notes if "apenas" in n]
        result.error_detail = coverage[0] if coverage else None
        return result

    async def _llm_fallback(
        self, plan: RunPlan, target: TargetPlan, domains: list[str], outcome: SearchOutcome
    ) -> tuple[list[Listing] | None, tuple[str, str]]:
        if not plan.allow_llm:
            return None, ("llm_disabled", "fallback por IA desativado nesta busca")
        if not outcome.llm_snippet or not outcome.llm_source_url:
            return None, ("llm_no_snippet", "sem conteúdo para o fallback por IA")
        with self.factory() as db:
            run = db.get(Run, plan.run_id)
            budget = self.settings.llm_max_calls_per_run
            if run is not None and run.llm_calls >= budget:
                return None, (
                    "llm_budget",
                    f"orçamento de {budget} chamadas de IA por busca atingido",
                )
            service = self.llm_factory(db)
            status = service.status()
            if not status.available:
                return None, (
                    "llm_unavailable",
                    f"extração determinística falhou e não há IA configurada ({status.reason})",
                )
            if run is not None:
                run.llm_calls += 1
                db.commit()
            try:
                listings, rejected = service.extract_listings(
                    snippet=outcome.llm_snippet,
                    source_url=outcome.llm_source_url,
                    allowed_domains=domains,
                    run_id=plan.run_id,
                    target_id=target.id,
                )
            except LlmError as exc:
                return None, (exc.error_type, f"fallback por IA falhou: {exc}")
        if rejected:
            outcome.notes.append(
                f"{len(rejected)} item(ns) da IA descartados por não constarem no conteúdo"
            )
        return listings, ("", "")

    # --- persistence ---------------------------------------------------------------------

    def _persist(
        self,
        plan: RunPlan,
        target: TargetPlan,
        adapter: MarketAdapter,
        market: MarketPlan,
        spec: MatchSpec,
        result: TargetResult,
    ) -> None:
        now = utcnow()
        with self.factory() as db:
            row = db.get(RunTarget, target.id)
            if row is None:
                return
            version = self._adapter_version(db, market, adapter)
            ordered = sorted(
                range(len(result.evaluations)),
                key=lambda i: (
                    0 if i == result.best_index else 1,
                    0 if result.evaluations[i][1].accepted else 1,
                    -result.evaluations[i][1].score,
                ),
            )[:MAX_CANDIDATES_STORED]
            for rank, index in enumerate(ordered):
                listing, match = result.evaluations[index]
                db.add(
                    Candidate(
                        target_id=row.id,
                        rank=rank,
                        match_score=match.score,
                        accepted=match.accepted,
                        chosen=index == result.best_index,
                        reasons=match.reasons,
                        raw=_small_raw(listing),
                        **_offer_fields(listing),
                    )
                )
            if result.best_index is not None or result.status == TargetStatus.UNAVAILABLE:
                chosen_index = result.best_index
                if chosen_index is None:
                    chosen_index = next(
                        i for i, (_, m) in enumerate(result.evaluations) if m.accepted
                    )
                listing, match = result.evaluations[chosen_index]
                fields = _offer_fields(listing)
                outlier = self._assess(db, plan.user_id, target, fields)
                raw = _small_raw(listing)
                digest = hashlib.sha256(
                    json.dumps(raw, sort_keys=True, default=str).encode()
                ).hexdigest()
                key = hashlib.sha256(
                    f"{plan.run_id}|{target.product_id}|{target.store_id}".encode()
                ).hexdigest()
                existing = db.scalar(select(Observation).where(Observation.idempotency_key == key))
                if existing is None:
                    db.add(
                        Observation(
                            user_id=plan.user_id,
                            run_id=plan.run_id,
                            target_id=row.id,
                            product_id=target.product_id,
                            market_id=target.market_id,
                            store_id=target.store_id,
                            adapter_version=version,
                            observed_at=now,
                            match_score=match.score,
                            raw_payload=raw,
                            raw_sha256=digest,
                            is_outlier=outlier[0],
                            outlier_reason=outlier[1],
                            review_status=ReviewStatus.FLAGGED.value
                            if outlier[0]
                            else ReviewStatus.OK.value,
                            idempotency_key=key,
                            **fields,
                        )
                    )
                    if outlier[0]:
                        db.add(
                            RunEvent(
                                run_id=plan.run_id,
                                target_id=row.id,
                                level="warning",
                                event="outlier",
                                message=(outlier[1] or "")[:300],
                            )
                        )
            row.status = result.status.value
            row.finished_at = now
            row.duration_ms = result.duration_ms
            row.method = result.method
            row.adapter_version = version
            row.search_query = (result.query_used or "")[:200] or None
            row.error_type = result.error_type or None
            row.error_detail = (result.error_detail or "")[:500] or None
            row.candidate_count = len(result.listings)
            row.llm_needed = result.llm_needed
            row.llm_used = result.llm_used
            row.diagnostics = {"requests": result.requests, "notes": result.notes[:10]}
            run = db.get(Run, plan.run_id)
            if run is not None:
                run.done_targets = (run.done_targets or 0) + 1
                run.heartbeat_at = now
            if result.status.is_failure:
                db.add(
                    RunEvent(
                        run_id=plan.run_id,
                        target_id=row.id,
                        level="warning",
                        event=result.status.value,
                        message=f"{market.slug}: {result.error_detail or result.status.value}"[
                            :300
                        ],
                    )
                )
            db.commit()
        log_event(
            logger,
            logging.INFO if not result.status.is_failure else logging.WARNING,
            "target finished",
            status=result.status.value,
            method=result.method,
            candidates=len(result.listings),
            duration_ms=result.duration_ms,
            requests=result.requests,
            error_type=result.error_type,
        )

    def _persist_failure(self, plan: RunPlan, target: TargetPlan, detail: str) -> None:
        with self.factory() as db:
            row = db.get(RunTarget, target.id)
            if row is None:
                return
            row.status = TargetStatus.ADAPTER_ERROR.value
            row.error_type = "internal_error"
            row.error_detail = detail
            row.finished_at = utcnow()
            run = db.get(Run, plan.run_id)
            if run is not None:
                run.done_targets = (run.done_targets or 0) + 1
            db.commit()

    def _adapter_version(self, db: Session, market: MarketPlan, adapter: MarketAdapter) -> str:
        found = db.scalar(
            select(AdapterVersion).where(
                AdapterVersion.market_id == market.id, AdapterVersion.version == adapter.version
            )
        )
        if found is None:
            db.add(
                AdapterVersion(
                    market_id=market.id,
                    adapter_key=adapter.key,
                    version=adapter.version,
                    strategy=adapter.strategy,
                    config=adapter.describe(),
                )
            )
            db.flush()
        return adapter.version

    def _assess(
        self, db: Session, user_id: uuid.UUID, target: TargetPlan, fields: dict[str, Any]
    ) -> tuple[bool, str | None]:
        unit_price = fields.get("unit_price")
        unit = fields.get("unit_price_unit")
        if unit_price is None or unit is None:
            return False, None
        history = [
            value
            for (value,) in db.execute(
                select(Observation.unit_price)
                .where(
                    Observation.user_id == user_id,
                    Observation.product_id == target.product_id,
                    Observation.store_id == target.store_id,
                    Observation.unit_price.is_not(None),
                    Observation.review_status != ReviewStatus.REJECTED.value,
                )
                .order_by(Observation.observed_at.desc())
                .limit(10)
            ).all()
        ]
        peers = [
            value
            for (value,) in db.execute(
                select(Observation.unit_price).where(
                    Observation.user_id == user_id,
                    Observation.product_id == target.product_id,
                    Observation.store_id != target.store_id,
                    Observation.unit_price.is_not(None),
                    Observation.unit_price_unit == unit,
                    Observation.observed_at > utcnow() - timedelta(days=7),
                )
            ).all()
        ]
        from pricetracker.models.enums import Unit

        assessment = assess_outlier(
            unit_price,
            Unit(unit),
            [h for h in history if h is not None],
            [p for p in peers if p is not None],
        )
        return assessment.is_outlier, assessment.reason

    def _finalize(self, run_id: uuid.UUID) -> RunStatus:
        with self.factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                return RunStatus.FAILED
            if self._cancelled.is_set() or run.cancel_requested_at is not None:
                for target in db.scalars(select(RunTarget).where(RunTarget.run_id == run_id)):
                    if not TargetStatus(target.status).is_terminal:
                        target.status = TargetStatus.CANCELLED.value
                        target.finished_at = utcnow()
                db.flush()
            counts = target_counts(db, run_id)
            pending = counts.get(TargetStatus.PENDING.value, 0) + counts.get(
                TargetStatus.RUNNING.value, 0
            )
            if pending:
                # Should not happen; keep the run resumable rather than marking success.
                run.status = RunStatus.QUEUED.value
                db.commit()
                return RunStatus.QUEUED
            status = final_status(
                counts, run.cancel_requested_at is not None or self._cancelled.is_set()
            )
            run.status = status.value
            run.counts = counts
            run.done_targets = sum(counts.values())
            run.finished_at = utcnow()
            failures = {k: v for k, v in counts.items() if TargetStatus(k).is_failure}
            run.error_summary = (
                ", ".join(f"{v} {k}" for k, v in failures.items())[:500] if failures else None
            )
            db.add(
                RunEvent(
                    run_id=run_id,
                    level="info" if status == RunStatus.SUCCESS else "warning",
                    event="finished",
                    message=f"Busca terminou como {status.value}: "
                    + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())),
                )
            )
            db.commit()
            log_event(logger, logging.INFO, "run finished", status=status.value, counts=counts)
        if status in (RunStatus.SUCCESS, RunStatus.PARTIAL):
            self._evaluate_alerts(run_id)
        return status

    def _evaluate_alerts(self, run_id: uuid.UUID) -> None:
        """Price alerts are a side effect: a failure here never changes the run's outcome."""
        from pricetracker.services import alerts

        try:
            with self.factory() as db:
                created = alerts.evaluate_run(db, run_id)
            if created:
                log_event(logger, logging.INFO, "price alerts triggered", count=created)
        except Exception:
            logger.exception("price alert evaluation failed")


def market_domains(adapter: MarketAdapter, client: PoliteClient) -> list[str]:
    return list(client.allowed_domains or adapter.allowed_domains)


def _offer_fields(listing: Listing) -> dict[str, Any]:
    package = listing.effective_package
    pricing = OfferPricing(
        sale_unit=listing.sale_unit,
        price=listing.price,
        regular_price=listing.regular_price,
        club_price=listing.club_price,
        quantity_min=listing.quantity_min,
        quantity_price=listing.quantity_price,
        quantity_mode=listing.quantity_mode,
        package_measure=package.measure,
        package_count=package.count,
        piece_weight_kg=listing.piece_weight_kg,
    )
    selling = listing.price if listing.price is not None else listing.regular_price
    unit_price, unit = unit_price_for(pricing, selling) if selling is not None else (None, None)
    measure = package.measure
    return {
        "title": listing.title[:300],
        "brand": (listing.brand or None) and listing.brand[:120],
        "url": listing.url,
        "external_id": listing.external_id,
        "sku": listing.sku,
        "gtin": listing.gtin,
        "package_quantity": measure.quantity
        if measure
        else (Decimal(package.count) if package.count else None),
        "package_unit": measure.unit.value if measure else ("un" if package.count else None),
        "sold_by": listing.sold_by.value,
        "unit_multiplier": listing.piece_weight_kg,
        "regular_price": listing.base_price,
        "promo_price": listing.promo_price,
        "club_price": listing.club_price,
        "club_label": listing.club_label,
        "quantity_min": listing.quantity_min,
        "quantity_price": listing.quantity_price,
        "quantity_mode": listing.quantity_mode,
        "extra_prices": listing.extra_prices,
        "unit_price": unit_price,
        "unit_price_unit": unit.value if unit else None,
        "availability": listing.availability.value,
        "image_url": listing.image_url,
        "method": listing.method.value,
        "confidence": listing.confidence,
    }


def _small_raw(listing: Listing) -> dict[str, Any]:
    data = listing_to_dict(listing)
    raw = data.pop("raw", {}) or {}
    return {"listing": data, "source": raw}
