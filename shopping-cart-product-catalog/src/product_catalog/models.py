"""SQLAlchemy models for Product Catalog."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class Category(Base):
    """Admin-managed product taxonomy entry."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(100), unique=True, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base):
    """Product entity."""

    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="VND")
    quantity = Column(Numeric(10, 0), nullable=False, default=0)
    category = Column(String(100), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    image_url = Column(String(500), nullable=True)
    seller_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name})>"


class ProcessedEvent(Base):
    """Durable idempotency record for RabbitMQ events handled by this service."""

    __tablename__ = "processed_events"

    event_id = Column(String(100), primary_key=True)
    event_type = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=True)
    payload = Column(Text, nullable=False)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
