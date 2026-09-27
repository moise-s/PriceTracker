"""Instance settings stored in the database (administrator-editable, no secrets)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from pricetracker.models import AppSetting
from pricetracker.settings import get_settings

PUBLIC_DEFAULTS: dict[str, Any] = {
    "registration_enabled": False,
    "default_freshness_days": None,  # None -> PRICETRACKER_DEFAULT_FRESHNESS_DAYS
    "llm_enabled": True,
    "llm_max_calls_per_run": None,  # None -> PRICETRACKER_LLM_MAX_CALLS_PER_RUN
}
INTERNAL_KEYS = frozenset({"setup_code"})


def get_value(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    if row is None:
        default = PUBLIC_DEFAULTS.get(key)
        if default is None:
            settings = get_settings()
            if key == "default_freshness_days":
                return settings.default_freshness_days
            if key == "llm_max_calls_per_run":
                return settings.llm_max_calls_per_run
        return default
    return row.value.get("v")


def set_value(db: Session, key: str, value: Any, user_id: uuid.UUID | None = None) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value={"v": value}, updated_by=user_id))
    else:
        row.value = {"v": value}
        row.updated_by = user_id


def delete_value(db: Session, key: str) -> None:
    row = db.get(AppSetting, key)
    if row is not None:
        db.delete(row)


def public_settings(db: Session) -> dict[str, Any]:
    return {key: get_value(db, key) for key in PUBLIC_DEFAULTS}
