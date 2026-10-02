from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from pricetracker.api import schemas
from pricetracker.api.deps import CsrfProtected, CurrentUser, DbSession
from pricetracker.models import Market, Observation, Product, Run, RunTarget, Store
from pricetracker.models.enums import FAILURE_STATES, ReviewStatus, RunStatus, TargetStatus
from pricetracker.services import history as history_service
from pricetracker.services import runs as run_service
from pricetracker.services.comparison import build_comparison, serialize

router = APIRouter()


def _run_out(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "list_id": run.list_id,
        "parent_run_id": run.parent_run_id,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "cancel_requested": run.cancel_requested_at is not None,
        "total_targets": run.total_targets,
        "done_targets": run.done_targets,
        "counts": run.counts or {},
        "llm_calls": run.llm_calls,
        "error_summary": run.error_summary,
    }


def _detail(db: DbSession, run: Run) -> schemas.RunDetailOut:
    targets = list(db.scalars(select(RunTarget).where(RunTarget.run_id == run.id)))
    products = {
        p.id: p
        for p in db.scalars(select(Product).where(Product.id.in_({t.product_id for t in targets})))
    }
    stores = {
        s.id: s
        for s in db.scalars(select(Store).where(Store.id.in_({t.store_id for t in targets})))
    }
    markets = {m.id: m for m in db.scalars(select(Market))}
    observations = {
        o.target_id: o for o in db.scalars(select(Observation).where(Observation.run_id == run.id))
    }
    counts = run_service.target_counts(db, run.id)
    items = []
    for t in sorted(
        targets,
        key=lambda x: (
            markets[x.market_id].name,
            stores[x.store_id].name,
            products[x.product_id].name,
        ),
    ):
        obs = observations.get(t.id)
        items.append(
            schemas.RunTargetOut(
                id=t.id,
                product_id=t.product_id,
                product_name=products[t.product_id].name,
                store_id=t.store_id,
                store_name=stores[t.store_id].name,
                market_slug=markets[t.market_id].slug,
                market_name=markets[t.market_id].name,
                status=t.status,
                method=t.method,
                error_type=t.error_type,
                error_detail=t.error_detail,
                duration_ms=t.duration_ms,
                candidate_count=t.candidate_count,
                llm_needed=t.llm_needed,
                llm_used=t.llm_used,
                started_at=t.started_at,
                finished_at=t.finished_at,
                observation=None
                if obs is None
                else {
                    "title": obs.title,
                    "price": obs.promo_price if obs.promo_price is not None else obs.regular_price,
                    "regular_price": obs.regular_price,
                    "unit_price": obs.unit_price,
                    "unit_price_unit": obs.unit_price_unit,
                    "url": obs.url,
                    "availability": obs.availability,
                    "flagged": obs.review_status == ReviewStatus.FLAGGED.value,
                },
            )
        )
    events = [schemas.RunEventOut.model_validate(e) for e in run_service.recent_events(db, run.id)]
    data = _run_out(run)
    data["counts"] = counts
    data["done_targets"] = sum(v for k, v in counts.items() if TargetStatus(k).is_terminal)
    retryable = sum(
        v
        for k, v in counts.items()
        if TargetStatus(k) in FAILURE_STATES or k == TargetStatus.CANCELLED.value
    )
    return schemas.RunDetailOut(
        **data,
        targets=items,
        events=events,
        retryable=retryable if RunStatus(run.status).is_terminal else 0,
    )


@router.post(
    "/runs",
    response_model=schemas.RunDetailOut,
    status_code=201,
    tags=["runs"],
    dependencies=[CsrfProtected],
)
def create_run(body: schemas.RunCreateIn, user: CurrentUser, db: DbSession) -> schemas.RunDetailOut:
    run = run_service.create_run(
        db,
        user,
        list_id=body.list_id,
        store_ids=body.store_ids,
        product_ids=body.product_ids,
        options={"allow_llm": body.allow_llm},
    )
    return _detail(db, run)


@router.get("/runs", response_model=list[schemas.RunOut], tags=["runs"])
def list_runs(user: CurrentUser, db: DbSession, limit: int = 20) -> list[schemas.RunOut]:
    return [
        schemas.RunOut(**_run_out(r))
        for r in run_service.list_runs(db, user, min(max(limit, 1), 100))
    ]


@router.get("/runs/active", response_model=schemas.RunOut | None, tags=["runs"])
def active_run(user: CurrentUser, db: DbSession) -> schemas.RunOut | None:
    run = db.scalar(
        select(Run)
        .where(Run.user_id == user.id, Run.status.in_(run_service.ACTIVE_STATUSES))
        .order_by(Run.created_at.desc())
    )
    return schemas.RunOut(**_run_out(run)) if run else None


@router.get("/runs/{run_id}", response_model=schemas.RunDetailOut, tags=["runs"])
def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.RunDetailOut:
    return _detail(db, run_service.get_run(db, user, run_id))


@router.post(
    "/runs/{run_id}/cancel",
    response_model=schemas.RunDetailOut,
    tags=["runs"],
    dependencies=[CsrfProtected],
)
def cancel_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.RunDetailOut:
    return _detail(db, run_service.cancel_run(db, user, run_id))


@router.post(
    "/runs/{run_id}/retry",
    response_model=schemas.RunDetailOut,
    status_code=201,
    tags=["runs"],
    dependencies=[CsrfProtected],
)
def retry_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.RunDetailOut:
    return _detail(db, run_service.retry_failed(db, user, run_id))


# --- comparison & history -----------------------------------------------------------------------


@router.get("/comparison", response_model=schemas.ComparisonOut, tags=["comparison"])
def comparison(
    user: CurrentUser,
    db: DbSession,
    list_id: uuid.UUID | None = None,
    store_ids: str | None = None,
    allow_stale: bool = False,
    include_travel: bool | None = None,
    max_stops: int | None = None,
) -> dict[str, Any]:
    """Comparison of the list across stores: common basket, coverage, economic plan, recommendation."""
    ids = [uuid.UUID(s) for s in store_ids.split(",") if s] if store_ids else None
    context = build_comparison(
        db, user, list_id=list_id, store_ids=ids, allow_stale=allow_stale,
        include_travel=include_travel, max_stops=max_stops,
    )  # fmt: skip
    return serialize(context)


@router.get("/history/products/{product_id}", response_model=schemas.HistoryOut, tags=["history"])
def product_history(
    product_id: uuid.UUID, user: CurrentUser, db: DbSession, days: int = 180
) -> dict[str, Any]:
    return history_service.product_history(db, user, product_id, days=min(max(days, 7), 730))


@router.post(
    "/observations/{observation_id}/review",
    response_model=schemas.Ok,
    tags=["history"],
    dependencies=[CsrfProtected],
)
def review_observation(
    observation_id: uuid.UUID, decision: str, user: CurrentUser, db: DbSession
) -> schemas.Ok:
    status = {
        "confirm": ReviewStatus.CONFIRMED,
        "reject": ReviewStatus.REJECTED,
        "flag": ReviewStatus.FLAGGED,
    }.get(decision)
    if status is None:
        from pricetracker.services.errors import ValidationFailed

        raise ValidationFailed(
            "Decisão inválida (confirm, reject ou flag).", code="invalid_decision"
        )
    history_service.review_observation(db, user, observation_id, status)
    return schemas.Ok()
