"""Administration of LLM providers: configuration, safe connection test and metrics."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pricetracker.db.base import utcnow
from pricetracker.llm.providers import (
    LlmError,
    OpenAICompatibleClient,
    ProviderConfig,
    config_from_row,
    encrypt_key,
)
from pricetracker.llm.service import LlmService
from pricetracker.models import LlmCall, LlmProvider
from pricetracker.models.enums import LlmKind
from pricetracker.services.errors import NotFound, ValidationFailed
from pricetracker.settings import get_settings

ALLOWED_ENV_NAMES = {"GROQ_API_KEY", "OPENAI_API_KEY", "PRICETRACKER_COMPATIBLE_API_KEY"}


def list_providers(db: Session) -> list[LlmProvider]:
    return list(
        db.scalars(select(LlmProvider).order_by(LlmProvider.is_default.desc(), LlmProvider.name))
    )


def provider_view(row: LlmProvider) -> dict[str, Any]:
    config = config_from_row(row)
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "base_url": row.base_url,
        "model": row.model,
        "structured_output": row.structured_output,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "key_configured": config.has_key,
        "key_source": config.key_source.split(":")[0] if config.key_source else "none",
        "key_env": row.api_key_env,
        "last_check_status": row.last_check_status,
        "last_check_at": row.last_check_at,
        "last_check_detail": row.last_check_detail,
    }


def save_provider(db: Session, provider_id: uuid.UUID | None, data: dict[str, Any]) -> LlmProvider:
    kind = data.get("kind")
    if kind is not None and kind not in {k.value for k in LlmKind}:
        raise ValidationFailed("Tipo de provedor inválido.", code="invalid_kind")
    base_url = data.get("base_url")
    if base_url is not None and not base_url.startswith("https://"):
        raise ValidationFailed("Use uma URL https:// para o provedor.", code="invalid_base_url")
    env_name = data.get("api_key_env")
    if env_name is not None and env_name not in ALLOWED_ENV_NAMES:
        raise ValidationFailed(
            "Variável de chave não permitida. Use GROQ_API_KEY, OPENAI_API_KEY ou PRICETRACKER_COMPATIBLE_API_KEY.",
            code="invalid_key_env",
        )
    new_key = data.pop("api_key", None)
    clear_key = data.pop("clear_stored_key", False)
    if provider_id is None:
        row = LlmProvider(**data)
        db.add(row)
    else:
        found = db.get(LlmProvider, provider_id)
        if found is None:
            raise NotFound("Provedor não encontrado.")
        row = found
        for key, value in data.items():
            if value is not None:
                setattr(row, key, value)
    if new_key:
        row.api_key_encrypted = encrypt_key(new_key.strip())
    elif clear_key:
        row.api_key_encrypted = None
    if data.get("is_default"):
        db.flush()
        for other in db.scalars(select(LlmProvider).where(LlmProvider.id != row.id)):
            other.is_default = False
    db.commit()
    return row


def test_provider(db: Session, provider_id: uuid.UUID) -> dict[str, Any]:
    row = db.get(LlmProvider, provider_id)
    if row is None:
        raise NotFound("Provedor não encontrado.")
    result = _check(config_from_row(row))
    row.last_check_status = "ok" if result["ok"] else result["error_type"]
    row.last_check_at = utcnow()
    row.last_check_detail = result["message"][:300]
    db.commit()
    return result


def _check(config: ProviderConfig) -> dict[str, Any]:
    base: dict[str, Any] = {
        "provider": config.name,
        "model": config.model,
        "key_configured": config.has_key,
    }
    if not config.has_key:
        return {
            **base,
            "ok": False,
            "error_type": "llm_unavailable",
            "message": "Nenhuma chave configurada no servidor.",
        }
    client = OpenAICompatibleClient(config, timeout=get_settings().llm_timeout_seconds)
    try:
        models = client.list_models()
    except LlmError as exc:
        return {**base, "ok": False, "error_type": exc.error_type, "message": _friendly(exc)}
    if models and config.model not in models:
        suggestions = [m for m in models if any(w in m for w in ("qwen", "llama", "gpt", "oss"))][
            :6
        ]
        return {
            **base,
            "ok": False,
            "error_type": "llm_model_not_found",
            "message": f"O modelo '{config.model}' não está disponível neste provedor.",
            "available_models": suggestions or models[:6],
        }
    try:
        completion = client.complete_json(
            [
                {"role": "system", "content": "Responda apenas com JSON."},
                {"role": "user", "content": 'Responda exatamente {"ok": true}.'},
            ],
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}},
            },
            "health_check",
        )
    except LlmError as exc:
        return {**base, "ok": False, "error_type": exc.error_type, "message": _friendly(exc)}
    ok = completion.content.get("ok") is True
    return {
        **base,
        "ok": ok,
        "error_type": None if ok else "llm_bad_response",
        "message": f"Conexão ok ({completion.latency_ms} ms)."
        if ok
        else "Resposta inesperada do modelo.",
        "latency_ms": completion.latency_ms,
    }


def _friendly(exc: LlmError) -> str:
    return {
        "llm_auth": "A chave foi recusada pelo provedor. Verifique a chave configurada no servidor.",
        "llm_model_not_found": "O modelo configurado não existe mais neste provedor. Escolha outro modelo.",
        "llm_rate_limited": "Limite de uso do provedor atingido. Tente mais tarde.",
        "llm_timeout": "O provedor não respondeu a tempo.",
        "llm_unavailable": "Nenhuma chave configurada.",
    }.get(exc.error_type, f"Falha ao contatar o provedor ({exc}).")


def check_active_provider(db: Session) -> dict[str, Any]:
    service = LlmService(db)
    config = service.active_config()
    if config is None:
        return {
            "ok": False,
            "error_type": "llm_disabled",
            "message": "IA desativada nas configurações.",
        }
    return _check(config)


def usage_summary(db: Session, days: int = 30) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(
        select(LlmCall.status, LlmCall.cache_hit, func.count())
        .where(LlmCall.created_at > since)
        .group_by(LlmCall.status, LlmCall.cache_hit)
    ).all()
    total = sum(int(r[2]) for r in rows)
    return {
        "days": days,
        "calls": total,
        "cache_hits": sum(int(r[2]) for r in rows if r[1]),
        "errors": sum(int(r[2]) for r in rows if r[0] != "ok"),
    }
