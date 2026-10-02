"""Request dependencies: database session, authentication, authorization and CSRF."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from pricetracker import security
from pricetracker.db.session import get_db
from pricetracker.models import User, UserSession
from pricetracker.services import accounts
from pricetracker.services.errors import Forbidden, Unauthorized
from pricetracker.settings import get_settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def db_session() -> Iterator[Session]:
    yield from get_db()


DbSession = Annotated[Session, Depends(db_session)]


def client_address(request: Request) -> str:
    """Client IP; X-Forwarded-For is only trusted from a private/loopback proxy (the web container)."""
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    try:
        trusted_peer = (
            ipaddress.ip_address(peer).is_private or ipaddress.ip_address(peer).is_loopback
        )
    except ValueError:
        trusted_peer = False
    if forwarded and trusted_peer:
        return forwarded.split(",")[0].strip()[:64]
    return peer


def client_label(request: Request) -> str:
    agent = request.headers.get("user-agent", "")
    browser = next((b for b in ("Edg", "Firefox", "Chrome", "Safari") if b in agent), "Navegador")
    browser = {"Edg": "Edge"}.get(browser, browser)
    system = next(
        (s for s in ("iPhone", "iPad", "Android", "Mac OS", "Windows", "Linux") if s in agent), ""
    )
    system = {"Mac OS": "macOS"}.get(system, system)
    return f"{browser} · {system}".strip(" ·")


def set_session_cookies(response: Response, token: str) -> str:
    settings = get_settings()
    max_age = settings.session_absolute_days * 86400
    response.set_cookie(
        security.SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return issue_csrf_cookie(response)


def issue_csrf_cookie(response: Response) -> str:
    settings = get_settings()
    csrf = security.new_token(24)
    response.set_cookie(
        security.CSRF_COOKIE,
        csrf,
        max_age=settings.session_absolute_days * 86400,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return csrf


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (security.SESSION_COOKIE, security.CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


def verify_csrf(request: Request) -> None:
    """Double-submit token + Origin check for every state-changing request."""
    if request.method in SAFE_METHODS:
        return
    settings = get_settings()
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    source = origin or (
        f"{urlsplit(referer).scheme}://{urlsplit(referer).netloc}" if referer else None
    )
    if source and source.rstrip("/") not in settings.allowed_origins:
        raise Forbidden("Origem da requisição não permitida.", code="bad_origin")
    cookie = request.cookies.get(security.CSRF_COOKIE)
    header = request.headers.get(security.CSRF_HEADER)
    if not cookie or not header or not security.constant_time_equals(cookie, header):
        raise Forbidden("Token CSRF ausente ou inválido. Recarregue a página.", code="csrf_failed")


CsrfProtected = Depends(verify_csrf)


def optional_user(request: Request, db: DbSession) -> User | None:
    resolved = accounts.resolve_session(db, request.cookies.get(security.SESSION_COOKIE))
    if resolved is None:
        return None
    user, session = resolved
    request.state.session = session
    return user


def current_user(request: Request, db: DbSession) -> User:
    user = optional_user(request, db)
    if user is None:
        raise Unauthorized("Entre na sua conta para continuar.", code="not_authenticated")
    return user


def current_session(request: Request, user: Annotated[User, Depends(current_user)]) -> UserSession:
    session: UserSession = request.state.session
    return session


def active_user(user: Annotated[User, Depends(current_user)]) -> User:
    """Authenticated user who is not required to change the password first."""
    if user.must_change_password:
        raise Forbidden(
            "Troque a senha temporária para continuar.", code="password_change_required"
        )
    return user


def admin_user(user: Annotated[User, Depends(active_user)]) -> User:
    if not user.is_admin:
        raise Forbidden("Apenas administradores.", code="admin_only")
    return user


CurrentUser = Annotated[User, Depends(active_user)]
AnyUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
CurrentSession = Annotated[UserSession, Depends(current_session)]
