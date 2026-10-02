from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pricetracker.db.base import (
    Base,
    BigIntPK,
    JSONType,
    Money,
    Quantity,
    UnitPrice,
    UTCDateTime,
    new_uuid,
    utcnow,
)
from pricetracker.models.enums import (
    Availability,
    ReviewStatus,
    RunStatus,
    RunTrigger,
    TargetStatus,
    sql_in,
)


class Run(Base):
    """A collection job. The ``runs`` table doubles as the durable job queue."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(f"status IN {sql_in(RunStatus)}", name="status"),
        CheckConstraint(f"trigger IN {sql_in(RunTrigger)}", name="trigger"),
        Index("ix_runs_status_created_at", "status", "created_at"),
        Index("ix_runs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    list_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="SET NULL"), nullable=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(16), default=RunTrigger.MANUAL.value)
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.QUEUED.value)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    total_targets: Mapped[int] = mapped_column(Integer, default=0)
    done_targets: Mapped[int] = mapped_column(Integer, default=0)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    targets: Mapped[list[RunTarget]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class RunTarget(Base):
    """One (product, store) unit of work inside a run."""

    __tablename__ = "run_targets"
    __table_args__ = (
        UniqueConstraint("run_id", "product_id", "store_id"),
        CheckConstraint(f"status IN {sql_in(TargetStatus)}", name="status"),
        Index("ix_run_targets_run_id_status", "run_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default=TargetStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    search_query: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    run: Mapped[Run] = relationship(back_populates="targets")
    candidates: Mapped[list[Candidate]] = relationship(
        back_populates="target",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Candidate.rank",
    )


class OfferFieldsMixin:
    title: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    package_quantity: Mapped[Decimal | None] = mapped_column(Quantity(), nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sold_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    regular_price: Mapped[Decimal | None] = mapped_column(Money(), nullable=True)
    promo_price: Mapped[Decimal | None] = mapped_column(Money(), nullable=True)
    club_price: Mapped[Decimal | None] = mapped_column(Money(), nullable=True)
    club_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_price: Mapped[Decimal | None] = mapped_column(UnitPrice(), nullable=True)
    quantity_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extra_prices: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    unit_price: Mapped[Decimal | None] = mapped_column(UnitPrice(), nullable=True)
    unit_price_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    availability: Mapped[str] = mapped_column(String(16), default=Availability.UNKNOWN.value)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    method: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("1"))


class Candidate(OfferFieldsMixin, Base):
    """A listing collected for a target, with the deterministic match decision."""

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("run_targets.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer, default=0)
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 3), default=Decimal("0"))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    chosen: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    target: Mapped[RunTarget] = relationship(back_populates="candidates")


class Observation(OfferFieldsMixin, Base):
    """A price observation (offer) chosen for a user's product at a store."""

    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(f"review_status IN {sql_in(ReviewStatus)}", name="review_status"),
        Index(
            "ix_observations_user_product_store_observed",
            "user_id",
            "product_id",
            "store_id",
            "observed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("run_targets.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    adapter_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 3), default=Decimal("0"))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    raw_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    outlier_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), default=ReviewStatus.OK.value)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RunEvent(Base):
    """Timeline of a run (progress, retries, diagnostics) for the UI and audits."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("run_targets.id", ondelete="CASCADE"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(8), default="info")
    event: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
