"""Deterministic, explainable matching of market listings to a user's product.

Hard rules (identity, required words, exclusions, brand, size/unit) decide whether
a listing is *equivalent*. Soft signals only rank equivalent listings. Every
decision carries machine-readable reasons so the UI can explain it. The LLM is
never allowed to override these rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.text import normalize, phrase_in, tokens
from pricetracker.domain.units import Measure, describe_quantity, to_base, within_tolerance
from pricetracker.models.enums import Availability, SoldBy, Unit


class SizeSpec(BaseModel):
    quantity: Decimal = Field(gt=0)
    unit: Unit
    tolerance_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    def base(self) -> Measure:
        return to_base(self.quantity, self.unit)


class MatchSpec(BaseModel):
    """Matching rules for one product. Stored as JSON on catalog items and products."""

    search_terms: list[str] = Field(min_length=1)
    required: list[list[str]] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    strict_brand: bool = False
    sold_by: SoldBy = SoldBy.PACKAGE
    size: SizeSpec | None = None
    gtins: list[str] = Field(default_factory=list)
    approx_unit_weight_kg: Decimal | None = Field(default=None, gt=0)
    max_piece_kg: Decimal = Field(default=Decimal("3"), gt=0)
    allow_bulk: bool = False

    @field_validator("search_terms", "excluded", "brands", "gtins")
    @classmethod
    def _strip(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v and v.strip()]

    @field_validator("required")
    @classmethod
    def _strip_groups(cls, groups: list[list[str]]) -> list[list[str]]:
        return [[v.strip() for v in g if v.strip()] for g in groups if any(v.strip() for v in g)]


@dataclass(frozen=True)
class Pins:
    accepted: frozenset[str] = frozenset()
    rejected: frozenset[str] = frozenset()


@dataclass
class MatchResult:
    accepted: bool
    score: Decimal
    reasons: list[str] = field(default_factory=list)
    identity: bool = False

    def reject(self, reason: str) -> None:
        self.accepted = False
        self.reasons.append(reason)


def _name_overlap(spec: MatchSpec, title_tokens: set[str]) -> Decimal:
    wanted = set(tokens(spec.search_terms[0]))
    wanted = {t for t in wanted if not t.isdigit()}
    if not wanted:
        return Decimal("0")
    return Decimal(len(wanted & title_tokens)) / Decimal(len(wanted))


def evaluate(listing: Listing, spec: MatchSpec, pins: Pins | None = None) -> MatchResult:
    pins = pins or Pins()
    haystack = normalize(" ".join(filter(None, [listing.title, listing.brand])))
    title_tokens = set(tokens(haystack))
    result = MatchResult(accepted=True, score=Decimal("0"))
    key = listing.listing_key

    if key in pins.rejected:
        result.reject("pin_rejected")
        return result
    if key in pins.accepted:
        result.identity = True
        result.reasons.append("pin_accepted")
        result.score = Decimal("1")
        return result
    if (
        listing.gtin
        and spec.gtins
        and listing.gtin.lstrip("0") in {g.lstrip("0") for g in spec.gtins}
    ):
        result.identity = True
        result.reasons.append("gtin_match")
        result.score = Decimal("1")
        return result

    for group in spec.required:
        if not any(phrase_in(option, haystack) for option in group):
            result.reject(f"missing_required:{group[0]}")
    for excluded in spec.excluded:
        if phrase_in(excluded, haystack):
            result.reject(f"excluded:{excluded}")

    brand_hit = False
    if spec.brands:
        listing_brand = normalize(listing.brand)
        brand_hit = any(
            phrase_in(brand, haystack) or (listing_brand and listing_brand == normalize(brand))
            for brand in spec.brands
        )
        if brand_hit:
            result.reasons.append("brand_preferred")
        elif spec.strict_brand:
            result.reject("brand_mismatch")

    size_exact = _check_size_and_unit(listing, spec, result)

    overlap = _name_overlap(spec, title_tokens)
    score = Decimal("0.55") + Decimal("0.25") * overlap
    if brand_hit:
        score += Decimal("0.1")
    if size_exact:
        score += Decimal("0.1")
    score = min(score, Decimal("1")) * listing.confidence
    result.score = score.quantize(Decimal("0.001"))
    return result


def _check_size_and_unit(listing: Listing, spec: MatchSpec, result: MatchResult) -> bool:
    """Apply sold-by and package-size rules. Returns True when the size is an exact match."""
    package = listing.effective_package

    if spec.sold_by == SoldBy.WEIGHT:
        if listing.sale_unit == SaleUnit.KG or package.per_kg:
            result.reasons.append("sold_per_kg")
            return True
        if listing.sale_unit == SaleUnit.PIECE and listing.piece_weight_kg:
            if listing.piece_weight_kg > spec.max_piece_kg:
                result.reject(
                    f"piece_too_large:{describe_quantity(listing.piece_weight_kg, Unit.KG)}"
                )
                return False
            result.reasons.append("variable_weight_piece")
            return False
        if package.measure is not None and package.measure.unit == Unit.KG:
            if package.measure.quantity > spec.max_piece_kg:
                result.reject(f"piece_too_large:{package.measure.describe()}")
                return False
            result.reasons.append(
                "variable_weight_pack" if package.approximate else "fixed_weight_pack"
            )
            return False
        result.reject("not_sold_by_weight")
        return False

    if spec.sold_by == SoldBy.UNIT:
        if listing.sale_unit == SaleUnit.PIECE or package.single_unit or package.count == 1:
            result.reasons.append("sold_per_unit")
            return True
        if (listing.sale_unit == SaleUnit.KG or package.per_kg) and spec.approx_unit_weight_kg:
            result.reasons.append("per_kg_with_estimated_unit_weight")
            return False
        if package.count and package.count > 1:
            result.reject(f"multi_unit_pack:{package.count}")
            return False
        if listing.sale_unit == SaleUnit.KG or package.per_kg:
            result.reject("sold_per_kg_without_unit_weight")
            return False
        if package.measure is None:
            # A plain "Mamão Papaia" listing priced per piece.
            result.reasons.append("assumed_single_unit")
            return False
        result.reject(f"unexpected_package:{package.measure.describe()}")
        return False

    # PACKAGE
    if spec.size is None:
        result.reasons.append("no_size_rule")
        return False
    required = spec.size.base()
    if listing.sale_unit == SaleUnit.KG or (package.per_kg and package.measure is None):
        if spec.allow_bulk and required.unit == Unit.KG:
            result.reasons.append("bulk_per_kg_allowed")
            return False
        result.reject("sold_per_kg_not_package")
        return False
    if required.unit == Unit.UN:
        if package.count is None:
            result.reject("count_unknown")
            return False
        actual = Decimal(package.count)
        if actual == required.quantity:
            result.reasons.append(f"size_ok:{package.count} un")
            return True
        if within_tolerance(actual, required.quantity, spec.size.tolerance_pct):
            result.reasons.append(f"size_within_tolerance:{package.count} un")
            return False
        result.reject(f"size_mismatch:{package.count} un")
        return False
    if package.measure is None:
        result.reject("size_unknown")
        return False
    if package.measure.unit != required.unit:
        result.reject(f"unit_mismatch:{package.measure.describe()}")
        return False
    if package.measure.quantity == required.quantity:
        result.reasons.append(f"size_ok:{package.measure.describe()}")
        return True
    if within_tolerance(package.measure.quantity, required.quantity, spec.size.tolerance_pct):
        result.reasons.append(f"size_within_tolerance:{package.measure.describe()}")
        return False
    result.reject(f"size_mismatch:{package.measure.describe()}")
    return False


def comparable_unit_price(listing: Listing, spec: MatchSpec) -> Decimal | None:
    """Price per base unit (kg, l or un) used to pick the best equivalent listing."""
    price = listing.price if listing.price is not None else listing.regular_price
    if price is None:
        return None
    package = listing.effective_package
    if listing.sale_unit == SaleUnit.KG or (package.per_kg and package.measure is None):
        return price
    if listing.sale_unit == SaleUnit.PIECE:
        if spec.sold_by == SoldBy.WEIGHT and listing.piece_weight_kg:
            return price / listing.piece_weight_kg
        return price
    if spec.sold_by == SoldBy.UNIT:
        return price
    if spec.size is not None and spec.size.base().unit == Unit.UN and package.count:
        return price / Decimal(package.count)
    if package.measure is not None and package.measure.quantity > 0:
        return price / package.measure.quantity
    return price


def select_best(
    listings: list[Listing], spec: MatchSpec, pins: Pins | None = None
) -> tuple[list[tuple[Listing, MatchResult]], int | None]:
    """Evaluate listings and return (evaluations, index of the chosen listing).

    The chosen listing is the cheapest *available, priced, equivalent* listing by
    comparable unit price; ties go to the higher match score. Identity matches
    (pin/GTIN) win over heuristic matches.
    """
    evaluations = [(listing, evaluate(listing, spec, pins)) for listing in listings]
    best_index: int | None = None
    best_key: tuple[int, Decimal, Decimal] | None = None
    for index, (listing, match) in enumerate(evaluations):
        if not match.accepted:
            continue
        if listing.availability == Availability.OUT_OF_STOCK:
            continue
        unit_price = comparable_unit_price(listing, spec)
        if unit_price is None:
            continue
        key = (0 if match.identity else 1, unit_price, -match.score)
        if best_key is None or key < best_key:
            best_key = key
            best_index = index
    return evaluations, best_index
