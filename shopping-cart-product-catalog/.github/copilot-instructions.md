# Copilot Instructions — Product Catalog Service

## Service Overview

Python 3.11+ FastAPI microservice managing the product catalog.
PostgreSQL (SQLAlchemy 2.0), RabbitMQ for inventory events, Pydantic v2 validation.

---

## Architecture Guardrails

### Layer Boundaries — Never Cross These
- **Router** (`routers/`): HTTP request/response, input validation only — no DB calls
- **Service logic**: business rules, inventory management — no raw SQL
- **Database layer** (`models.py`, SQLAlchemy): data access only — no business logic
- A router must never call SQLAlchemy models directly. Always through the service/CRUD layer.

### Inventory Rules — Non-Negotiable
- Quantity can never go below zero — validate before any update
- Inventory reservation must be idempotent: same `correlationId` must not reduce stock twice
- Soft deletes only (`is_active = False`) — never hard-delete product records
- Price and quantity updates must publish the corresponding RabbitMQ event

### RabbitMQ Ownership
- This service publishes: `inventory.updated`, `inventory.low`, `inventory.reserved`
- This service does NOT consume queues from other services
- Always use the common `EventEnvelope` format from `events.py` — never publish raw dicts
- `correlationId` must be set on every published event

### Service Isolation
- This service owns the `products` database — no other service connects to it directly
- Never call another service's REST API from this service — use events
- Never import from another service's codebase

---

## Security Rules (treat violations as bugs)

### Secrets (OWASP A02)
- All DB credentials and RabbitMQ passwords come from environment variables (ESO/Vault)
- Never hardcode credentials or connection strings
- Never log credential values — not even partially
- `VAULT_TOKEN` must never appear in source code, logs, or test fixtures

### Injection (OWASP A03)
- Never build SQL by string formatting — always use SQLAlchemy ORM or parameterized queries
- Never pass raw user input to `eval()` or `exec()`
- Validate all inputs with Pydantic schemas before passing to the DB layer

### Access Control (OWASP A01)
- Product reads are public — no auth required
- Product writes (create, update, delete) require admin role
- Never allow quantity or price manipulation via public endpoints

### Cryptographic Failures (OWASP A02)
- Never disable SSL on PostgreSQL or RabbitMQ connections in non-test code

---

## Code Quality Rules

### Testing
- All new route and business logic requires pytest unit tests
- Never delete or comment out existing tests
- Never weaken an assertion
- Run `pytest` before every commit; must pass clean
- Use `pytest --cov=product_catalog` to verify coverage is not reduced

### Code Style
- Type hints everywhere — no untyped function signatures
- Pydantic v2 for all request/response schemas — never raw dicts in route handlers
- Prefer `async` for route handlers and DB operations
- Use `structlog` for structured logging — never `print()` in production paths
- `black`, `isort`, `ruff`, `mypy` must all pass clean

### Dependencies
- Never add a dependency without justification in the PR description
- Use `pyproject.toml` for all dependency declarations — no `requirements.txt` patches
- Pin all dependency versions

---

## Completion Report Requirements

Before marking any task complete, the agent must provide:
- `pytest` output (must be clean)
- `mypy src` output (must be clean)
- `ruff check src tests` output (must be clean)
- Confirmation that inventory quantity never goes below zero in any code path
- Confirmation that no credential appears in any changed file
- Confirmation that no test was deleted or weakened
- List of exact files modified

---

## What NOT To Do

- Do not hard-delete product records — soft delete only
- Do not add new RabbitMQ event types without updating `shopping-cart-infra` message schemas
- Do not add synchronous REST calls to other services
- Do not bypass Pydantic validation with raw dict access
- Do not use `float` for price or quantity — use `Decimal`
