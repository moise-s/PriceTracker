"""Opt-in live smoke tests against the real supermarket sites.

Run with ``uv run pytest tests/live --live``. They are polite (robots-checked,
paced) and deliberately small: three product natures per market. They are kept
out of the deterministic suite because the sites and their prices change.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import pytest

from pricetracker.adapters.base import AdapterContext, DocumentCache, SearchQuery, StoreContext
from pricetracker.adapters.http import PoliteClient
from pricetracker.adapters.registry import get_adapter
from pricetracker.domain.matching import MatchSpec, select_best
from pricetracker.seed.catalog import CATALOG

pytestmark = pytest.mark.live

SPECS = {item["slug"]: MatchSpec.model_validate(item["match_spec"]) for item in CATALOG}
STORES = {
    s["slug"]: s
    for s in json.loads((resources.files("pricetracker.seed") / "stores.json").read_text())[
        "stores"
    ]
}
NATURES = {
    "package": "arroz-branco-1kg",
    "weight": "alcatra-kg",
    "unit": "ovos-30-unidades",
}
CASES = [
    ("angeloni", "beira-mar", ["package", "weight", "unit"]),
    ("bistek", "costeira-do-pirajubae-florianopolis", ["package", "weight", "unit"]),
    ("fort", "kobrasol-160", ["package", "weight", "unit"]),
]


def _store(slug: str) -> StoreContext:
    row = STORES[slug]
    return StoreContext(
        store_id=slug, slug=slug, name=row["name"], external_id=row.get("external_id"),
        price_context=row.get("price_context") or {}, postal_code=row.get("postal_code"),
    )  # fmt: skip


@pytest.mark.parametrize(("market", "store_slug", "natures"), CASES)
async def test_market_finds_three_natures(
    settings: Any, market: str, store_slug: str, natures: list[str]
) -> None:
    adapter = get_adapter(market)
    client = PoliteClient(
        allowed_domains=adapter.allowed_domains,
        settings=settings.model_copy(update={"http_min_interval_seconds": 1.2}),
    )
    try:
        for nature in natures:
            spec = SPECS[NATURES[nature]]
            ctx = AdapterContext(client=client, store=_store(store_slug), cache=DocumentCache())
            outcome = await adapter.search(
                ctx, SearchQuery(spec.search_terms[0], spec.search_terms, spec)
            )
            evaluations, best = select_best(outcome.listings, spec)
            assert best is not None, (
                f"{market}/{nature}: nothing matched ({len(outcome.listings)} listings)"
            )
            listing = evaluations[best][0]
            assert listing.price is not None and listing.price > 0
    finally:
        await client.aclose()


async def test_imperatriz_club_offers_reachable(settings: Any) -> None:
    adapter = get_adapter("imperatriz")
    client = PoliteClient(allowed_domains=adapter.allowed_domains, settings=settings)
    try:
        spec = SPECS["arroz-branco-1kg"]
        ctx = AdapterContext(
            client=client, store=_store("presidente-kennedy-sao-jose"), cache=DocumentCache()
        )
        outcome = await adapter.search(
            ctx, SearchQuery(spec.search_terms[0], spec.search_terms, spec)
        )
        assert len(outcome.listings) > 20  # current club offers for the store
        assert all(listing.price is not None for listing in outcome.listings)
    finally:
        await client.aclose()
