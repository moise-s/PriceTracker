"""Line cost: list quantity versus package quantity.

List quantity (what the user wants: 2 packages, 1.5 kg, 3 units) and package
quantity (what the store sells: a 1 kg bag, a price per kg, a piece of ~450 g)
are different concepts. ``line_cost`` converts one into the other explicitly and
reports every assumption it makes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal

from pricetracker.domain.listing import SaleUnit
from pricetracker.domain.money import quantize_money, quantize_unit_price
from pricetracker.domain.units import Measure, describe_quantity, to_base
from pricetracker.models.enums import PriceKind, Unit


@dataclass(frozen=True)
class OfferPricing:
    """Pricing facts of one observation, independent of the list quantity."""

    sale_unit: SaleUnit
    price: Decimal | None  # selling price per sale unit (promo included)
    regular_price: Decimal | None = None
    club_price: Decimal | None = None
    quantity_min: int | None = None
    quantity_price: Decimal | None = None
    quantity_mode: str | None = None  # "from_min" | "per_group"
    package_measure: Measure | None = None
    package_count: int | None = None
    piece_weight_kg: Decimal | None = None


@dataclass(frozen=True)
class LineCost:
    cost: Decimal
    sale_units: Decimal  # packages / pieces / kilograms to buy
    sale_unit_label: str
    price_kind: PriceKind
    unit_price: Decimal | None  # per kg / l / un
    unit_price_unit: Unit | None
    approximate: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


class IncompatibleQuantity(ValueError):
    """The requested quantity cannot be converted for this offer."""


def _ceil(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding=ROUND_CEILING)


def unit_price_for(pricing: OfferPricing, price: Decimal) -> tuple[Decimal | None, Unit | None]:
    if pricing.sale_unit == SaleUnit.KG:
        return quantize_unit_price(price), Unit.KG
    if pricing.sale_unit == SaleUnit.PIECE:
        if pricing.piece_weight_kg:
            return quantize_unit_price(price / pricing.piece_weight_kg), Unit.KG
        return quantize_unit_price(price), Unit.UN
    if pricing.package_measure is not None and pricing.package_measure.quantity > 0:
        return (
            quantize_unit_price(price / pricing.package_measure.quantity),
            pricing.package_measure.unit,
        )
    if pricing.package_count:
        return quantize_unit_price(price / Decimal(pricing.package_count)), Unit.UN
    return None, None


def _cost_for_units(
    pricing: OfferPricing, sale_units: Decimal, use_club: bool
) -> tuple[Decimal, PriceKind, Decimal]:
    """Cheapest applicable total for ``sale_units`` -> (cost, price kind, average unit price)."""
    if pricing.price is None:
        raise IncompatibleQuantity("offer has no price")
    kind = (
        PriceKind.PROMO
        if pricing.regular_price is not None and pricing.price < pricing.regular_price
        else PriceKind.REGULAR
    )
    options: list[tuple[Decimal, PriceKind]] = [(pricing.price * sale_units, kind)]
    if use_club and pricing.club_price is not None:
        options.append((pricing.club_price * sale_units, PriceKind.CLUB))
    if pricing.quantity_min is not None and pricing.quantity_price is not None:
        minimum = Decimal(pricing.quantity_min)
        if pricing.quantity_mode == "per_group":
            groups = (sale_units / minimum).to_integral_value(rounding="ROUND_FLOOR")
            if groups >= 1:
                rest = sale_units - groups * minimum
                options.append(
                    (
                        groups * minimum * pricing.quantity_price + rest * pricing.price,
                        PriceKind.QUANTITY,
                    )
                )
        elif sale_units >= minimum:
            options.append((pricing.quantity_price * sale_units, PriceKind.QUANTITY))
    cost, chosen = min(options, key=lambda option: option[0])
    average = cost / sale_units if sale_units else cost
    return cost, chosen, average


def line_cost(
    pricing: OfferPricing,
    quantity: Decimal,
    unit: Unit,
    *,
    use_club: bool = False,
    approx_unit_weight_kg: Decimal | None = None,
    weight_based: bool = False,
) -> LineCost:
    """Cost of buying ``quantity`` ``unit`` of this offer.

    ``weight_based`` marks products the user buys by weight (meat, fruit): a pack of
    approximate weight is then converted to a price per kg and multiplied by the
    requested kilograms, which is what the purchase costs at the counter.
    """
    if quantity <= 0:
        raise IncompatibleQuantity("quantity must be positive")
    notes: list[str] = []
    approximate = False

    if weight_based and unit in (Unit.KG, Unit.G):
        pack_kg: Decimal | None = None
        if pricing.sale_unit == SaleUnit.PIECE and pricing.piece_weight_kg:
            pack_kg = pricing.piece_weight_kg
        elif (
            pricing.sale_unit == SaleUnit.PACKAGE
            and pricing.package_measure is not None
            and pricing.package_measure.unit == Unit.KG
        ):
            pack_kg = pricing.package_measure.quantity
        if pack_kg is not None and pack_kg > 0:
            kilos = to_base(quantity, unit).quantity
            _pack_total, kind, pack_price = _cost_for_units(pricing, Decimal("1"), use_club)
            per_kg = pack_price / pack_kg
            notes.append(
                f"preço por kg calculado da embalagem de ~{describe_quantity(pack_kg, Unit.KG)}"
            )
            return LineCost(
                cost=quantize_money(per_kg * kilos),
                sale_units=kilos,
                sale_unit_label="kg",
                price_kind=kind,
                unit_price=quantize_unit_price(per_kg),
                unit_price_unit=Unit.KG,
                approximate=True,
                notes=tuple(notes),
            )

    if pricing.sale_unit == SaleUnit.KG:
        if unit in (Unit.KG, Unit.G):
            kilos = to_base(quantity, unit).quantity
        elif unit in (Unit.UN, Unit.PCT):
            weight = pricing.piece_weight_kg or approx_unit_weight_kg
            if weight is None:
                raise IncompatibleQuantity("offer is priced per kg and the unit weight is unknown")
            kilos = quantity * weight
            approximate = True
            notes.append(f"peso médio estimado de {describe_quantity(weight, Unit.KG)} por unidade")
        else:
            raise IncompatibleQuantity(f"cannot buy {unit} of a per-kg offer")
        total, kind, price = _cost_for_units(pricing, kilos, use_club)
        unit_price, unit_price_unit = unit_price_for(pricing, price)
        return LineCost(
            cost=quantize_money(total),
            sale_units=kilos,
            sale_unit_label="kg",
            price_kind=kind,
            unit_price=unit_price,
            unit_price_unit=unit_price_unit,
            approximate=approximate,
            notes=tuple(notes),
        )

    if pricing.sale_unit == SaleUnit.PIECE:
        if unit in (Unit.UN, Unit.PCT):
            pieces = _ceil(quantity)
        elif unit in (Unit.KG, Unit.G):
            if not pricing.piece_weight_kg:
                raise IncompatibleQuantity("piece weight unknown; cannot convert kg to pieces")
            pieces = _ceil(to_base(quantity, unit).quantity / pricing.piece_weight_kg)
            approximate = True
            notes.append(
                f"{pieces} peça(s) de ~{describe_quantity(pricing.piece_weight_kg, Unit.KG)}"
            )
        else:
            raise IncompatibleQuantity(f"cannot buy {unit} of a per-piece offer")
        if pricing.piece_weight_kg:
            approximate = True
        total, kind, price = _cost_for_units(pricing, pieces, use_club)
        unit_price, unit_price_unit = unit_price_for(pricing, price)
        return LineCost(
            cost=quantize_money(total),
            sale_units=pieces,
            sale_unit_label="un",
            price_kind=kind,
            unit_price=unit_price,
            unit_price_unit=unit_price_unit,
            approximate=approximate,
            notes=tuple(notes),
        )

    # Fixed package.
    if unit == Unit.PCT:
        packages = _ceil(quantity)
    elif unit == Unit.UN:
        if pricing.package_count and pricing.package_count > 1:
            packages = _ceil(quantity / Decimal(pricing.package_count))
            if packages * pricing.package_count != quantity:
                notes.append(
                    f"{packages} embalagem(ns) com {pricing.package_count} un para {quantity.normalize()} un"
                )
        else:
            packages = _ceil(quantity)
    else:
        wanted = to_base(quantity, unit)
        if pricing.package_measure is None or pricing.package_measure.unit != wanted.unit:
            raise IncompatibleQuantity("package size unknown or in a different unit")
        packages = _ceil(wanted.quantity / pricing.package_measure.quantity)
        bought = packages * pricing.package_measure.quantity
        if bought != wanted.quantity:
            notes.append(
                f"{packages} embalagem(ns) de {pricing.package_measure.describe()} "
                f"= {describe_quantity(bought, wanted.unit)}"
            )
    total, kind, price = _cost_for_units(pricing, packages, use_club)
    unit_price, unit_price_unit = unit_price_for(pricing, price)
    return LineCost(
        cost=quantize_money(total),
        sale_units=packages,
        sale_unit_label="pct",
        price_kind=kind,
        unit_price=unit_price,
        unit_price_unit=unit_price_unit,
        approximate=approximate,
        notes=tuple(notes),
    )
