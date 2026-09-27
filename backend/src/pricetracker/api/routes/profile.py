from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import func, select

from pricetracker.api import schemas
from pricetracker.api.deps import CsrfProtected, CurrentUser, DbSession
from pricetracker.db.base import utcnow
from pricetracker.domain.travel import GeoPoint, haversine_km
from pricetracker.models import Observation, RunTarget
from pricetracker.models.enums import TargetStatus
from pricetracker.services import profile

router = APIRouter()


# --- markets & stores ------------------------------------------------------------------------


@router.get("/markets", response_model=list[schemas.MarketOut], tags=["markets"])
def markets(user: CurrentUser, db: DbSession) -> list[schemas.MarketOut]:
    selected = profile.selections(db, user.id)
    home = profile.primary_address(db, user.id)
    last_seen = dict(
        db.execute(
            select(Observation.store_id, func.max(Observation.observed_at))
            .where(Observation.user_id == user.id)
            .group_by(Observation.store_id)
        ).all()
    )
    since = utcnow() - timedelta(days=14)
    health_rows = db.execute(
        select(RunTarget.market_id, RunTarget.status, func.count(), func.max(RunTarget.finished_at))
        .where(RunTarget.finished_at > since)
        .group_by(RunTarget.market_id, RunTarget.status)
    ).all()
    health: dict[uuid.UUID, dict[str, int]] = {}
    last_success: dict[uuid.UUID, object] = {}
    for market_id, status, count, finished in health_rows:
        health.setdefault(market_id, {})[status] = int(count)
        if status == TargetStatus.FOUND.value:
            last_success[market_id] = finished
    result = []
    for market in profile.list_markets(db):
        stats = health.get(market.id, {})
        failures = sum(v for k, v in stats.items() if TargetStatus(k).is_failure)
        total = sum(stats.values())
        state = (
            "sem_dados"
            if total == 0
            else (
                "saudavel"
                if failures == 0
                else ("instavel" if failures / total <= 0.2 else "falhando")
            )
        )
        stores = []
        for store in market.stores:
            if not store.is_active:
                continue
            distance = None
            if (
                home
                and home.latitude is not None
                and store.latitude is not None
                and store.longitude is not None
                and home.longitude is not None
            ):
                distance = haversine_km(
                    GeoPoint(home.latitude, home.longitude),
                    GeoPoint(store.latitude, store.longitude),
                ).quantize(Decimal("0.1"))
            selection = selected.get(store.id)
            stores.append(
                schemas.StoreOut(
                    id=store.id,
                    slug=store.slug,
                    name=store.name,
                    street=store.street,
                    number=store.number,
                    district=store.district,
                    city=store.city,
                    state=store.state,
                    postal_code=store.postal_code,
                    latitude=store.latitude,
                    longitude=store.longitude,
                    price_scope_note=store.price_scope_note,
                    selected=selection is not None,
                    toll_round_trip=selection.toll_round_trip if selection else Decimal("0"),
                    last_observed_at=last_seen.get(store.id),
                    distance_km=distance,
                )
            )
        stores.sort(key=lambda s: (s.distance_km is None, s.distance_km or 0, s.city or "", s.name))
        result.append(
            schemas.MarketOut(
                id=market.id,
                slug=market.slug,
                name=market.name,
                website=market.website,
                brand_color=market.brand_color,
                enabled=market.enabled,
                notes=market.notes,
                health=state,
                last_success_at=last_success.get(market.id),
                stores=stores,
            )
        )
    return result


@router.put("/me/stores", response_model=schemas.Ok, tags=["markets"], dependencies=[CsrfProtected])
def set_stores(body: schemas.StoreSelectionsIn, user: CurrentUser, db: DbSession) -> schemas.Ok:
    profile.set_selections(db, user, [s.model_dump() for s in body.selections])
    return schemas.Ok()


# --- profile ------------------------------------------------------------------------------------


