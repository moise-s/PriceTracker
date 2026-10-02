from __future__ import annotations

from pricetracker.adapters.angeloni import AngeloniAdapter
from pricetracker.adapters.base import MarketAdapter
from pricetracker.adapters.bistek import BistekAdapter
from pricetracker.adapters.fort import FortAdapter
from pricetracker.adapters.imperatriz import ImperatrizAdapter
from pricetracker.adapters.structured import StructuredAdapter

ADAPTERS: dict[str, type[MarketAdapter]] = {
    AngeloniAdapter.key: AngeloniAdapter,
    BistekAdapter.key: BistekAdapter,
    FortAdapter.key: FortAdapter,
    ImperatrizAdapter.key: ImperatrizAdapter,
    StructuredAdapter.key: StructuredAdapter,
}


def get_adapter(key: str) -> MarketAdapter:
    try:
        return ADAPTERS[key]()
    except KeyError as exc:
        raise LookupError(f"unknown adapter '{key}'") from exc
