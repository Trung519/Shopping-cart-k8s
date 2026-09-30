# System Patterns: Product Catalog Service

## Architectural Pattern: FastAPI with Modular Routers

```
HTTP Client
    │
    ▼ (security middleware: rate limit + headers)
┌─────────────────────────────────────────────────┐
│  FastAPI Application (main.py)                   │
│  - Lifespan: init_db() on startup               │
│  - Prometheus ASGI mounted at /metrics          │
│  - Routers: /api/products, /health, /ready, /live│
└────────────────────────┬────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
    products.router  health.router  metrics_app
              │
              ▼ (optional JWT auth dependency)
    ┌─────────────────┐
    │  Route Handler   │
    │  (Pydantic in,  │
    │   Pydantic out) │
    └────────┬────────┘
             │
             ▼
    SQLAlchemy Session
    (database.py)
             │
             ▼
        PostgreSQL
             │
    Separately:
    events.py → messaging.py → RabbitMQ
```

## Domain Model

### Product (SQLAlchemy model, `models.py`)
```python
class Product(Base):
    __tablename__ = "products"

    id = Column(UUID, primary_key=True, default=uuid4)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    quantity = Column(Numeric(10, 0), nullable=False, default=0)
    category = Column(String(100), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
```

Indexes: `sku` (unique), `category`, `is_active` (via SQLAlchemy `index=True`)

### Pydantic Schemas (`schemas.py`)
Separate request and response schemas using Pydantic 2.x:
- `ProductCreate` — for POST /api/products
- `ProductUpdate` — for PATCH /api/products/{id} (all fields optional)
- `ProductResponse` — for GET responses
- `InventoryUpdateRequest` — for POST /api/products/{id}/inventory

## Configuration Pattern

Using pydantic-settings `BaseSettings` with environment variable aliases:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = Field(default="localhost", alias="DB_HOST")
    # ...

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`get_settings()` cached with `@lru_cache` — single Settings instance per process.

## Application Lifecycle (Lifespan)

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    init_db()   # creates tables if they don't exist (SQLAlchemy create_all)
    yield
    # Shutdown (cleanup if needed)
```

## Event Publishing Pattern

Events published to RabbitMQ with common envelope format (same as all platform services):

```python
event = InventoryUpdatedEvent.create(
    product_id=str(product.id),
    sku=product.sku,
    previous_quantity=100,
    new_quantity=95,
    reason="Order fulfillment",
)
publisher.publish("events", "inventory.updated", event.model_dump_json_for_rabbitmq())
```

Event types and routing keys:
- `inventory.updated` — quantity changed
- `inventory.low` — stock dropped below threshold
- `inventory.reserved` — stock reserved for an order

Event envelope format:
```json
{
  "id": "uuid",
  "type": "inventory.updated",
  "version": "1.0",
  "timestamp": "ISO8601",
  "source": "product-catalog",
  "correlationId": "uuid",
  "data": { "productId": "...", "sku": "...", "previousQuantity": 100, "newQuantity": 95, "reason": "..." }
}
```

## Security Architecture

### SecurityConfig (`security.py`)
- `setup_security(app)` called in main.py
- Adds rate limiting middleware
- Adds security headers: X-Content-Type-Options: nosniff, X-Frame-Options: DENY, X-XSS-Protection: 1; mode=block, Content-Security-Policy: default-src 'self'

### Auth (`auth.py`)
- JWT validation via Keycloak JWKS (5-minute JWKS cache)
- `OAUTH2_ENABLED=false` → no auth required (dev mode)
- `OAUTH2_ENABLED=true` → Bearer token required; roles from JWT claims
- FastAPI dependency injection for auth: route handlers declare `Depends(get_current_user)` or similar

### Roles (from architecture docs)
- `catalog-user` — read products
- `catalog-admin` — full CRUD
- `platform-admin` — full access + admin operations

## Soft Delete Pattern

Products are never hard-deleted:
```python
# DELETE /api/products/{id} → sets is_active = False
product.is_active = False
session.commit()
```

List endpoint default: `active_only=True` filters out inactive products.
Inactive products still accessible by ID (for historical order references).

## Database Session Pattern

SQLAlchemy synchronous sessions via dependency injection in FastAPI:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    ...
```

## Observability

- **Logging**: structlog JSON output; `logger.info("event_name", key=value, ...)` — event-centric naming (not string messages)
- **Metrics**: Prometheus ASGI app mounted at `/metrics`; counter/histogram for request tracking
- **Health endpoints**: `/health` (full status with DB check), `/ready` (K8s readiness), `/live` (K8s liveness)
- **Structured startup logs**: `logger.info("starting_application", environment=settings.environment)`, `logger.info("database_initialized")`

## Kubernetes Deployment

- Namespace: `shopping-cart-apps`
- ArgoCD application: `product-catalog`
- Service port: 8000
- Has HPA (k8s/base/hpa.yaml)
- Production: Gunicorn + UvicornWorker for multi-process serving (`make prod-gunicorn`)
  ```bash
  gunicorn product_catalog.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
  ```

## Note on Architecture Documentation vs Implementation

The `docs/architecture/README.md` describes a more elaborate structure with separate `services/`, `repositories/`, and `models/` subdirectories with `CategoryService`, `ProductService`, etc. The actual implemented source in `src/product_catalog/` is a flatter structure with a single `models.py` (one `Product` model), `schemas.py`, `routers/`, and top-level modules. When adding new code, follow the **implemented** flat structure, not the architecture doc aspirational layout, unless explicitly expanding to that structure.
