"""Freshness and outlier detection. Suspicious data is flagged, never silently dropped."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median

from pricetracker.domain.money import format_brl
from pricetracker.models.enums import Unit

# Sanity bounds per comparable unit (R$ per kg / l / un) for supermarket groceries.
PLAUSIBLE_UNIT_PRICE: dict[Unit, tuple[Decimal, Decimal]] = {
    Unit.KG: (Decimal("0.50"), Decimal("600")),
    Unit.L: (Decimal("0.30"), Decimal("400")),
    Unit.UN: (Decimal("0.03"), Decimal("600")),
}


def is_stale(observed_at: datetime, now: datetime, freshness_days: int) -> bool:
    return now - observed_at > timedelta(days=freshness_days)


def age_days(observed_at: datetime, now: datetime) -> Decimal:
    seconds = Decimal(str((now - observed_at).total_seconds()))
    return (seconds / Decimal(86400)).quantize(Decimal("0.1"))


@dataclass(frozen=True)
class OutlierAssessment:
    is_outlier: bool
    reason: str | None = None


def assess_outlier(
    unit_price: Decimal | None,
    unit: Unit | None,
    history: list[Decimal],
    peers: list[Decimal],
) -> OutlierAssessment:
    """Flag implausible prices.

    - outside absolute sanity bounds for the unit;
    - a change beyond 2.5x / 0.4x of the product's own historical median (>= 3 points);
    - far from other stores' current prices for the same product (>= 2 peers).
    """
    if unit_price is None or unit is None:
        return OutlierAssessment(False)
    low, high = PLAUSIBLE_UNIT_PRICE.get(unit, (Decimal("0"), Decimal("100000")))
    if unit_price < low or unit_price > high:
        return OutlierAssessment(
            True, f"preço por {unit.value} fora da faixa plausível ({format_brl(unit_price)})"
        )
    if len(history) >= 3:
        reference = Decimal(median(history))
        if reference > 0 and (
            unit_price > reference * Decimal("2.5") or unit_price < reference * Decimal("0.4")
        ):
            return OutlierAssessment(
                True,
                f"mudança implausível: {format_brl(unit_price)} vs mediana histórica {format_brl(reference)}",
            )
    if len(peers) >= 2:
        reference = Decimal(median(peers))
        if reference > 0 and (
            unit_price > reference * Decimal("3") or unit_price < reference * Decimal("0.35")
        ):
            return OutlierAssessment(
                True,
                f"muito diferente das outras lojas: {format_brl(unit_price)} vs mediana {format_brl(reference)}",
            )
    return OutlierAssessment(False)
