# Tech Context: Product Catalog Service

## Language & Runtime

- **Python 3.11+** (also supports 3.12)
- Package name: `shopping-cart-product-catalog` version `1.0.0`
- Entry point: `product-catalog` CLI script → `product_catalog.main:main`
- Source layout: `src/` layout (`src/product_catalog/`)

## Core Dependencies (pyproject.toml)

| Package | Version | Purpose |
|---|---|---|
| fastapi | >=0.109.0 | Web framework |
| uvicorn[standard] | >=0.27.0 | ASGI server |
| sqlalchemy | >=2.0.25 | ORM (synchronous) |
| psycopg2-binary | >=2.9.9 | PostgreSQL driver |
| alembic | >=1.13.1 | Database migrations |
| pydantic | >=2.5.3 | Data validation |
| pydantic-settings | >=2.1.0 | Environment-based config |
| prometheus-client | >=0.19.0 | Prometheus metrics |
| structlog | >=24.1.0 | Structured logging |
| httpx | >=0.26.0 | HTTP client (for JWKS fetch) |
| python-jose[cryptography] | >=3.3.0 | JWT validation |

## Optional Dependencies

### `.[rabbitmq]`
| Package | Version | Purpose |
|---|---|---|
| pika | >=1.3.2 | RabbitMQ AMQP client |
| hvac | >=2.1.0 | HashiCorp Vault client |
| tenacity | >=8.2.3 | Retry logic for connections |

### `.[dev]`
| Package | Version | Purpose |
|---|---|---|
| pytest | >=7.4.4 | Test runner |
| pytest-asyncio | >=0.23.3 | Async test support |
| pytest-cov | >=4.1.0 | Coverage reporting |
| black | >=24.1.0 | Code formatter (line-length 100) |
| isort | >=5.13.2 | Import sorter (black profile) |
| mypy | >=1.8.0 | Static type checker (strict) |
| ruff | >=0.1.13 | Fast linter |
| testcontainers | >=3.7.1 | Container-based integration tests |

## Code Quality Configuration (pyproject.toml)

```toml
[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## Infrastructure Dependencies

| Service | Required | Default | Purpose |
|---|---|---|---|
| PostgreSQL 15+ | Yes | localhost:5432/products | Product persistence |
| RabbitMQ 3.12+ | Optional | localhost:5672 | Inventory event publishing |
| Keycloak | Optional | — | JWT issuer / JWKS |
| HashiCorp Vault | Optional | localhost:8200 | Dynamic RabbitMQ credentials |

## Development Environment Setup

### Prerequisites

- Python 3.11 or 3.12
- PostgreSQL 15+ running (local or Docker)
- pip / venv

### Local Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# Install all dependencies including dev and RabbitMQ
pip install -e ".[dev,rabbitmq]"

# Optional: local RabbitMQ client library
pip install -e "../rabbitmq-client-library/python"

# Start PostgreSQL via Docker
docker run -d -p 5432:5432 -e POSTGRES_DB=products -e POSTGRES_PASSWORD=postgres postgres:15

# Set up database
export DB_PASSWORD=postgres
alembic upgrade head  # or make db-migrate

# Run development server with auto-reload
uvicorn product_catalog.main:app --reload --host 0.0.0.0 --port 8000
# or:
make run-dev
```

### Environment Variables

```
ENVIRONMENT=development
DEBUG=false
HOST=0.0.0.0
PORT=8000
DB_HOST=localhost
DB_PORT=5432
DB_NAME=products
DB_USERNAME=postgres
DB_PASSWORD=postgres
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_VHOST=/
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_USE_TLS=false
VAULT_ENABLED=false
VAULT_ADDR=http://localhost:8200
VAULT_ROLE=product-publisher
VAULT_RABBITMQ_PATH=rabbitmq
OAUTH2_ENABLED=false
OAUTH2_ISSUER_URI=http://keycloak.identity.svc.cluster.local/realms/shopping-cart
OAUTH2_CLIENT_ID=product-catalog
OAUTH2_CLIENT_SECRET=
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_SECOND=20
RATE_LIMIT_BURST=50
```

Supports `.env` file in project root.

## Build & Deployment Tooling

- **Makefile** — primary developer interface; `make help` for all targets; includes ArgoCD, K8s, Gunicorn, Alembic, OpenAPI export, pipdeptree, bandit security scan
- **pyproject.toml** — PEP 517/518 compliant build config; setuptools backend
- **Dockerfile** — multi-stage build
- **Dockerfile.local** — local development variant

## Database Migrations

Managed with **Alembic** (`alembic upgrade head`). Migration files go in `alembic/` directory (referenced in architecture docs but actual alembic directory not visible in file listing — may need initialization: `alembic init alembic`).

## Testing Infrastructure

- Unit tests: `tests/unit/` — mock database and external services
- Integration tests: `tests/integration/` — may use testcontainers for real PostgreSQL
- asyncio_mode = "auto" — all tests can use async/await natively
- Coverage threshold not configured but `make test-cov` generates HTML report

## Kubernetes & GitOps

- Manifests in `k8s/base/` with Kustomize
- Resources: deployment.yaml, service.yaml (port 8000), configmap.yaml, serviceaccount.yaml, secret.yaml, namespace.yaml, hpa.yaml, kustomization.yaml
- Namespace: `shopping-cart-apps`
- ArgoCD application name: `product-catalog`
- Production server: Gunicorn + UvicornWorker (4 workers): `make prod-gunicorn`
