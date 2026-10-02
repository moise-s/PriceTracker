"""Collection runs: creation, progress, cancellation and retry of failed targets."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pricetracker.db.base import utcnow
from pricetracker.models import (
    ListItem,
    Market,
    Product,
    Run,
    RunEvent,
    RunTarget,
    ShoppingList,
    Store,
    User,
)
from pricetracker.models.enums import (
    FAILURE_STATES,
    LEGITIMATE_STATES,
    RunStatus,
    RunTrigger,
    TargetStatus,
)
from pricetracker.services import catalog, profile
from pricetracker.services.errors import Conflict, NotFound, ValidationFailed

ACTIVE_STATUSES = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)


def _resolve_products(
    db: Session, user: User, shopping_list: ShoppingList | None, product_ids: list[uuid.UUID] | None
) -> list[Product]:
    if shopping_list is not None:
        items = db.scalars(
            select(ListItem)
            .where(ListItem.list_id == shopping_list.id)
            .options(selectinload(ListItem.product))
        )
        products = [item.product for item in items if item.product.is_active]
    else:
        products = catalog.list_products(db, user, include_inactive=False)
    if product_ids:
        wanted = set(product_ids)
        owned = {p.id for p in catalog.list_products(db, user)}
        if not wanted <= owned:
            raise NotFound("Produto não encontrado.")
        products = [p for p in products if p.id in wanted]
    return products


def _resolve_stores(db: Session, user: User, store_ids: list[uuid.UUID] | None) -> list[Store]:
    if not store_ids:
        store_ids = list(profile.selections(db, user.id).keys())
    if not store_ids:
        raise ValidationFailed("Escolha pelo menos um mercado ou filial.", code="no_stores")
    stores = list(
        db.scalars(
            select(Store)
            .join(Market)
            .where(Store.id.in_(store_ids), Store.is_active.is_(True), Market.enabled.is_(True))
        )
    )
    if len(stores) != len(set(store_ids)):
        raise ValidationFailed(
            "Há lojas inválidas ou desativadas na seleção.", code="invalid_store"
        )
    return stores


def create_run(
    db: Session,
    user: User,
    *,
    list_id: uuid.UUID | None = None,
    store_ids: list[uuid.UUID] | None = None,
    product_ids: list[uuid.UUID] | None = None,
    trigger: RunTrigger = RunTrigger.MANUAL,
    schedule_id: uuid.UUID | None = None,
    parent_run_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    options: dict[str, Any] | None = None,
    pairs: list[tuple[uuid.UUID, uuid.UUID]] | None = None,
    allow_concurrent: bool = False,
) -> Run:
    if idempotency_key:
        existing = db.scalar(select(Run).where(Run.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    if not allow_concurrent:
        active = db.scalar(
            select(Run).where(Run.user_id == user.id, Run.status.in_(ACTIVE_STATUSES)).limit(1)
        )
        if active is not None:
            raise Conflict(
                "Já existe uma busca em andamento.",
                code="run_in_progress",
                details={"run_id": str(active.id)},
            )
    shopping_list = None
    if pairs is None:
        shopping_list = (
            catalog.get_list(db, user, list_id) if list_id else catalog.default_list(db, user)
        )
        products = _resolve_products(db, user, shopping_list, product_ids)
        stores = _resolve_stores(db, user, store_ids)
        if not products:
            raise ValidationFailed("A lista não tem produtos ativos.", code="empty_list")
        pairs = [(p.id, s.id) for p in products for s in stores]
        store_by_id = {s.id: s for s in stores}
    else:
        # A retry must respect availability just like a new collection.
        _resolve_stores(db, user, list({s for _, s in pairs}))
        store_by_id = {
            s.id: s for s in db.scalars(select(Store).where(Store.id.in_({s for _, s in pairs})))
        }
    run = Run(
        user_id=user.id,
        list_id=shopping_list.id if shopping_list else list_id,
        schedule_id=schedule_id,
        parent_run_id=parent_run_id,
        trigger=trigger.value,
        status=RunStatus.QUEUED.value,
        idempotency_key=idempotency_key,
        params={
            "store_ids": sorted({str(s) for _, s in pairs}),
            "product_ids": sorted({str(p) for p, _ in pairs}),
            **(options or {}),
        },
        total_targets=len(pairs),
    )
    db.add(run)
    db.flush()
    for product_id, store_id in pairs:
        db.add(
            RunTarget(
                run_id=run.id,
                user_id=user.id,
                product_id=product_id,
                market_id=store_by_id[store_id].market_id,
                store_id=store_id,
            )
        )
    db.add(
        RunEvent(run_id=run.id, event="queued", message=f"Busca criada com {len(pairs)} alvo(s).")
    )
    db.commit()
    return run


def get_run(db: Session, user: User, run_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.user_id != user.id:
        raise NotFound("Busca não encontrada.")
    return run


def list_runs(db: Session, user: User, limit: int = 20) -> list[Run]:
    return list(
        db.scalars(
            select(Run).where(Run.user_id == user.id).order_by(Run.created_at.desc()).limit(limit)
        )
    )


def target_counts(db: Session, run_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(RunTarget.status, func.count())
        .where(RunTarget.run_id == run_id)
        .group_by(RunTarget.status)
    ).all()
    return {status: int(count) for status, count in rows}


def final_status(counts: dict[str, int], cancel_requested: bool) -> RunStatus:
    """success only if nothing failed; partial if some failed; failed if nothing legitimate."""
    legit = sum(counts.get(s.value, 0) for s in LEGITIMATE_STATES)
    failures = sum(counts.get(s.value, 0) for s in FAILURE_STATES)
    if cancel_requested and counts.get(TargetStatus.CANCELLED.value, 0):
        return RunStatus.CANCELLED
    if failures == 0 and legit > 0:
        return RunStatus.SUCCESS
    if legit == 0:
        return RunStatus.FAILED
    return RunStatus.PARTIAL


def cancel_run(db: Session, user: User, run_id: uuid.UUID) -> Run:
    run = get_run(db, user, run_id)
    if RunStatus(run.status).is_terminal:
        return run
    run.cancel_requested_at = run.cancel_requested_at or utcnow()
    if run.status == RunStatus.QUEUED.value:
        for target in db.scalars(select(RunTarget).where(RunTarget.run_id == run.id)):
            if not TargetStatus(target.status).is_terminal:
                target.status = TargetStatus.CANCELLED.value
                target.finished_at = utcnow()
        counts = target_counts(db, run.id)
        db.flush()
        counts = target_counts(db, run.id)
        run.status = RunStatus.CANCELLED.value
        run.counts = counts
        run.done_targets = run.total_targets
        run.finished_at = utcnow()
    db.add(RunEvent(run_id=run.id, event="cancel_requested", message="Cancelamento solicitado."))
    db.commit()
    return run


def retry_failed(db: Session, user: User, run_id: uuid.UUID) -> Run:
    run = get_run(db, user, run_id)
    if not RunStatus(run.status).is_terminal:
        raise Conflict("A busca ainda está em andamento.", code="run_active")
    failed = list(
        db.scalars(
            select(RunTarget).where(
                RunTarget.run_id == run.id,
                RunTarget.status.in_(
                    [s.value for s in FAILURE_STATES] + [TargetStatus.CANCELLED.value]
                ),
            )
        )
    )
    if not failed:
        raise ValidationFailed("Não há alvos com falha para repetir.", code="nothing_to_retry")
    return create_run(
        db,
        user,
        list_id=run.list_id,
        trigger=RunTrigger.RETRY,
        parent_run_id=run.id,
        pairs=[(t.product_id, t.store_id) for t in failed],
        options={
            k: v for k, v in (run.params or {}).items() if k not in ("store_ids", "product_ids")
        },
    )


def progress(db: Session, run: Run) -> dict[str, Any]:
    targets = list(db.scalars(select(RunTarget).where(RunTarget.run_id == run.id)))
    counts = Counter(t.status for t in targets)
    by_market: dict[str, Counter[str]] = {}
    for target in targets:
        by_market.setdefault(str(target.market_id), Counter())[target.status] += 1
    done = sum(v for k, v in counts.items() if TargetStatus(k).is_terminal)
    return {
        "counts": dict(counts),
        "done": done,
        "total": len(targets),
        "by_market": {k: dict(v) for k, v in by_market.items()},
    }


def recent_events(db: Session, run_id: uuid.UUID, limit: int = 50) -> list[RunEvent]:
    return list(
        db.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.id.desc())
            .limit(limit)
        )
    )[::-1]
