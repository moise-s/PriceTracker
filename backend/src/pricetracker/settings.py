"""Application settings, validated once at startup.

Values come from environment variables prefixed with ``PRICETRACKER_`` (and an
optional ``.env`` file for local development). Every secret also accepts a
``<NAME>_FILE`` variant pointing to a file, which is how Docker secrets are
mounted in production. Secrets are held as ``SecretStr`` so they never appear in
``repr()`` or logs.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "secret_key": ("PRICETRACKER_SECRET_KEY",),
    "db_password": ("PRICETRACKER_DB_PASSWORD", "POSTGRES_PASSWORD"),
    "groq_api_key": ("PRICETRACKER_GROQ_API_KEY", "GROQ_API_KEY"),
    "openai_api_key": ("PRICETRACKER_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "compatible_api_key": ("PRICETRACKER_COMPATIBLE_API_KEY",),
}


def _read_secret_files() -> dict[str, str]:
    """Resolve ``<ENV>_FILE`` variables into values for the secret fields."""
    resolved: dict[str, str] = {}
    for field, env_names in _SECRET_FIELDS.items():
        for env_name in env_names:
            file_path = os.environ.get(f"{env_name}_FILE")
            if file_path:
                path = Path(file_path)
                if not path.is_file():
                    raise ValueError(f"{env_name}_FILE points to a missing file")
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    resolved[field] = value
                    break
    return resolved


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PRICETRACKER_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True

    # --- database -------------------------------------------------------------
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "pricetracker"
    db_user: str = "pricetracker"
    db_password: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("PRICETRACKER_DB_PASSWORD", "POSTGRES_PASSWORD")
    )
    db_pool_size: int = 5

    # --- web/auth -------------------------------------------------------------
    secret_key: SecretStr | None = None
    public_origin: str = "http://localhost:5173"
    extra_allowed_origins: list[str] = Field(default_factory=list)
    cookie_secure: bool = True
    session_absolute_days: int = 30
    session_idle_days: int = 7
    setup_require_code: bool = True
    login_max_failures: int = 5
    login_window_minutes: int = 15
    min_password_length: int = 10

    # --- storage --------------------------------------------------------------
    data_dir: Path = Path("./var")
    max_upload_mb: int = 5
    image_max_dimension: int = 1024

    # --- locale / product rules ------------------------------------------------
    timezone: str = "America/Sao_Paulo"
    default_freshness_days: int = 7

    # --- collection -------------------------------------------------------------
    http_user_agent: str = "PriceTracker/1.0 (self-hosted household price comparison; low volume)"
    http_timeout_seconds: float = 20.0
    http_per_host_concurrency: int = 2
    http_min_interval_seconds: float = 1.0
    http_max_retries: int = 3
    target_timeout_seconds: float = 90.0
    circuit_breaker_threshold: int = 4
    robots_cache_hours: int = 12
    sitemap_cache_hours: int = 24

    # --- jobs --------------------------------------------------------------------
    worker_concurrency: int = 4
    worker_poll_seconds: float = 2.0
    worker_heartbeat_seconds: float = 10.0
    worker_stale_after_seconds: float = 120.0
    scheduler_poll_seconds: float = 30.0

    # --- LLM (optional fallback) ---------------------------------------------
    llm_enabled: bool = True
    llm_default_provider: Literal["groq", "openai", "openai_compatible"] = "groq"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "qwen/qwen3.8-27b"
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("PRICETRACKER_GROQ_API_KEY", "GROQ_API_KEY")
    )
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("PRICETRACKER_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    compatible_base_url: str | None = None
    compatible_model: str | None = None
    compatible_api_key: SecretStr | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_calls_per_run: int = 12
    llm_max_input_chars: int = 12000

    # --- geo -----------------------------------------------------------------------
    geocoder: Literal["manual", "nominatim"] = "manual"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_contact: str | None = None
    router: Literal["estimate", "osrm"] = "estimate"
    osrm_url: str | None = None
    route_detour_factor: float = 1.35
    geo_cache_days: int = 90

    @model_validator(mode="before")
    @classmethod
    def _inject_secret_files(cls, data: object) -> object:
        if isinstance(data, dict):
            for field, value in _read_secret_files().items():
                data.setdefault(field, value)
        return data

    @field_validator("public_origin")
    @classmethod
    def _strip_origin(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _validate_production(self) -> Settings:
        if self.environment == "production":
            if self.secret_key is None or len(self.secret_key.get_secret_value()) < 32:
                raise ValueError("PRICETRACKER_SECRET_KEY must be set (>= 32 chars) in production")
            if not self.cookie_secure:
                raise ValueError("PRICETRACKER_COOKIE_SECURE must be true in production")
            if not self.public_origin.startswith("https://"):
                raise ValueError(
                    "PRICETRACKER_PUBLIC_ORIGIN must be an https:// origin in production"
                )
            if self.resolved_database_url.startswith("sqlite"):
                raise ValueError("SQLite is only supported for development and tests")
        if self.router == "osrm" and not self.osrm_url:
            raise ValueError("PRICETRACKER_OSRM_URL is required when PRICETRACKER_ROUTER=osrm")
        return self

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.db_host:
            password = self.db_password.get_secret_value() if self.db_password else ""
            auth = quote(self.db_user, safe="")
            if password:
                auth += ":" + quote(password, safe="")
            return f"postgresql+psycopg://{auth}@{self.db_host}:{self.db_port}/{self.db_name}"
        return f"sqlite:///{(self.data_dir / 'pricetracker-dev.db').as_posix()}"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def allowed_origins(self) -> list[str]:
        return [self.public_origin, *[o.rstrip("/") for o in self.extra_allowed_origins]]

    @property
    def signing_key(self) -> bytes:
        """Key used for HMAC pseudonymisation (login attempts). Dev fallback is fixed."""
        if self.secret_key is not None:
            return self.secret_key.get_secret_value().encode()
        return b"pricetracker-development-only-key"


_override: Settings | None = None


@lru_cache(maxsize=1)
def _cached_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    return _override if _override is not None else _cached_settings()


def configure_settings(settings: Settings | None) -> None:
    """Use explicit settings (CLI --config, tests) instead of the environment."""
    global _override
    _override = settings


def reset_settings_cache() -> None:
    _cached_settings.cache_clear()
    configure_settings(None)
