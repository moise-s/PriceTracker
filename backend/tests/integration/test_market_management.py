from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pricetracker.models import CatalogItem, Market, Store
from pricetracker.seed import seed_all
from pricetracker.services import catalog, profile, runs
from pricetracker.services.errors import ValidationFailed
from tests.conftest import api, create_user, login


def market_id(client: TestClient, slug: str = "fort") -> str:
    return next(m["id"] for m in api(client, "GET", "/admin/markets").json() if m["slug"] == slug)


def branch(**changes: Any) -> dict[str, Any]:
    return {"name": "Centro", "city": "Curitiba", "state": "PR", "external_id": "987654", **changes}


def test_management_requires_admin_and_csrf(client: TestClient, seeded: Any) -> None:
    assert api(client, "GET", "/admin/markets").status_code == 401
    create_user(seeded, "regular")
    login(client, "regular")
    mid = str(seeded.scalar(select(Market.id)))
    assert api(client, "GET", "/admin/markets").status_code == 403
    assert api(client, "PATCH", f"/admin/markets/{mid}", json={"enabled": False}).status_code == 403
    assert api(client, "POST", f"/admin/markets/{mid}/stores", json=branch()).status_code == 403
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    assert client.patch(f"/api/v1/admin/markets/{mid}", json={"enabled": False}).status_code == 403
    assert (
        api(
            client, "PATCH", f"/admin/markets/{mid}", json={"allowed_domains": ["evil.example"]}
        ).status_code
        == 422
    )


