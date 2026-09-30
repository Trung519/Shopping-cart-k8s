"""RabbitMQ messaging integration for Product Catalog service."""

from functools import lru_cache
import json
import ssl
from typing import Optional

import pika
import structlog

from .config import get_settings
from .events import (
    InventoryLowEvent,
    InventoryUpdatedEvent,
)

logger = structlog.get_logger(__name__)

EVENTS_EXCHANGE = "events"
LOW_STOCK_THRESHOLD = 10


class PikaPublisher:
    """Small adapter around pika so service code publishes through AMQP directly."""

    def __init__(self, connection: pika.BlockingConnection):
        self._connection = connection
        self._channel = connection.channel()
        # With mandatory publishing, this makes an unroutable event fail loudly instead of disappearing.
        self._channel.confirm_delivery()

    def declare_exchange(self, exchange: str, exchange_type: str, durable: bool) -> None:
        self._channel.exchange_declare(exchange=exchange, exchange_type=exchange_type, durable=durable)

    def publish(self, exchange: str, routing_key: str, body: dict) -> bool:
        self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(body, default=str),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            mandatory=True,
        )
        return True


class ProductEventPublisher:
    """Publisher for product catalog events."""

    def __init__(self, publisher: Optional[PikaPublisher] = None):
        """Initialize the event publisher.

        Args:
            publisher: RabbitMQ publisher instance. If None, publishing is disabled.
        """
        self._publisher = publisher

        if self._publisher:
            logger.info("product_event_publisher_initialized")
        else:
            logger.warning("product_event_publisher_disabled", reason="no_publisher")

    @property
    def enabled(self) -> bool:
        """Check if publishing is enabled."""
        return self._publisher is not None

    def publish_inventory_updated(
        self,
        product_id: str,
        sku: str,
        previous_quantity: int,
        new_quantity: int,
        reason: str,
        correlation_id: str | None = None,
    ) -> bool:
        """Publish an inventory.updated event.

        Args:
            product_id: Product UUID
            sku: Product SKU
            previous_quantity: Previous inventory quantity
            new_quantity: New inventory quantity
            reason: Reason for the change

        Returns:
            True if published successfully, False otherwise.
        """
        publisher = self._publisher
        if not publisher:
            logger.debug("publish_skipped", event="inventory.updated", reason="disabled")
            return False

        event = InventoryUpdatedEvent.create(
            product_id=product_id,
            sku=sku,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            reason=reason,
            correlation_id=correlation_id,
        )

        try:
            result = publisher.publish(
                exchange=EVENTS_EXCHANGE,
                routing_key=InventoryUpdatedEvent.TYPE,
                body=event.model_dump(mode="json", by_alias=True),
            )

            logger.info(
                "event_published",
                event_type=InventoryUpdatedEvent.TYPE,
                product_id=product_id,
                correlation_id=event.correlation_id,
            )

            # Check if we should also publish a low stock warning
            if new_quantity <= LOW_STOCK_THRESHOLD and new_quantity < previous_quantity:
                self._publish_inventory_low(product_id, sku, new_quantity, event.correlation_id)

            return result

        except Exception as e:
            logger.error(
                "event_publish_failed",
                event_type=InventoryUpdatedEvent.TYPE,
                product_id=product_id,
                error=str(e),
            )
            return False

    def _publish_inventory_low(
        self,
        product_id: str,
        sku: str,
        current_quantity: int,
        correlation_id: str,
    ) -> bool:
        """Publish an inventory.low event (internal)."""
        publisher = self._publisher
        if not publisher:
            return False

        # Note: We'd need product_name here - in real implementation would fetch it
        event = InventoryLowEvent.create(
            product_id=product_id,
            sku=sku,
            current_quantity=current_quantity,
            product_name=f"Product {sku}",  # Would typically fetch from DB
            threshold=LOW_STOCK_THRESHOLD,
            correlation_id=correlation_id,
        )

        try:
            result = publisher.publish(
                exchange=EVENTS_EXCHANGE,
                routing_key=InventoryLowEvent.TYPE,
                body=event.model_dump(mode="json", by_alias=True),
            )

            logger.warning(
                "low_stock_alert",
                event_type=InventoryLowEvent.TYPE,
                product_id=product_id,
                sku=sku,
                quantity=current_quantity,
            )

            return result

        except Exception as e:
            logger.error(
                "event_publish_failed",
                event_type=InventoryLowEvent.TYPE,
                product_id=product_id,
                error=str(e),
            )
            return False


def create_publisher() -> Optional[PikaPublisher]:
    """Create a RabbitMQ publisher.

    Returns:
        Publisher instance if connection successful, None otherwise.
    """
    settings = get_settings()

    try:
        if settings.vault_enabled:
            raise RuntimeError("VAULT_ENABLED requires a Vault credential provider; use static RabbitMQ credentials until it is configured")

        ssl_options = pika.SSLOptions(ssl.create_default_context()) if settings.rabbitmq_use_tls else None
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                virtual_host=settings.rabbitmq_vhost,
                credentials=pika.PlainCredentials(settings.rabbitmq_username, settings.rabbitmq_password),
                ssl_options=ssl_options,
                connection_attempts=3,
                retry_delay=2,
            )
        )
        publisher = PikaPublisher(connection)

        # Ensure events exchange exists
        publisher.declare_exchange(EVENTS_EXCHANGE, exchange_type="topic", durable=True)

        logger.info("rabbitmq_publisher_created", host=settings.rabbitmq_host, port=settings.rabbitmq_port)

        return publisher

    except Exception as e:
        logger.error("rabbitmq_connection_failed", error=str(e))
        return None


@lru_cache
def get_event_publisher() -> ProductEventPublisher:
    """Get or create the product event publisher singleton."""
    publisher = create_publisher()
    return ProductEventPublisher(publisher)
