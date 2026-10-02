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
    Coordinate,
    JSONType,
    Money,
    TimestampMixin,
    UTCDateTime,
    new_uuid,
    utcnow,
)
from pricetracker.models.enums import Role, sql_in


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {sql_in(Role)}", name="role"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=Role.USER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    client_label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship()


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"
    __table_args__ = (UniqueConstraint("user_id", "code_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class LoginAttempt(Base):
    """Pseudonymised login attempts (HMAC of username and client address)."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_username_key_created_at", "username_key", "created_at"),
        Index("ix_login_attempts_client_key_created_at", "client_key", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    username_key: Mapped[str] = mapped_column(String(64))
    client_key: Mapped[str] = mapped_column(String(64))
    succeeded: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("freshness_days BETWEEN 1 AND 90", name="freshness_days"),
        CheckConstraint("max_stops BETWEEN 1 AND 4", name="max_stops"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    freshness_days: Mapped[int] = mapped_column(Integer, default=7)
    include_travel_cost: Mapped[bool] = mapped_column(Boolean, default=True)
    max_stops: Mapped[int] = mapped_column(Integer, default=2)
    use_club_prices: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class Address(TimestampMixin, Base):
    """Home address. Personal data: never logged, only returned to its owner."""

    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(60), default="Casa")
    postal_code: Mapped[str | None] = mapped_column(String(9), nullable=True)
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    complement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Coordinate(), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Coordinate(), nullable=True)
    geocode_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("km_per_liter > 0", name="km_per_liter_positive"),
        CheckConstraint("fuel_price_per_liter >= 0", name="fuel_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    fuel_type: Mapped[str] = mapped_column(String(16), default="gasolina")
    km_per_liter: Mapped[Decimal] = mapped_column(Numeric(6, 2, asdecimal=True))
    fuel_price_per_liter: Mapped[Decimal] = mapped_column(Numeric(8, 3, asdecimal=True))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)


class UserStoreSelection(TimestampMixin, Base):
    """Stores (branches) a user compares, with optional round-trip toll cost."""

    __tablename__ = "user_store_selections"
    __table_args__ = (
        UniqueConstraint("user_id", "store_id"),
        CheckConstraint("toll_round_trip >= 0", name="toll_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    toll_round_trip: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0"))
