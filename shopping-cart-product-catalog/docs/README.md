# Product Catalog Service Documentation

Welcome to the Product Catalog Service documentation. This service manages product and category information for the Shopping Cart platform.

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture](architecture/README.md) | System design, components, and data model |
| [API Reference](api/README.md) | REST API endpoints and examples |
| [Troubleshooting](troubleshooting/README.md) | Common issues and debugging guide |

## Overview

The Product Catalog Service is a FastAPI microservice responsible for:
- Product CRUD operations
- Category hierarchy management
- Inventory tracking
- Publishing catalog events to RabbitMQ
- Integration with Keycloak for OAuth2/OIDC authentication

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- RabbitMQ 3.12+ (optional)
- Keycloak (optional, for OAuth2)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head
```

### Running Locally

```bash
# Development server
uvicorn product_catalog.main:app --reload --port 8000

# With OAuth2 enabled
OAUTH2_ENABLED=true \
OAUTH2_ISSUER_URI=http://keycloak:8080/realms/shopping-cart \
uvicorn product_catalog.main:app --reload
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit -v

# With coverage
pytest --cov=product_catalog --cov-report=html
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL URL | `postgresql://localhost/catalog` |
| `RABBITMQ_HOST` | RabbitMQ host | `localhost` |
| `OAUTH2_ENABLED` | Enable OAuth2 | `false` |
| `OAUTH2_ISSUER_URI` | Keycloak issuer | - |
| `LOG_LEVEL` | Logging level | `INFO` |

See [Architecture > Configuration](architecture/README.md#configuration) for full list.

## API Quick Reference

### Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/products` | List products |
| GET | `/api/v1/products/{id}` | Get product |
| POST | `/api/v1/products` | Create product |
| PUT | `/api/v1/products/{id}` | Update product |
| DELETE | `/api/v1/products/{id}` | Delete product |
| PATCH | `/api/v1/products/{id}/inventory` | Update inventory |

### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/categories` | List categories |
| GET | `/api/v1/categories/{id}` | Get category |
| POST | `/api/v1/categories` | Create category |
| PUT | `/api/v1/categories/{id}` | Update category |
| DELETE | `/api/v1/categories/{id}` | Delete category |

### Health & Docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

See [API Reference](api/README.md) for complete documentation.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Routers   │────▶│  Services   │────▶│Repositories │
│  (FastAPI)  │     │  (Logic)    │     │(SQLAlchemy) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Auth     │     │   Events    │     │  PostgreSQL │
│  (OAuth2)   │     │ (RabbitMQ)  │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

See [Architecture](architecture/README.md) for detailed design.

## Project Structure

```
src/product_catalog/
├── main.py           # FastAPI app entry
├── config.py         # Configuration
├── auth.py           # OAuth2/OIDC auth
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas
├── routers/          # API endpoints
├── services/         # Business logic
└── repositories/     # Data access
```

## Related Services

- **Order Service**: Order management
- **Keycloak**: Identity and access management
- **RabbitMQ**: Message broker for event publishing

## Support

- [Troubleshooting Guide](troubleshooting/README.md)
- [GitHub Issues](https://github.com/your-org/shopping-cart-product-catalog/issues)
