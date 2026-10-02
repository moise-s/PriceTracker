"""Public JSON-LD Product/Offer pages discovered through a bounded sitemap.

This adapter reads the anonymous online reference price. It does not configure
delivery regions, authenticate, execute JavaScript, or guess prices from ranges.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar
from urllib.parse import unquote, urlsplit
from xml.etree.ElementTree import ParseError as XmlParseError

from defusedxml.common import DefusedXmlException
from selectolax.parser import HTMLParser

from pricetracker.adapters.base import (
    AdapterContext,
    DocumentCache,
    MarketAdapter,
    SearchOutcome,
    SearchQuery,
)
from pricetracker.adapters.errors import ParseError, StoreContextError
from pricetracker.adapters.http import FetchError, PoliteClient
from pricetracker.adapters.public_http import public_url
from pricetracker.adapters.sitemap import SitemapEntry, SitemapIndex, entry_from_url, parse_urlset
from pricetracker.domain.listing import Listing, SaleUnit
from pricetracker.domain.units import parse_package
from pricetracker.models.enums import Availability, ExtractionMethod

PRICE_SCOPE = (
    "Preço online público de referência; não confirma o preço da filial nem a região de entrega."
)
MAX_SITEMAPS = 6
MAX_PAGES = 5000


def _has_type(node: dict[str, Any], kind: str) -> bool:
    value = node.get("@type", [])
    types = value if isinstance(value, list) else [value]
    return any(str(t).rstrip("/").rsplit("/", 1)[-1] == kind for t in types)


def parse_product(html: str, url: str) -> Listing:
    products: list[dict[str, Any]] = []
    for node in HTMLParser(html).css('script[type="application/ld+json"]'):
        try:
            document = json.loads(node.text())
        except (ValueError, RecursionError):
            continue
        roots = document if isinstance(document, list) else [document]
        for root in roots:
            if not isinstance(root, dict):
                continue
            graph = root.get("@graph", [])
            for item in [root, *(graph if isinstance(graph, list) else [])]:
                if isinstance(item, dict) and _has_type(item, "Product"):
                    products.append(item)
    if len(products) != 1:
        raise ParseError("A página precisa publicar um único produto em JSON-LD (Product).")
    product = products[0]
    title = product.get("name")
    if not isinstance(title, str) or not title.strip():
        raise ParseError("Produto sem nome nos dados públicos.")
    offers = product.get("offers")
    offers = offers if isinstance(offers, list) else [offers]
    if len(offers) != 1 or not isinstance(offers[0], dict) or not _has_type(offers[0], "Offer"):
        raise ParseError(
            "A página precisa publicar uma oferta única; faixas e múltiplos preços não são suportados."
        )
    offer = offers[0]
    if str(offer.get("priceCurrency", "")).upper() != "BRL":
        raise ParseError("A oferta precisa informar preço em reais (BRL).")
    if any(
        offer.get(key)
        for key in ("eligibleQuantity", "eligibleCustomerType", "eligibleTransactionVolume")
    ):
        raise ParseError(
            "Ofertas condicionadas a quantidade ou categoria de cliente precisam de integração própria."
        )
    try:
        price = Decimal(str(offer["price"]))
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise ParseError("A oferta não informa um preço numérico público.") from exc
    if not price.is_finite() or price <= 0 or price > Decimal("1000000"):
        raise ParseError("Preço público inválido.")
    if offer.get("priceValidUntil"):
        try:
            expires = date.fromisoformat(str(offer["priceValidUntil"])[:10])
        except ValueError as exc:
            raise ParseError("Validade de preço inválida.") from exc
        if expires < datetime.now(UTC).date():
            raise ParseError("A oferta pública está vencida.")
    availability = str(offer.get("availability", "")).rstrip("/").rsplit("/", 1)[-1]
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    return Listing(
        title=title.strip()[:500],
        url=url,
        method=ExtractionMethod.JSON_LD,
        brand=brand[:100] if isinstance(brand, str) else None,
        sku=str(product.get("sku") or "")[:120] or None,
        gtin=str(product.get("gtin13") or product.get("gtin") or "")[:14] or None,
        price=price,
        sale_unit=SaleUnit.KG if parse_package(title).per_kg else SaleUnit.PACKAGE,
        availability={
            "InStock": Availability.IN_STOCK,
            "OutOfStock": Availability.OUT_OF_STOCK,
        }.get(availability, Availability.UNKNOWN),
        confidence=Decimal("0.85"),
        raw={"source": "public_json_ld", "price_scope": PRICE_SCOPE},
    )


def same_site(url: str, website: str) -> bool:
    try:
        return urlsplit(public_url(url)).hostname == urlsplit(website).hostname
    except FetchError:
        return False


async def load_public_index(
    client: PoliteClient, cache: DocumentCache, website: str, sitemap_url: str
) -> SitemapIndex:
    key = f"{website}:{sitemap_url}"
    cached = cache.get_json("public-sitemap", key)
    if cached is not None:
        return SitemapIndex([SitemapEntry(**row) for row in cached])
    queue = [sitemap_url]
    seen: set[str] = set()
    entries: dict[str, SitemapEntry] = {}
    while queue and len(seen) < MAX_SITEMAPS and len(entries) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen or not same_site(url, website):
            continue
        seen.add(url)
        result = await client.get(url, accept="application/xml,text/xml")
        if result.status != 200:
            continue
        try:
            pages, children = parse_urlset(result.text)
        except (DefusedXmlException, XmlParseError) as exc:
            raise ParseError("O índice do site não é um sitemap XML válido.") from exc
        queue.extend(children[:MAX_SITEMAPS])
        for page in pages[:MAX_PAGES]:
            if same_site(page, website):
                page = public_url(page)
                slug = unquote(urlsplit(page).path).strip("/").replace("/", "-")
                entries[page] = entry_from_url(page, slug)
                if len(entries) >= MAX_PAGES:
                    break
    cache.put_json(
        "public-sitemap",
        key,
        [{"url": e.url, "slug": e.slug, "text": e.text} for e in entries.values()],
        timedelta(hours=24),
    )
    return SitemapIndex(list(entries.values()))


class StructuredAdapter(MarketAdapter):
    key = "public_jsonld"
    version = "2026.10.02"
    strategy = "public_sitemap+json_ld"
    # Bound per market, never inferred from product data.
    allowed_domains: ClassVar[tuple[str, ...]] = ()

    async def search(self, ctx: AdapterContext, query: SearchQuery) -> SearchOutcome:
        website = ctx.store.price_context.get("website")
        sitemap = ctx.store.price_context.get("sitemap_url")
        if not website or not sitemap:
            raise StoreContextError("Mercado sem fonte pública validada.")
        index = await load_public_index(ctx.client, ctx.cache, website, sitemap)
        if not len(index):
            raise ParseError(
                "O índice público não expõe páginas utilizáveis; revise o sitemap do mercado."
            )
        urls = list(
            dict.fromkeys(
                [
                    *(url for url in query.preferred_urls if same_site(url, website)),
                    *(e.url for e in index.candidates(query.spec, min(query.max_candidates, 6))),
                ]
            )
        )[: query.max_candidates]
        outcome = SearchOutcome(
            method=ExtractionMethod.JSON_LD,
            query_used=f"sitemap público: {len(urls)} candidatos de {len(index)} páginas",
            notes=[PRICE_SCOPE],
        )
        parse_failures = 0
        for url in urls:
            result = await ctx.client.get(url)
            if result.status != 200:
                continue
            if not same_site(result.url, website):
                raise StoreContextError(
                    "A página redireciona para outro domínio; revise a fonte pública do mercado."
                )
            try:
                outcome.listings.append(parse_product(result.text, result.url))
            except ParseError:
                parse_failures += 1
        if not outcome.listings and parse_failures:
            raise ParseError(
                "As páginas candidatas não publicam uma oferta única em BRL compatível com esta integração."
            )
        return outcome
