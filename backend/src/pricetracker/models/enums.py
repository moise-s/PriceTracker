from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"


class SoldBy(StrEnum):
    PACKAGE = "package"  # fixed package, e.g. rice 1 kg
    WEIGHT = "weight"  # variable weight priced per kg, e.g. steak, apples
    UNIT = "unit"  # individual unit or pack, e.g. papaya, a pack of 30 eggs


class Unit(StrEnum):
    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"
    M = "m"  # length in metres
    UN = "un"  # unit / piece
    PCT = "pct"  # package (list quantity only)


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.SUCCESS, RunStatus.PARTIAL, RunStatus.FAILED, RunStatus.CANCELLED}


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    CLI = "cli"
    RETRY = "retry"


class TargetStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FOUND = "found"  # matching offer with a price
    NOT_FOUND = "not_found"  # search worked, nothing matched
    UNAVAILABLE = "unavailable"  # matched product exists but is out of stock
    NO_PRICE = "no_price"  # matched product exists but shows no price
    BLOCKED = "blocked"  # robots.txt, 403/429, anti-bot challenge, circuit open
    TIMEOUT = "timeout"
    ADAPTER_ERROR = "adapter_error"  # broken adapter / unexpected response
    NEEDS_LLM = "needs_llm"  # deterministic extraction failed and no LLM fallback available
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self not in {TargetStatus.PENDING, TargetStatus.RUNNING}

    @property
    def is_failure(self) -> bool:
        return self in FAILURE_STATES

    @property
    def is_legitimate_outcome(self) -> bool:
        return self in LEGITIMATE_STATES


LEGITIMATE_STATES = frozenset(
    {TargetStatus.FOUND, TargetStatus.NOT_FOUND, TargetStatus.UNAVAILABLE, TargetStatus.NO_PRICE}
)
FAILURE_STATES = frozenset(
    {TargetStatus.BLOCKED, TargetStatus.TIMEOUT, TargetStatus.ADAPTER_ERROR, TargetStatus.NEEDS_LLM}
)


class ExtractionMethod(StrEnum):
    API = "api"
    JSON_LD = "json_ld"
    EMBEDDED_STATE = "embedded_state"
    DOM = "dom"
    LLM = "llm"


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class PriceKind(StrEnum):
    REGULAR = "regular"
    PROMO = "promo"
    CLUB = "club"
    QUANTITY = "quantity"


class ReviewStatus(StrEnum):
    OK = "ok"
    FLAGGED = "flagged"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class PinDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class ImageSource(StrEnum):
    SEED = "seed"
    UPLOAD = "upload"
    URL = "url"


class LlmKind(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"


class ScheduleFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


def sql_in(values: type[StrEnum]) -> str:
    """Render an ``IN (...)`` list for CHECK constraints."""
    return "(" + ", ".join(f"'{v.value}'" for v in values) + ")"
