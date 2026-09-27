"""OpenAI-compatible LLM providers (Groq, OpenAI, any compatible endpoint).

API keys are server secrets (environment / Docker secrets). An optional
bring-your-own-key value can be stored encrypted with a master key derived from
``PRICETRACKER_SECRET_KEY`` (held outside the database). Keys are never returned
by the API, never logged and never placed in error messages.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken

from pricetracker.models import LlmProvider
from pricetracker.models.enums import LlmKind
from pricetracker.settings import Settings, get_settings


class LlmError(Exception):
    error_type = "llm_error"


class LlmUnavailable(LlmError):
    error_type = "llm_unavailable"  # no provider / no key configured


class LlmAuthError(LlmError):
    error_type = "llm_auth"


class LlmModelNotFound(LlmError):
    error_type = "llm_model_not_found"


class LlmRateLimited(LlmError):
    error_type = "llm_rate_limited"

    def __init__(self, message: str, *, retry_after: float | None = None, daily: bool = False):
        super().__init__(message)
        self.retry_after = retry_after  # seconds, from the provider's Retry-After header
        self.daily = daily  # the provider reported a per-day quota (e.g. tokens per day)


def _retry_after_seconds(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None


class LlmBadResponse(LlmError):
    error_type = "llm_bad_response"


class LlmTimeout(LlmError):
    error_type = "llm_timeout"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: LlmKind
    base_url: str
    model: str
    api_key: str | None
    structured_output: str  # "json_schema" | "json_object"
    key_source: str  # "env:NAME" | "encrypted" | "none"

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def _fernet(settings: Settings) -> Fernet:
    if settings.secret_key is None:
        raise LlmUnavailable("PRICETRACKER_SECRET_KEY is required to store provider keys")
    digest = hashlib.sha256(
        b"pricetracker-byok:" + settings.secret_key.get_secret_value().encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(value: str, settings: Settings | None = None) -> str:
    return _fernet(settings or get_settings()).encrypt(value.encode()).decode()


def decrypt_key(token: str, settings: Settings | None = None) -> str:
    try:
        return _fernet(settings or get_settings()).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise LlmAuthError(
            "stored provider key cannot be decrypted with the current master key"
        ) from exc


_ENV_FIELDS = {
    "GROQ_API_KEY": "groq_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "PRICETRACKER_COMPATIBLE_API_KEY": "compatible_api_key",
}


def resolve_key(
    env_name: str | None, encrypted: str | None, settings: Settings
) -> tuple[str | None, str]:
    if encrypted:
        return decrypt_key(encrypted, settings), "encrypted"
    if env_name:
        field = _ENV_FIELDS.get(env_name)
        if field is not None:
            secret = getattr(settings, field)
            if secret is not None:
                return secret.get_secret_value(), f"env:{env_name}"
        value = os.environ.get(env_name)
        if value:
            return value, f"env:{env_name}"
        return None, f"env:{env_name}"
    return None, "none"


def default_env_name(kind: LlmKind) -> str:
    return {
        LlmKind.GROQ: "GROQ_API_KEY",
        LlmKind.OPENAI: "OPENAI_API_KEY",
        LlmKind.OPENAI_COMPATIBLE: "PRICETRACKER_COMPATIBLE_API_KEY",
    }[kind]


def config_from_row(row: LlmProvider, settings: Settings | None = None) -> ProviderConfig:
    settings = settings or get_settings()
    kind = LlmKind(row.kind)
    key, source = resolve_key(
        row.api_key_env or default_env_name(kind), row.api_key_encrypted, settings
    )
    return ProviderConfig(
        name=row.name,
        kind=kind,
        base_url=row.base_url.rstrip("/"),
        model=row.model,
        api_key=key,
        structured_output=row.structured_output,
        key_source=source,
    )


def config_from_settings(kind: LlmKind, settings: Settings | None = None) -> ProviderConfig:
    settings = settings or get_settings()
    if kind == LlmKind.GROQ:
        base, model, mode = settings.groq_base_url, settings.groq_model, "json_object"
    elif kind == LlmKind.OPENAI:
        base, model, mode = settings.openai_base_url, settings.openai_model, "json_schema"
    else:
        base, model, mode = (
            settings.compatible_base_url or "",
            settings.compatible_model or "",
            "json_object",
        )
    key, source = resolve_key(default_env_name(kind), None, settings)
    return ProviderConfig(
        name=kind.value, kind=kind, base_url=base.rstrip("/"), model=model,
        api_key=key, structured_output=mode, key_source=source,
    )  # fmt: skip


@dataclass
class Completion:
    content: dict[str, Any]
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


class OpenAICompatibleClient:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.config = config
        self.timeout = timeout
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise LlmUnavailable(f"no API key configured for provider '{self.config.name}'")
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _raise_for(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        body = response.text[:2000].lower()
        if response.status_code in (401, 403):
            raise LlmAuthError(f"provider rejected the credentials (HTTP {response.status_code})")
        if (
            response.status_code == 404
            or "model_not_found" in body
            or "does not exist" in body
            or "decommissioned" in body
        ):
            raise LlmModelNotFound(f"model '{self.config.model}' is not available at this provider")
        if response.status_code == 429:
            # Only derived facts are kept: the body can name the provider account.
            daily = "per day" in body
            raise LlmRateLimited(
                "provider rate limit reached (HTTP 429" + (", daily quota)" if daily else ")"),
                retry_after=_retry_after_seconds(response.headers.get("retry-after")),
                daily=daily,
            )
        raise LlmBadResponse(f"provider error (HTTP {response.status_code})")

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.get(f"{self.config.base_url}/models", headers=self._headers())
        except httpx.TimeoutException as exc:
            raise LlmTimeout("provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LlmError(f"provider unreachable ({type(exc).__name__})") from exc
        self._raise_for(response)
        data = response.json().get("data") or []
        return sorted(str(item.get("id")) for item in data if item.get("id"))

    def complete_json(
        self, messages: list[dict[str, str]], schema: dict[str, Any], schema_name: str
    ) -> Completion:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1500,
        }
        if self.config.structured_output == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LlmTimeout("provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LlmError(f"provider unreachable ({type(exc).__name__})") from exc
        self._raise_for(response)
        latency = int((time.monotonic() - started) * 1000)
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_reasoning(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LlmBadResponse("provider returned malformed JSON") from exc
        if not isinstance(parsed, dict):
            raise LlmBadResponse("provider returned a non-object JSON value")
        usage = body.get("usage") or {}
        return Completion(
            parsed, latency, usage.get("prompt_tokens"), usage.get("completion_tokens")
        )


def _strip_reasoning(content: str) -> str:
    """Some reasoning models prepend <think>...</think>; keep only the JSON object."""
    text = content.strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :]
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end != -1 else text