def _profile_out(db: DbSession, user: CurrentUser) -> schemas.ProfileOut:
    prof = profile.get_profile(db, user)
    return schemas.ProfileOut(
        display_name=user.display_name,
        timezone=prof.timezone,
        freshness_days=prof.freshness_days,
        include_travel_cost=prof.include_travel_cost,
        max_stops=prof.max_stops,
        use_club_prices=list(prof.use_club_prices or []),
        onboarding_completed_at=prof.onboarding_completed_at,
    )


@router.get("/me/profile", response_model=schemas.ProfileOut, tags=["profile"])
def get_profile(user: CurrentUser, db: DbSession) -> schemas.ProfileOut:
    return _profile_out(db, user)


@router.patch(
    "/me/profile", response_model=schemas.ProfileOut, tags=["profile"], dependencies=[CsrfProtected]
)
def update_profile(
    body: schemas.ProfilePatch, user: CurrentUser, db: DbSession
) -> schemas.ProfileOut:
    profile.update_profile(db, user, body.model_dump(exclude_unset=True))
    return _profile_out(db, user)


@router.get("/me/addresses", response_model=list[schemas.AddressOut], tags=["profile"])
def addresses(user: CurrentUser, db: DbSession) -> list[schemas.AddressOut]:
    return [schemas.AddressOut.model_validate(a) for a in profile.list_addresses(db, user)]


@router.post(
    "/me/addresses",
    response_model=schemas.AddressOut,
    status_code=201,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def create_address(body: schemas.AddressIn, user: CurrentUser, db: DbSession) -> schemas.AddressOut:
    return schemas.AddressOut.model_validate(
        profile.save_address(db, user, None, body.model_dump())
    )


@router.put(
    "/me/addresses/{address_id}",
    response_model=schemas.AddressOut,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def update_address(
    address_id: uuid.UUID, body: schemas.AddressIn, user: CurrentUser, db: DbSession
) -> schemas.AddressOut:
    return schemas.AddressOut.model_validate(
        profile.save_address(db, user, address_id, body.model_dump())
    )


@router.post(
    "/me/addresses/{address_id}/geocode",
    response_model=schemas.AddressOut,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def geocode_address(address_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.AddressOut:
    return schemas.AddressOut.model_validate(profile.geocode(db, user, address_id))


@router.delete(
    "/me/addresses/{address_id}",
    response_model=schemas.Ok,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def delete_address(address_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    profile.delete_address(db, user, address_id)
    return schemas.Ok()


@router.get("/me/vehicles", response_model=list[schemas.VehicleOut], tags=["profile"])
def vehicles(user: CurrentUser, db: DbSession) -> list[schemas.VehicleOut]:
    return [schemas.VehicleOut.model_validate(v) for v in profile.list_vehicles(db, user)]


@router.post(
    "/me/vehicles",
    response_model=schemas.VehicleOut,
    status_code=201,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def create_vehicle(body: schemas.VehicleIn, user: CurrentUser, db: DbSession) -> schemas.VehicleOut:
    return schemas.VehicleOut.model_validate(
        profile.save_vehicle(db, user, None, body.model_dump())
    )


@router.put(
    "/me/vehicles/{vehicle_id}",
    response_model=schemas.VehicleOut,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def update_vehicle(
    vehicle_id: uuid.UUID, body: schemas.VehicleIn, user: CurrentUser, db: DbSession
) -> schemas.VehicleOut:
    return schemas.VehicleOut.model_validate(
        profile.save_vehicle(db, user, vehicle_id, body.model_dump())
    )


@router.delete(
    "/me/vehicles/{vehicle_id}",
    response_model=schemas.Ok,
    tags=["profile"],
    dependencies=[CsrfProtected],
)
def delete_vehicle(vehicle_id: uuid.UUID, user: CurrentUser, db: DbSession) -> schemas.Ok:
    profile.delete_vehicle(db, user, vehicle_id)
    return schemas.Ok()
