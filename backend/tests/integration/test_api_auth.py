from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from pricetracker import settings as settings_module
from pricetracker.models import User, UserSession
from pricetracker.models.enums import Role
from tests.conftest import api, create_user, csrf_headers, login, make_settings


def test_first_access_creates_admin_and_disables_registration(client: TestClient, db: Any) -> None:
    status = api(client, "GET", "/setup/status").json()
    assert status == {"needs_setup": True, "requires_code": False}
    weak = api(
        client,
        "POST",
        "/setup/admin",
        json={"username": "casa", "display_name": "Casa", "password": "123"},
    )
    assert weak.status_code == 422 and weak.json()["code"] == "weak_password"
    created = api(
        client, "POST", "/setup/admin",
        json={"username": "Beatriz", "display_name": "Beatriz Conceição", "password": "uma-senha-bem-forte"},
    )  # fmt: skip
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["user"]["role"] == "admin" and body["user"]["username"] == "beatriz"
    assert len(body["recovery_codes"]) == 10
    assert "password_hash" not in created.text
    assert api(client, "GET", "/setup/status").json()["needs_setup"] is False
    again = api(
        client,
        "POST",
        "/setup/admin",
        json={"username": "x2x", "display_name": "x", "password": "uma-senha-bem-forte"},
    )
    assert again.status_code == 409
    me = api(client, "GET", "/auth/me").json()
    assert me["user"]["username"] == "beatriz" and me["onboarding_completed"] is False
    meta = api(client, "GET", "/meta").json()
    assert meta["registration_enabled"] is False
    register = api(
        client,
        "POST",
        "/auth/register",
        json={"username": "visita", "display_name": "V", "password": "outra-senha-forte"},
    )
    assert register.status_code == 403 and register.json()["code"] == "registration_disabled"


def test_setup_requires_one_time_code_when_configured(
    tmp_path: Any, client: TestClient, db: Any
) -> None:
    from pricetracker.services import accounts

    settings_module.configure_settings(make_settings(tmp_path, setup_require_code=True))
    body = {"username": "dono", "display_name": "Dono", "password": "uma-senha-bem-forte"}
    missing = api(client, "POST", "/setup/admin", json=body)
    assert missing.status_code == 403 and missing.json()["code"] == "setup_code_required"
    code = accounts.generate_setup_code(db)
    wrong = api(client, "POST", "/setup/admin", json={**body, "setup_code": "AAAA-BBBB-CCCC"})
    assert wrong.status_code == 403
    ok = api(client, "POST", "/setup/admin", json={**body, "setup_code": code.lower()})
    assert ok.status_code == 201


def test_login_logout_sessions_and_cookie_flags(client: TestClient, db: Any) -> None:
    create_user(db, "ana")
    client.get("/api/v1/auth/csrf")
    response = api(
        client, "POST", "/auth/login", json={"username": "ana", "password": "senha-forte-123"}
    )
    assert response.status_code == 200
    cookie_header = "; ".join(response.headers.get_list("set-cookie"))
    assert (
        "pt_session=" in cookie_header and "HttpOnly" in cookie_header and "Secure" in cookie_header
    )
    assert "SameSite=lax" in cookie_header or "samesite=lax" in cookie_header.lower()
    token = client.cookies["pt_session"]
    stored = db.scalar(select(UserSession))
    assert stored is not None and stored.token_hash != token and len(stored.token_hash) == 64
    sessions = api(client, "GET", "/auth/sessions").json()
    assert len(sessions) == 1 and sessions[0]["current"] is True
    assert api(client, "POST", "/auth/logout").status_code == 200
    client.cookies.set("pt_session", token)
    assert api(client, "GET", "/auth/me").status_code == 401


def test_csrf_and_origin_are_enforced(client: TestClient, db: Any) -> None:
    create_user(db, "bia")
    login(client, "bia")
    no_token = client.post("/api/v1/lists", json={"name": "Sem token"})
    assert no_token.status_code == 403 and no_token.json()["code"] == "csrf_failed"
    bad_origin = client.post(
        "/api/v1/lists",
        json={"name": "Origem"},
        headers={**csrf_headers(client), "Origin": "https://evil.example"},
    )
    assert bad_origin.status_code == 403 and bad_origin.json()["code"] == "bad_origin"
    ok = api(client, "POST", "/lists", json={"name": "Com token"})
    assert ok.status_code == 201


def test_login_rate_limit(client: TestClient, db: Any) -> None:
    create_user(db, "caio")
    client.get("/api/v1/auth/csrf")
    for _ in range(5):
        wrong = api(
            client, "POST", "/auth/login", json={"username": "caio", "password": "errada-errada"}
        )
        assert wrong.status_code == 401
    blocked = api(
        client, "POST", "/auth/login", json={"username": "caio", "password": "senha-forte-123"}
    )
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    unknown = api(
        client, "POST", "/auth/login", json={"username": "nao-existe", "password": "qualquer-coisa"}
    )
    assert (
        unknown.status_code == 401 and unknown.json()["message"] == "Usuário ou senha incorretos."
    )


def test_recovery_code_resets_password_once(client: TestClient, db: Any) -> None:
    from pricetracker.services import accounts

    account = accounts._create_user(
        db, username="duda", display_name="Duda", password="senha-forte-123", role=Role.USER
    )
    db.commit()
    code = account.recovery_codes[0]
    client.get("/api/v1/auth/csrf")
    body = {"username": "duda", "recovery_code": code, "new_password": "nova-senha-segura"}
    assert api(client, "POST", "/auth/recover", json=body).status_code == 200
    assert api(client, "POST", "/auth/recover", json=body).status_code == 401  # single use
    login(client, "duda", "nova-senha-segura")


def test_admin_reset_forces_password_change(client: TestClient, db: Any) -> None:
    create_user(db, "admin", admin=True)
    user = create_user(db, "edu")
    login(client, "admin")
    reset = api(
        client,
        "POST",
        f"/admin/users/{user.id}/reset-password",
        json={"temporary_password": "temporaria-123"},
    )
    assert reset.status_code == 200
    login(client, "edu", "temporaria-123")
    blocked = api(client, "GET", "/lists")
    assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"
    changed = api(
        client,
        "POST",
        "/auth/change-password",
        json={"current_password": "temporaria-123", "new_password": "definitiva-456"},
    )
    assert changed.status_code == 200
    assert api(client, "GET", "/lists").status_code == 200


def test_admin_endpoints_require_admin(client: TestClient, db: Any) -> None:
    create_user(db, "fabi")
    login(client, "fabi")
    assert api(client, "GET", "/admin/users").status_code == 403
    assert api(client, "GET", "/admin/health").status_code == 403
    assert (
        api(client, "PATCH", "/admin/settings", json={"registration_enabled": True}).status_code
        == 403
    )


def test_last_admin_cannot_be_demoted(client: TestClient, db: Any) -> None:
    admin = create_user(db, "root", admin=True)
    login(client, "root")
    response = api(client, "PATCH", f"/admin/users/{admin.id}", json={"role": "user"})
    assert response.status_code == 409
    assert db.scalar(select(User).where(User.username == "root")).role == "admin"
