"""Product/catalog images: upload re-encoding, rejection of unsafe formats, isolation, cleanup."""

from __future__ import annotations

import io
import uuid
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import select

from pricetracker.models import CatalogItem, Image
from pricetracker.settings import Settings
from tests.conftest import api, create_user, login


def _png(color: tuple[int, int, int] = (200, 60, 40), size: tuple[int, int] = (64, 48)) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _custom_product(client: TestClient) -> dict[str, Any]:
    response = api(
        client,
        "POST",
        "/products",
        json={
            "name": "Granola artesanal da feira",
            "category": "Mercearia",
            "sold_by": "package",
            "package_quantity": "500",
            "package_unit": "g",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client: TestClient, product_id: str, data: bytes, name: str, mime: str) -> Any:
    return api(client, "POST", f"/products/{product_id}/image", files={"file": (name, data, mime)})


def test_upload_returns_image_and_serves_reencoded_webp(
    client: TestClient, seeded: Any, settings: Settings
) -> None:
    create_user(seeded, "ana")
    login(client, "ana")
    product = _custom_product(client)
    assert product["image"] is None

    uploaded = _upload(client, product["id"], _png(), "granola.png", "image/png")
    assert uploaded.status_code == 200, uploaded.text
    image = uploaded.json()["image"]
    assert image is not None and image["url"].startswith("/api/v1/images/")

    # The same image is visible on a fresh read and in the product list.
    again = api(client, "GET", f"/products/{product['id']}").json()
    assert again["image"]["id"] == image["id"]

    served = client.get(image["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in served.headers["content-security-policy"]
    assert served.content[:4] == b"RIFF" and served.content[8:12] == b"WEBP"


def test_upload_rejects_svg_and_corrupt_files(client: TestClient, seeded: Any) -> None:
    create_user(seeded, "ana")
    login(client, "ana")
    product = _custom_product(client)

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    rejected = _upload(client, product["id"], svg, "x.svg", "image/svg+xml")
    assert rejected.status_code == 422 and rejected.json()["code"] == "image_format"

    corrupt = _upload(
        client, product["id"], b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "x.png", "image/png"
    )
    assert corrupt.status_code == 422
    assert corrupt.json()["code"] in {"image_invalid", "image_format"}

    assert api(client, "GET", f"/products/{product['id']}").json()["image"] is None


def test_upload_rejects_files_over_the_limit(
    client: TestClient, seeded: Any, settings: Settings, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    create_user(seeded, "ana")
    login(client, "ana")
    product = _custom_product(client)
    too_big = _png() + b"\x00" * (1024 * 1024 + 10)
    response = _upload(client, product["id"], too_big, "big.png", "image/png")
    assert response.status_code == 422 and response.json()["code"] == "image_too_large"


def test_uploaded_image_is_private_to_its_owner(client: TestClient, seeded: Any) -> None:
    create_user(seeded, "ana")
    create_user(seeded, "bruno")
    login(client, "ana")
    product = _custom_product(client)
    image = _upload(client, product["id"], _png(), "g.png", "image/png").json()["image"]

    login(client, "bruno")
    assert client.get(image["url"]).status_code == 404
    assert api(client, "GET", f"/products/{product['id']}").status_code == 404

    # Seeded catalog images have no owner and stay visible to everyone.
    catalog = api(client, "GET", "/catalog").json()["items"]
    shared = next(item["image"] for item in catalog if item["image"])
    assert client.get(shared["url"]).status_code == 200


def test_replacing_an_image_removes_the_previous_file(
    client: TestClient, seeded: Any, settings: Settings
) -> None:
    create_user(seeded, "ana")
    login(client, "ana")
    product = _custom_product(client)
    first = _upload(client, product["id"], _png((10, 10, 10)), "a.png", "image/png").json()["image"]
    first_row = seeded.get(Image, uuid.UUID(first["id"]))
    first_path = settings.data_dir / "uploads" / first_row.storage_key
    assert first_path.is_file()

    second = _upload(client, product["id"], _png((240, 240, 240)), "b.png", "image/png").json()
    assert second["image"]["id"] != first["id"]
    first_id = first_row.id
    seeded.expire_all()
    assert seeded.get(Image, first_id) is None
    assert not first_path.exists()


def test_admin_can_replace_a_catalog_image(client: TestClient, seeded: Any) -> None:
    create_user(seeded, "admin", admin=True)
    login(client, "admin")
    item = seeded.scalar(select(CatalogItem).where(CatalogItem.slug == "arroz-branco-1kg"))
    before = api(client, "GET", "/catalog").json()["items"]
    old = next(entry["image"]["id"] for entry in before if entry["id"] == str(item.id))

    response = api(
        client,
        "POST",
        f"/admin/catalog/{item.id}/image",
        files={"file": ("arroz.png", _png((250, 250, 240)), "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["image"]["id"] != old

    create_user(seeded, "ana")
    login(client, "ana")
    assert api(client, "POST", f"/admin/catalog/{item.id}/image", files={
        "file": ("x.png", _png(), "image/png")
    }).status_code == 403  # fmt: skip