def test_regional_branch_creation_edit_and_seed_preservation(
    client: TestClient, seeded: Any
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    mid = market_id(client)
    created = api(
        client,
        "POST",
        f"/admin/markets/{mid}/stores",
        json=branch(latitude="-25.428400", longitude="-49.273300"),
    )
    assert created.status_code == 201, created.text
    store = next(s for s in created.json()["stores"] if s["external_id"] == "987654")
    assert store["source"] == "admin" and store["state"] == "PR"
    assert "Preço online de cada loja" in store["price_scope_note"]
    found = api(client, "GET", "/markets").json()
    assert any(s["id"] == store["id"] for m in found for s in m["stores"])
    assert api(client, "POST", f"/admin/markets/{mid}/stores", json=branch()).status_code == 409
    changed = api(
        client,
        "PUT",
        f"/admin/markets/{mid}/stores/{store['id']}",
        json=branch(name="Centro atualizado", is_active=False),
    )
    assert changed.status_code == 200, changed.text
    other = market_id(client, "angeloni")
    assert (
        api(
            client,
            "PUT",
            f"/admin/markets/{other}/stores/{store['id']}",
            json=branch(postal_code="80010-000"),
        ).status_code
        == 404
    )
    patch = {
        "name": "Fort local",
        "notes": "Nota da instalação",
        "brand_color": "#123456",
        "enabled": False,
    }
    assert api(client, "PATCH", f"/admin/markets/{mid}", json=patch).status_code == 200
    seeded.expire_all()
    seed_all(seeded)
    seeded.expire_all()
    stored_market = seeded.get(Market, uuid.UUID(mid))
    assert stored_market.name == patch["name"] and stored_market.notes == patch["notes"]
    assert stored_market.enabled is False and stored_market.brand_color == patch["brand_color"]
    persisted = seeded.get(Store, uuid.UUID(store["id"]))
    assert persisted.name == "Centro atualizado" and persisted.is_active is False


@pytest.mark.parametrize(
    ("slug", "payload"),
    [
        ("angeloni", branch(external_id=None)),
        ("fort", branch(external_id="../wrong")),
        ("imperatriz", branch(external_id=None)),
        ("fort", branch(latitude="-25", longitude=None)),
        ("fort", branch(latitude="91", longitude="0")),
        ("fort", branch(state="XX")),
        ("angeloni", branch(postal_code="invalid")),
        ("fort", branch(price_context={"url": "http://localhost"})),
    ],
)
def test_invalid_context_is_rejected(
    client: TestClient, seeded: Any, slug: str, payload: dict[str, Any]
) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    response = api(client, "POST", f"/admin/markets/{market_id(client, slug)}/stores", json=payload)
    assert response.status_code == 422, response.text


def test_seed_branch_edits_are_kept(client: TestClient, seeded: Any) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    market = next(m for m in api(client, "GET", "/admin/markets").json() if m["slug"] == "bistek")
    store = market["stores"][0]
    payload = {
        key: store[key]
        for key in ("name", "city", "state", "external_id", "postal_code", "latitude", "longitude")
    }
    payload.update(name="Nome corrigido", is_active=False)
    response = api(
        client, "PUT", f"/admin/markets/{market['id']}/stores/{store['id']}", json=payload
    )
    assert response.status_code == 200, response.text
    seed_all(seeded)
    seeded.expire_all()
    saved = next(m for m in api(client, "GET", "/admin/markets").json() if m["id"] == market["id"])
    saved_store = next(s for s in saved["stores"] if s["id"] == store["id"])
    assert saved_store["name"] == "Nome corrigido" and saved_store["is_active"] is False
    assert "Florianópolis/SC" in saved_store["price_scope_note"]


def test_disabled_markets_do_not_break_default_selection_or_lose_history(
    client: TestClient, seeded: Any
) -> None:
    user = create_user(seeded, "admin", admin=True)
    login(client, "admin")
    mid = market_id(client)
    market = seeded.scalar(select(Market).where(Market.slug == "fort"))
    store = market.stores[0]
    profile.set_selections(seeded, user, [{"store_id": store.id}])
    assert api(client, "PATCH", f"/admin/markets/{mid}", json={"enabled": False}).status_code == 200
    seeded.expire_all()
    assert profile.selections(seeded, user.id) == {}
    assert len(profile.selections(seeded, user.id, include_unavailable=True)) == 1
    assert (
        api(
            client, "PUT", "/me/stores", json={"selections": [{"store_id": str(store.id)}]}
        ).status_code
        == 422
    )
    assert api(client, "GET", "/comparison", params={"store_ids": str(store.id)}).status_code == 422
    with pytest.raises(ValidationFailed, match="Escolha pelo menos"):
        runs._resolve_stores(seeded, user, None)
    with pytest.raises(ValidationFailed, match="desativadas"):
        runs._resolve_stores(seeded, user, [store.id])
    assert api(client, "PATCH", f"/admin/markets/{mid}", json={"enabled": True}).status_code == 200
    seeded.expire_all()
    assert store.id in profile.selections(seeded, user.id)


def test_price_region_cannot_relabel_existing_searches(client: TestClient, seeded: Any) -> None:
    user = create_user(seeded, "admin", admin=True)
    login(client, "admin")
    market = next(m for m in api(client, "GET", "/admin/markets").json() if m["slug"] == "fort")
    store = market["stores"][0]
    item = seeded.scalar(select(CatalogItem))
    product = catalog.product_from_catalog(seeded, user, item.id)
    shopping_list = catalog.default_list(seeded, user)
    catalog.upsert_list_item(
        seeded,
        user,
        shopping_list.id,
        product_id=product.id,
        quantity=Decimal("1"),
        unit=None,
        notes=None,
    )
    runs.create_run(seeded, user, store_ids=[uuid.UUID(store["id"])])
    payload = {
        key: store[key]
        for key in ("name", "city", "state", "external_id", "postal_code", "latitude", "longitude")
    }
    response = api(
        client,
        "PUT",
        f"/admin/markets/{market['id']}/stores/{store['id']}",
        json={**payload, "external_id": "987654"},
    )
    assert response.status_code == 409 and response.json()["code"] == "price_context_in_use"
    response = api(
        client,
        "PUT",
        f"/admin/markets/{market['id']}/stores/{store['id']}",
        json={**payload, "name": "Nome atualizado"},
    )
    assert response.status_code == 200
