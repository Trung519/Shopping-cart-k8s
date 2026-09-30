# Product Catalog Service Troubleshooting Guide

## Common Issues

### Connection Issues

#### Database Connection Failed

**Symptoms:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection refused
```

**Causes:**
- PostgreSQL not running
- Incorrect DATABASE_URL
- Network connectivity issues
- Connection pool exhausted

**Solutions:**

1. Verify PostgreSQL is running:
   ```bash
   kubectl get pods -n shopping-cart -l app=postgresql
   ```

2. Check connection string:
   ```bash
   kubectl get secret product-catalog-secrets -o jsonpath='{.data.DATABASE_URL}' | base64 -d
   ```

3. Test connectivity from pod:
   ```bash
   kubectl exec -it product-catalog-xxx -- python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"
   ```

4. Check pool settings:
   ```python
   # config.py
   database_pool_size: int = 10
   database_max_overflow: int = 20
   ```

#### RabbitMQ Connection Failed

**Symptoms:**
```
pika.exceptions.AMQPConnectionError: Connection refused
```

**Solutions:**

1. Check RabbitMQ service:
   ```bash
   kubectl get svc -n rabbitmq
   ```

2. Verify Vault credentials:
   ```bash
   vault read rabbitmq/creds/product-catalog
   ```

3. Test connectivity:
   ```bash
   kubectl exec -it product-catalog-xxx -- nc -zv rabbitmq 5672
   ```

### Authentication Issues

#### 401 Unauthorized

**Symptoms:**
```json
{
  "detail": "Authentication required"
}
```

**Causes:**
- Missing Authorization header
- Expired JWT token
- Invalid token signature
- JWKS fetch failed

**Solutions:**

1. Check if OAuth2 is enabled:
   ```bash
   kubectl get configmap product-catalog-config -o yaml | grep OAUTH2_ENABLED
   ```

2. Verify token format:
   ```bash
   # Token should be: Bearer <jwt>
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/products
   ```

3. Check token expiration:
   ```python
   import jwt
   decoded = jwt.decode(token, options={"verify_signature": False})
   print(f"Expires: {decoded['exp']}")
   ```

4. Verify Keycloak JWKS is accessible:
   ```bash
   curl -s "$OAUTH2_ISSUER_URI/protocol/openid-connect/certs"
   ```

5. Check logs for JWKS errors:
   ```bash
   kubectl logs product-catalog-xxx | grep -i jwks
   ```

#### 403 Forbidden

**Symptoms:**
```json
{
  "detail": "Catalog admin access required"
}
```

**Causes:**
- User lacks required role
- Wrong role claim location in JWT

**Solutions:**

1. Check user roles:
   ```python
   import jwt
   decoded = jwt.decode(token, options={"verify_signature": False})
   print(decoded.get("realm_access", {}).get("roles", []))
   print(decoded.get("groups", []))
   ```

2. Verify role requirements in router:
   ```python
   # Check Depends(require_catalog_admin) or Depends(require_role(...))
   ```

3. Add role in Keycloak:
   - Navigate to Users → Select User → Role Mappings
   - Add `catalog-admin` role

### Data Issues

#### Product Not Found

**Symptoms:**
```json
{
  "detail": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Product with ID xxx not found"
  }
}
```

**Solutions:**

1. Verify product exists:
   ```sql
   SELECT * FROM products WHERE id = 'xxx';
   ```

2. Check if product is soft-deleted:
   ```sql
   SELECT * FROM products WHERE id = 'xxx' AND deleted_at IS NULL;
   ```

#### Duplicate SKU Error

**Symptoms:**
```json
{
  "detail": {
    "code": "DUPLICATE_SKU",
    "message": "SKU already exists"
  }
}
```

**Solutions:**

1. Find existing product with SKU:
   ```sql
   SELECT id, name, sku FROM products WHERE sku = 'xxx';
   ```

2. Use a unique SKU or update existing product

#### Category Deletion Failed

**Symptoms:**
```json
{
  "detail": {
    "code": "CATEGORY_HAS_PRODUCTS",
    "message": "Cannot delete category with products"
  }
}
```

**Solutions:**

1. Check products in category:
   ```sql
   SELECT COUNT(*) FROM products WHERE category_id = 'xxx';
   ```

2. Move products to different category first:
   ```sql
   UPDATE products SET category_id = 'new-category-id' WHERE category_id = 'xxx';
   ```

### Performance Issues

#### Slow Response Times

**Symptoms:**
- API latency > 500ms
- Request timeouts

**Diagnosis:**

1. Enable SQL query logging:
   ```python
   # config.py
   database_echo: bool = True
   ```

2. Check slow queries:
   ```sql
   SELECT query, calls, mean_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

