from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Site(Base):
    __tablename__ = "sites"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    base_url: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    observations: Mapped[List["Observation"]] = relationship(back_populates="site")

class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String)
    brand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    observations: Mapped[List["Observation"]] = relationship(back_populates="product")
    query_configs: Mapped[List["ProductSiteQuery"]] = relationship(back_populates="product")

class ProductSiteQuery(Base):
    __tablename__ = "product_site_queries"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    query_text: Mapped[str] = mapped_column(String)
    constraints_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    product: Mapped["Product"] = relationship(back_populates="query_configs")

class Run(Base):
    __tablename__ = "runs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String) # running, success, failed, partial
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    observations: Mapped[List["Observation"]] = relationship(back_populates="run")

class Observation(Base):
    __tablename__ = "observations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    site_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    canonical_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="BRL")
    
    unit_price: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    promo_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    promo_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    availability: Mapped[str] = mapped_column(String) # in_stock, out_of_stock, unknown
    title: Mapped[str] = mapped_column(String)
    product_url: Mapped[str] = mapped_column(String)
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    fetch_type: Mapped[Optional[str]] = mapped_column(String, nullable=True) # deterministic, llm
    raw_json: Mapped[dict] = mapped_column(JSON)
    
    run: Mapped["Run"] = relationship(back_populates="observations")
    product: Mapped["Product"] = relationship(back_populates="observations")
    site: Mapped["Site"] = relationship(back_populates="observations")
