"""Public-market sources stay bounded and never fetch private destinations."""

from __future__ import annotations

import json
import socket
from decimal import Decimal
from typing import Any

import httpx
import pytest

from pricetracker.adapters.base import DocumentCache
from pricetracker.adapters.errors import ParseError
from pricetracker.adapters.http import NotAllowedHost, PoliteClient, RobotsDisallowed, UpstreamError
from pricetracker.adapters.public_http import MAX_DOCUMENT_BYTES, PublicHttpsTransport
from pricetracker.adapters.structured import (
    MAX_PAGES,
    MAX_SITEMAPS,
    load_public_index,
    parse_product,
)


def product_page(**offer_changes: Any) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Arroz branco 1 kg",
        "brand": {"@type": "Brand", "name": "Boa Colheita"},
        "sku": "rice-1",
        "offers": {
            "@type": "Offer",
            "price": "7.49",
            "priceCurrency": "BRL",
            "availability": "https://schema.org/InStock",
            **offer_changes,
        },
    }
    return '<script type="application/ld+json">' + json.dumps({"@graph": [data]}) + "</script>"


def test_structured_offer_and_package() -> None:
    listing = parse_product(product_page(), "https://mercado.example/arroz-branco-1kg")
    assert listing.price == Decimal("7.49")
    assert listing.brand == "Boa Colheita" and listing.effective_package.measure.quantity == 1
    assert listing.method.value == "json_ld" and listing.availability.value == "in_stock"
    assert "não confirma o preço da filial" in listing.raw["price_scope"]


@pytest.mark.parametrize(
    "changes",
    [
        {"priceCurrency": "USD"},
        {"priceCurrency": None},
        {"price": "NaN"},
        {"price": "Infinity"},
        {"price": "0"},
        {"price": "-1"},
        {"@type": "AggregateOffer", "lowPrice": "7.49"},
        {"eligibleQuantity": {"minValue": 3}},
        {"eligibleCustomerType": "Members"},
        {"priceValidUntil": "2020-01-01"},
        {"priceValidUntil": "not-a-date"},
    ],
)
def test_ambiguous_conditional_foreign_or_invalid_prices_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ParseError):
        parse_product(product_page(**changes), "https://mercado.example/arroz")


def test_multiple_products_and_offers_rejected() -> None:
    with pytest.raises(ParseError):
        parse_product(product_page() * 2, "https://mercado.example/category")
    with pytest.raises(ParseError):
        parse_product(
            '<script type="application/ld+json">{"@type":"Product","name":"Arroz","offers":[{},{}]}</script>',
            "https://mercado.example/arroz",
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/private",
        "https://127.0.0.1/",
        "https://169.254.169.254/",
        "https://[::1]/",
        "https://machine.local/",
        "http://mercado.example/",
        "https://user:secret@mercado.example/",
        "https://mercado.example:8443/",
    ],
)
async def test_private_urls_never_reach_transport(url: str) -> None:
    calls: list[httpx.Request] = []
    transport = PublicHttpsTransport(
        httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200))
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NotAllowedHost):
            await client.get(url)
    assert calls == []


async def test_dns_answers_and_every_request_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    addresses = ["8.8.8.8"]
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addresses
        ],
    )
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "mercado.example"
        assert request.extensions["sni_hostname"] == "mercado.example"
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(
        transport=PublicHttpsTransport(httpx.MockTransport(handler))
    ) as client:
        response = await client.get("https://mercado.example/product")
        assert response.url.host == "mercado.example" and response.text == "ok"
        addresses.append("127.0.0.1")  # Mixed answers are unsafe, not just the selected address.
        with pytest.raises(NotAllowedHost):
            await client.get("https://mercado.example/product")
        addresses[:] = ["192.168.1.2"]  # Changed DNS cannot move the next request into the LAN.
        with pytest.raises(NotAllowedHost):
            await client.get("https://mercado.example/product")
    assert len(calls) == 1


async def test_document_size_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    async with httpx.AsyncClient(
        transport=PublicHttpsTransport(
            httpx.MockTransport(
                lambda r: httpx.Response(200, content=b"x" * (MAX_DOCUMENT_BYTES + 1))
            )
        )
    ) as client:
        with pytest.raises(UpstreamError):
            await client.get("https://mercado.example/huge")


async def test_sitemap_cycles_and_document_count_bounded(settings: Any) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        children = "".join(
            f"<sitemap><loc>https://mercado.example/map-{n}.xml</loc></sitemap>" for n in range(100)
        )
        return httpx.Response(200, text=f"<sitemapindex>{children}</sitemapindex>")

    async with PoliteClient(
        allowed_domains=["mercado.example"],
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        index = await load_public_index(
            client,
            DocumentCache(),
            "https://mercado.example",
            "https://mercado.example/sitemap.xml",
        )
    assert len(index) == 0 and len(paths) == MAX_SITEMAPS + 1  # robots + bounded maps


async def test_sitemap_page_count_and_cached_index(settings: Any) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        pages = "".join(
            f"<url><loc>https://mercado.example/arroz-{n}-1kg</loc></url>"
            for n in range(MAX_PAGES + 10)
        )
        return httpx.Response(200, text=f"<urlset>{pages}</urlset>")

    cache = DocumentCache()
    async with PoliteClient(
        allowed_domains=["mercado.example"],
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        first = await load_public_index(
            client, cache, "https://mercado.example", "https://mercado.example/sitemap.xml"
        )
        second = await load_public_index(
            client, cache, "https://mercado.example", "https://mercado.example/sitemap.xml"
        )
    assert len(first) == len(second) == MAX_PAGES and len(paths) == 2


async def test_robots_redirect_cannot_silently_allow_outside_host(settings: Any) -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://private.example/robots.txt"})

    async with PoliteClient(
        allowed_domains=["mercado.example"],
        settings=settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(RobotsDisallowed):
            await client.get("https://mercado.example/arroz-1kg")
    assert paths == ["https://mercado.example/robots.txt"]
