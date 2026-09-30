# Shopping Cart Product Catalog Service

A Python/FastAPI service that manages product data, inventory adjustments, and publishes RabbitMQ events consumed by other Shopping Cart microservices. It persists catalog data in PostgreSQL and exposes REST APIs for CRUD/search flows.

---

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- RabbitMQ 3.12+

### Install & Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,rabbitmq]"

# Run development server
uvicorn product_catalog.main:app --reload --host 0.0.0.0 --port 8000

# Optional: start Docker Compose backing services
docker-compose up -d
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | products | Database name |
| `DB_USERNAME` | postgres | Database username |
| `DB_PASSWORD` | postgres | Database password |
| `RABBITMQ_HOST` | localhost | RabbitMQ host |
| `RABBITMQ_PORT` | 5672 | RabbitMQ port |
| `VAULT_ENABLED` | false | Enable Vault integration |
| `VAULT_ADDR` | http://localhost:8200 | Vault address |
| `VAULT_ROLE` | product-publisher | Vault role for RabbitMQ |

---

## Usage

### Architecture

```mermaid
graph TD
    GW[API Gateway] --> RT[FastAPI Routers]
    subgraph PCS[Product Catalog Service]
        RT --> SVC[Service Logic]
        SVC --> REPO[Repository]
        SVC --> EP[Event Publisher]
        REPO --> PG[(PostgreSQL)]
    end
    EP --> MQ[RabbitMQ]
```

### Event Publishing
| Event | Routing Key | Description |
|-------|-------------|-------------|
| `inventory.updated` | `inventory.updated` | Inventory quantity changed |
| `inventory.low` | `inventory.low` | Stock below threshold |
| `inventory.reserved` | `inventory.reserved` | Stock reserved for order |

### API Examples
```bash
# List products
GET /api/products?page=1&page_size=20&category=electronics&active_only=true

# Get by ID
GET /api/products/{product_id}

# Create product
POST /api/products

# Update inventory
POST /api/products/{product_id}/inventory
```

### Health & Metrics
| Endpoint | Description |
|----------|-------------|
| `/health` | Health check with database status |
| `/ready` | Kubernetes readiness probe |
| `/live` | Kubernetes liveness probe |
| `/metrics` | Prometheus metrics |

### Development Commands
```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# Coverage
pytest --cov=product_catalog --cov-report=term-missing

# Formatting & linting
black src tests && isort src tests && mypy src && ruff check src tests
```

---

## Architecture
See **[Service Architecture](docs/architecture/README.md)** for detailed component diagrams, data model, and RabbitMQ integration.

---

## Directory Layout
```
shopping-cart-product-catalog/
├── src/product_catalog/
│   ├── config.py      # Settings management
│   ├── database.py    # SQLAlchemy engine/session
│   ├── events.py      # RabbitMQ event payloads
│   ├── main.py        # FastAPI app entrypoint
│   ├── models.py      # SQLAlchemy models
│   ├── routers/       # FastAPI routers
│   └── schemas.py     # Pydantic schemas
├── tests/             # Unit/integration tests
├── docs/              # Architecture/API/testing/troubleshooting
├── pyproject.toml
└── Dockerfile, Makefile, etc.
```

---

## Documentation

### Architecture
- **[Service Architecture](docs/architecture/README.md)** — System design, data flow, security considerations.

### API Reference
- **[API Reference](docs/api/README.md)** — Endpoint payloads, filtering options, and error responses.

### Testing
- **[Testing Guide](docs/testing/README.md)** — Pytest/mypy/ruff/pip-audit commands.

### Troubleshooting
- **[Troubleshooting Guide](docs/troubleshooting/README.md)** — Database connectivity, RabbitMQ auth, env var tips.

### Issue Logs
- No logged issues yet — add Markdown files under `docs/issues/` as they arise.

---

## Releases

| Version | Date | Highlights |
|---------|------|------------|
| v0.1.0 | TBD | Initial FastAPI catalog service with PostgreSQL + RabbitMQ events |

---

## Related
- [Platform Architecture](https://github.com/wilddog64/shopping-cart-infra/blob/main/docs/architecture.md)
- [shopping-cart-infra](https://github.com/wilddog64/shopping-cart-infra)
- [shopping-cart-order](https://github.com/wilddog64/shopping-cart-order)
- [shopping-cart-payment](https://github.com/wilddog64/shopping-cart-payment)
- [shopping-cart-basket](https://github.com/wilddog64/shopping-cart-basket)

---

## License
Apache 2.0
