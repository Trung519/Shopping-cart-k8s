# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**Shopping Cart Product Catalog Service** is a FastAPI microservice that manages the product catalog for the shopping cart platform. It publishes inventory events to RabbitMQ for event-driven communication with other services.

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL 15+ (SQLAlchemy 2.0)
- **Messaging**: RabbitMQ (via rabbitmq-client-library)
- **Validation**: Pydantic 2.x
- **Testing**: pytest, pytest-asyncio

## Key Patterns

### Event-Driven Architecture

Inventory changes publish events to RabbitMQ:
- `inventory.updated` - Quantity changed
- `inventory.low` - Stock below threshold
- `inventory.reserved` - Stock reserved for order

Events use a common envelope format defined in `events.py`:
```python
{
    "id": "uuid",
    "type": "inventory.updated",
    "version": "1.0",
    "timestamp": "2025-01-01T00:00:00Z",
    "source": "product-catalog",
    "correlationId": "uuid",
    "data": { ... }
}
```

### Domain Models

- `Product` - Main entity with SKU, name, price, quantity
- Soft deletes via `is_active` flag
- UUID primary keys

## Directory Structure

```
src/product_catalog/
├── __init__.py         # Package version
├── config.py           # Pydantic settings
├── database.py         # SQLAlchemy session
├── events.py           # RabbitMQ event classes
├── main.py             # FastAPI app
├── models.py           # SQLAlchemy models
├── schemas.py          # Pydantic request/response
└── routers/
    ├── health.py       # Health endpoints
    └── products.py     # Product CRUD
```

## Common Development Tasks

### Setup

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,rabbitmq]"
```

### Run

```bash
# Development with auto-reload
uvicorn product_catalog.main:app --reload

# Or via entry point
python -m product_catalog.main
```

### Testing

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit -v

# With coverage
pytest --cov=product_catalog
```

### Code Quality

```bash
black src tests          # Format
isort src tests          # Sort imports
mypy src                 # Type check
ruff check src tests     # Lint
```

## Configuration

All config via environment variables or `.env` file. See `config.py` for full list.

Key settings:
- `DB_*` - PostgreSQL connection
- `RABBITMQ_*` - RabbitMQ connection
- `VAULT_*` - Vault credentials (optional)

## Dependencies

### RabbitMQ Client Library

Uses `rabbitmq-client-library` for RabbitMQ integration. Install with:
```bash
pip install -e ".[rabbitmq]"
```

Or install from local path:
```bash
pip install -e ../rabbitmq-client-library/python
```

## Event Publishing

Example of publishing an inventory event:

```python
from product_catalog.events import InventoryUpdatedEvent

# Create event
event = InventoryUpdatedEvent.create(
    product_id=str(product.id),
    sku=product.sku,
    previous_quantity=100,
    new_quantity=95,
    reason="Order fulfillment",
)

# Publish to RabbitMQ
publisher.publish("events", "inventory.updated", event.model_dump_json_for_rabbitmq())
```

## Related Documentation

- [Message Schemas](../shopping-cart-infra/docs/message-schemas.md) - Event contracts
- [RabbitMQ Operations](../shopping-cart-infra/docs/rabbitmq-operations.md) - Queue management
- [rabbitmq-client-library](../rabbitmq-client-library/README.md) - Client library docs

## Troubleshooting

### Database Connection Issues

```bash
# Verify PostgreSQL is accessible
psql -h localhost -U postgres -d products -c "SELECT 1"

# Check Docker container
docker ps | grep postgres
```

### RabbitMQ Connection Issues

```bash
# Check RabbitMQ is running (Kubernetes)
kubectl get pods -n shopping-cart-data -l app=rabbitmq

# Test local connection
curl -u "$RABBITMQ_USERNAME:$RABBITMQ_PASSWORD" http://localhost:15672/api/overview
```

## Code Style

- Follow PEP 8 and use type hints everywhere
- Use Pydantic for all data validation
- Prefer async where appropriate
- Log structured data with structlog
- Never log credentials

## Agent Instructions

Rules that apply to ALL agents (Codex, Claude, Gemini) working in this repo:

1. **CI only** — do NOT run `pytest`, `mypy`, or `ruff` locally without first activating the virtualenv. Use `gh run list` to verify results.
2. **Memory-bank discipline** — do NOT update `memory-bank/activeContext.md` until `gh run list --repo wilddog64/shopping-cart-product-catalog` shows `completed success`.
3. **SHA verification** — always verify commit SHA with `gh api repos/wilddog64/shopping-cart-product-catalog/commits/<sha>` before reporting.
4. **Do NOT merge PRs** — open the PR and stop. The repo owner merges.
5. **No unsolicited changes** — only touch files listed in the task spec. Flat structure is intentional — do not refactor to services/repositories/models.
