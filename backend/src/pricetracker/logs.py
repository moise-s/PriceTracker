"""Structured JSON logging with correlation IDs and secret redaction.

Correlation fields (``request_id``, ``run_id``, ``target_id``, ``market``) live in
context variables so every log line emitted while handling a request or a run
target carries them automatically. A redaction filter scrubs anything that looks
like an API key, bearer token, cookie or password before it is written.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "pricetracker_log_context", default=None
)

_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"gsk_[A-Za-z0-9]{10,}"), "gsk_***"),
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{10,}"), "sk-***"),
    (re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)(bearer\s+)?[^\s'\",]+"), r"\1***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|password|passwd|secret|token|cookie)['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+"
        ),
        r"\1***",
    ),
    (re.compile(r"(?i)(pt_session=)[^;\s]+"), r"\1***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def bind(**fields: str | None) -> None:
    current = dict(_context.get() or {})
    for key, value in fields.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = str(value)
    _context.set(current)


@contextmanager
def bound(**fields: str | None) -> Iterator[None]:
    token = _context.set(dict(_context.get() or {}))
    try:
        bind(**fields)
        yield
    finally:
        _context.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        payload.update(_context.get() or {})
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update({k: _safe(v) for k, v in extra.items()})
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ctx = " ".join(f"{k}={v}" for k, v in (_context.get() or {}).items())
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            ctx = " ".join([ctx, *(f"{k}={_safe(v)}" for k, v in extra.items())]).strip()
        base = f"{record.levelname:<7} {record.name}: {redact(record.getMessage())}"
        if ctx:
            base += f"  [{ctx}]"
        if record.exc_info:
            base += "\n" + redact(self.formatException(record.exc_info))
        return base


def _safe(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    return value


def configure_logging(level: str = "INFO", json_output: bool = True, stream: Any = None) -> None:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Keep noisy libraries quiet; they could otherwise log full URLs with query strings.
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "PIL", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"fields": fields})
