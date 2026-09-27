"""Price alerts: tell the user when a freshly collected price reaches their target.

The target is a price per sale unit of the product — one package, one kilogram (products
sold by weight) or one unit — computed with the same pricing rules as the comparison
(promotions yes, club prices only when the user opted into that club). Only offers that
are in stock, not rejected and not flagged as outliers can trigger an alert, and only
prices collected by the run being evaluated count, so a stale price never fires.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.domain.money import format_brl
from pricetracker.domain.pricing import IncompatibleQuantity, line_cost
from pricetracker.models import (
    Market,
    Notification,
    Observation,
    PriceAlert,
    Product,
    Profile,
    Run,
    Store,
    User,
)
from pricetracker.models.enums import Availability, ReviewStatus, SoldBy, Unit
from pricetracker.services import catalog
from pricetracker.services.comparison import offer_from_observation
from pricetracker.services.errors import NotFound

logger = logging.getLogger(__name__)

KIND_PRICE_ALERT = "price_alert"
# The same target is not re-announced for this long unless the price drops further.
RENOTIFY_AFTER = timedelta(days=6)


@dataclass
class AlertView:
    alert: PriceAlert
    product: Product
    best_price: Decimal | None
    best_store: str | None
    best_observed_at: datetime | None


def unit_label(product: Product) -> str:
    return {SoldBy.WEIGHT.value: "kg", SoldBy.UNIT.value: "unidade"}.get(
        product.sold_by, "embalagem"
    )


def _sale_quantity(product: Product) -> tuple[Decimal, Unit]:
    if product.sold_by == SoldBy.WEIGHT.value:
        return Decimal("1"), Unit.KG
    if product.sold_by == SoldBy.UNIT.value:
        return Decimal("1"), Unit.UN
    return Decimal("1"), Unit.PCT


def alert_price(obs: Observation, product: Product, use_club: bool) -> Decimal | None:
    """Effective price per sale unit of one observation, or None when it cannot count."""
    if (
        obs.availability != Availability.IN_STOCK.value
        or obs.is_outlier
        or obs.review_status == ReviewStatus.REJECTED.value
    ):
        return None
    quantity, unit = _sale_quantity(product)
    spec = product.match_spec or {}
    approx = spec.get("approx_unit_weight_kg")
    try:
        cost = line_cost(
            offer_from_observation(obs).pricing,
            quantity,
            unit,
            use_club=use_club,
            approx_unit_weight_kg=Decimal(str(approx)) if approx else None,
            weight_based=product.sold_by == SoldBy.WEIGHT.value,
        )
    except (IncompatibleQuantity, ValueError, TypeError):
        return None
    return cost.cost


def _clubs(db: Session, user_id: uuid.UUID) -> set[str]:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    return set(profile.use_club_prices or []) if profile else set()


def _store_labels(db: Session, store_ids: set[uuid.UUID]) -> dict[uuid.UUID, tuple[str, str]]:
    rows = db.execute(
        select(Store.id, Market.name, Market.slug, Store.name)
        .join(Market, Market.id == Store.market_id)
        .where(Store.id.in_(store_ids))
    ).all()
    return {sid: (f"{market} {store}", slug) for sid, market, slug, store in rows}


# --- management ----------------------------------------------------------------------------


def get_alert(db: Session, user: User, product_id: uuid.UUID) -> PriceAlert | None:
    catalog.get_product(db, user, product_id)  # 404 unless the product is the user's
    return db.scalar(
        select(PriceAlert).where(PriceAlert.user_id == user.id, PriceAlert.product_id == product_id)
    )


def upsert_alert(
    db: Session, user: User, product_id: uuid.UUID, target_price: Decimal, enabled: bool = True
) -> PriceAlert:
    alert = get_alert(db, user, product_id)
    if alert is None:
        alert = PriceAlert(user_id=user.id, product_id=product_id, target_price=target_price)
        db.add(alert)
    elif alert.target_price != target_price:
        alert.last_triggered_at = None  # a new target deserves a fresh announcement
    alert.target_price = target_price
    alert.enabled = enabled
    db.commit()
    return alert


def delete_alert(db: Session, user: User, product_id: uuid.UUID) -> None:
    alert = get_alert(db, user, product_id)
    if alert is None:
        raise NotFound("Alerta não encontrado.")
    db.delete(alert)
    db.commit()


def list_alerts(db: Session, user: User, freshness_days: int) -> list[AlertView]:
    alerts = list(
        db.scalars(
            select(PriceAlert)
            .where(PriceAlert.user_id == user.id)
            .order_by(PriceAlert.created_at.desc())
        )
    )
    if not alerts:
        return []
    products = {
        p.id: p
        for p in db.scalars(select(Product).where(Product.id.in_({a.product_id for a in alerts})))
    }
    since = utcnow() - timedelta(days=freshness_days)
    observations = list(
        db.scalars(
            select(Observation).where(
                Observation.user_id == user.id,
                Observation.product_id.in_(products),
                Observation.observed_at > since,
            )
        )
    )
    labels = _store_labels(db, {o.store_id for o in observations})
    clubs = _clubs(db, user.id)
    latest: dict[tuple[uuid.UUID, uuid.UUID], Observation] = {}
    for obs in sorted(observations, key=lambda o: o.observed_at, reverse=True):
        latest.setdefault((obs.product_id, obs.store_id), obs)
    views = []
    for alert in alerts:
        product = products[alert.product_id]
        best: tuple[Decimal, Observation] | None = None
        for (product_id, store_id), obs in latest.items():
            if product_id != product.id:
                continue
            price = alert_price(obs, product, labels.get(store_id, ("", ""))[1] in clubs)
            if price is not None and (best is None or price < best[0]):
                best = (price, obs)
        views.append(
            AlertView(
                alert=alert,
                product=product,
                best_price=best[0] if best else None,
                best_store=labels.get(best[1].store_id, ("", ""))[0] if best else None,
                best_observed_at=best[1].observed_at if best else None,
            )
        )
    return views


# --- evaluation after a run ----------------------------------------------------------------


def _last_notified_price(db: Session, alert: PriceAlert) -> Decimal | None:
    data = db.scalar(
        select(Notification.data)
        .where(
            Notification.user_id == alert.user_id,
            Notification.kind == KIND_PRICE_ALERT,
            Notification.data["alert_id"].as_string() == str(alert.id),
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    if not data or data.get("price") is None:
        return None
    return Decimal(str(data["price"]))


def evaluate_run(db: Session, run_id: uuid.UUID) -> int:
    """Create notifications for alerts whose target the run's fresh prices reached."""
    run = db.get(Run, run_id)
    if run is None:
        return 0
    observations = list(db.scalars(select(Observation).where(Observation.run_id == run_id)))
    if not observations:
        return 0
    alerts = {
        a.product_id: a
        for a in db.scalars(
            select(PriceAlert).where(
                PriceAlert.user_id == run.user_id,
                PriceAlert.enabled.is_(True),
                PriceAlert.product_id.in_({o.product_id for o in observations}),
            )
        )
    }
    if not alerts:
        return 0
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(alerts)))}
    labels = _store_labels(db, {o.store_id for o in observations})
    clubs = _clubs(db, run.user_id)
    created = 0
    now = utcnow()
    for product_id, alert in alerts.items():
        product = products[product_id]
        candidates = []
        for obs in observations:
            if obs.product_id != product_id:
                continue
            label, slug = labels.get(obs.store_id, ("", ""))
            price = alert_price(obs, product, slug in clubs)
            if price is not None and price <= alert.target_price:
                candidates.append((price, label, obs))
        if not candidates:
            continue
        price, label, obs = min(candidates, key=lambda c: c[0])
        previous = _last_notified_price(db, alert)
        recent = alert.last_triggered_at is not None and now - alert.last_triggered_at < (
            RENOTIFY_AFTER
        )
        if recent and previous is not None and price >= previous:
            continue
        unit = unit_label(product)
        db.add(
            Notification(
                user_id=run.user_id,
                kind=KIND_PRICE_ALERT,
                title=f"{product.name}: {format_brl(price)} por {unit}"[:160],
                body=(
                    f"{label} está com {product.name} a {format_brl(price)} por {unit}, "
                    f"dentro do seu alvo de {format_brl(alert.target_price)}. "
                    f"Preço observado nesta busca ({obs.title})."
                )[:600],
                data={
                    "alert_id": str(alert.id),
                    "product_id": str(product_id),
                    "store_id": str(obs.store_id),
                    "observation_id": str(obs.id),
                    "run_id": str(run_id),
                    "price": str(price),
                    "target": str(alert.target_price),
                },
            )
        )
        alert.last_triggered_at = now
        created += 1
    db.commit()
    return created


# --- notifications ---------------------------------------------------------------------------


def list_notifications(db: Session, user: User, limit: int = 50) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    )


def unread_count(db: Session, user: User) -> int:
    return int(
        db.scalar(
            select(func.count()).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        )
        or 0
    )


def mark_read(db: Session, user: User, ids: list[uuid.UUID] | None = None) -> int:
    stmt = update(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    result: Any = db.execute(stmt.values(read_at=utcnow()))
    db.commit()
    return int(result.rowcount or 0)
