"""Password hashing (Argon2id), opaque tokens and CSRF helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi defaults to Argon2id with RFC 9106 "low memory" parameters.
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("pricetracker-timing-equaliser")

SESSION_COOKIE = "pt_session"
CSRF_COOKIE = "pt_csrf"
CSRF_HEADER = "X-CSRF-Token"

_RECOVERY_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1IL")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time verification; unknown users still pay the hashing cost."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hmac_hex(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_setup_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def password_problems(password: str, username: str, min_length: int) -> list[str]:
    problems = []
    if len(password) < min_length:
        problems.append(f"A senha precisa ter pelo menos {min_length} caracteres.")
    if len(password) > 256:
        problems.append("A senha pode ter no máximo 256 caracteres.")
    if username and username.lower() in password.lower():
        problems.append("A senha não pode conter o nome de usuário.")
    if password.lower() in {"1234567890", "senha12345", "password123", "qwertyuiop"}:
        problems.append("Escolha uma senha menos previsível.")
    return problems
