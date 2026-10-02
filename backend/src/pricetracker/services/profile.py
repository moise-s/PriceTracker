"""Profile, home address, vehicle and store selections (all per user)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pricetracker.db.base import utcnow
from pricetracker.geo.providers import GeoError, geocode_address
from pricetracker.models import Address, Market, Profile, Store, User, UserStoreSelection, Vehicle
from pricetracker.services.errors import NotFound, ValidationFailed
from pricetracker.settings import get_settings


def get_profile(db: Session, user: User) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, freshness_days=get_settings().default_freshness_days)
        db.add(profile)
        db.commit()
    return profile


def update_profile(db: Session, user: User, data: dict[str, Any]) -> Profile:
    profile = get_profile(db, user)
    if "display_name" in data:
        name = (data.pop("display_name") or "").strip()
        if name:
            user.display_name = name[:120]
    if data.pop("complete_onboarding", False):
        profile.onboarding_completed_at = profile.onboarding_completed_at or utcnow()
    if "use_club_prices" in data and data["use_club_prices"] is not None:
        known = set(db.scalars(select(Market.slug)))
        data["use_club_prices"] = sorted({s for s in data["use_club_prices"] if s in known})
    for key, value in data.items():
        if value is not None:
            setattr(profile, key, value)
    db.commit()
    return profile


# --- addresses ------------------------------------------------------------------------


def list_addresses(db: Session, user: User) -> list[Address]:
    return list(
        db.scalars(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.is_primary.desc(), Address.created_at)
        )
    )


def primary_address(db: Session, user_id: uuid.UUID) -> Address | None:
    return db.scalar(
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_primary.desc(), Address.created_at)
        .limit(1)
    )


def _get_address(db: Session, user: User, address_id: uuid.UUID) -> Address:
    address = db.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise NotFound("Endereço não encontrado.")
    return address


def _validate_coordinates(lat: Decimal | None, lon: Decimal | None) -> None:
    if (lat is None) != (lon is None):
        raise ValidationFailed("Informe latitude e longitude juntas.", code="invalid_coordinates")
    if lat is not None and lon is not None:
        if not (Decimal(-90) <= lat <= Decimal(90) and Decimal(-180) <= lon <= Decimal(180)):
            raise ValidationFailed(
                "Coordenadas fora do intervalo válido.", code="invalid_coordinates"
            )


def save_address(
    db: Session, user: User, address_id: uuid.UUID | None, data: dict[str, Any]
) -> Address:
    _validate_coordinates(data.get("latitude"), data.get("longitude"))
    if address_id is None:
        address = Address(user_id=user.id, **data)
        db.add(address)
    else:
        address = _get_address(db, user, address_id)
        for key, value in data.items():
            setattr(address, key, value)
    if data.get("latitude") is not None:
        address.geocode_source = "manual"
        address.geocoded_at = utcnow()
    if address.is_primary:
        db.flush()
        for other in db.scalars(
            select(Address).where(Address.user_id == user.id, Address.id != address.id)
        ):
            other.is_primary = False
    db.commit()
    return address


def geocode(db: Session, user: User, address_id: uuid.UUID) -> Address:
    address = _get_address(db, user, address_id)
    try:
        result = geocode_address(
            db,
            street=address.street,
            number=address.number,
            district=address.district,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
        )
    except GeoError as exc:
        raise ValidationFailed(str(exc), code="geocode_failed") from exc
    address.latitude = result.latitude.quantize(Decimal("0.000001"))
    address.longitude = result.longitude.quantize(Decimal("0.000001"))
    address.geocode_source = result.provider
    address.geocoded_at = utcnow()
    db.commit()
    return address


def delete_address(db: Session, user: User, address_id: uuid.UUID) -> None:
    db.delete(_get_address(db, user, address_id))
    db.commit()


# --- vehicles ----------------------------------------------------------------------------


def list_vehicles(db: Session, user: User) -> list[Vehicle]:
    return list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.user_id == user.id)
            .order_by(Vehicle.is_primary.desc(), Vehicle.created_at)
        )
    )


def primary_vehicle(db: Session, user_id: uuid.UUID) -> Vehicle | None:
    return db.scalar(
        select(Vehicle)
        .where(Vehicle.user_id == user_id)
        .order_by(Vehicle.is_primary.desc(), Vehicle.created_at)
        .limit(1)
    )


def save_vehicle(
    db: Session, user: User, vehicle_id: uuid.UUID | None, data: dict[str, Any]
) -> Vehicle:
    if data.get("km_per_liter") is not None and data["km_per_liter"] <= 0:
        raise ValidationFailed("Consumo deve ser maior que zero.", code="invalid_consumption")
    if data.get("fuel_price_per_liter") is not None and data["fuel_price_per_liter"] < 0:
        raise ValidationFailed("Preço do combustível inválido.", code="invalid_fuel_price")
    if vehicle_id is None:
        vehicle = Vehicle(user_id=user.id, **data)
        db.add(vehicle)
    else:
        found = db.get(Vehicle, vehicle_id)
        if found is None or found.user_id != user.id:
            raise NotFound("Veículo não encontrado.")
        vehicle = found
        for key, value in data.items():
            setattr(vehicle, key, value)
    if vehicle.is_primary:
        db.flush()
        for other in db.scalars(
            select(Vehicle).where(Vehicle.user_id == user.id, Vehicle.id != vehicle.id)
        ):
            other.is_primary = False
    db.commit()
    return vehicle


def delete_vehicle(db: Session, user: User, vehicle_id: uuid.UUID) -> None:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.user_id != user.id:
        raise NotFound("Veículo não encontrado.")
    db.delete(vehicle)
    db.commit()


# --- markets & store selections ----------------------------------------------------------


def list_markets(db: Session, include_disabled: bool = False) -> list[Market]:
    stmt = select(Market).options(selectinload(Market.stores)).order_by(Market.name)
    if not include_disabled:
        stmt = stmt.where(Market.enabled.is_(True))
    return list(db.scalars(stmt))


def selections(
    db: Session, user_id: uuid.UUID, *, include_unavailable: bool = False
) -> dict[uuid.UUID, UserStoreSelection]:
    stmt = select(UserStoreSelection).where(UserStoreSelection.user_id == user_id)
    if not include_unavailable:
        stmt = (
            stmt.join(Store).join(Market).where(Store.is_active.is_(True), Market.enabled.is_(True))
        )
    rows = db.scalars(stmt)
    return {row.store_id: row for row in rows}


def set_selections(
    db: Session, user: User, entries: list[dict[str, Any]]
) -> dict[uuid.UUID, UserStoreSelection]:
    wanted: dict[uuid.UUID, Decimal] = {}
    for entry in entries:
        store = db.get(Store, entry["store_id"])
        if store is None or not store.is_active or not store.market.enabled:
            raise ValidationFailed("Loja inválida.", code="invalid_store")
        toll = entry.get("toll_round_trip") or Decimal("0")
        if toll < 0:
            raise ValidationFailed("Pedágio inválido.", code="invalid_toll")
        wanted[store.id] = toll
    current = selections(db, user.id, include_unavailable=True)
    for store_id, row in current.items():
        if store_id not in wanted:
            db.delete(row)
    for store_id, toll in wanted.items():
        existing = current.get(store_id)
        if existing is None:
            db.add(UserStoreSelection(user_id=user.id, store_id=store_id, toll_round_trip=toll))
        else:
            existing.toll_round_trip = toll
    db.commit()
    return selections(db, user.id)
