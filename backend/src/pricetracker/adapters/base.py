"""Common contract for market adapters.

An adapter turns a product query + store context into normalised ``Listing``
objects using the market's *deterministic* sources (public JSON endpoints used by
the storefront, JSON-LD, embedded state, then DOM parsing). Adapters never decide
equivalence: matching is done by ``pricetracker.domain.matching`` afterwards.

If an adapter can see content but cannot parse it deterministically, it returns
``needs_llm=True`` with a small sanitised ``llm_snippet``; the worker then decides
whether an LLM fallback is available and within budget.
"""

from __future__ import annotations

import abc
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, ClassVar

from pricetracker.adapters.http import PoliteClient
from pricetracker.domain.listing import Listing
from pricetracker.domain.matching import MatchSpec
from pricetracker.models.enums import ExtractionMethod


@dataclass(frozen=True)
class StoreContext:
    store_id: str
    slug: str
    name: str
    external_id: str | None
    price_context: dict[str, Any]
    postal_code: str | None = None
    city: str | None = None


@dataclass(frozen=True)
class SearchQuery:
    product_name: str
    terms: list[str]
    spec: MatchSpec
    preferred_urls: tuple[str, ...] = ()  # user pins and previously chosen listings, fetched first
    max_candidates: int = 16


@dataclass
class SearchOutcome:
    listings: list[Listing] = field(default_factory=list)
    method: ExtractionMethod | None = None
    query_used: str | None = None
    notes: list[str] = field(default_factory=list)
    needs_llm: bool = False
    llm_snippet: str | None = None
    llm_source_url: str | None = None


@dataclass(frozen=True)
class DiscoveredStore:
    slug: str
    name: str
    external_id: str | None
    street: str | None = None
    number: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    price_context: dict[str, Any] = field(default_factory=dict)
    price_scope_note: str | None = None


class DocumentCache:
    """Small key/value cache for public documents (sitemaps, indexes)."""

    def __init__(
        self,
        loader: Callable[[str], str | None] | None = None,
        saver: Callable[[str, str, str, timedelta], None] | None = None,
    ) -> None:
        self._memory: dict[str, str] = {}
        self._loader = loader
        self._saver = saver

    @staticmethod
    def key_for(namespace: str, value: str) -> str:
        return hashlib.sha256(f"{namespace}:{value}".encode()).hexdigest()

    def get(self, namespace: str, value: str) -> str | None:
        key = self.key_for(namespace, value)
        if key in self._memory:
            return self._memory[key]
        if self._loader:
            found = self._loader(key)
            if found is not None:
                self._memory[key] = found
            return found
        return None

    def put(self, namespace: str, value: str, body: str, ttl: timedelta) -> None:
        key = self.key_for(namespace, value)
        self._memory[key] = body
        if self._saver:
            self._saver(key, f"{namespace}:{value}"[:1000], body, ttl)

    def get_json(self, namespace: str, value: str) -> Any:
        body = self.get(namespace, value)
        return None if body is None else json.loads(body)

    def put_json(self, namespace: str, value: str, data: Any, ttl: timedelta) -> None:
        self.put(namespace, value, json.dumps(data, ensure_ascii=False), ttl)


@dataclass
class AdapterContext:
    client: PoliteClient
    store: StoreContext
    cache: DocumentCache
    debug: bool = False
    headless: bool = True


class MarketAdapter(abc.ABC):
    key: ClassVar[str]
    version: ClassVar[str]
    strategy: ClassVar[str]
    allowed_domains: ClassVar[tuple[str, ...]]
    requires_browser: ClassVar[bool] = False
    health_query: ClassVar[str] = "arroz"

    @abc.abstractmethod
    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        """Return candidate listings for the query at the given store."""

    async def discover_stores(self, ctx: AdapterContext) -> list[DiscoveredStore]:
        return []

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "strategy": self.strategy,
            "allowed_domains": list(self.allowed_domains),
            "requires_browser": self.requires_browser,
        }
