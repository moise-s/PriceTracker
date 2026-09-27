"""httpx transports that replay sanitised fixtures captured from the real sites (2026-09-27)."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

FIXTURES = Path(__file__).parent / "fixtures"

BISTEK_ROBOTS = """User-agent: *
Disallow: /account/
Disallow: /login/
Disallow: /checkout/
Disallow: /busca/
Disallow: /buscapagina/
Disallow: /quick-view/
Disallow: /espiar/
Disallow: /*?_q=
Disallow: /*&_q=
Disallow: /*?map=
Disallow: /*&map=
Disallow: /*?initialMap=
Disallow: /*&initialMap=
Disallow: /*?initialQuery=
Disallow: /*&initialQuery=
Disallow: /*?*filter=
Disallow: /*&filter=
Disallow: /api/
Sitemap: https://www.bistek.com.br/sitemap.xml
"""

FORT_ROBOTS = """User-agent: *
Disallow: /admin
Disallow: /minha-conta
Disallow: /account/*
Disallow: /painel-do-cliente
Disallow: /carrinho
Disallow: /checkout
Disallow: /login
Disallow: /pedido
Disallow: /busca
Disallow: /search
Disallow: /embed/
Disallow: /lojas
Disallow: /*?*
Allow: /categorias
Allow: /receitas
Allow: /produtos/
Allow: /listas/
Allow: /*.css$
Allow: /*.js$

Sitemap: https://fortatacadista.com.br/sitemap.xml
"""

EMPTY_URLSET = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _json(path: Path, key: str | None = None) -> object:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data.pop("_fixture_meta", None)
        if key is not None:
            return data[key]
    return data


class Recorder:
    """Wraps a handler and records every request (for robots/politeness assertions)."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]):
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def paths(self) -> list[str]:
        return [f"{r.url.host}{r.url.raw_path.decode()}" for r in self.requests]


# --- Angeloni -------------------------------------------------------------------------------

ANGELONI_SEARCH = [
    ("xptoinexistente", "search_notfound.json"),
    ("5331481", "search_promo_product_5331481.json"),
    ("cafe tres coracoes", "search_cafe_tres_coracoes_zero.json"),
    ("cafe 3 coracoes", "search_cafe_3_coracoes.json"),
    ("arroz", "search_arroz.json"),
    ("feijao", "search_feijao.json"),
    ("lentilha", "search_lentilha.json"),
    ("ovos", "search_ovos.json"),
    ("alcatra", "search_alcatra.json"),
    ("maminha", "search_maminha.json"),
    ("filtro", "search_filtro_cafe.json"),
    ("maca fuji", "search_maca_fuji.json"),
    ("mamao", "search_mamao.json"),
]


def angeloni_handler(request: httpx.Request) -> httpx.Response:
    base = FIXTURES / "angeloni"
    url = request.url
    path = url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=(base / "robots_super.angeloni.com.br.txt").read_text())
    if path == "/api/checkout/pub/regions":
        cep = parse_qs(url.query.decode())["postalCode"][0]
        # Seeded stores use their own postal codes; map them to the captured regions.
        cep = {"88025202": "88010000", "88085001": "88101000"}.get(cep, cep)
        fixture = base / f"regions_{cep}.json"
        return httpx.Response(200, json=_json(fixture, "response") if fixture.exists() else [])
    if path.startswith("/api/io/_v/api/intelligent-search/product_search/"):
        query = _norm(parse_qs(url.query.decode())["query"][0])
        for needle, name in ANGELONI_SEARCH:
            if query.startswith(needle) or needle in query:
                return httpx.Response(200, json=_json(base / name))
        return httpx.Response(200, json={"products": [], "recordsFiltered": 0})
    if path == "/api/dataentities/PR/search":
        return httpx.Response(200, json=_json(base / "promotions_pr_superangeloni14.json", "batch_lookup_rows"))
    return httpx.Response(404, text="not found")


# --- Bistek ------------------------------------------------------------------------------------


def bistek_handler(request: httpx.Request) -> httpx.Response:
    base = FIXTURES / "bistek"
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=BISTEK_ROBOTS)
    if path == "/sitemap.xml":
        return httpx.Response(200, text=(base / "sitemap_index.xml").read_text())
    if path == "/sitemap/product-0.xml":
        return httpx.Response(200, text=(base / "sitemap_products_trimmed.xml").read_text())
    if path.startswith("/sitemap/"):
        return httpx.Response(200, text=EMPTY_URLSET) if "product-" not in path else httpx.Response(404)
    match = re.match(r"^/([a-z0-9-]+)/p$", path)
    if match:
        page = base / f"product_{match.group(1)}.html"
        if page.exists():
            return httpx.Response(200, text=page.read_text(encoding="utf-8"), headers={"etag": f'"{match.group(1)}"'})
        return httpx.Response(404, text=(base / "product_not_found_404.html").read_text(encoding="utf-8"))
    return httpx.Response(404)


# --- Fort ----------------------------------------------------------------------------------------


def fort_store_from_cookie(request: httpx.Request) -> str | None:
    cookie = request.headers.get("cookie", "")
    match = re.search(r"st_334=([^;]+)", cookie)
    if not match:
        return None
    return str(json.loads(unquote(match.group(1)))["id"])


def fort_handler(request: httpx.Request) -> httpx.Response:
    base = FIXTURES / "fort"
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=FORT_ROBOTS)
    if path == "/sitemap.xml":
        return httpx.Response(200, text=(base / "sitemap_trimmed.xml").read_text())
    match = re.match(r"^/produtos/(\d+)/[a-z0-9-]+$", path)
    if match:
        product_id = match.group(1)
        store = fort_store_from_cookie(request)
        for name in (f"{product_id}_{store}.html", f"{product_id}_nostore.html"):
            page = base / "products" / name
            if page.exists():
                return httpx.Response(200, text=page.read_text(encoding="utf-8"))
        return httpx.Response(404, text="<html>Página não encontrada</html>")
    return httpx.Response(404)


# --- Imperatriz ------------------------------------------------------------------------------------


def imperatriz_handler_factory(offers: list[dict[str, object]] | None = None) -> Callable[[httpx.Request], httpx.Response]:
    base = FIXTURES / "imperatriz"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(404)
        if request.url.host == "api.zoombox.com.br" and path == "/admin/v1/varejista":
            assert request.method == "POST"
            return httpx.Response(200, json=_json(base / "clube_bootstrap_response.json", "response"))
        if path == "/v1/ofertas":
            if request.headers.get("x-api-key") != "<public-token>":
                return httpx.Response(403, json={"message": "Forbidden"})
            data = _json(base / "clube_ofertas_loja16_sample.json", "response")
            assert isinstance(data, dict)
            if offers is not None:
                data = {**data, "ofertas": offers}
            return httpx.Response(200, json=data)
        return httpx.Response(404)

    return handler


def combined_handler(overrides: dict[str, Callable[[httpx.Request], httpx.Response]] | None = None) -> Callable[[httpx.Request], httpx.Response]:
    """One transport for every market, routed by host (used by executor tests)."""
    routes: dict[str, Callable[[httpx.Request], httpx.Response]] = {
        "super.angeloni.com.br": angeloni_handler,
        "www.bistek.com.br": bistek_handler,
        "www.fortatacadista.com.br": fort_handler,
        "fortatacadista.com.br": fort_handler,
        "api.zoombox.com.br": imperatriz_handler_factory(),
        "9zli2drdqe.execute-api.us-east-1.amazonaws.com": imperatriz_handler_factory(),
    }
    routes.update(overrides or {})

    def handler(request: httpx.Request) -> httpx.Response:
        host = urlsplit(str(request.url)).hostname or ""
        route = routes.get(host)
        if route is None:
            return httpx.Response(599, text=f"unexpected host {host}")
        return route(request)

    return handler