3. Check connection pool:
   ```bash
   curl http://localhost:8000/metrics | grep pool
   ```

**Solutions:**

1. Add database indexes:
   ```sql
   CREATE INDEX idx_products_category ON products(category_id);
   CREATE INDEX idx_products_sku ON products(sku);
   CREATE INDEX idx_products_active ON products(is_active);
   ```

2. Increase connection pool size:
   ```python
   database_pool_size: int = 20
   ```

3. Add caching for frequently accessed data

#### High Memory Usage

**Symptoms:**
- OOMKilled pods
- Memory growing over time

**Solutions:**

1. Check memory usage:
   ```bash
   kubectl top pod product-catalog-xxx
   ```

2. Profile memory:
   ```python
   import tracemalloc
   tracemalloc.start()
   # ... run code ...
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')
   ```

3. Adjust worker settings:
   ```bash
   # In Dockerfile or deployment
   uvicorn main:app --workers 2 --limit-max-requests 1000
   ```

### Startup Issues

#### Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'product_catalog'
```

**Solutions:**

1. Check PYTHONPATH:
   ```bash
   echo $PYTHONPATH
   # Should include /app/src
   ```

2. Verify package structure:
   ```bash
   ls -la src/product_catalog/
   # Should have __init__.py
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

#### Database Migration Errors

**Symptoms:**
```
alembic.util.exc.CommandError: Target database is not up to date
```

**Solutions:**

1. Check current migration:
   ```bash
   alembic current
   ```

2. Run pending migrations:
   ```bash
   alembic upgrade head
   ```

3. Check migration history:
   ```bash
   alembic history
   ```

## Logging

### Configure Log Level

```python
# config.py or environment
LOG_LEVEL=DEBUG
```

```python
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

### Useful Log Patterns

```bash
# Authentication errors
kubectl logs product-catalog-xxx | grep -i "auth\|jwt\|token"

# Database queries
kubectl logs product-catalog-xxx | grep -i "sql\|query"

# All errors
kubectl logs product-catalog-xxx | grep -E "(ERROR|CRITICAL)"
```

### Log Format

Structured JSON logging:
```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "error",
  "logger": "product_catalog.auth",
  "message": "JWT verification failed",
  "error": "Token expired",
  "request_id": "abc-123"
}
```

## Health Checks

### Verify Service Health

```bash
# Health endpoint
curl http://localhost:8000/health

# Readiness
curl http://localhost:8000/ready

# Liveness (basic)
curl http://localhost:8000/
```

### Check Dependencies

```python
# health.py returns:
{
  "status": "healthy",
  "checks": {
    "database": "ok",      # or "error: connection failed"
    "rabbitmq": "ok"       # or "error: connection refused"
  }
}
```

## Metrics

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `http_requests_total` | Request count | - |
| `http_request_duration_seconds` | Latency | p99 > 1s |
| `db_pool_connections` | DB connections | > 80% |
| `products_total` | Product count | - |

### Prometheus Queries

```promql
# Request rate
rate(http_requests_total{app="product-catalog"}[5m])

# Error rate
rate(http_requests_total{app="product-catalog",status=~"5.."}[5m])

# P99 latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{app="product-catalog"}[5m]))
```

## Testing

### Run Tests Locally

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires Docker)
pytest tests/integration -v

# With coverage
pytest --cov=product_catalog --cov-report=html
```

### Test Authentication

```python
# Create test token
from tests.unit.test_auth_integration import create_test_token

token = create_test_token(
    username="testuser",
    roles=["catalog-admin"]
)
```

## Environment Variables

Required variables for debugging:

```bash
# Enable debug mode
export LOG_LEVEL=DEBUG
export DATABASE_ECHO=true

# Disable OAuth2 for local testing
export OAUTH2_ENABLED=false
```

## Support

For issues not covered here:
1. Check application logs with DEBUG level
2. Review [Architecture docs](../architecture/README.md)
3. Check [API docs](../api/README.md) for correct usage
4. Open an issue in GitHub repository
