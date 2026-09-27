"""Two users: lists, products, addresses, vehicles, runs and history never leak across tenants."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from pricetracker.db.base import utcnow
from pricetracker.models import CatalogItem, Market, Observation, Store, User
from tests.conftest import api, create_user, login


def _setup_user(client: TestClient, db: Any, username: str) -> dict[str, Any]:
    create_user(db, username)
    login(client, username)
    rice = db.scalar(select(CatalogItem).where(CatalogItem.slug == "arroz-branco-1kg"))
    lists = api(client, "GET", "/lists").json()
    list_id = lists[0]["id"]
    item = api(client, "POST", f"/lists/{list_id}/items", json={"catalog_item_id": str(rice.id), "quantity": "2", "unit": "pct"})
    assert item.status_code == 201, item.text
    product = api(client, "POST", "/products", json={"name": f"Pão de {username}", "category": "Padaria", "sold_by": "unit"}).json()
    address = api(client, "POST", "/me/addresses", json={"label": "Casa", "street": f"Rua {username}", "city": "Florianópolis", "state": "SC", "latitude": "-27.59", "longitude": "-48.55"}).json()
    vehicle = api(client, "POST", "/me/vehicles", json={"name": "Carro", "km_per_liter": "12", "fuel_price_per_liter": "6.29"}).json()
    return {"list_id": list_id, "item_id": item.json()["id"], "product_id": product["id"], "rice_product_id": item.json()["product_id"], "address_id": address["id"], "vehicle_id": vehicle["id"]}


def test_users_cannot_read_or_modify_each_other(client: TestClient, seeded: Any) -> None:
    db = seeded
    alice = _setup_user(client, db, "alice")
    bob = _setup_user(client, db, "bob")  # logged in as bob now
    store = db.scalar(select(Store).join(Market).where(Market.slug == "bistek"))
    db.add(
        Observation(
            user_id=db.scalar(select(User.id).where(User.username == "alice")),
            product_id=uuid.UUID(alice["rice_product_id"]), market_id=store.market_id, store_id=store.id,
            observed_at=utcnow() - timedelta(days=1), title="Arroz Tio João 1kg", method="api",
            regular_price=Decimal("8.29"), unit_price=Decimal("8.29"), unit_price_unit="kg",
            sold_by="package", package_quantity=Decimal("1"), package_unit="kg", availability="in_stock",
            idempotency_key="alice-obs-1",
        )  # fmt: skip
    )
    db.commit()
    forbidden_reads = [
        f"/lists/{alice['list_id']}",
        f"/products/{alice['product_id']}",
        f"/products/{alice['rice_product_id']}",
        f"/history/products/{alice['rice_product_id']}",
    ]
    for path in forbidden_reads:
        assert api(client, "GET", path).status_code == 404, path
    forbidden_writes = [
        ("PATCH", f"/lists/{alice['list_id']}", {"name": "hack"}),
        ("POST", f"/lists/{alice['list_id']}/items", {"product_id": bob["product_id"], "quantity": "1"}),
        ("POST", f"/lists/{bob['list_id']}/items", {"product_id": alice["product_id"], "quantity": "1"}),
        ("PATCH", f"/lists/{alice['list_id']}/items/{alice['item_id']}", {"quantity": "9"}),
        ("DELETE", f"/lists/{alice['list_id']}/items/{alice['item_id']}", None),
        ("PATCH", f"/products/{alice['product_id']}", {"name": "hack"}),
        ("DELETE", f"/products/{alice['product_id']}", None),
        ("PUT", f"/me/addresses/{alice['address_id']}", {"label": "hack", "city": "X"}),
        ("DELETE", f"/me/addresses/{alice['address_id']}", None),
        ("PUT", f"/me/vehicles/{alice['vehicle_id']}", {"name": "hack", "km_per_liter": "1", "fuel_price_per_liter": "1"}),
        ("DELETE", f"/me/vehicles/{alice['vehicle_id']}", None),
        ("POST", "/runs", {"list_id": alice["list_id"], "store_ids": [str(store.id)]}),
    ]
    for method, path, body in forbidden_writes:
        response = api(client, method, path, json=body) if body is not None else api(client, method, path)
        assert response.status_code == 404, (method, path, response.status_code, response.text)
    # Bob's own views never include Alice's data.
    assert [a["street"] for a in api(client, "GET", "/me/addresses").json()] == ["Rua bob"]
    assert all(p["name"] != "Pão de alice" for p in api(client, "GET", "/products").json())
    comparison = api(client, "GET", "/comparison", params={"store_ids": str(store.id)}).json()
    assert all(cell["offer"] is None for item in comparison["items"] for cell in item["cells"].values())
    # Alice still sees her untouched data.
    login(client, "alice")
    assert api(client, "GET", f"/lists/{alice['list_id']}").json()["items"][0]["quantity"] == "2.000"
    history = api(client, "GET", f"/history/products/{alice['rice_product_id']}").json()
    assert history["series"][0]["points"][0]["price"] == "8.29"
