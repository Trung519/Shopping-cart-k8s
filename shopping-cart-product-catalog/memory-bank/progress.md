# Progress: Product Catalog Service

## What's Built

### Core Application
- [x] `Product` SQLAlchemy model with all fields: id (UUID), sku (unique, indexed), name, description, price (Numeric 10,2), currency, quantity, category (indexed), is_active, image_url, created_at, updated_at
- [x] `Settings` pydantic-settings class with all env var mappings and `database_url` property
- [x] `get_settings()` singleton via `@lru_cache`
- [x] `database.py` — SQLAlchemy engine, `SessionLocal`, `init_db()` for table creation
- [x] `events.py` — RabbitMQ event classes with common envelope (InventoryUpdatedEvent, InventoryLowEvent, InventoryReservedEvent)
- [x] `messaging.py` — RabbitMQ publisher
- [x] `auth.py` — OAuth2/OIDC JWT validation with Keycloak JWKS and caching
- [x] `security.py` — `setup_security(app)` adding rate limiting and security headers middleware
- [x] `main.py` — FastAPI app with lifespan, security setup, Prometheus mount, router includes
- [x] `routers/products.py` — product CRUD endpoints (list, get by ID, get by SKU, create, update, delete/soft-delete, inventory update)
- [x] `routers/health.py` — /health, /ready, /live endpoints
- [x] `schemas.py` — Pydantic request/response schemas

### Tests
- [x] `tests/unit/test_auth.py` — authentication unit tests
- [x] `tests/unit/test_auth_integration.py` — auth integration tests
- [x] `tests/unit/test_security.py` — security configuration tests
- [x] `tests/unit/test_security_middleware.py` — security middleware tests
- [x] `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`

### Infrastructure & Operations
- [x] `pyproject.toml` — full package config, dependencies, tool configuration (black, isort, mypy, ruff, pytest)
- [x] `Makefile` — comprehensive targets: venv, install, run, test, lint, format, typecheck, docker, k8s, ArgoCD, Alembic, OpenAPI export, security scan
- [x] `Dockerfile` — multi-stage build
- [x] `Dockerfile.local` — local development variant
- [x] `k8s/base/deployment.yaml`
- [x] `k8s/base/service.yaml` — ClusterIP port 8000
- [x] `k8s/base/configmap.yaml`
- [x] `k8s/base/serviceaccount.yaml`
- [x] `k8s/base/secret.yaml`
- [x] `k8s/base/namespace.yaml`
- [x] `k8s/base/hpa.yaml`
- [x] `k8s/base/kustomization.yaml`
- [x] `.gitignore`

### Documentation
- [x] `CLAUDE.md` — AI assistant guidance
- [x] `README.md` — setup and usage guide
- [x] `docs/README.md`
- [x] `docs/api/README.md`
- [x] `docs/architecture/README.md`
- [x] `docs/troubleshooting/README.md`

## What's Pending / Known Gaps

- [ ] **Integration tests** — `tests/integration/` directory exists but no test files implemented; integration tests against real PostgreSQL (Testcontainers) are pending
- [ ] **Alembic initialization** — Alembic is a dependency and Makefile has migration targets, but no `alembic/` directory visible; currently relying on `create_all()` in `init_db()` (development-only approach)
- [ ] **Pydantic schemas** — `schemas.py` exists but content not deeply explored; full CRUD schema set may be partially implemented
- [ ] **Category hierarchy** — architecture docs reference Category entity and `CategoryService`; current implementation uses a flat `category: String` field in Product; full category tree is not implemented
- [ ] **Search functionality** — architecture docs reference search/filtering; only basic category filter and pagination visible in API docs
- [x] **GitHub Actions CI/CD** — `.github/workflows/ci.yml` exists and now pins `build-push-deploy.yml@999f8d7` for linux/amd64+linux/arm64 builds (2026-03-17)
- [ ] **Load/performance testing**
- [ ] **Full mypy strict compliance** — `mypy src/` should pass with strict mode; may have remaining type annotation gaps
- [ ] **RabbitMQ consumer** — service publishes `inventory.*` events but there is no visible consumer setup for `order.*` events that might trigger inventory reservation

## API Endpoints Summary

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | `/api/products` | Optional | Implemented |
| GET | `/api/products/{id}` | Optional | Implemented |
| GET | `/api/products/sku/{sku}` | Optional | Implemented |
| POST | `/api/products` | Required | Implemented |
| PATCH | `/api/products/{id}` | Required | Implemented |
| DELETE | `/api/products/{id}` | Required | Implemented (soft delete) |
| POST | `/api/products/{id}/inventory` | Required | Implemented |
| GET | `/health` | Public | Implemented |
| GET | `/ready` | Public | Implemented |
| GET | `/live` | Public | Implemented |
| GET | `/metrics` | Public | Implemented (Prometheus) |

## Events Published Summary

| Routing Key | Trigger | Status |
|---|---|---|
| `inventory.updated` | Inventory quantity change | Implemented (events.py) |
| `inventory.low` | Stock drops below threshold | Implemented (events.py) |
| `inventory.reserved` | Stock reserved for order | Implemented (events.py) |

## Query Parameters for List Endpoint

| Parameter | Type | Default | Description |
|---|---|---|---|
| page | int | 1 | Page number |
| page_size | int | 20 | Items per page |
| category | string | — | Filter by category |
| active_only | bool | true | Filter to active products only |
