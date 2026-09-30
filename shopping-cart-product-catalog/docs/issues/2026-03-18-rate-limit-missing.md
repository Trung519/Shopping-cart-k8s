# Issue: Product Catalog Has No Rate Limiting

**Date:** 2026-03-18
**Status:** Open

## Problem

The product catalog (Python/FastAPI) has no rate limiting. It is a public-read
service — product listings are browsable without authentication. This makes it
the most exposed entry point for volumetric attacks: a bot can enumerate all
products and hammer the PostgreSQL read path without any throttling.

## Fix: Add slowapi rate limiting

`slowapi` is the standard FastAPI rate limiting library (wraps `limits`).
Supports Redis backend for cluster-wide enforcement.

### 1. Add dependencies

```toml
# pyproject.toml
slowapi>=0.1.9
redis>=5.0.0
```

### 2. Add rate limiter to `main.py`

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

REDIS_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL,
    default_limits=["100/minute", "20/second"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 3. Apply to routes in `routers/products.py`

```python
from fastapi import Request
from main import limiter  # reuse Redis-backed limiter configured in main.py

@router.get("/products")
@limiter.limit("60/minute")          # list — generous, read-only
async def list_products(request: Request, ...):
    ...

@router.get("/products/{product_id}")
@limiter.limit("120/minute")         # single product — high read volume expected
async def get_product(request: Request, ...):
    ...

@router.post("/products")
@limiter.limit("10/minute")          # write — admin only, strict
async def create_product(request: Request, ...):
    ...
```

### 4. Health endpoint exemption

Health routes in `routers/health.py` do not need rate limiting — leave them undecorated.

### 5. 429 response format

`slowapi` default returns plain text. Override to return JSON consistent with other services:

```python
from fastapi.responses import JSONResponse

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests", "message": str(exc.detail)},
        headers={"Retry-After": str(exc.retry_after)},
    )

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

## Definition of Done

- [ ] `slowapi` and `redis` added to dependencies
- [ ] `Limiter` configured with Redis backend (`REDIS_HOST` / `REDIS_PORT`)
- [ ] Rate limits applied to all product routes (list, get, create, update, delete)
- [ ] Health routes excluded
- [ ] 429 response is JSON with `Retry-After` header
- [ ] Unit tests: limit triggers after N requests; health endpoint bypasses limit
- [ ] No changes to Dockerfiles or database code (k8s manifests will need REDIS_HOST/REDIS_PORT added to configmap)

## What NOT to Do

- Do NOT use in-memory storage — must be Redis-backed for cluster-wide enforcement
- Do NOT rate limit the health endpoints
- Do NOT change database models or authentication logic
