from __future__ import annotations

import socket
import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pricetracker.adapters.public_http import PublicHttpsTransport
from pricetracker.db.session import session_factory
from pricetracker.models import CatalogItem, Market, Observation
from pricetracker.models.enums import RunStatus
from pricetracker.services import markets
from pricetracker.worker.executor import RunExecutor
from tests.conftest import api, create_user, login
from tests.contract.test_structured_market import product_page

SITE = "https://mercado.example"
SAMPLE = SITE + "/arroz-branco-1kg"
SOURCE = {"website": SITE, "sample_url": SAMPLE}
CREATE = {
    **SOURCE,
    "name": "Mercado Independente",
    "brand_color": "#194C81",
    "confirm_public_price": True,
    "first_store": {"name": "Centro", "city": "Curitiba", "state": "PR"},
}


@pytest.fixture
def public_source(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "page": product_page(),
        "robots": "User-agent: *\nAllow: /\nSitemap: " + SITE + "/products.xml",
        "indexed": SAMPLE,
    }
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=state["robots"])
        if request.url.path in {"/products.xml", "/sitemap.xml"}:
            return httpx.Response(
                200,
                text=f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{state["indexed"]}</loc></url></urlset>',
            )
        if request.url.path == "/arroz-branco-1kg":
            return httpx.Response(200, text=state["page"])
        return httpx.Response(404)

    state["handler"] = handler
    monkeypatch.setattr(
        markets, "PublicHttpsTransport", lambda: PublicHttpsTransport(httpx.MockTransport(handler))
    )
    return state


def test_onboarding_admin_csrf_and_confirmation(
    client: TestClient, seeded: Any, public_source: Any
) -> None:
    assert api(client, "POST", "/admin/markets/probe", json=SOURCE).status_code == 401
    create_user(seeded, "user")
    login(client, "user")
    assert api(client, "POST", "/admin/markets/probe", json=SOURCE).status_code == 403
    assert api(client, "POST", "/admin/markets", json=CREATE).status_code == 403
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    assert client.post("/api/v1/admin/markets/probe", json=SOURCE).status_code == 403
    assert client.post("/api/v1/admin/markets", json=CREATE).status_code == 403
    assert (
        api(
            client, "POST", "/admin/markets", json={**CREATE, "confirm_public_price": False}
        ).status_code
        == 422
    )


