# Message Schemas & Event Contracts

This document defines the message schemas and event contracts for the shopping cart platform's message queue system.

## Table of Contents

1. [Overview](#overview)
2. [Exchange & Queue Design](#exchange--queue-design)
3. [Event Schemas](#event-schemas)
4. [Message Format](#message-format)
5. [Error Handling](#error-handling)
6. [Versioning Strategy](#versioning-strategy)

---

## Overview

### Design Principles

1. **Schema-first** - Define contracts before implementation
2. **Backward compatible** - New fields are optional, old fields never removed
3. **Self-describing** - Messages include type, version, and metadata
4. **Idempotent** - Consumers can safely process the same message twice

### Message Flow Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Product        │     │     Order       │     │     Cart        │
│  Catalog        │     │    Service      │     │    Service      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    [inventory.*]           [order.*]              [cart.*]
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │   RabbitMQ Exchange     │
                    │   (topic: events)       │
                    └─────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Notification   │     │    Payment      │     │   Analytics     │
│    Service      │     │    Service      │     │    Service      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Exchange & Queue Design

### Exchanges

| Exchange | Type | Purpose | Durability |
|----------|------|---------|------------|
| `events` | topic | Main event bus for all domain events | durable |
| `commands` | direct | Point-to-point command messages | durable |
| `dlx` | fanout | Dead letter exchange for failed messages | durable |

### Queues

| Queue | Routing Key | Consumer | Purpose |
|-------|-------------|----------|---------|
| `order.created` | `order.created` | Payment Service | Process new orders |
| `order.paid` | `order.paid` | Fulfillment Service | Ship paid orders |
| `order.completed` | `order.completed` | Notification, Analytics | Post-order actions |
| `order.cancelled` | `order.cancelled` | Inventory, Refund | Handle cancellations |
| `inventory.updated` | `inventory.*` | Cache, Search | Sync inventory changes |
| `inventory.low` | `inventory.low` | Procurement | Restock alerts |
| `cart.abandoned` | `cart.abandoned` | Notification | Recovery emails |
| `notification.email` | `notification.email` | Email Service | Send emails |
| `notification.push` | `notification.push` | Push Service | Send push notifications |
| `dead-letters` | `#` (from dlx) | Error Handler | Failed message review |

### Routing Key Conventions

```
<domain>.<event>.<optional-qualifier>

Examples:
  order.created
  order.paid
  order.cancelled.refund-requested
  inventory.updated.product-123
  inventory.low
  cart.abandoned
  notification.email.order-confirmation
```

---

## Event Schemas

### Common Envelope

All messages use this envelope format:

```json
{
  "id": "uuid-v4",
  "type": "order.created",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "order-service",
  "correlationId": "uuid-v4",
  "data": { ... }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string (UUID) | Yes | Unique message identifier |
| `type` | string | Yes | Event type (routing key) |
| `version` | string | Yes | Schema version (semver) |
| `timestamp` | string (ISO8601) | Yes | When event occurred |
| `source` | string | Yes | Service that produced the event |
| `correlationId` | string (UUID) | No | For request tracing |
| `data` | object | Yes | Event-specific payload |

---

### Order Events

#### order.created (v1.0)

Published when a new order is placed.

```json
{
  "id": "msg-uuid",
  "type": "order.created",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "order-service",
  "correlationId": "request-uuid",
  "data": {
    "orderId": "ORD-123456",
    "customerId": "CUST-789",
    "customerEmail": "customer@example.com",
    "items": [
      {
        "productId": "PROD-001",
        "productName": "Widget",
        "quantity": 2,
        "unitPrice": 29.99,
        "totalPrice": 59.98
      }
    ],
    "subtotal": 59.98,
    "tax": 5.40,
    "shipping": 5.00,
    "total": 70.38,
    "currency": "USD",
    "shippingAddress": {
      "name": "John Doe",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "zipCode": "12345",
      "country": "US"
    },
    "billingAddress": {
      "name": "John Doe",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "zipCode": "12345",
      "country": "US"
    },
    "paymentMethod": "credit_card",
    "createdAt": "2025-12-27T12:00:00.000Z"
  }
}
```

**Consumers:**
- Payment Service - Initiates payment processing
- Inventory Service - Reserves stock
- Notification Service - Sends order confirmation email

---

#### order.paid (v1.0)

Published when payment is successfully processed.

```json
{
  "id": "msg-uuid",
  "type": "order.paid",
  "version": "1.0",
  "timestamp": "2025-12-27T12:05:00.000Z",
  "source": "payment-service",
  "correlationId": "request-uuid",
  "data": {
    "orderId": "ORD-123456",
    "customerId": "CUST-789",
    "paymentId": "PAY-456789",
    "amount": 70.38,
    "currency": "USD",
    "paymentMethod": "credit_card",
    "cardLast4": "4242",
    "paidAt": "2025-12-27T12:05:00.000Z"
  }
}
```

**Consumers:**
- Fulfillment Service - Begins shipping process
- Notification Service - Sends payment receipt

---

#### order.shipped (v1.0)

Published when order is shipped.

```json
{
  "id": "msg-uuid",
  "type": "order.shipped",
  "version": "1.0",
  "timestamp": "2025-12-27T14:00:00.000Z",
  "source": "fulfillment-service",
  "correlationId": "request-uuid",
  "data": {
    "orderId": "ORD-123456",
    "customerId": "CUST-789",
    "trackingNumber": "1Z999AA10123456784",
    "carrier": "UPS",
    "estimatedDelivery": "2025-12-30",
    "shippedAt": "2025-12-27T14:00:00.000Z"
  }
}
```

**Consumers:**
- Notification Service - Sends shipping notification with tracking

---

#### order.completed (v1.0)

Published when order is delivered.

```json
{
  "id": "msg-uuid",
  "type": "order.completed",
  "version": "1.0",
  "timestamp": "2025-12-30T10:00:00.000Z",
  "source": "fulfillment-service",
  "correlationId": "request-uuid",
  "data": {
    "orderId": "ORD-123456",
    "customerId": "CUST-789",
    "deliveredAt": "2025-12-30T10:00:00.000Z"
  }
}
```

**Consumers:**
- Notification Service - Sends delivery confirmation, requests review
- Analytics Service - Records completed order metrics

---

#### order.cancelled (v1.0)

Published when order is cancelled.

```json
{
  "id": "msg-uuid",
  "type": "order.cancelled",
  "version": "1.0",
  "timestamp": "2025-12-27T13:00:00.000Z",
  "source": "order-service",
  "correlationId": "request-uuid",
  "data": {
    "orderId": "ORD-123456",
    "customerId": "CUST-789",
    "reason": "customer_requested",
    "refundAmount": 70.38,
    "cancelledAt": "2025-12-27T13:00:00.000Z"
  }
}
```

**Reason values:** `customer_requested`, `payment_failed`, `out_of_stock`, `fraud_suspected`, `other`

**Consumers:**
- Inventory Service - Releases reserved stock
- Payment Service - Initiates refund
- Notification Service - Sends cancellation email

---

### Inventory Events

#### inventory.updated (v1.0)

Published when product inventory changes.

```json
{
  "id": "msg-uuid",
  "type": "inventory.updated",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "product-catalog",
  "data": {
    "productId": "PROD-001",
    "productName": "Widget",
    "previousQuantity": 100,
    "newQuantity": 98,
    "changeAmount": -2,
    "reason": "order_placed",
    "referenceId": "ORD-123456"
  }
}
```

**Reason values:** `order_placed`, `order_cancelled`, `restock`, `adjustment`, `return`

**Consumers:**
- Cache Service - Invalidates product cache
- Search Service - Updates search index

---

#### inventory.low (v1.0)

Published when product stock falls below threshold.

```json
{
  "id": "msg-uuid",
  "type": "inventory.low",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "product-catalog",
  "data": {
    "productId": "PROD-001",
    "productName": "Widget",
    "currentQuantity": 5,
    "threshold": 10,
    "reorderQuantity": 100
  }
}
```

**Consumers:**
- Procurement Service - Triggers reorder
- Notification Service - Alerts inventory manager

---

#### inventory.reserved (v1.0)

Published when stock is reserved for an order.

```json
{
  "id": "msg-uuid",
  "type": "inventory.reserved",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "product-catalog",
  "data": {
    "orderId": "ORD-123456",
    "reservations": [
      {
        "productId": "PROD-001",
        "quantity": 2,
        "reservedUntil": "2025-12-27T12:30:00.000Z"
      }
    ]
  }
}
```

---

### Cart Events

#### cart.abandoned (v1.0)

Published when a cart is abandoned (no activity for 1 hour with items).

```json
{
  "id": "msg-uuid",
  "type": "cart.abandoned",
  "version": "1.0",
  "timestamp": "2025-12-27T13:00:00.000Z",
  "source": "cart-service",
  "data": {
    "cartId": "CART-123",
    "customerId": "CUST-789",
    "customerEmail": "customer@example.com",
    "items": [
      {
        "productId": "PROD-001",
        "productName": "Widget",
        "quantity": 2,
        "unitPrice": 29.99
      }
    ],
    "subtotal": 59.98,
    "lastActivityAt": "2025-12-27T12:00:00.000Z",
    "abandonedAt": "2025-12-27T13:00:00.000Z"
  }
}
```

**Consumers:**
- Notification Service - Sends cart recovery email

---

#### cart.item.added (v1.0)

Published when item is added to cart.

```json
{
  "id": "msg-uuid",
  "type": "cart.item.added",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "cart-service",
  "data": {
    "cartId": "CART-123",
    "customerId": "CUST-789",
    "productId": "PROD-001",
    "productName": "Widget",
    "quantity": 2,
    "unitPrice": 29.99
  }
}
```

**Consumers:**
- Analytics Service - Tracks add-to-cart events
- Recommendation Service - Updates recommendations

---

### Notification Events

#### notification.email (v1.0)

Command message to send an email.

```json
{
  "id": "msg-uuid",
  "type": "notification.email",
  "version": "1.0",
  "timestamp": "2025-12-27T12:00:00.000Z",
  "source": "order-service",
  "correlationId": "request-uuid",
  "data": {
    "to": "customer@example.com",
    "template": "order_confirmation",
    "subject": "Order Confirmation - ORD-123456",
    "variables": {
      "customerName": "John Doe",
      "orderId": "ORD-123456",
      "orderTotal": "$70.38",
      "items": [...]
    },
    "priority": "high"
  }
}
```

**Template values:** `order_confirmation`, `payment_receipt`, `shipping_notification`, `delivery_confirmation`, `cart_abandoned`, `password_reset`

---

## Message Format

### Content Type

All messages use JSON format:
- Content-Type: `application/json`
- Encoding: UTF-8

### Message Properties

| Property | Value | Description |
|----------|-------|-------------|
| `content_type` | `application/json` | Message format |
| `delivery_mode` | `2` (persistent) | Survive broker restart |
| `message_id` | UUID | Unique message ID |
| `timestamp` | Unix timestamp | When published |
| `type` | Event type | e.g., `order.created` |
| `app_id` | Service name | e.g., `order-service` |
| `correlation_id` | UUID | Request tracing |

### Headers

| Header | Type | Description |
|--------|------|-------------|
| `x-version` | string | Schema version |
| `x-retry-count` | integer | Number of retry attempts |
| `x-original-exchange` | string | For DLQ messages |
| `x-original-routing-key` | string | For DLQ messages |
| `x-death` | array | Automatic death history |

---

## Error Handling

### Dead Letter Queue (DLQ)

Messages are routed to DLQ when:
1. Consumer explicitly rejects (nack without requeue)
2. Message TTL expires
3. Queue length limit exceeded
4. Maximum retry attempts exceeded

### DLQ Message Format

Original message is preserved with additional headers:

```json
{
  "x-death": [
    {
      "count": 3,
      "reason": "rejected",
      "queue": "order.created",
      "exchange": "events",
      "routing-keys": ["order.created"],
      "time": "2025-12-27T12:00:00.000Z"
    }
  ],
  "x-first-death-reason": "rejected",
  "x-first-death-queue": "order.created",
  "x-first-death-exchange": "events"
}
```

### Retry Strategy

| Attempt | Delay | Action |
|---------|-------|--------|
| 1 | Immediate | Retry |
| 2 | 1 second | Retry |
| 3 | 5 seconds | Retry |
| 4 | 30 seconds | Retry |
| 5 | - | Route to DLQ |

---

## Versioning Strategy

### Semantic Versioning

Schema versions follow semver: `MAJOR.MINOR`

- **MAJOR**: Breaking changes (removed fields, changed types)
- **MINOR**: Backward compatible (new optional fields)

### Compatibility Rules

1. **Adding fields**: Always optional, with defaults
2. **Removing fields**: Never (deprecate instead)
3. **Changing types**: Never (add new field instead)
4. **Renaming fields**: Never (add alias instead)

### Migration Example

**v1.0 → v1.1**: Add optional `metadata` field

```json
// v1.0
{
  "type": "order.created",
  "version": "1.0",
  "data": {
    "orderId": "ORD-123"
  }
}

// v1.1 (backward compatible)
{
  "type": "order.created",
  "version": "1.1",
  "data": {
    "orderId": "ORD-123",
    "metadata": {           // New optional field
      "source": "web",
      "campaign": "holiday-sale"
    }
  }
}
```

### Consumer Compatibility

Consumers should:
1. Ignore unknown fields
2. Handle missing optional fields with defaults
3. Log warning for unknown event versions
4. Process older versions without error

---

## Service Integration

### Publishing Events

```python
# Python example
publisher.publish(
    exchange="events",
    routing_key="order.created",
    message={
        "id": str(uuid.uuid4()),
        "type": "order.created",
        "version": "1.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "order-service",
        "correlationId": request_id,
        "data": order_data
    }
)
```

### Consuming Events

```python
# Python example
@consumer.subscribe("order.created")
def handle_order_created(message):
    event = message.body

    # Validate version
    if event["version"] not in ["1.0", "1.1"]:
        logger.warning(f"Unknown version: {event['version']}")

    # Process event
    order_id = event["data"]["orderId"]
    process_payment(order_id)

    # Acknowledge
    message.ack()
```

---

## Repository Structure

Services will be in separate repositories:

```
shopping-cart-order/          # Order Service (Java)
├── src/main/java/
│   └── com/shoppingcart/order/
│       ├── events/           # Event DTOs matching schemas
│       │   ├── OrderCreatedEvent.java
│       │   ├── OrderPaidEvent.java
│       │   └── ...
│       ├── publishers/       # Event publishers
│       └── consumers/        # Event consumers
└── ...

shopping-cart-product-catalog/ # Product Catalog (Python)
├── src/
│   └── product_catalog/
│       ├── events/           # Event dataclasses
│       │   ├── inventory_updated.py
│       │   └── ...
│       ├── publishers/
│       └── consumers/
└── ...
```

---

**Last Updated**: 2025-12-27
**Owner**: Platform Team
