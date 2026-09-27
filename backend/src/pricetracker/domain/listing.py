"""The normalised listing every adapter must produce."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pricetracker.domain.units import Measure, PackageInfo, parse_package
from pricetracker.models.enums import Availability, ExtractionMethod, SoldBy, Unit


class SaleUnit(StrEnum):
    """What one unit of ``Listing.price`` buys."""

    PACKAGE = "package"  # a fixed package (size from structured data or the title)
    KG = "kg"  # price per kilogram (variable weight, weighed at checkout)
    PIECE = "piece"  # one piece of approximate weight (``piece_weight_kg``)


@dataclass
class Listing:
    title: str
    method: ExtractionMethod
    url: str | None = None
    brand: str | None = None
    external_id: str | None = None
    sku: str | None = None
    gtin: str | None = None
    image_url: str | None = None
    price: Decimal | None = None  # current selling price for one sale unit (promo included)
    regular_price: Decimal | None = None  # list price ("de"), when shown
    club_price: Decimal | None = None
    club_label: str | None = None
    quantity_min: int | None = None
    quantity_price: Decimal | None = None  # price per sale unit when buying >= quantity_min
    quantity_mode: str | None = (
        None  # "from_min" (atacado) | "per_group" (leve X pague Y, 2a unidade -N%)
    )
    extra_prices: list[dict[str, Any]] = field(default_factory=list)  # e.g. store credit card price
    sale_unit: SaleUnit = SaleUnit.PACKAGE
    package_measure: Measure | None = None  # structured package size (overrides the title)
    package_count: int | None = None
    piece_weight_kg: Decimal | None = None
    listed_unit_price: Decimal | None = None  # e.g. R$ 39,90 per kg as displayed by the market
    listed_unit_price_unit: Unit | None = None
    availability: Availability = Availability.UNKNOWN
    confidence: Decimal = Decimal("1")
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def listing_key(self) -> str:
        """Stable identity inside a market: external id, then SKU, then URL path."""
        if self.external_id:
            return f"id:{self.external_id}"
        if self.sku:
            return f"sku:{self.sku}"
        if self.url:
            from urllib.parse import urlsplit

            return f"url:{urlsplit(self.url).path}"
        return f"title:{self.title.strip().lower()}"

    @property
    def title_package(self) -> PackageInfo:
        return parse_package(self.title)

    @property
    def effective_package(self) -> PackageInfo:
        """Title-derived package info refined by structured fields when available."""
        parsed = self.title_package
        measure = self.package_measure or parsed.measure
        count = self.package_count or parsed.count
        return PackageInfo(
            measure=measure,
            count=count,
            per_kg=parsed.per_kg or self.sale_unit == SaleUnit.KG,
            approximate=parsed.approximate or self.sale_unit == SaleUnit.PIECE,
            single_unit=parsed.single_unit,
            matched=parsed.matched,
        )

    @property
    def sold_by(self) -> SoldBy:
        return {
            SaleUnit.PACKAGE: SoldBy.PACKAGE,
            SaleUnit.KG: SoldBy.WEIGHT,
            SaleUnit.PIECE: SoldBy.UNIT,
        }[self.sale_unit]

    @property
    def promo_price(self) -> Decimal | None:
        if (
            self.price is not None
            and self.regular_price is not None
            and self.price < self.regular_price
        ):
            return self.price
        return None

    @property
    def base_price(self) -> Decimal | None:
        """Regular (list) price when known, else the selling price."""
        return self.regular_price if self.regular_price is not None else self.price


_DECIMAL_FIELDS = (
    "price", "regular_price", "club_price", "quantity_price", "piece_weight_kg",
    "listed_unit_price", "confidence",
)  # fmt: skip


def listing_to_dict(listing: Listing) -> dict[str, Any]:
    """JSON-safe representation (Decimals as strings) used for caches and raw payloads."""
    data: dict[str, Any] = {}
    for name in Listing.__dataclass_fields__:
        value = getattr(listing, name)
        if isinstance(value, Decimal):
            value = str(value)
        elif isinstance(value, StrEnum):
            value = value.value
        elif isinstance(value, Measure):
            value = {"quantity": str(value.quantity), "unit": value.unit.value}
        data[name] = value
    return data


def listing_from_dict(data: dict[str, Any]) -> Listing:
    values = dict(data)
    for name in _DECIMAL_FIELDS:
        if values.get(name) is not None:
            values[name] = Decimal(values[name])
    values["method"] = ExtractionMethod(values["method"])
    values["sale_unit"] = SaleUnit(values.get("sale_unit", "package"))
    values["availability"] = Availability(values.get("availability", "unknown"))
    if values.get("listed_unit_price_unit"):
        values["listed_unit_price_unit"] = Unit(values["listed_unit_price_unit"])
    measure = values.get("package_measure")
    if measure:
        values["package_measure"] = Measure(Decimal(measure["quantity"]), Unit(measure["unit"]))
    return Listing(**values)
