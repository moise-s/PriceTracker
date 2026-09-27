"""Transparent car travel cost.

    custo = distância (km, ida e volta) ÷ consumo (km/l) × preço do combustível (R$/l) + pedágios

Distances come from a routing provider (road distance) or, when none is
configured, from a straight-line estimate multiplied by a detour factor. The
method is always reported so the UI never implies precision that does not exist.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import permutations

from pricetracker.domain.money import quantize_money

KM = Decimal("0.1")
LITERS = Decimal("0.01")


@dataclass(frozen=True)
class GeoPoint:
    latitude: Decimal
    longitude: Decimal


@dataclass(frozen=True)
class VehicleSpec:
    km_per_liter: Decimal
    fuel_price_per_liter: Decimal


@dataclass(frozen=True)
class TravelCost:
    distance_km: Decimal
    liters: Decimal
    fuel_cost: Decimal
    tolls: Decimal
    total: Decimal
    method: str  # "osrm" (road distance) | "estimate" (straight line x detour factor)
    route: tuple[str, ...]  # "home" -> stop ids -> "home"
    formula: str


def haversine_km(a: GeoPoint, b: GeoPoint) -> Decimal:
    lat1, lon1 = math.radians(float(a.latitude)), math.radians(float(a.longitude))
    lat2, lon2 = math.radians(float(b.latitude)), math.radians(float(b.longitude))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance = 2 * 6371.0088 * math.asin(math.sqrt(h))
    return Decimal(repr(round(distance, 3)))


def fuel_cost(distance_km: Decimal, vehicle: VehicleSpec) -> tuple[Decimal, Decimal]:
    if vehicle.km_per_liter <= 0:
        raise ValueError("km_per_liter must be positive")
    liters = distance_km / vehicle.km_per_liter
    return liters.quantize(LITERS, rounding=ROUND_HALF_UP), quantize_money(
        liters * vehicle.fuel_price_per_liter
    )


def travel_cost(
    distance_km: Decimal,
    vehicle: VehicleSpec,
    *,
    tolls: Decimal = Decimal("0"),
    method: str,
    route: Sequence[str],
) -> TravelCost:
    distance = distance_km.quantize(KM, rounding=ROUND_HALF_UP)
    liters, fuel = fuel_cost(distance, vehicle)
    total = quantize_money(fuel + tolls)
    formula = (
        f"{_fmt(distance, 1)} km ÷ {_fmt(vehicle.km_per_liter)} km/l × "
        f"R$ {_fmt(vehicle.fuel_price_per_liter)}/l + R$ {_fmt(tolls, 2)} de pedágio "
        f"= R$ {_fmt(total, 2)}"
    )
    return TravelCost(
        distance_km=distance,
        liters=liters,
        fuel_cost=fuel,
        tolls=quantize_money(tolls),
        total=total,
        method=method,
        route=tuple(route),
        formula=formula,
    )


def best_route(
    stops: Sequence[str], distance: Callable[[str, str], Decimal]
) -> tuple[tuple[str, ...], Decimal]:
    """Shortest closed tour home -> stops -> home (exact for the small stop counts used)."""
    if not stops:
        return ("home", "home"), Decimal("0")
    best: tuple[tuple[str, ...], Decimal] | None = None
    for order in permutations(stops):
        path = ("home", *order, "home")
        total = sum(
            (distance(path[i], path[i + 1]) for i in range(len(path) - 1)), start=Decimal("0")
        )
        if best is None or total < best[1]:
            best = (path, total)
    assert best is not None
    return best


def _fmt(value: Decimal, places: int | None = None) -> str:
    text = f"{value:.{places}f}" if places is not None else f"{value.normalize():f}"
    return text.replace(".", ",")
