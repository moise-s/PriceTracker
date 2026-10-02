"""Accounts: first-run setup, login, sessions, recovery codes and admin actions."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from pricetracker import security
from pricetracker.db.base import utcnow
from pricetracker.models import (
    LoginAttempt,
    Profile,
    RecoveryCode,
    ShoppingList,
    User,
    UserSession,
)
from pricetracker.models.enums import Role
from pricetracker.services import app_settings
from pricetracker.services.errors import (
    Conflict,
    Forbidden,
    NotFound,
    TooManyRequests,
    Unauthorized,
    ValidationFailed,
)
from pricetracker.settings import Settings, get_settings

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
RECOVERY_CODE_COUNT = 10
LAST_SEEN_RESOLUTION = timedelta(minutes=5)


@dataclass
class NewAccount:
    user: User
    recovery_codes: list[str]


def normalize_username(username: str) -> str:
    return username.strip().lower()


def _validate_new_credentials(db: Session, username: str, password: str, settings: Settings) -> str:
    normalized = normalize_username(username)
    if not USERNAME_RE.match(normalized):
        raise ValidationFailed(
            "Use de 3 a 32 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado.",
            code="invalid_username",
        )
    problems = security.password_problems(password, normalized, settings.min_password_length)
    if problems:
        raise ValidationFailed(" ".join(problems), code="weak_password")
    exists = db.scalar(select(func.count()).select_from(User).where(User.username == normalized))
    if exists:
        raise Conflict("Este nome de usuário já está em uso.", code="username_taken")
    return normalized


def _issue_recovery_codes(db: Session, user: User) -> list[str]:
    db.query(RecoveryCode).filter(RecoveryCode.user_id == user.id).delete()
    codes = [security.new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in codes:
        db.add(
            RecoveryCode(
                user_id=user.id,
                code_hash=security.sha256_hex(
                    f"{user.id}:{security.normalize_recovery_code(code)}"
                ),
            )
        )
    return codes


def _create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    role: Role,
    must_change_password: bool = False,
) -> NewAccount:
    user = User(
        username=username,
        display_name=display_name.strip()[:120] or username,
        password_hash=security.hash_password(password),
        role=role.value,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, freshness_days=get_settings().default_freshness_days))
    db.add(ShoppingList(user_id=user.id, name="Minha lista", is_default=True))
    codes = _issue_recovery_codes(db, user)
    db.flush()
    return NewAccount(user=user, recovery_codes=codes)


# --- first-run setup -----------------------------------------------------------


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def setup_status(db: Session) -> dict[str, bool]:
    settings = get_settings()
    needs_setup = user_count(db) == 0
    return {
        "needs_setup": needs_setup,
        "requires_code": needs_setup and settings.setup_require_code,
    }


def generate_setup_code(db: Session, ttl_minutes: int = 30) -> str:
    if user_count(db) > 0:
        raise Conflict("A instalação já tem um administrador.", code="already_set_up")
    code = security.new_setup_code()
    expires = utcnow() + timedelta(minutes=ttl_minutes)
    app_settings.set_value(
        db,
        "setup_code",
        {
            "hash": security.sha256_hex(security.normalize_recovery_code(code)),
            "expires_at": expires.isoformat(),
        },
    )
    db.commit()
    return code


def _check_setup_code(db: Session, code: str | None) -> None:
    stored = app_settings.get_value(db, "setup_code")
    if not stored or not code:
        raise Forbidden(
            "Código de configuração ausente. Gere um no servidor com `pricetracker setup-code`.",
            code="setup_code_required",
        )
    if datetime.fromisoformat(stored["expires_at"]) < utcnow():
        raise Forbidden("O código de configuração expirou. Gere outro.", code="setup_code_expired")
    candidate = security.sha256_hex(security.normalize_recovery_code(code))
    if not security.constant_time_equals(candidate, stored["hash"]):
        raise Forbidden("Código de configuração inválido.", code="setup_code_invalid")


def create_first_admin(
    db: Session, *, username: str, display_name: str, password: str, setup_code: str | None
) -> NewAccount:
    settings = get_settings()
    if user_count(db) > 0:
        raise Conflict("A instalação já tem um administrador.", code="already_set_up")
    if settings.setup_require_code:
        _check_setup_code(db, setup_code)
    normalized = _validate_new_credentials(db, username, password, settings)
    account = _create_user(
        db, username=normalized, display_name=display_name, password=password, role=Role.ADMIN
    )
    app_settings.delete_value(db, "setup_code")
    app_settings.set_value(db, "registration_enabled", False, account.user.id)
    db.commit()
    return account


def create_first_admin_trusted(
    db: Session, *, username: str, display_name: str, password: str
) -> NewAccount:
    """First administrator from the local CLI (server access replaces the setup code)."""
    if user_count(db) > 0:
        raise Conflict("A instalação já tem um administrador.", code="already_set_up")
    normalized = _validate_new_credentials(db, username, password, get_settings())
    account = _create_user(
        db, username=normalized, display_name=display_name, password=password, role=Role.ADMIN
    )
    app_settings.delete_value(db, "setup_code")
    db.commit()
    return account


def register(db: Session, *, username: str, display_name: str, password: str) -> NewAccount:
    if user_count(db) == 0:
        raise Forbidden("Conclua a configuração inicial primeiro.", code="setup_required")
    if not app_settings.get_value(db, "registration_enabled"):
        raise Forbidden(
            "O cadastro está desativado. Peça uma conta ao administrador.",
            code="registration_disabled",
        )
    normalized = _validate_new_credentials(db, username, password, get_settings())
    account = _create_user(
        db, username=normalized, display_name=display_name, password=password, role=Role.USER
    )
    db.commit()
    return account


# --- login & rate limiting -------------------------------------------------------


def _attempt_keys(settings: Settings, username: str, client: str) -> tuple[str, str]:
    key = settings.signing_key
    return security.hmac_hex(key, "u:" + normalize_username(username)), security.hmac_hex(
        key, "c:" + client
    )


def _check_rate_limit(db: Session, settings: Settings, username_key: str, client_key: str) -> None:
    window_start = utcnow() - timedelta(minutes=settings.login_window_minutes)
    last_success = db.scalar(
        select(func.max(LoginAttempt.created_at)).where(
            LoginAttempt.username_key == username_key, LoginAttempt.succeeded.is_(True)
        )
    )
    since = max(window_start, last_success) if last_success else window_start
    user_failures = db.scalar(
        select(func.count()).where(
            LoginAttempt.username_key == username_key,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.created_at > since,
        )
    )
    client_failures = db.scalar(
        select(func.count()).where(
            LoginAttempt.client_key == client_key,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.created_at > window_start,
        )
    )
    if (user_failures or 0) >= settings.login_max_failures or (client_failures or 0) >= (
        settings.login_max_failures * 4
    ):
        raise TooManyRequests(
            f"Muitas tentativas. Aguarde {settings.login_window_minutes} minutos e tente novamente.",
            details={"retry_after_seconds": settings.login_window_minutes * 60},
        )


def _record_attempt(db: Session, username_key: str, client_key: str, ok: bool) -> None:
    db.add(LoginAttempt(username_key=username_key, client_key=client_key, succeeded=ok))
    cutoff = utcnow() - timedelta(days=7)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))


def authenticate(db: Session, *, username: str, password: str, client: str) -> User:
    settings = get_settings()
    username_key, client_key = _attempt_keys(settings, username, client)
    _check_rate_limit(db, settings, username_key, client_key)
    user = db.scalar(select(User).where(User.username == normalize_username(username)))
    ok = security.verify_password(user.password_hash if user else None, password)
    if not ok or user is None or not user.is_active:
        _record_attempt(db, username_key, client_key, False)
        db.commit()
        raise Unauthorized("Usuário ou senha incorretos.", code="invalid_credentials")
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    user.last_login_at = utcnow()
    _record_attempt(db, username_key, client_key, True)
    db.flush()
    return user


# --- sessions ----------------------------------------------------------------------


def create_session(db: Session, user: User, client_label: str | None) -> str:
    settings = get_settings()
    token = security.new_token()
    now = utcnow()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=security.sha256_hex(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.session_absolute_days),
            client_label=(client_label or "")[:120] or None,
        )
    )
    db.commit()
    return token


def resolve_session(db: Session, token: str | None) -> tuple[User, UserSession] | None:
    if not token or len(token) > 200:
        return None
    settings = get_settings()
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == security.sha256_hex(token))
    )
    if session is None or session.revoked_at is not None:
        return None
    now = utcnow()
    if session.expires_at <= now or now - session.last_seen_at > timedelta(
        days=settings.session_idle_days
    ):
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    if now - session.last_seen_at > LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return user, session


def revoke_session(db: Session, user: User, session_id: uuid.UUID) -> None:
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != user.id:
        raise NotFound("Sessão não encontrada.")
    session.revoked_at = session.revoked_at or utcnow()
    db.commit()


def revoke_all_sessions(db: Session, user_id: uuid.UUID, except_id: uuid.UUID | None = None) -> int:
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if except_id is not None:
        stmt = stmt.where(UserSession.id != except_id)
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def list_sessions(db: Session, user: User) -> list[UserSession]:
    now = utcnow()
    return list(
        db.scalars(
            select(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_seen_at.desc())
        )
    )


# --- passwords & recovery ------------------------------------------------------------


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
    keep_session: uuid.UUID | None,
) -> None:
    if not security.verify_password(user.password_hash, current_password):
        raise Unauthorized("Senha atual incorreta.", code="invalid_credentials")
    problems = security.password_problems(
        new_password, user.username, get_settings().min_password_length
    )
    if problems:
        raise ValidationFailed(" ".join(problems), code="weak_password")
    user.password_hash = security.hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    db.commit()
    revoke_all_sessions(db, user.id, except_id=keep_session)


def regenerate_recovery_codes(db: Session, user: User, *, password: str) -> list[str]:
    if not security.verify_password(user.password_hash, password):
        raise Unauthorized("Senha incorreta.", code="invalid_credentials")
    codes = _issue_recovery_codes(db, user)
    db.commit()
    return codes


def remaining_recovery_codes(db: Session, user: User) -> int:
    return int(
        db.scalar(
            select(func.count()).where(
                RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
            )
        )
        or 0
    )


def recover_with_code(
    db: Session, *, username: str, code: str, new_password: str, client: str
) -> User:
    settings = get_settings()
    username_key, client_key = _attempt_keys(settings, username, client)
    _check_rate_limit(db, settings, username_key, client_key)
    user = db.scalar(select(User).where(User.username == normalize_username(username)))
    record = None
    if user is not None and user.is_active:
        digest = security.sha256_hex(f"{user.id}:{security.normalize_recovery_code(code)}")
        record = db.scalar(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == digest,
                RecoveryCode.used_at.is_(None),
            )
        )
    if user is None or record is None:
        _record_attempt(db, username_key, client_key, False)
        db.commit()
        raise Unauthorized("Usuário ou código de recuperação inválido.", code="invalid_recovery")
    problems = security.password_problems(new_password, user.username, settings.min_password_length)
    if problems:
        raise ValidationFailed(" ".join(problems), code="weak_password")
    record.used_at = utcnow()
    user.password_hash = security.hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    _record_attempt(db, username_key, client_key, True)
    db.commit()
    revoke_all_sessions(db, user.id)
    return user


# --- administration ----------------------------------------------------------------------


def admin_create_user(
    db: Session, *, username: str, display_name: str, temporary_password: str, role: Role
) -> NewAccount:
    normalized = _validate_new_credentials(db, username, temporary_password, get_settings())
    account = _create_user(
        db,
        username=normalized,
        display_name=display_name,
        password=temporary_password,
        role=role,
        must_change_password=True,
    )
    db.commit()
    return account


def admin_reset_password(db: Session, *, user_id: uuid.UUID, temporary_password: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Usuário não encontrado.")
    problems = security.password_problems(
        temporary_password, user.username, get_settings().min_password_length
    )
    if problems:
        raise ValidationFailed(" ".join(problems), code="weak_password")
    user.password_hash = security.hash_password(temporary_password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    db.commit()
    revoke_all_sessions(db, user.id)
    return user


def _admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count()).where(User.role == Role.ADMIN.value, User.is_active.is_(True))
        )
        or 0
    )


def admin_update_user(
    db: Session, actor: User, *, user_id: uuid.UUID, is_active: bool | None, role: Role | None
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("Usuário não encontrado.")
    demoting = role is not None and role != Role.ADMIN and user.is_admin
    deactivating = is_active is False and user.is_admin
    if (demoting or deactivating) and _admin_count(db) <= 1:
        raise Conflict("É preciso manter pelo menos um administrador ativo.", code="last_admin")
    if user.id == actor.id and (is_active is False):
        raise Conflict("Você não pode desativar a própria conta.", code="self_deactivate")
    if is_active is not None:
        user.is_active = is_active
    if role is not None:
        user.role = role.value
    db.commit()
    if is_active is False:
        revoke_all_sessions(db, user.id)
    return user
