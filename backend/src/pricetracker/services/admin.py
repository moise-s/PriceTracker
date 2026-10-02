"""Administrative views: adapter health, users and instance settings."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pricetracker.adapters.registry import ADAPTERS
from pricetracker.db.base import utcnow
from pricetracker.models import Market, RunTarget, User
from pricetracker.models.enums import FAILURE_STATES, LEGITIMATE_STATES, TargetStatus


def adapter_health(db: Session, days: int = 14) -> list[dict[str, Any]]:
    """Aggregated, user-agnostic adapter metrics (no user data exposed)."""
    since = utcnow() - timedelta(days=days)
    markets = list(db.scalars(select(Market).order_by(Market.name)))
    rows = db.execute(
        select(
            RunTarget.market_id,
            RunTarget.status,
            RunTarget.method,
            RunTarget.error_type,
            RunTarget.llm_used,
            RunTarget.llm_needed,
            RunTarget.duration_ms,
            RunTarget.finished_at,
        ).where(RunTarget.finished_at.is_not(None), RunTarget.finished_at > since)
    ).all()
    per_market: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        per_market[row.market_id].append(row)
    result = []
    for market in markets:
        items = per_market.get(market.id, [])
        statuses = Counter(r.status for r in items)
        methods = Counter(r.method for r in items if r.method)
        errors = Counter(
            r.error_type for r in items if r.error_type and TargetStatus(r.status).is_failure
        )
        legit = sum(statuses.get(s.value, 0) for s in LEGITIMATE_STATES)
        failures = sum(statuses.get(s.value, 0) for s in FAILURE_STATES)
        durations = sorted(r.duration_ms for r in items if r.duration_ms is not None)
        last_ok = max(
            (r.finished_at for r in items if r.status == TargetStatus.FOUND.value), default=None
        )
        last_failure = max(
            (r.finished_at for r in items if TargetStatus(r.status).is_failure), default=None
        )
        total = legit + failures
        if total == 0:
            state = "sem_dados"
        elif failures == 0:
            state = "saudavel"
        elif failures / total <= 0.2:
            state = "instavel"
        else:
            state = "falhando"
        adapter_cls = ADAPTERS.get(market.adapter_key)
        result.append(
            {
                "market_id": market.id,
                "slug": market.slug,
                "name": market.name,
                "enabled": market.enabled,
                "adapter_version": adapter_cls.version if adapter_cls else None,
                "strategy": adapter_cls.strategy if adapter_cls else None,
                "state": state,
                "targets": total,
                "success_rate": round(legit / total, 3) if total else None,
                "statuses": dict(statuses),
                "methods": dict(methods),
                "errors": dict(errors),
                "llm_used": sum(1 for r in items if r.llm_used),
                "llm_needed": sum(1 for r in items if r.llm_needed),
                "median_duration_ms": durations[len(durations) // 2] if durations else None,
                "last_success_at": last_ok,
                "last_failure_at": last_failure,
                "notes": market.notes,
            }
        )
    return result


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)
