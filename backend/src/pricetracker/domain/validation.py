"""Identifier validation helpers."""

from __future__ import annotations


def valid_gtin(code: str | None) -> bool:
    """GTIN-8/12/13/14 with a correct check digit (internal short codes are rejected)."""
    if not code or not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if (len(body) - i) % 2 == 1 else 1) for i, d in enumerate(body))
    return (10 - total % 10) % 10 == check