def test_probe_create_and_add_unrelated_chain(
    client: TestClient, seeded: Any, public_source: Any
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    probe = api(client, "POST", "/admin/markets/probe", json=SOURCE)
    assert probe.status_code == 200 and probe.json()["supported"] is True, probe.text
    assert probe.json()["sample_price"] == "7.49" and probe.json()["indexed_pages"] == 1
    assert probe.json()["sitemap_url"] == SITE + "/products.xml"
    assert not seeded.scalar(select(Market).where(Market.slug == "mercado-independente"))
    created = api(client, "POST", "/admin/markets", json=CREATE)
    assert created.status_code == 201, created.text
    market = created.json()
    assert market["slug"] == "mercado-independente" and market["adapter_key"] == "public_jsonld"
    assert market["enabled"] and market["stores"][0]["state"] == "PR"
    assert "não confirma o preço da filial" in market["stores"][0]["price_scope_note"]
    assert any(m["id"] == market["id"] for m in api(client, "GET", "/markets").json())
    second = api(
        client,
        "POST",
        f"/admin/markets/{market['id']}/stores",
        json={"name": "Bairro", "city": "Londrina", "state": "PR"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["sitemap_url"] == SITE + "/products.xml"
    assert api(client, "POST", "/admin/markets", json=CREATE).status_code == 409


def test_source_revalidation_updates_all_stores_but_never_changes_domain(
    client: TestClient, seeded: Any, public_source: Any
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    market = api(client, "POST", "/admin/markets", json=CREATE).json()
    mid = market["id"]
    assert (
        api(
            client,
            "POST",
            f"/admin/markets/{mid}/stores",
            json={"name": "Bairro", "city": "Londrina", "state": "PR", "is_active": False},
        ).status_code
        == 201
    )
    source = {**SOURCE, "sitemap_url": SITE + "/sitemap.xml", "confirm_public_price": True}
    assert client.put(f"/api/v1/admin/markets/{mid}/source", json=source).status_code == 403
    response = api(client, "PUT", f"/admin/markets/{mid}/source", json=source)
    assert response.status_code == 200 and response.json()["sitemap_url"] == source["sitemap_url"]
    assert any(not s["is_active"] for s in response.json()["stores"])
    seeded.expire_all()
    stored = seeded.get(Market, uuid.UUID(mid))
    assert all(s.price_context["sitemap_url"] == source["sitemap_url"] for s in stored.stores)
    public_source["page"] = "<p>Preço após login</p>"
    assert api(client, "PUT", f"/admin/markets/{mid}/source", json=source).status_code == 422
    seeded.expire_all()
    assert all(s.price_context["sitemap_url"] == source["sitemap_url"] for s in stored.stores)
    changed_domain = {
        **source,
        "website": "https://other.example",
        "sample_url": "https://other.example/arroz",
        "sitemap_url": "https://other.example/sitemap.xml",
    }
    assert (
        api(client, "PUT", f"/admin/markets/{mid}/source", json=changed_domain).status_code == 422
    )
    fort = seeded.scalar(select(Market).where(Market.slug == "fort"))
    assert api(client, "PUT", f"/admin/markets/{fort.id}/source", json=source).status_code == 422
    create_user(seeded, "regular")
    login(client, "regular")
    assert api(client, "PUT", f"/admin/markets/{mid}/source", json=source).status_code == 403


def test_failed_or_changed_source_cannot_activate(
    client: TestClient, seeded: Any, public_source: Any
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    assert api(client, "POST", "/admin/markets/probe", json=SOURCE).json()["supported"]
    public_source["page"] = "<p>Preço apenas após login</p>"
    failed = api(client, "POST", "/admin/markets", json=CREATE)
    assert failed.status_code == 422 and failed.json()["code"] == "market_not_supported"
    assert not seeded.scalar(select(Market).where(Market.slug == "mercado-independente"))
    public_source["page"] = product_page()
    public_source["indexed"] = SITE + "/outra-pagina"
    missing = api(client, "POST", "/admin/markets/probe", json=SOURCE).json()
    assert not missing["supported"] and "não foi encontrado no índice" in missing["reason"]
    public_source["robots"] = "User-agent: *\nDisallow: /"
    denied = api(client, "POST", "/admin/markets/probe", json=SOURCE).json()
    assert not denied["supported"] and "robots.txt" in denied["reason"]
    assert (
        api(
            client,
            "POST",
            "/admin/markets/probe",
            json={**SOURCE, "sample_url": "https://elsewhere.example/arroz"},
        ).status_code
        == 422
    )


async def test_new_chain_collects_real_worker_and_comparison(
    client: TestClient, seeded: Any, settings: Any, public_source: Any
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    market = api(client, "POST", "/admin/markets", json=CREATE).json()
    store = market["stores"][0]
    item = seeded.scalar(select(CatalogItem).where(CatalogItem.slug == "arroz-branco-1kg"))
    list_id = api(client, "GET", "/lists").json()[0]["id"]
    assert (
        api(
            client, "POST", f"/lists/{list_id}/items", json={"catalog_item_id": str(item.id)}
        ).status_code
        == 201
    )
    assert (
        api(
            client, "PUT", "/me/stores", json={"selections": [{"store_id": store["id"]}]}
        ).status_code
        == 200
    )
    run = api(client, "POST", "/runs", json={}).json()
    executor = RunExecutor(
        factory=session_factory(),
        settings=settings,
        worker_id="test",
        transport=httpx.MockTransport(public_source["handler"]),
    )
    assert await executor.execute(uuid.UUID(run["id"])) == RunStatus.SUCCESS
    seeded.expire_all()
    observation = seeded.scalar(
        select(Observation).where(Observation.market_id == uuid.UUID(market["id"]))
    )
    assert observation.regular_price == Decimal("7.49")
    comparison = api(client, "GET", "/comparison").json()
    cell = comparison["items"][0]["cells"][store["id"]]
    assert cell["offer"]["title"] == "Arroz branco 1 kg" and cell["line"]["cost"] == "7.49"
