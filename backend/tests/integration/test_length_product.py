from __future__ import annotations

import socket
import uuid
from decimal import Decimal as D
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pricetracker.adapters.public_http import PublicHttpsTransport
from pricetracker.db.session import session_factory
from pricetracker.models import Observation
from pricetracker.models.enums import RunStatus
from pricetracker.services import markets
from pricetracker.worker.executor import RunExecutor
from tests.conftest import api, create_user, login
from tests.contract.test_structured_market import product_page

SITE = "https://paper.example"
SAMPLE = SITE + "/papel-higienico-folha-dupla-30m-12-rolos"
CREATE = {
    "website": SITE,
    "sample_url": SAMPLE,
    "name": "Paper Market",
    "confirm_public_price": True,
    "first_store": {"name": "Centro", "city": "Curitiba", "state": "PR"},
}


@pytest.fixture
def paper_source(monkeypatch: pytest.MonkeyPatch) -> Any:
    page = product_page(price="24.00").replace(
        "Arroz branco 1 kg", "Papel higienico folha dupla 12 rolos 30m"
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                text=f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{SAMPLE}</loc></url></urlset>',
            )
        return (
            httpx.Response(200, text=page)
            if request.url.path == "/papel-higienico-folha-dupla-30m-12-rolos"
            else httpx.Response(404)
        )

    monkeypatch.setattr(
        markets, "PublicHttpsTransport", lambda: PublicHttpsTransport(httpx.MockTransport(handler))
    )
    return handler


@pytest.mark.parametrize("from_catalog", [False, True], ids=["custom", "standard-catalog"])
async def test_length_product_collects_and_compares(
    client: TestClient, seeded: Any, settings: Any, paper_source: Any, from_catalog: bool
) -> None:
    create_user(seeded, "paper", admin=True)
    login(client, "paper")
    created = api(client, "POST", "/admin/markets", json=CREATE)
    assert created.status_code == 201, created.text
    market = created.json()
    store = market["stores"][0]
    list_id = api(client, "GET", "/lists").json()[0]["id"]
    if from_catalog:
        entries = api(client, "GET", "/catalog").json()["items"]
        paper = next(item for item in entries if item["slug"] == "papel-higienico-folha-dupla")
        assert paper["category"] == "Higiene" and paper["image"] is not None
        assert paper["default_unit"] == "m" and D(paper["default_quantity"]) == D("120")
        added = api(
            client, "POST", f"/lists/{list_id}/items", json={"catalog_item_id": paper["id"]}
        )
        assert added.status_code == 201, added.text
        item = added.json()
        assert item["unit"] == "m" and D(item["quantity"]) == D("120")
        product = api(client, "GET", f"/products/{item['product_id']}").json()
        assert product["match_spec"]["comparison_unit"] == "m"
    else:
        response = api(
            client,
            "POST",
            "/products",
            json={
                "name": "Papel higienico folha dupla",
                "category": "Higiene",
                "sold_by": "package",
                "package_quantity": "120",
                "package_unit": "m",
                "match_spec": {
                    "search_terms": ["papel higienico"],
                    "required": [["papel higienico"], ["folha dupla"]],
                    "comparison_unit": "m",
                },
            },
        )
        assert response.status_code == 201, response.text
        product = response.json()
        assert product["default_unit"] == "m" and "m" in product["allowed_units"]
        added = api(
            client,
            "POST",
            f"/lists/{list_id}/items",
            json={"product_id": product["id"], "quantity": "120", "unit": "m"},
        )
        assert added.status_code == 201, added.text
    api(client, "PUT", "/me/stores", json={"selections": [{"store_id": store["id"]}]})
    run = api(client, "POST", "/runs", json={}).json()
    executor = RunExecutor(
        factory=session_factory(),
        settings=settings,
        worker_id="test",
        transport=httpx.MockTransport(paper_source),
    )
    assert await executor.execute(uuid.UUID(run["id"])) == RunStatus.SUCCESS
    seeded.expire_all()
    observation = seeded.scalar(
        select(Observation).where(Observation.product_id == uuid.UUID(product["id"]))
    )
    assert observation.package_quantity == D("360") and observation.package_unit == "m"
    assert observation.unit_price == D("0.0667") and observation.unit_price_unit == "m"
    comparison = api(client, "GET", "/comparison").json()
    cell = comparison["items"][0]["cells"][store["id"]]
    assert cell["line"]["cost"] == "24.00" and cell["line"]["unit_price_unit"] == "m"
    bad = api(
        client,
        "POST",
        "/products",
        json={
            "name": "Invalid length",
            "category": "Higiene",
            "sold_by": "package",
            "package_quantity": "1",
            "package_unit": "kg",
            "match_spec": {"search_terms": ["paper"], "comparison_unit": "m"},
        },
    )
    assert bad.status_code == 422
