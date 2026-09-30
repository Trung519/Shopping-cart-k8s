"""RabbitMQ consumer for order.created events."""

import json
import threading
import time

import pika
import structlog

from .config import get_settings
from .database import SessionLocal
from .models import ProcessedEvent

logger = structlog.get_logger(__name__)

EXCHANGE = "events"
QUEUE = "inventory.order-created"
ROUTING_KEY = "order.created"


class OrderCreatedConsumer:
    """Consumes each unique order.created event and records it durably before ACKing."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()
        self._connection: pika.BlockingConnection | None = None
        self._channel = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._run, name="order-created-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        if self._connection and self._connection.is_open and self._channel:
            self._connection.add_callback_threadsafe(self._channel.stop_consuming)
        if self._thread:
            self._thread.join(timeout=10)

    def _connection_parameters(self) -> pika.ConnectionParameters:
        return pika.ConnectionParameters(
            host=self._settings.rabbitmq_host,
            port=self._settings.rabbitmq_port,
            virtual_host=self._settings.rabbitmq_vhost,
            credentials=pika.PlainCredentials(
                self._settings.rabbitmq_username,
                self._settings.rabbitmq_password,
            ),
            connection_attempts=3,
            retry_delay=2,
            heartbeat=30,
        )

    def _run(self) -> None:
        while not self._stop_requested.is_set():
            try:
                self._connection = pika.BlockingConnection(self._connection_parameters())
                self._channel = self._connection.channel()
                self._channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
                self._channel.queue_declare(queue=QUEUE, durable=True)
                self._channel.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=ROUTING_KEY)
                self._channel.basic_qos(prefetch_count=10)
                self._channel.basic_consume(queue=QUEUE, on_message_callback=self._handle_message, auto_ack=False)
                logger.info("rabbitmq_consumer_started", queue=QUEUE, routing_key=ROUTING_KEY)
                self._channel.start_consuming()
            except Exception as exc:
                if not self._stop_requested.is_set():
                    logger.error("rabbitmq_consumer_connection_failed", queue=QUEUE, error=str(exc))
                    time.sleep(5)
            finally:
                if self._connection and self._connection.is_open:
                    self._connection.close()
                self._connection = None
                self._channel = None

    def _handle_message(self, channel, method, _properties, body: bytes) -> None:
        try:
            event = json.loads(body.decode("utf-8"))
            event_id = str(event["id"])
            event_type = str(event["type"])
            if event_type != ROUTING_KEY:
                raise ValueError(f"unexpected event type {event_type!r}")

            with SessionLocal() as session:
                already_processed = session.get(ProcessedEvent, event_id)
                if already_processed:
                    logger.info("rabbitmq_event_duplicate", event_id=event_id, event_type=event_type)
                else:
                    session.add(
                        ProcessedEvent(
                            event_id=event_id,
                            event_type=event_type,
                            source=event.get("source"),
                            payload=json.dumps(event, separators=(",", ":")),
                        )
                    )
                    session.commit()
                    logger.info(
                        "order_created_event_processed",
                        event_id=event_id,
                        order_id=event.get("data", {}).get("orderId"),
                    )

            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            logger.error("order_created_event_failed", error=str(exc))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
