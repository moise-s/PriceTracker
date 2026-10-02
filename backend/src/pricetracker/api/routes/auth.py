from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response

from pricetracker.api import schemas
from pricetracker.api.deps import (
    AnyUser,
    CsrfProtected,
    CurrentSession,
    DbSession,
    clear_session_cookies,
    client_address,
    client_label,
    issue_csrf_cookie,
    set_session_cookies,
)
from pricetracker.api.serializers import user_out
from pricetracker.services import accounts, profile

router = APIRouter(tags=["auth"])


def _me(db: DbSession, user: object) -> schemas.MeOut:
    from pricetracker.models import User

    assert isinstance(user, User)
    prof = profile.get_profile(db, user)
    return schemas.MeOut(
        user=user_out(user),
        onboarding_completed=prof.onboarding_completed_at is not None,
        recovery_codes_remaining=accounts.remaining_recovery_codes(db, user),
    )


@router.get("/setup/status", response_model=schemas.SetupStatus)
def setup_status(db: DbSession) -> schemas.SetupStatus:
    return schemas.SetupStatus(**accounts.setup_status(db))


@router.post(
    "/setup/admin",
    response_model=schemas.AccountCreatedOut,
    status_code=201,
    dependencies=[CsrfProtected],
)
def setup_admin(
    body: schemas.SetupAdminIn, request: Request, response: Response, db: DbSession
) -> schemas.AccountCreatedOut:
    account = accounts.create_first_admin(
        db,
        username=body.username,
        display_name=body.display_name,
        password=body.password,
        setup_code=body.setup_code,
    )
    token = accounts.create_session(db, account.user, client_label(request))
    set_session_cookies(response, token)
    return schemas.AccountCreatedOut(
        user=user_out(account.user), recovery_codes=account.recovery_codes
    )


@router.get("/auth/csrf", response_model=schemas.Ok)
def csrf(request: Request, response: Response) -> schemas.Ok:
    """Issue the CSRF cookie (double-submit token) if it is missing."""
    if not request.cookies.get("pt_csrf"):
        issue_csrf_cookie(response)
    return schemas.Ok()


@router.post("/auth/login", response_model=schemas.MeOut, dependencies=[CsrfProtected])
def login(
    body: schemas.LoginIn, request: Request, response: Response, db: DbSession
) -> schemas.MeOut:
    user = accounts.authenticate(
        db, username=body.username, password=body.password, client=client_address(request)
    )
    token = accounts.create_session(db, user, client_label(request))
    set_session_cookies(response, token)
    return _me(db, user)


@router.post(
    "/auth/register",
    response_model=schemas.AccountCreatedOut,
    status_code=201,
    dependencies=[CsrfProtected],
)
def register(
    body: schemas.RegisterIn, request: Request, response: Response, db: DbSession
) -> schemas.AccountCreatedOut:
    account = accounts.register(
        db, username=body.username, display_name=body.display_name, password=body.password
    )
    token = accounts.create_session(db, account.user, client_label(request))
    set_session_cookies(response, token)
    return schemas.AccountCreatedOut(
        user=user_out(account.user), recovery_codes=account.recovery_codes
    )


@router.post("/auth/recover", response_model=schemas.Ok, dependencies=[CsrfProtected])
def recover(body: schemas.RecoverIn, request: Request, db: DbSession) -> schemas.Ok:
    accounts.recover_with_code(
        db,
        username=body.username,
        code=body.recovery_code,
        new_password=body.new_password,
        client=client_address(request),
    )
    return schemas.Ok()


@router.post("/auth/logout", response_model=schemas.Ok, dependencies=[CsrfProtected])
def logout(response: Response, user: AnyUser, session: CurrentSession, db: DbSession) -> schemas.Ok:
    accounts.revoke_session(db, user, session.id)
    clear_session_cookies(response)
    return schemas.Ok()


@router.get("/auth/me", response_model=schemas.MeOut)
def me(request: Request, response: Response, user: AnyUser, db: DbSession) -> schemas.MeOut:
    if not request.cookies.get("pt_csrf"):
        issue_csrf_cookie(response)
    return _me(db, user)


@router.post("/auth/change-password", response_model=schemas.Ok, dependencies=[CsrfProtected])
def change_password(
    body: schemas.ChangePasswordIn, user: AnyUser, session: CurrentSession, db: DbSession
) -> schemas.Ok:
    accounts.change_password(
        db,
        user,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_session=session.id,
    )
    return schemas.Ok()


@router.get("/auth/sessions", response_model=list[schemas.SessionOut])
def sessions(user: AnyUser, session: CurrentSession, db: DbSession) -> list[schemas.SessionOut]:
    return [
        schemas.SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            client_label=s.client_label,
            current=s.id == session.id,
        )
        for s in accounts.list_sessions(db, user)
    ]


@router.delete(
    "/auth/sessions/{session_id}", response_model=schemas.Ok, dependencies=[CsrfProtected]
)
def revoke_session(session_id: uuid.UUID, user: AnyUser, db: DbSession) -> schemas.Ok:
    accounts.revoke_session(db, user, session_id)
    return schemas.Ok()


@router.post(
    "/auth/sessions/revoke-others", response_model=schemas.Ok, dependencies=[CsrfProtected]
)
def revoke_others(user: AnyUser, session: CurrentSession, db: DbSession) -> schemas.Ok:
    accounts.revoke_all_sessions(db, user.id, except_id=session.id)
    return schemas.Ok()


@router.post(
    "/auth/recovery-codes", response_model=schemas.RecoveryCodesOut, dependencies=[CsrfProtected]
)
def regenerate_codes(
    body: schemas.PasswordConfirmIn, user: AnyUser, db: DbSession
) -> schemas.RecoveryCodesOut:
    return schemas.RecoveryCodesOut(
        recovery_codes=accounts.regenerate_recovery_codes(db, user, password=body.password)
    )
