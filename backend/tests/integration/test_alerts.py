"""Price alerts fire from fresh, usable prices only, once per target, and stay private."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from pricetracker.models.enums import RunStatus
from tests.conftest import api, create_user, login
from tests.integration.test_runs import execute, prepare, store_id


def _product_id(client: TestClient, name_prefix: str) -> str:
    items = api(client, "GET", "/lists").json()[0]["items"]
    return next(i["product_id"] for i in items if i["product_name"].startswith(name_prefix))


async def test_alert_fires_once_when_a_fresh_price_reaches_the_target(
    client: TestClient, seeded: Any, settings: Any
) -> None:
    prepare(client, seeded, ["arroz-branco-1kg"], [store_id(seeded, "fort", "kobrasol-160")])
    rice = _product_id(client, "Arroz")
    created = api(client, "PUT", f"/products/{rice}/alert", json={"target_price": "7.00"})
    assert created.status_code == 200, created.text
    assert created.json()["best_price"] is None and created.json()["unit_label"] == "embalagem"

    first = api(client, "POST", "/runs", json={}).json()["id"]
    assert await execute(settings, first) == RunStatus.SUCCESS
    inbox = api(client, "GET", "/notifications").json()
    assert inbox["unread"] == 1
    note = inbox["items"][0]
    assert note["kind"] == "price_alert"
    assert "R$ 6,79" in note["title"] and "Fort Atacadista Kobrasol" in note["body"]
    assert note["data"]["target"] == "7.00"
    alert = api(client, "GET", "/alerts").json()[0]
    assert alert["best_price"] == "6.79" and alert["last_triggered_at"] is not None

    # Same price in the next collection: no repeated announcement.
    second = api(client, "POST", "/runs", json={}).json()["id"]
    assert await execute(settings, second) == RunStatus.SUCCESS
    assert api(client, "GET", "/notifications").json()["unread"] == 1

    assert api(client, "POST", "/notifications/read", json={}).json()["marked"] == 1
    assert api(client, "GET", "/notifications").json()["unread"] == 0


async def test_prices_above_target_or_out_of_stock_never_fire(
    client: TestClient, seeded: Any, settings: Any
) -> None:
    angeloni = store_id(seeded, "angeloni", "beira-mar")
    prepare(
        client,
        seeded,
        ["arroz-branco-1kg", "cafe-tres-coracoes-gourmet-sul-de-minas-250g"],
        [angeloni],
    )
    rice = _product_id(client, "Arroz")
    coffee = _product_id(client, "Café")
    api(client, "PUT", f"/products/{rice}/alert", json={"target_price": "3.00"})  # fixture: 3.89
    api(client, "PUT", f"/products/{coffee}/alert", json={"target_price": "999"})  # out of stock
    run_id = api(client, "POST", "/runs", json={}).json()["id"]
    assert await execute(settings, run_id) == RunStatus.SUCCESS
    assert api(client, "GET", "/notifications").json() == {"unread": 0, "items": []}
    listed = {a["product_name"].split()[0]: a for a in api(client, "GET", "/alerts").json()}
    assert listed["Arroz"]["best_price"] == "3.89"
    assert listed["Café"]["best_price"] is None  # unavailable offers never count


def test_alerts_and_notifications_are_private(client: TestClient, seeded: Any) -> None:
    create_user(seeded, "ana")
    create_user(seeded, "bruno")
    login(client, "ana")
    product = api(
        client,
        "POST",
        "/products",
        json={
            "name": "Granola da Ana",
            "category": "Mercearia",
            "sold_by": "package",
            "package_quantity": "500",
            "package_unit": "g",
        },
    ).json()
    assert api(client, "PUT", f"/products/{product['id']}/alert", json={"target_price": "9.9"}).status_code == 200  # fmt: skip

    login(client, "bruno")
    stolen = api(client, "PUT", f"/products/{product['id']}/alert", json={"target_price": "1"})
    assert stolen.status_code == 404
    assert api(client, "DELETE", f"/products/{product['id']}/alert").status_code == 404
    assert api(client, "GET", "/alerts").json() == []
    assert api(client, "GET", "/notifications").json()["items"] == []

    login(client, "ana")
    assert api(client, "DELETE", f"/products/{product['id']}/alert").status_code == 200
    assert api(client, "GET", "/alerts").json() == []
