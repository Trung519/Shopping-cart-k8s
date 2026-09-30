"""Event definitions for Product Catalog service.

These events match the schemas defined in shopping-cart-infra/docs/message-schemas.md
"""

from datetime import datetime
from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class EventEnvelope(BaseModel, Generic[T]):
    """Common envelope format for all events."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "product-catalog"
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        alias="correlationId",
    )
    data: T

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat() + "Z"}

    def model_dump_json_for_rabbitmq(self) -> str:
        """Serialize to JSON string for RabbitMQ publishing."""
        return self.model_dump_json(by_alias=True)


class InventoryUpdatedData(BaseModel):
    """Data payload for inventory.updated event."""

    product_id: str = Field(alias="productId")
    sku: str
    previous_quantity: int = Field(alias="previousQuantity")
    new_quantity: int = Field(alias="newQuantity")
    change: int
    reason: str

    class Config:
        populate_by_name = True


class InventoryLowData(BaseModel):
    """Data payload for inventory.low event."""

    product_id: str = Field(alias="productId")
    sku: str
    current_quantity: int = Field(alias="currentQuantity")
    threshold: int
    product_name: str = Field(alias="productName")

    class Config:
        populate_by_name = True


class InventoryReservedData(BaseModel):
    """Data payload for inventory.reserved event."""

    reservation_id: str = Field(alias="reservationId")
    product_id: str = Field(alias="productId")
    quantity: int
    order_id: str = Field(alias="orderId")
    expires_at: datetime = Field(alias="expiresAt")

    class Config:
        populate_by_name = True


class InventoryUpdatedEvent:
    """Factory for inventory.updated events."""

    TYPE = "inventory.updated"
    VERSION = "1.0"

    @classmethod
    def create(
        cls,
        product_id: str,
        sku: str,
        previous_quantity: int,
        new_quantity: int,
        reason: str,
        correlation_id: str | None = None,
    ) -> EventEnvelope[InventoryUpdatedData]:
        """Create an inventory.updated event envelope."""
        data = InventoryUpdatedData(
            product_id=product_id,
            sku=sku,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            change=new_quantity - previous_quantity,
            reason=reason,
        )
        return EventEnvelope(
            type=cls.TYPE,
            version=cls.VERSION,
            data=data,
            correlation_id=correlation_id or str(uuid4()),
        )


class InventoryLowEvent:
    """Factory for inventory.low events."""

    TYPE = "inventory.low"
    VERSION = "1.0"
    DEFAULT_THRESHOLD = 10

    @classmethod
    def create(
        cls,
        product_id: str,
        sku: str,
        current_quantity: int,
        product_name: str,
        threshold: int = DEFAULT_THRESHOLD,
        correlation_id: str | None = None,
    ) -> EventEnvelope[InventoryLowData]:
        """Create an inventory.low event envelope."""
        data = InventoryLowData(
            product_id=product_id,
            sku=sku,
            current_quantity=current_quantity,
            threshold=threshold,
            product_name=product_name,
        )
        return EventEnvelope(
            type=cls.TYPE,
            version=cls.VERSION,
            data=data,
            correlation_id=correlation_id or str(uuid4()),
        )


class InventoryReservedEvent:
    """Factory for inventory.reserved events."""

    TYPE = "inventory.reserved"
    VERSION = "1.0"

    @classmethod
    def create(
        cls,
        reservation_id: str,
        product_id: str,
        quantity: int,
        order_id: str,
        expires_at: datetime,
        correlation_id: str | None = None,
    ) -> EventEnvelope[InventoryReservedData]:
        """Create an inventory.reserved event envelope."""
        data = InventoryReservedData(
            reservation_id=reservation_id,
            product_id=product_id,
            quantity=quantity,
            order_id=order_id,
            expires_at=expires_at,
        )
        return EventEnvelope(
            type=cls.TYPE,
            version=cls.VERSION,
            data=data,
            correlation_id=correlation_id or str(uuid4()),
        )
