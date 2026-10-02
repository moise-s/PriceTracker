from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pricetracker.db.base import (
    Base,
    Coordinate,
    JSONType,
    TimestampMixin,
    UTCDateTime,
    new_uuid,
    utcnow,
)


class Market(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    website: Mapped[str] = mapped_column(String(200))
    adapter_key: Mapped[str] = mapped_column(String(40))
    allowed_domains: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    brand_color: Mapped[str | None] = mapped_column(String(9), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    stores: Mapped[list[Store]] = relationship(back_populates="market", order_by="Store.name")


class Store(TimestampMixin, Base):
    """A physical branch (filial) and/or the online price region it maps to."""

    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("market_id", "slug"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("markets.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(9), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Coordinate(), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Coordinate(), nullable=True)
    price_context: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    price_scope_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(16), default="seed")

    market: Mapped[Market] = relationship(back_populates="stores")


class AdapterVersion(Base):
    """Provenance: which adapter version/strategy produced an observation."""

    __tablename__ = "adapter_versions"
    __table_args__ = (UniqueConstraint("market_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    adapter_key: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(40))
    strategy: Mapped[str] = mapped_column(String(80))
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
