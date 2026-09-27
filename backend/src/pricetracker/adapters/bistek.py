"""Bistek (www.bistek.com.br, VTEX IO).

robots.txt disallows ``/api/``, ``/busca/`` and the search parameters (``_q``,
``map``, ...). The compliant path is: discover products from the product sitemaps
(``/sitemap/product-{n}.xml``, allowed; not listed in the sitemap index, so they
are probed by the VTEX naming convention), then read each candidate product page
(``/<slug>/p``, allowed) and parse the server-rendered ``__STATE__`` (Apollo
cache), falling back to JSON-LD.

Store/region context cannot be set without disallowed endpoints, so prices are
the storefront default, which the site states is referenced to its
Florianópolis/SC store. Club prices and cart promotions are not available.
Product pages are heavy (~2 MB), so candidates per item are capped and pages are
revalidated with ``If-None-Match`` (a 304 reuses the parsed offer).
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

from selectolax.parser import HTMLParser

from pricetracker.adapters.base import (
    AdapterContext,
    DiscoveredStore,
    MarketAdapter,
    SearchOutcome,
    SearchQuery,
)
from pricetracker.adapters.errors import ParseError
from pricetracker.adapters.http import FetchError
from pricetracker.adapters.sitemap import load_index
from pricetracker.domain.listing import Listing, SaleUnit, listing_from_dict, listing_to_dict
from pricetracker.domain.money import to_money
from pricetracker.domain.units import Measure, parse_package
from pricetracker.domain.validation import valid_gtin
from pricetracker.models.enums import Availability, ExtractionMethod, Unit

BASE = "https://www.bistek.com.br"
PRODUCT_URL = re.compile(r"^https://www\.bistek\.com\.br/[^?#]+/p$")
SLUG = re.compile(r"/(?P<slug>[a-z0-9][a-z0-9-]*)/p$")
PRICE_SCOPE = "preço online de referência (loja de Florianópolis/SC)"
_STATE_RE = re.compile(
    r'<template data-type="json" data-varname="__STATE__">\s*<script>(.*?)</script>\s*</template>',
    re.S,
)


def _state(html: str) -> dict[str, Any]:
    match = _STATE_RE.search(html)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError("__STATE__ is not valid JSON") from exc
    return data if isinstance(data, dict) else {}


def _deref(state: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and value.get("type") == "id" and "id" in value:
        return state.get(value["id"], {})
    return value


def _properties(state: dict[str, Any], product: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for ref in product.get("properties") or []:
        prop = _deref(state, ref)
        values = prop.get("values") or {}
        if isinstance(values, dict):
            values = values.get("json") or []
        if prop.get("name") and values:
            result[prop["name"]] = str(values[0])
    return result


def parse_product_page(html: str, url: str) -> Listing | None:
    """Parse a Bistek product page. Returns None for pages without a product."""
    state = _state(html)
    slug_match = SLUG.search(url)
    slug = slug_match.group("slug") if slug_match else None
    product_key = f"Product:{slug}" if slug else None
    product = state.get(product_key or "", {}) if state else {}
    if not product:
        return _parse_json_ld(html, url)
    item = state.get(f"{product_key}.items.0", {})
    offer = state.get(f"${product_key}.items.0.sellers.0.commertialOffer", {})
    props = _properties(state, product)
    title = (product.get("productName") or item.get("name") or "").strip()
    if not title:
        raise ParseError("product without a name in __STATE__")
    price = to_money(offer.get("Price"))
    list_price = to_money(offer.get("ListPrice"))
    available = bool(price and price > 0 and (offer.get("AvailableQuantity") or 0) > 0)
    if price is not None and price <= 0:
        price = None
    ean = str(item.get("ean") or "")
    weighed_code = ean.startswith(("2", "30000"))
    weight_value = _decimal(props.get("Peso Produto"))
    measure_unit = (props.get("Unidade de Medida") or "").upper()
    sale_unit = SaleUnit.PACKAGE
    package_measure: Measure | None = None
    package_count: int | None = None
    piece_weight: Decimal | None = None
    title_pkg = parse_package(title)
    if measure_unit == "KG" and weight_value and (weighed_code or title_pkg.approximate):
        sale_unit, piece_weight = SaleUnit.PIECE, weight_value  # approximate-weight pack
    elif measure_unit in ("KG", "LT") and weight_value:
        package_measure = Measure(weight_value, Unit.KG if measure_unit == "KG" else Unit.L)
    elif measure_unit == "UN" and weight_value:
        package_count = (
            int(weight_value) if weight_value == weight_value.to_integral_value() else None
        )
    image = None
    images = item.get("images") or []
    if images:
        image_obj = _deref(state, images[0])
        image = image_obj.get("imageUrl")
    return Listing(
        title=title,
        method=ExtractionMethod.EMBEDDED_STATE,
        url=url,
        brand=product.get("brand"),
        external_id=str(product.get("productId") or item.get("itemId") or "") or None,
        sku=str(item.get("itemId")) if item.get("itemId") else None,
        gtin=ean if valid_gtin(ean) and not weighed_code else None,
        image_url=image,
        price=price,
        regular_price=list_price if list_price and price and list_price > price else None,
        sale_unit=sale_unit,
        package_measure=package_measure,
        package_count=package_count,
        piece_weight_kg=piece_weight,
        availability=Availability.IN_STOCK if available else Availability.OUT_OF_STOCK,
        raw={
            "source": "__STATE__",
            "product_id": product.get("productId"),
            "peso_produto": props.get("Peso Produto"),
            "unidade_medida": props.get("Unidade de Medida"),
            "internal_code": ean if weighed_code else None,
            "price_scope": PRICE_SCOPE,
            "list_price": str(list_price) if list_price else None,
        },
    )


def _parse_json_ld(html: str, url: str) -> Listing | None:
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        offers = data.get("offers") or {}
        price = to_money(offers.get("lowPrice") or (offers.get("offers") or [{}])[0].get("price"))
        availability = str((offers.get("offers") or [{}])[0].get("availability") or "")
        return Listing(
            title=str(data.get("name") or "").strip(),
            method=ExtractionMethod.JSON_LD,
            url=url,
            brand=(data.get("brand") or {}).get("name"),
            external_id=str(data.get("mpn") or "") or None,
            image_url=(data.get("image") or None) if isinstance(data.get("image"), str) else None,
            price=price if price and price > 0 else None,
            availability=Availability.IN_STOCK
            if availability.endswith("InStock")
            else Availability.UNKNOWN,
            confidence=Decimal("0.85"),
            raw={"source": "json_ld", "price_scope": PRICE_SCOPE},
        )
    return None


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        number = Decimal(value.replace(",", "."))
    except ArithmeticError:
        return None
    return number if number > 0 else None


class BistekAdapter(MarketAdapter):
    key = "bistek"
    version = "2026.09.27"
    strategy = "sitemap+product_page_state"
    allowed_domains = ("bistek.com.br",)
    candidates_per_item = 6

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        index = await load_index(
            ctx.client,
            ctx.cache,
            cache_key="bistek",
            sitemap_urls=[BASE + "/sitemap.xml"],
            probe_pattern=BASE + "/sitemap/product-{n}.xml",
            url_filter=PRODUCT_URL,
            slug_of=SLUG,
            ttl=timedelta(days=7),
        )
        outcome = SearchOutcome(method=ExtractionMethod.EMBEDDED_STATE)
        urls: list[str] = list(query.preferred_urls)
        for entry in index.candidates(query.spec, self.candidates_per_item):
            if entry.url not in urls:
                urls.append(entry.url)
        outcome.query_used = f"sitemap: {len(urls)} candidato(s) de {len(index)} produtos"
        for url in urls[: self.candidates_per_item + len(query.preferred_urls)]:
            listing = await self._fetch(ctx, url)
            if listing is not None:
                outcome.listings.append(listing)
        outcome.notes.append(PRICE_SCOPE)
        return outcome

    async def _fetch(self, ctx: AdapterContext, url: str) -> Listing | None:
        cached = ctx.cache.get_json("bistek-offer", url)
        headers = {"If-None-Match": cached["etag"]} if cached and cached.get("etag") else None
        try:
            result = await ctx.client.get(url, headers=headers)
        except FetchError:
            raise
        if result.status == 304 and cached:
            return listing_from_dict(cached["listing"])
        if result.status == 404:
            return None
        if result.status != 200:
            return None
        listing = parse_product_page(result.text, url)
        if listing is not None and result.headers.get("etag"):
            ctx.cache.put_json(
                "bistek-offer",
                url,
                {"etag": result.headers["etag"], "listing": listing_to_dict(listing)},
                timedelta(days=2),
            )
        return listing

    async def discover_stores(self, ctx: AdapterContext) -> list[DiscoveredStore]:
        return []
