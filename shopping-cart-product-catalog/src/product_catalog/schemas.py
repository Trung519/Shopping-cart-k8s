"""Pydantic schemas for API request/response models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    """Base product schema."""

    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="VND", min_length=3, max_length=3)
    quantity: int = Field(default=0, ge=0)
    category: str | None = Field(default=None, max_length=100)
    image_url: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter ISO code")
        return normalized

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.strip()
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("image_url must use http or https")
        return normalized


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    quantity: int | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    image_url: str | None = Field(default=None, max_length=500)


class ProductResponse(ProductBase):
    """Schema for product response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seller_id: UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InventoryUpdate(BaseModel):
    """Schema for inventory adjustment."""

    quantity_change: int = Field(..., description="Positive to add, negative to subtract")
    reason: str = Field(..., min_length=1, max_length=200)


class InventoryBatchItem(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0, le=9999)


class InventoryBatchRequest(BaseModel):
    operation: str = Field(..., pattern="^(reserve|release)$")
    items: list[InventoryBatchItem] = Field(..., min_length=1, max_length=100)


class CategoryCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=80, pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(..., min_length=2, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=1000)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int
