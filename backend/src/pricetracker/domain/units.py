"""Units, package-size parsing and conversions.

Mass is normalised to kilograms, volume to litres and counts to units. Package
sizes are parsed from listing titles (``"Arroz Tio João 1kg"``, ``"2 x 500 g"``,
``"Ovos c/30"``) and from structured fields when a market provides them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from pricetracker.domain.text import strip_accents
from pricetracker.models.enums import Unit

BASE_UNIT: dict[Unit, Unit] = {
    Unit.G: Unit.KG,
    Unit.KG: Unit.KG,
    Unit.ML: Unit.L,
    Unit.L: Unit.L,
    Unit.M: Unit.M,
    Unit.UN: Unit.UN,
    Unit.PCT: Unit.UN,
}
TO_BASE_FACTOR: dict[Unit, Decimal] = {
    Unit.G: Decimal("0.001"),
    Unit.KG: Decimal("1"),
    Unit.ML: Decimal("0.001"),
    Unit.L: Decimal("1"),
    Unit.M: Decimal("1"),
    Unit.UN: Decimal("1"),
    Unit.PCT: Decimal("1"),
}

_UNIT_ALIASES: dict[str, Unit] = {
    "kg": Unit.KG, "kgs": Unit.KG, "kilo": Unit.KG, "kilos": Unit.KG, "quilo": Unit.KG,
    "quilos": Unit.KG, "g": Unit.G, "gr": Unit.G, "grs": Unit.G, "grama": Unit.G,
    "gramas": Unit.G, "ml": Unit.ML, "l": Unit.L, "lt": Unit.L, "lts": Unit.L,
    "m": Unit.M, "metro": Unit.M, "metros": Unit.M, "metres": Unit.M, "meters": Unit.M,
    "litro": Unit.L, "litros": Unit.L, "un": Unit.UN, "und": Unit.UN, "unid": Unit.UN,
    "unidade": Unit.UN, "unidades": Unit.UN, "pct": Unit.PCT, "pacote": Unit.PCT,
}  # fmt: skip

_MASS_VOLUME_UNITS = (
    r"(kg|kgs|kilos?|quilos?|g|gr|grs|gramas?|mg|ml|l|lt|lts|litros?|m|metros?|metres?|meters?)"
)
_NUMBER = r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)"
_MULTIPACK = re.compile(rf"(?<![\d.,])(\d{{1,3}})\s*x\s*{_NUMBER}\s*{_MASS_VOLUME_UNITS}\b")
_SIZE = re.compile(rf"(?<![\d.,])(?<![a-z]){_NUMBER}\s*{_MASS_VOLUME_UNITS}\b")
_COUNT_PATTERNS = [
    re.compile(r"(?<![\d.,])(\d{1,4})\s*(?:unidades|unidade|unids?|unds?|un)\b"),
    re.compile(r"\bc\s*/\s*(\d{1,4})\b"),
    re.compile(r"\bcom\s+(\d{1,4})\b"),
    re.compile(
        r"(?<![\d.,])(\d{1,4})\s*(?:ovos|filtros|saches|sachets|capsulas|rolos|folhas|pecas|saquinhos)\b"
    ),
    re.compile(
        r"\b(?:cartela|bandeja|caixa|pacote|pct|pack|embalagem)\s+(?:com\s+|c\s*/\s*)?(\d{1,4})\b"
    ),
]
_DOZEN = re.compile(r"\b(duzia|dz)\b")
_PER_KG = re.compile(r"(?:\bpor\s+kg\b|/\s*kg\b|\bgranel\b|\ba\s+granel\b|(?<![\d.,\s])\s*\bkg\b)")
_BARE_KG = re.compile(r"(?<![\d.,])(?<!\d)\s(kg|kilo|quilo)\b|^(kg|kilo|quilo)\b")
_APPROX = re.compile(r"\b(aprox|aproximadamente|aprox\.|peso\s+medio|media\s+de)\b")
_SINGLE_UNIT = re.compile(r"\b(unidade|unid|und)\b")


@dataclass(frozen=True)
class Measure:
    """A quantity in a base unit (kg, l or un)."""

    quantity: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        if self.unit not in (Unit.KG, Unit.L, Unit.M, Unit.UN):
            raise ValueError(f"Measure must use a base unit, got {self.unit}")

    def describe(self) -> str:
        return describe_quantity(self.quantity, self.unit)


@dataclass(frozen=True)
class PackageInfo:
    measure: Measure | None = None  # total mass/volume (multipacks multiplied)
    count: int | None = None  # number of units in the pack (eggs, filters) or multipack count
    per_kg: bool = False  # listing priced per kg without an explicit amount ("Alcatra kg")
    approximate: bool = False  # "aprox." variable-weight piece
    single_unit: bool = False  # "unidade" without a number
    matched: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_size(self) -> bool:
        return self.measure is not None or self.count is not None


def parse_number(raw: str) -> Decimal | None:
    raw = raw.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_unit(text: str | None) -> Unit | None:
    if not text:
        return None
    alias = strip_accents(text).strip().lower().rstrip(".")
    if alias == "mg":
        return None
    return _UNIT_ALIASES.get(alias)


def to_base(quantity: Decimal, unit: Unit) -> Measure:
    return Measure(quantity * TO_BASE_FACTOR[unit], BASE_UNIT[unit])


def _unit_from_token(raw_unit: str) -> tuple[Unit, Decimal] | None:
    word = raw_unit.lower()
    if word == "mg":
        return Unit.KG, Decimal("0.000001")
    unit = _UNIT_ALIASES.get(word) or _UNIT_ALIASES.get(word.rstrip("s"))
    if unit is None:
        return None
    return BASE_UNIT[unit], TO_BASE_FACTOR[unit]


def parse_package(title: str | None) -> PackageInfo:
    """Extract package size information from a listing title."""
    if not title:
        return PackageInfo()
    text = strip_accents(title).lower().replace("\xa0", " ")
    matched: list[str] = []

    measure: Measure | None = None
    count: int | None = None

    multi = _MULTIPACK.search(text)
    if multi:
        n = int(multi.group(1))
        size = parse_number(multi.group(2))
        unit_info = _unit_from_token(multi.group(3))
        if size is not None and unit_info and n > 0:
            base_unit, factor = unit_info
            measure = Measure(size * factor * n, base_unit)
            count = n
            matched.append(multi.group(0))
    if measure is None:
        for size_match in _SIZE.finditer(text):
            size = parse_number(size_match.group(1))
            unit_info = _unit_from_token(size_match.group(2))
            if size is None or unit_info is None or size <= 0:
                continue
            base_unit, factor = unit_info
            measure = Measure(size * factor, base_unit)
            matched.append(size_match.group(0))
            break

    if count is None:
        for pattern in _COUNT_PATTERNS:
            count_match = pattern.search(text)
            if count_match:
                value = int(count_match.group(1))
                if 0 < value <= 1000:
                    count = value
                    matched.append(count_match.group(0))
                    break
        if count is None and _DOZEN.search(text):
            count = 12
            matched.append("duzia")

    # Roll lengths are per roll, never per ply. Prefer an explicit roll count
    # over generic counts (e.g. "2 folhas"). Missing counts must not invent a
    # pack size or make a multi-roll pack look cheaper than it is.
    if measure is not None and measure.unit == Unit.M and not multi:
        roll_context = bool(re.search(r"\b(?:rolos?|rolls?)\b|higienico|toilet", text))
        if roll_context:
            roll_match = re.search(r"\b(\d{1,3})\s*(?:rolos?|rolls?|unidades?|un)\b", text)
            if roll_match is None:
                roll_match = re.search(r"\b(?:c\s*/|com|pack of|leve)\s*(\d{1,3})\b", text)
            count = int(roll_match.group(1)) if roll_match else None
            if roll_match is not None and count and count > 0:
                if not re.search(r"\btotal\b", text):
                    measure = Measure(measure.quantity * count, Unit.M)
                matched.append(roll_match.group(0))
            elif not re.search(r"\btotal\b", text):
                measure = None
    approximate = bool(_APPROX.search(text))
    per_kg = measure is None and bool(_BARE_KG.search(" " + text) or _PER_KG.search(text))
    if measure is None and not per_kg and re.search(r"\bgranel\b", text):
        per_kg = True
    single_unit = count is None and measure is None and bool(_SINGLE_UNIT.search(text))

    return PackageInfo(
        measure=measure,
        count=count,
        per_kg=per_kg,
        approximate=approximate,
        single_unit=single_unit,
        matched=tuple(matched),
    )


def describe_quantity(quantity: Decimal, unit: Unit | str) -> str:
    unit = Unit(unit)
    q = quantity.normalize()
    if unit == Unit.KG and quantity < 1:
        grams = (quantity * 1000).normalize()
        return f"{_fmt(grams)} g"
    if unit == Unit.L and quantity < 1:
        ml = (quantity * 1000).normalize()
        return f"{_fmt(ml)} ml"
    label = {
        Unit.KG: "kg",
        Unit.L: "L",
        Unit.M: "m",
        Unit.UN: "un",
        Unit.G: "g",
        Unit.ML: "ml",
        Unit.PCT: "pct",
    }[unit]
    return f"{_fmt(q)} {label}"


def _fmt(value: Decimal) -> str:
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def within_tolerance(actual: Decimal, required: Decimal, tolerance_pct: Decimal) -> bool:
    if required <= 0:
        return False
    delta = abs(actual - required) / required * Decimal(100)
    return delta <= tolerance_pct
