from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pricetracker.db.base import (
    Base,
    JSONType,
    Quantity,
    TimestampMixin,
    UTCDateTime,
    new_uuid,
    utcnow,
)
from pricetracker.models.enums import ImageSource, PinDecision, SoldBy, Unit, sql_in


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (CheckConstraint(f"source IN {sql_in(ImageSource)}", name="source"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(40))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    attribution: Mapped[str | None] = mapped_column(String(300), nullable=True)
    license: Mapped[str | None] = mapped_column(String(80), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CatalogItem(TimestampMixin, Base):
    """Global, admin-curated starting catalog."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        CheckConstraint(f"sold_by IN {sql_in(SoldBy)}", name="sold_by"),
        CheckConstraint(f"default_unit IN {sql_in(Unit)}", name="default_unit"),
        CheckConstraint("default_quantity > 0", name="default_quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sold_by: Mapped[str] = mapped_column(String(16))
    package_quantity: Mapped[Decimal | None] = mapped_column(Quantity(), nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    default_quantity: Mapped[Decimal] = mapped_column(Quantity(), default=Decimal("1"))
    default_unit: Mapped[str] = mapped_column(String(8), default=Unit.UN.value)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)
    match_spec: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    image: Mapped[Image | None] = relationship()


class Product(TimestampMixin, Base):
    """A product a user tracks, either derived from the catalog or custom."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("user_id", "catalog_item_id"),
        CheckConstraint(f"sold_by IN {sql_in(SoldBy)}", name="sold_by"),
        CheckConstraint("size_tolerance_pct >= 0 AND size_tolerance_pct <= 100", name="tolerance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    sold_by: Mapped[str] = mapped_column(String(16))
    package_quantity: Mapped[Decimal | None] = mapped_column(Quantity(), nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    preferred_brand: Mapped[str | None] = mapped_column(String(80), nullable=True)
    strict_brand: Mapped[bool] = mapped_column(Boolean, default=False)
    size_tolerance_pct: Mapped[Decimal] = mapped_column(Quantity(), default=Decimal("0"))
    substitutions: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    match_spec: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    catalog_item: Mapped[CatalogItem | None] = relationship()
    image: Mapped[Image | None] = relationship()


class ProductMarketPin(Base):
    """User-confirmed identity (accept) or exclusion (reject) of a market listing."""

    __tablename__ = "product_market_pins"
    __table_args__ = (
        UniqueConstraint("product_id", "market_id", "listing_key"),
        CheckConstraint(f"decision IN {sql_in(PinDecision)}", name="decision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    market_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    listing_key: Mapped[str] = mapped_column(String(200))  # external id / sku / url path
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    decision: Mapped[str] = mapped_column(String(8), default=PinDecision.ACCEPT.value)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ShoppingList(TimestampMixin, Base):
    __tablename__ = "shopping_lists"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    items: Mapped[list[ListItem]] = relationship(
        back_populates="shopping_list",
        cascade="all, delete-orphan",
        order_by="ListItem.position",
    )


class ListItem(TimestampMixin, Base):
    __tablename__ = "list_items"
    __table_args__ = (
        UniqueConstraint("list_id", "product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(f"unit IN {sql_in(Unit)}", name="unit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[Decimal] = mapped_column(Quantity(), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(8), default=Unit.UN.value)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    shopping_list: Mapped[ShoppingList] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
