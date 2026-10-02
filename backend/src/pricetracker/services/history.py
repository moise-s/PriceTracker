"""Price history per product and store (only the user's own observations)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.domain.quality import is_stale
from pricetracker.models import Market, Observation, Store, User
from pricetracker.models.enums import ReviewStatus
from pricetracker.services import catalog, profile
from pricetracker.services.errors import NotFound


def product_history(
    db: Session,
    user: User,
    product_id: uuid.UUID,
    *,
    days: int = 180,
    store_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    product = catalog.get_product(db, user, product_id)
    freshness = profile.get_profile(db, user).freshness_days
    stmt = (
        select(Observation)
        .where(
            Observation.user_id == user.id,
            Observation.product_id == product.id,
            Observation.observed_at > utcnow() - timedelta(days=days),
        )
        .order_by(Observation.observed_at)
    )
    if store_ids:
        stmt = stmt.where(Observation.store_id.in_(store_ids))
    observations = list(db.scalars(stmt))
    stores = {
        s.id: s
        for s in db.scalars(select(Store).where(Store.id.in_({o.store_id for o in observations})))
    }
    markets = {m.id: m for m in db.scalars(select(Market))}
    now = utcnow()
    series: dict[uuid.UUID, dict[str, Any]] = {}
    for obs in observations:
        store = stores.get(obs.store_id)
        if store is None:
            continue
        entry = series.setdefault(
            obs.store_id,
            {
                "store_id": obs.store_id,
                "store_name": store.name,
                "market_slug": markets[store.market_id].slug,
                "market_name": markets[store.market_id].name,
                "points": [],
            },
        )
        selling = obs.promo_price if obs.promo_price is not None else obs.regular_price
        entry["points"].append(
            {
                "observation_id": obs.id,
                "observed_at": obs.observed_at,
                "price": selling,
                "regular_price": obs.regular_price,
                "promo_price": obs.promo_price,
                "club_price": obs.club_price,
                "unit_price": obs.unit_price,
                "unit_price_unit": obs.unit_price_unit,
                "title": obs.title,
                "url": obs.url,
                "availability": obs.availability,
                "stale": is_stale(obs.observed_at, now, freshness),
                "flagged": obs.review_status
                in (ReviewStatus.FLAGGED.value, ReviewStatus.REJECTED.value),
                "review_status": obs.review_status,
                "outlier_reason": obs.outlier_reason,
                "method": obs.method,
            }
        )
    for entry in series.values():
        values = [
            p["unit_price"]
            for p in entry["points"]
            if p["unit_price"] is not None and not p["flagged"]
        ]
        entry["stats"] = {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "median": Decimal(median(values)).quantize(Decimal("0.0001")) if values else None,
            "last": values[-1] if values else None,
            "count": len(entry["points"]),
        }
    return {
        "product_id": product.id,
        "product_name": product.name,
        "freshness_days": freshness,
        "days": days,
        "series": sorted(series.values(), key=lambda e: (e["market_name"], e["store_name"])),
    }


def review_observation(
    db: Session, user: User, observation_id: uuid.UUID, decision: ReviewStatus
) -> Observation:
    obs = db.get(Observation, observation_id)
    if obs is None or obs.user_id != user.id:
        raise NotFound("Observação não encontrada.")
    obs.review_status = decision.value
    db.commit()
    return obs
