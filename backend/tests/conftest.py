from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pricetracker import settings as settings_module
from pricetracker.db.session import init_engine, session_factory
from pricetracker.models import Base
from pricetracker.settings import Settings

# Never read real secrets (e.g. the repository's .env with a Groq key) during tests.
for name in ("GROQ_API_KEY", "OPENAI_API_KEY", "PRICETRACKER_COMPATIBLE_API_KEY"):
    os.environ.pop(name, None)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--live", action="store_true", default=False, help="run live smoke tests against real sites")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="live smoke test: pass --live to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "database_url": f"sqlite:///{tmp_path / 'test.db'}",
        "data_dir": tmp_path / "data",
        "public_origin": "https://testserver",
        "cookie_secure": True,
        "setup_require_code": False,
        "log_json": False,
        "log_level": "WARNING",
        "http_min_interval_seconds": 0.0,
        "http_max_retries": 2,
        "target_timeout_seconds": 20.0,
        "worker_heartbeat_seconds": 0.2,
        "groq_api_key": None,
        "openai_api_key": None,
        "secret_key": "test-secret-key-that-is-long-enough-123456",
        "geocoder": "manual",
        "router": "estimate",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    configured = make_settings(tmp_path)
    settings_module.configure_settings(configured)
    engine = init_engine(configured)
    Base.metadata.create_all(engine)
    yield configured
    engine.dispose()
    settings_module.configure_settings(None)


@pytest.fixture
def db(settings: Settings) -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded(db: Session) -> Session:
    from pricetracker.seed import seed_all

    seed_all(db)
    return db


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    from pricetracker.api.app import create_app

    with TestClient(create_app(), base_url="https://testserver") as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    if "pt_csrf" not in client.cookies:
        client.get("/api/v1/auth/csrf")
    return {"X-CSRF-Token": client.cookies["pt_csrf"], "Origin": "https://testserver"}


def api(client: TestClient, method: str, path: str, **kwargs: Any) -> Any:
    headers = kwargs.pop("headers", {})
    if method.upper() not in ("GET", "HEAD"):
        headers = {**csrf_headers(client), **headers}
    return client.request(method, f"/api/v1{path}", headers=headers, **kwargs)


def create_user(db: Session, username: str, password: str = "senha-forte-123", admin: bool = False) -> Any:
    from pricetracker.models.enums import Role
    from pricetracker.services import accounts

    account = accounts._create_user(  # noqa: SLF001 - test helper
        db,
        username=username,
        display_name=username.title(),
        password=password,
        role=Role.ADMIN if admin else Role.USER,
    )
    db.commit()
    return account.user


def login(client: TestClient, username: str, password: str = "senha-forte-123") -> Any:
    client.cookies.clear()
    response = api(client, "POST", "/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()
