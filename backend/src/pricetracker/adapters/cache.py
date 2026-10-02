"""Database-backed caches for robots.txt and public documents (sitemaps)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from pricetracker.adapters.base import DocumentCache
from pricetracker.adapters.robots import RobotsPolicy, parse_robots
from pricetracker.db.base import utcnow
from pricetracker.models import HttpCache
from pricetracker.settings import Settings


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def robots_loader(factory: sessionmaker[Session]) -> Callable[[str], RobotsPolicy | None]:
    def load(host: str) -> RobotsPolicy | None:
        with factory() as db:
            row = db.get(HttpCache, _key(f"robots:{host}"))
            if row is None or row.expires_at < utcnow():
                return None
            return parse_robots(row.body, row.status_code)

    return load


def robots_saver(
    factory: sessionmaker[Session], settings: Settings
) -> Callable[[str, RobotsPolicy, int, str], None]:
    def save(host: str, _policy: RobotsPolicy, status: int, text: str) -> None:
        with factory() as db:
            key = _key(f"robots:{host}")
            row = db.get(HttpCache, key)
            expires = utcnow() + timedelta(hours=settings.robots_cache_hours)
            if row is None:
                db.add(
                    HttpCache(
                        key=key,
                        url=f"https://{host}/robots.txt",
                        status_code=status,
                        body=text,
                        expires_at=expires,
                    )
                )
            else:
                row.status_code, row.body, row.fetched_at, row.expires_at = (
                    status,
                    text,
                    utcnow(),
                    expires,
                )
            db.commit()

    return save


def document_cache(factory: sessionmaker[Session]) -> DocumentCache:
    def load(key: str) -> str | None:
        with factory() as db:
            row = db.get(HttpCache, key)
            if row is None or row.expires_at < utcnow():
                return None
            return row.body

    def save(key: str, label: str, body: str, ttl: timedelta) -> None:
        with factory() as db:
            row = db.get(HttpCache, key)
            expires = utcnow() + ttl
            if row is None:
                db.add(
                    HttpCache(key=key, url=label, status_code=200, body=body, expires_at=expires)
                )
            else:
                row.body, row.fetched_at, row.expires_at = body, utcnow(), expires
            db.commit()

    return DocumentCache(load, save)
