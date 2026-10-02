"""Builds the basket comparison for a user's list from stored observations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.domain.comparison import (
    ComparisonOptions,
    ComparisonResult,
    LineRequest,
    OfferInput,
    StoreOption,
    compare,
)
from pricetracker.domain.listing import SaleUnit
from pricetracker.domain.pricing import OfferPricing
from pricetracker.domain.travel import GeoPoint, VehicleSpec
from pricetracker.domain.units import Measure
from pricetracker.geo.providers import DistanceService
from pricetracker.models import ListItem, Market, Observation, Product, RunTarget, Store, User
from pricetracker.models.enums import Availability, ReviewStatus, SoldBy, TargetStatus, Unit
from pricetracker.services import catalog, profile
from pricetracker.services.errors import ValidationFailed

LOOKBACK_DAYS = 120
# Outcomes worth showing next to a price cell ("why is this empty?").
INFORMATIVE_SEARCH_STATUSES = {s.value for s in TargetStatus if s.is_terminal} - {
    TargetStatus.CANCELLED.value
}


@dataclass
class ComparisonContext:
    result: ComparisonResult
    products: dict[str, Product]
    stores: dict[str, Store]
    markets: dict[uuid.UUID, Market]
    observations: dict[str, Observation]
    last_searches: dict[tuple[str, str], tuple[str, Any]]
    home_located: bool
    vehicle_configured: bool


def _sale_unit(obs: Observation) -> SaleUnit:
    if obs.sold_by == SoldBy.WEIGHT.value:
        return SaleUnit.KG
    if obs.sold_by == SoldBy.UNIT.value:
        return SaleUnit.PIECE
    return SaleUnit.PACKAGE


def offer_from_observation(obs: Observation) -> OfferInput:
    measure = None
    count = None
    if obs.package_unit in ("kg", "l", "m") and obs.package_quantity:
        measure = Measure(obs.package_quantity, Unit(obs.package_unit))
    elif obs.package_unit == "un" and obs.package_quantity:
        count = int(obs.package_quantity)
    selling = obs.promo_price if obs.promo_price is not None else obs.regular_price
    pricing = OfferPricing(
        sale_unit=_sale_unit(obs),
        price=selling,
        regular_price=obs.regular_price if obs.promo_price is not None else None,
        club_price=obs.club_price,
        quantity_min=obs.quantity_min,
        quantity_price=obs.quantity_price,
        quantity_mode=obs.quantity_mode,
        package_measure=measure,
        package_count=count,
        piece_weight_kg=obs.unit_multiplier,
    )
    review = ReviewStatus(obs.review_status)
    return OfferInput(
        product_id=str(obs.product_id),
        store_id=str(obs.store_id),
        observation_id=str(obs.id),
        title=obs.title,
        url=obs.url,
        observed_at=obs.observed_at,
        pricing=pricing,
        availability=Availability(obs.availability),
        review_status=review,
        confidence=obs.confidence,
        method=obs.method,
        club_label=obs.club_label,
    )


def latest_observations(
    db: Session, user_id: uuid.UUID, product_ids: set[uuid.UUID], store_ids: set[uuid.UUID]
) -> dict[tuple[uuid.UUID, uuid.UUID], Observation]:
    rows = db.scalars(
        select(Observation)
        .where(
            Observation.user_id == user_id,
            Observation.product_id.in_(product_ids),
            Observation.store_id.in_(store_ids),
            Observation.observed_at > utcnow() - timedelta(days=LOOKBACK_DAYS),
            Observation.review_status != ReviewStatus.REJECTED.value,
        )
        .order_by(Observation.observed_at.desc())
    )
    latest: dict[tuple[uuid.UUID, uuid.UUID], Observation] = {}
    for obs in rows:
        latest.setdefault((obs.product_id, obs.store_id), obs)
    return latest


def last_searches(
    db: Session, user_id: uuid.UUID, product_ids: set[uuid.UUID], store_ids: set[uuid.UUID]
) -> dict[tuple[str, str], tuple[str, Any]]:
    """Outcome of the most recent finished search per (product, store): not found, blocked, ..."""
    rows = db.execute(
        select(RunTarget.product_id, RunTarget.store_id, RunTarget.status, RunTarget.finished_at)
        .where(
            RunTarget.user_id == user_id,
            RunTarget.product_id.in_(product_ids),
            RunTarget.store_id.in_(store_ids),
            RunTarget.status.in_(INFORMATIVE_SEARCH_STATUSES),
            RunTarget.finished_at > utcnow() - timedelta(days=LOOKBACK_DAYS),
        )
        .order_by(RunTarget.finished_at.desc())
    )
    latest: dict[tuple[str, str], tuple[str, Any]] = {}
    for product_id, store_id, status, finished_at in rows:
        latest.setdefault((str(product_id), str(store_id)), (status, finished_at))
    return latest


def build_comparison(
    db: Session,
    user: User,
    *,
    list_id: uuid.UUID | None = None,
    store_ids: list[uuid.UUID] | None = None,
    allow_stale: bool = False,
    include_travel: bool | None = None,
    max_stops: int | None = None,
) -> ComparisonContext:
    shopping_list = (
        catalog.get_list(db, user, list_id) if list_id else catalog.default_list(db, user)
    )
    user_profile = profile.get_profile(db, user)
    items = list(
        db.scalars(
            select(ListItem).where(ListItem.list_id == shopping_list.id).order_by(ListItem.position)
        )
    )
    products = {
        p.id: p
        for p in db.scalars(select(Product).where(Product.id.in_({i.product_id for i in items})))
    }
    items = [
        i
        for i in items
        if products.get(i.product_id) is not None and products[i.product_id].is_active
    ]
    if not store_ids:
        store_ids = list(profile.selections(db, user.id).keys())
    stores = {
        s.id: s
        for s in db.scalars(
            select(Store)
            .join(Market)
            .where(
                Store.id.in_(store_ids or []), Store.is_active.is_(True), Market.enabled.is_(True)
            )
        )
    }
    if store_ids and len(stores) != len(set(store_ids)):
        raise ValidationFailed("Loja inválida na comparação.", code="invalid_store")
    markets = {m.id: m for m in db.scalars(select(Market))}
    selections = profile.selections(db, user.id)
    clubs = set(user_profile.use_club_prices or [])
    store_options = [
        StoreOption(
            store_id=str(s.id),
            market_slug=markets[s.market_id].slug,
            market_name=markets[s.market_id].name,
            store_name=s.name,
            use_club=markets[s.market_id].slug in clubs,
            tolls=selections[s.id].toll_round_trip if s.id in selections else Decimal("0"),
            has_location=s.latitude is not None and s.longitude is not None,
        )
        for s in sorted(stores.values(), key=lambda st: (markets[st.market_id].name, st.name))
    ]
    requests = []
    for item in items:
        product = products[item.product_id]
        spec = product.match_spec or {}
        approx = spec.get("approx_unit_weight_kg")
        requests.append(
            LineRequest(
                item_id=str(item.id),
                product_id=str(product.id),
                name=product.name,
                quantity=item.quantity,
                unit=Unit(item.unit),
                approx_unit_weight_kg=Decimal(str(approx)) if approx else None,
                weight_based=product.sold_by == SoldBy.WEIGHT.value,
            )
        )
    latest = latest_observations(db, user.id, set(products), set(stores))
    offers = [offer_from_observation(obs) for obs in latest.values()]
    home = profile.primary_address(db, user.id)
    vehicle = profile.primary_vehicle(db, user.id)
    travel_wanted = user_profile.include_travel_cost if include_travel is None else include_travel
    distances = None
    home_located = bool(home and home.latitude is not None and home.longitude is not None)
    if travel_wanted and home_located and vehicle is not None and stores:
        assert home is not None
        points = {
            str(s.id): GeoPoint(s.latitude, s.longitude)
            for s in stores.values()
            if s.latitude is not None and s.longitude is not None
        }
        distances = DistanceService(db).model(GeoPoint(home.latitude, home.longitude), points)  # type: ignore[arg-type]
    options = ComparisonOptions(
        now=utcnow(),
        freshness_days=user_profile.freshness_days,
        allow_stale=allow_stale,
        include_travel=bool(travel_wanted),
        max_stops=max(1, min(max_stops or user_profile.max_stops, 3)),
        vehicle=VehicleSpec(vehicle.km_per_liter, vehicle.fuel_price_per_liter)
        if vehicle
        else None,
        distances=distances,
    )
    result = compare(requests, store_options, offers, options)
    db.commit()  # persists geo cache entries
    return ComparisonContext(
        result=result,
        products={str(p.id): p for p in products.values()},
        stores={str(s.id): s for s in stores.values()},
        markets=markets,
        observations={str(o.id): o for o in latest.values()},
        last_searches=last_searches(db, user.id, set(products), set(stores)),
        home_located=home_located,
        vehicle_configured=vehicle is not None,
    )


def serialize(context: ComparisonContext) -> dict[str, Any]:
    """Convert the domain result to the API shape (money as strings)."""
    result = context.result
    stores = {s.store_id: s for s in result.stores}

    def travel(t: Any) -> dict[str, Any] | None:
        if t is None:
            return None
        return {
            "distance_km": t.distance_km,
            "liters": t.liters,
            "fuel_cost": t.fuel_cost,
            "tolls": t.tolls,
            "total": t.total,
            "method": t.method,
            "route": list(t.route),
            "formula": t.formula,
        }

    def totals(t: Any) -> dict[str, Any]:
        return {
            "store_id": t.store_id,
            "covered": t.covered,
            "total_items": t.total_items,
            "products_total": t.products_total,
            "missing_item_ids": t.missing_item_ids,
            "stale_used": t.stale_used,
            "oldest_age_days": t.oldest_age_days,
            "travel": travel(t.travel),
            "effective_total": t.effective_total,
            "travel_known": t.travel_known,
            "complete": t.complete,
        }

    def plan(p: Any) -> dict[str, Any] | None:
        if p is None:
            return None
        return {
            "kind": p.kind,
            "stops": [
                {"store_id": s.store_id, "item_ids": s.item_ids, "products_total": s.products_total}
                for s in p.stops
            ],
            "covered": p.covered,
            "missing_item_ids": p.missing_item_ids,
            "products_total": p.products_total,
            "travel": travel(p.travel),
            "effective_total": p.effective_total,
            "travel_known": p.travel_known,
        }

    items = []
    for row in result.items:
        cells = {}
        for store_id, cell in row.cells.items():
            obs = context.observations.get(cell.offer.observation_id) if cell.offer else None
            search = context.last_searches.get((row.request.product_id, store_id))
            cells[store_id] = {
                "status": cell.status,
                "usable": cell.usable,
                "reason": cell.reason,
                "age_days": cell.age_days,
                "last_search": None
                if search is None
                else {"status": search[0], "finished_at": search[1]},
                "line": None
                if cell.line is None
                else {
                    "cost": cell.line.cost,
                    "sale_units": cell.line.sale_units,
                    "sale_unit_label": cell.line.sale_unit_label,
                    "price_kind": cell.line.price_kind.value,
                    "unit_price": cell.line.unit_price,
                    "unit_price_unit": cell.line.unit_price_unit.value
                    if cell.line.unit_price_unit
                    else None,
                    "approximate": cell.line.approximate,
                    "notes": list(cell.line.notes),
                },
                "offer": None
                if obs is None
                else {
                    "observation_id": obs.id,
                    "title": obs.title,
                    "brand": obs.brand,
                    "url": obs.url,
                    "image_url": obs.image_url,
                    "observed_at": obs.observed_at,
                    "regular_price": obs.regular_price,
                    "promo_price": obs.promo_price,
                    "club_price": obs.club_price,
                    "club_label": obs.club_label,
                    "quantity_min": obs.quantity_min,
                    "quantity_price": obs.quantity_price,
                    "quantity_mode": obs.quantity_mode,
                    "extra_prices": obs.extra_prices or [],
                    "unit_price": obs.unit_price,
                    "unit_price_unit": obs.unit_price_unit,
                    "availability": obs.availability,
                    "method": obs.method,
                    "confidence": obs.confidence,
                    "review_status": obs.review_status,
                    "outlier_reason": obs.outlier_reason,
                },
            }
        product = context.products.get(row.request.product_id)
        items.append(
            {
                "item_id": row.request.item_id,
                "product_id": row.request.product_id,
                "name": row.request.name,
                "quantity": row.request.quantity,
                "unit": row.request.unit.value,
                "image_id": product.image_id if product else None,
                "category": product.category if product else None,
                "best_store_id": row.best_store_id,
                "best_cost": row.best_cost,
                "worst_cost": row.worst_cost,
                "cells": cells,
            }
        )
    rec = result.recommendation
    return {
        "generated_at": result.generated_at,
        "freshness_days": result.options.freshness_days,
        "allow_stale": result.options.allow_stale,
        "include_travel": result.options.include_travel,
        "max_stops": result.options.max_stops,
        "home_located": context.home_located,
        "vehicle_configured": context.vehicle_configured,
        "distance_method": result.options.distances.method if result.options.distances else None,
        "stores": [
            {
                "store_id": s.store_id,
                "market_slug": s.market_slug,
                "market_name": s.market_name,
                "store_name": s.store_name,
                "use_club": s.use_club,
                "tolls": s.tolls,
                "has_location": s.has_location,
                "price_scope_note": context.stores[s.store_id].price_scope_note
                if s.store_id in context.stores
                else None,
                "travel": travel(result.travel_by_store.get(s.store_id)),
            }
            for s in stores.values()
        ],
        "items": items,
        "common": {
            "item_ids": result.common.item_ids,
            "excluded_item_ids": result.common.excluded_item_ids,
            "stores": [totals(t) for t in result.common.stores],
            "winner_store_id": result.common.winner_store_id,
            "savings_vs_runner_up": result.common.savings_vs_runner_up,
            "savings_vs_most_expensive": result.common.savings_vs_most_expensive,
            "comparable": result.common.comparable,
            "note": result.common.note,
        },
        "coverage": {
            "stores": [totals(t) for t in result.coverage.stores],
            "max_coverage": result.coverage.max_coverage,
            "best_store_id": result.coverage.best_store_id,
            "note": result.coverage.note,
        },
        "plan": {
            "best": plan(result.plan.best),
            "best_single": plan(result.plan.best_single),
            "alternatives": [plan(p) for p in result.plan.alternatives],
            "split_savings": result.plan.split_savings,
            "assumptions": result.plan.assumptions,
        },
        "recommendation": {
            "kind": rec.kind,
            "store_ids": rec.store_ids,
            "headline": rec.headline,
            "explanation": rec.explanation,
            "products_total": rec.products_total,
            "travel_total": rec.travel_total,
            "effective_total": rec.effective_total,
            "savings": rec.savings,
            "savings_reference_store_id": rec.savings_reference_store_id,
            "covered": rec.covered,
            "total_items": rec.total_items,
            "newest_observed_at": rec.newest_observed_at,
            "oldest_observed_at": rec.oldest_observed_at,
            "confidence": rec.confidence,
            "confidence_reasons": rec.confidence_reasons,
            "warnings": rec.warnings,
        },
    }
