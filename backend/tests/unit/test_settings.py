"""Production settings guard rails."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_settings


def _production(tmp_path: Path, origin: str) -> object:
    return make_settings(
        tmp_path,
        environment="production",
        public_origin=origin,
        database_url="postgresql+psycopg://u:p@db/pricetracker",
    )


@pytest.mark.parametrize(
    "origin",
    ["https://precos.example.test", "http://localhost:8090", "http://127.0.0.1:8090"],
)
def test_production_accepts_https_or_loopback_origins(tmp_path: Path, origin: str) -> None:
    assert _production(tmp_path, origin)


@pytest.mark.parametrize(
    "origin",
    ["http://precos.example.test", "http://localhost.example.test", "http://10.0.0.5:8090"],
)
def test_production_rejects_plain_http_on_non_loopback(tmp_path: Path, origin: str) -> None:
    with pytest.raises(ValueError, match="PUBLIC_ORIGIN"):
        _production(tmp_path, origin)


def test_production_requires_secure_cookies_and_a_real_database(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        make_settings(
            tmp_path,
            environment="production",
            cookie_secure=False,
            database_url="postgresql+psycopg://u:p@db/pricetracker",
        )
    with pytest.raises(ValueError, match="SQLite"):
        make_settings(tmp_path, environment="production")
