"""robots.txt (RFC 9309) matching, allowlisted redirects and typed HTTP failures."""

from __future__ import annotations

import httpx
import pytest

from pricetracker.adapters.http import (
    Blocked,
    CircuitOpen,
    NotAllowedHost,
    PoliteClient,
    RobotsDisallowed,
    UpstreamError,
)
from pricetracker.adapters.robots import parse_robots
from tests.fakes import BISTEK_ROBOTS, FIXTURES, FORT_ROBOTS

UA = "PriceTracker/1.0 (self-hosted household price comparison; low volume)"


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://www.bistek.com.br/arroz-branco-tio-joao-1kg-1002236/p", True),
        ("https://www.bistek.com.br/sitemap/product-0.xml", True),
        ("https://www.bistek.com.br/api/catalog_system/pub/products/search", False),
        ("https://www.bistek.com.br/arroz?_q=arroz&map=ft", False),
        ("https://www.bistek.com.br/busca/?q=arroz", False),
        ("https://www.bistek.com.br/mercearia/alimentos-basicos/arroz?page=2", True),
    ],
)
def test_bistek_robots(url: str, allowed: bool) -> None:
    assert parse_robots(BISTEK_ROBOTS).is_allowed(url, UA) is allowed


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        (
            "https://www.fortatacadista.com.br/produtos/7895191/arroz-polido-tio-joao-tipo-1-com-1kg",
            True,
        ),
        # RFC 9309 longest match: "Allow: /produtos/" (10 chars) beats "Disallow: /*?*" (4 chars).
        # The Fort adapter still never sends query strings (asserted in the adapter tests).
        ("https://www.fortatacadista.com.br/produtos/7895191/arroz?loja=1638", True),
        ("https://www.fortatacadista.com.br/?q=arroz", False),
        ("https://www.fortatacadista.com.br/busca/arroz", False),
        ("https://www.fortatacadista.com.br/lojas/kobrasol", False),
        ("https://www.fortatacadista.com.br/categorias/mercearia", True),
    ],
)
def test_fort_robots(url: str, allowed: bool) -> None:
    assert parse_robots(FORT_ROBOTS).is_allowed(url, UA) is allowed


def test_angeloni_robots_allows_api_but_not_legacy_search() -> None:
    policy = parse_robots((FIXTURES / "angeloni" / "robots_super.angeloni.com.br.txt").read_text())
    base = "https://super.angeloni.com.br"
    assert policy.is_allowed(
        base + "/api/io/_v/api/intelligent-search/product_search/trade-policy/1?query=arroz", UA
    )
    assert policy.is_allowed(
        base + "/api/checkout/pub/regions?country=BRA&postalCode=88010000&sc=1", UA
    )
    assert not policy.is_allowed(base + "/api/catalog_system/pub/products/search?ft=arroz", UA)
    assert not policy.is_allowed(base + "/arroz?map=ft", UA)
    assert not policy.is_allowed(base + "/busca?q=arroz", UA)
    assert not policy.is_allowed(base + "/checkout/cart", UA)


def test_rfc9309_longest_match_and_status_semantics() -> None:
    policy = parse_robots("User-agent: *\nDisallow: /a\nAllow: /a/b\nDisallow: /*.pdf$\n")
    assert not policy.is_allowed("https://x.test/a/c", UA)
    assert policy.is_allowed("https://x.test/a/b/c", UA)
    assert not policy.is_allowed("https://x.test/doc.pdf", UA)
    assert policy.is_allowed("https://x.test/doc.pdf?x=1", UA)
    assert parse_robots("", 404).is_allowed("https://x.test/anything", UA)
    assert not parse_robots("", 503).is_allowed("https://x.test/anything", UA)
    specific = parse_robots(
        "User-agent: pricetracker\nDisallow: /private\n\nUser-agent: *\nDisallow: /\n"
    )
    assert specific.is_allowed("https://x.test/public", UA)
    assert not specific.is_allowed("https://x.test/private", UA)


def _client(
    handler: httpx.MockTransport, domains: tuple[str, ...], settings: object
) -> PoliteClient:
    return PoliteClient(allowed_domains=domains, settings=settings, transport=handler)  # type: ignore[arg-type]


async def test_client_refuses_disallowed_and_off_domain(settings: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=BISTEK_ROBOTS)
        if request.url.path == "/redirect-out":
            return httpx.Response(302, headers={"location": "https://evil.example/steal"})
        return httpx.Response(200, text="ok")

    async with _client(httpx.MockTransport(handler), ("bistek.com.br",), settings) as client:
        assert (await client.get("https://www.bistek.com.br/ok/p")).status == 200
        with pytest.raises(RobotsDisallowed):
            await client.get("https://www.bistek.com.br/api/sessions")
        with pytest.raises(NotAllowedHost):
            await client.get("https://evil.example/x")
        with pytest.raises(NotAllowedHost):
            await client.get("http://www.bistek.com.br/ok/p")
        with pytest.raises(NotAllowedHost):
            await client.get("https://www.bistek.com.br/redirect-out")


async def test_client_types_blocks_and_breaks_circuit(settings: object) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        calls["n"] += 1
        if request.url.path == "/blocked":
            return httpx.Response(403, text="Access denied")
        if request.url.path == "/challenge":
            return httpx.Response(
                200,
                text="<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'></script></html>",
            )
        return httpx.Response(503, text="down")

    async with _client(httpx.MockTransport(handler), ("x.test",), settings) as client:
        with pytest.raises(Blocked):
            await client.get("https://x.test/blocked")
        with pytest.raises(Blocked):
            await client.get("https://x.test/challenge")
        with pytest.raises(UpstreamError):
            await client.get("https://x.test/down")
        for _ in range(3):
            with pytest.raises((UpstreamError, CircuitOpen)):
                await client.get("https://x.test/down")
        with pytest.raises(CircuitOpen):
            await client.get("https://x.test/down")
