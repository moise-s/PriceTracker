"""Money helpers. All monetary values are ``Decimal``; floats are converted exactly."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
UNIT_PRICE_PLACES = Decimal("0.0001")
ZERO = Decimal("0")

_NUMBER = re.compile(r"\d[\d.,]*")
_SPACES = str.maketrans({"\xa0": " ", " ": " ", " ": " "})


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_unit_price(value: Decimal) -> Decimal:
    return value.quantize(UNIT_PRICE_PLACES, rounding=ROUND_HALF_UP)


def to_decimal(value: object) -> Decimal | None:
    """Convert JSON numbers or numeric strings to Decimal without float artefacts."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return Decimal(repr(value))
    if isinstance(value, str):
        return parse_brl(value)
    return None


def to_money(value: object) -> Decimal | None:
    number = to_decimal(value)
    if number is None:
        return None
    return quantize_money(number)


def parse_brl(text: str) -> Decimal | None:
    """Parse Brazilian-formatted money text.

    Handles ``"R$ 1.234,56"``, ``"7,79"``, ``"R$12"``, ``"12.90"`` and ``"1.234"``
    (thousands). Returns ``None`` when no number is present.
    """
    if not text:
        return None
    cleaned = text.translate(_SPACES)
    match = _NUMBER.search(cleaned)
    if not match:
        return None
    raw = match.group(0).rstrip(".,")
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            normalized = raw.replace(".", "").replace(",", ".")
        else:
            normalized = raw.replace(",", "")
    elif "," in raw:
        head, _, tail = raw.rpartition(",")
        normalized = head.replace(",", "") + "." + tail
    elif raw.count(".") >= 1:
        head, _, tail = raw.rpartition(".")
        if len(tail) == 3 and head.replace(".", "").isdigit():
            normalized = raw.replace(".", "")  # 1.234 -> thousands separator
        else:
            normalized = head.replace(".", "") + "." + tail
    else:
        normalized = raw
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def format_brl(value: Decimal | None) -> str:
    """Human format used in logs/CLI (the web UI formats with Intl)."""
    if value is None:
        return "—"
    quantized = quantize_money(value)
    sign = "-" if quantized < 0 else ""
    integer, _, cents = f"{abs(quantized):.2f}".partition(".")
    groups: list[str] = []
    while integer:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    return f"{sign}R$ {'.'.join(groups)},{cents}"
