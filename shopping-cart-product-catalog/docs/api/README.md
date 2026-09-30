# Product Catalog Service API Reference

## Base URL

```
http://localhost:8000/api/v1
```

In Kubernetes:
```
http://product-catalog.shopping-cart.svc.cluster.local/api/v1
```

## Authentication

When OAuth2 is enabled, protected endpoints require a valid JWT token:

```http
Authorization: Bearer <jwt-token>
```

## Endpoints

### Products

#### List Products

```http
GET /api/v1/products
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| category_id | uuid | No | Filter by category |
| is_active | bool | No | Filter by active status |
| search | string | No | Search in name/description |
| skip | int | No | Offset for pagination (default: 0) |
| limit | int | No | Max results (default: 20, max: 100) |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Premium Widget",
      "description": "High-quality widget for all purposes",
      "sku": "WDG-001",
      "price": 29.99,
      "category_id": "660e8400-e29b-41d4-a716-446655440001",
      "inventory_count": 150,
      "is_active": true,
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 45,
  "skip": 0,
  "limit": 20
}
```

#### Get Product

```http
GET /api/v1/products/{product_id}
```

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Premium Widget",
  "description": "High-quality widget for all purposes",
  "sku": "WDG-001",
  "price": 29.99,
  "category": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Widgets",
    "path": "home/electronics/widgets"
  },
  "inventory_count": 150,
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

#### Create Product

```http
POST /api/v1/products
Content-Type: application/json
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

**Request Body:**
```json
{
  "name": "New Widget",
  "description": "A brand new widget",
  "sku": "WDG-002",
  "price": 39.99,
  "category_id": "660e8400-e29b-41d4-a716-446655440001",
  "inventory_count": 100,
  "is_active": true
}
```

**Response:** `201 Created`
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "name": "New Widget",
  ...
}
```

#### Update Product

```http
PUT /api/v1/products/{product_id}
Content-Type: application/json
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

**Request Body:**
```json
{
  "name": "Updated Widget",
  "price": 34.99
}
```

**Response:** `200 OK`

#### Delete Product

```http
DELETE /api/v1/products/{product_id}
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

**Response:** `204 No Content`

#### Update Inventory

```http
PATCH /api/v1/products/{product_id}/inventory
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "adjustment": -5,
  "reason": "Order fulfillment"
}
```

**Response:** `200 OK`
```json
{
  "product_id": "550e8400-e29b-41d4-a716-446655440000",
  "previous_count": 150,
  "new_count": 145
}
```

### Categories

#### List Categories

```http
GET /api/v1/categories
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| parent_id | uuid | No | Filter by parent (null for root) |
| include_children | bool | No | Include child categories |

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "Electronics",
      "description": "Electronic devices and accessories",
      "parent_id": null,
      "path": "electronics",
      "children": [...]
    }
  ]
}
```

#### Get Category

```http
GET /api/v1/categories/{category_id}
```

**Response:** `200 OK`

#### Create Category

```http
POST /api/v1/categories
Content-Type: application/json
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

**Request Body:**
```json
{
  "name": "Smartphones",
  "description": "Mobile phones and accessories",
  "parent_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Response:** `201 Created`

#### Update Category

```http
PUT /api/v1/categories/{category_id}
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

#### Delete Category

```http
DELETE /api/v1/categories/{category_id}
Authorization: Bearer <token>
```

**Required Role:** `catalog-admin` or `platform-admin`

**Note:** Cannot delete categories with products or children.

### Health & Monitoring

#### Health Check

```http
GET /health
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "rabbitmq": "ok"
  }
}
```

#### Readiness Check

```http
GET /ready
```

#### Prometheus Metrics

```http
GET /metrics
```

## Error Responses

### Error Format

```json
{
  "detail": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Product with ID xxx not found",
    "field": null
  }
}
```

### Validation Error Format

```json
{
  "detail": [
    {
      "loc": ["body", "price"],
      "msg": "value is not a valid float",
      "type": "type_error.float"
    }
  ]
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request - Validation error |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - Duplicate SKU, etc. |
| 422 | Unprocessable Entity - Validation failed |
| 500 | Internal Server Error |

## Error Codes

| Code | Description |
|------|-------------|
| PRODUCT_NOT_FOUND | Product does not exist |
| CATEGORY_NOT_FOUND | Category does not exist |
| DUPLICATE_SKU | SKU already exists |
| CATEGORY_HAS_PRODUCTS | Cannot delete category with products |
| CATEGORY_HAS_CHILDREN | Cannot delete category with subcategories |
| INSUFFICIENT_INVENTORY | Not enough inventory |
| INVALID_CATEGORY_PARENT | Invalid parent category |

## Rate Limiting

Rate limits are applied per IP address:

| Limit Type | Value |
|------------|-------|
| Requests per minute | 100 |
| Burst capacity | 50 |

Headers in response:
```http
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705312200
```

## Pagination

List endpoints support pagination:

```http
GET /api/v1/products?skip=20&limit=10
```

Response includes pagination metadata:
```json
{
  "items": [...],
  "total": 150,
  "skip": 20,
  "limit": 10
}
```

## Examples

### Python (httpx)

```python
import httpx

async with httpx.AsyncClient() as client:
    # List products
    response = await client.get(
        "http://localhost:8000/api/v1/products",
        params={"category_id": "xxx", "limit": 10}
    )
    products = response.json()

    # Create product (with auth)
    response = await client.post(
        "http://localhost:8000/api/v1/products",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "New Product",
            "sku": "NEW-001",
            "price": 19.99,
            "category_id": "xxx"
        }
    )
```

### cURL

```bash
# List products
curl "http://localhost:8000/api/v1/products?limit=10"

# Create product
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Widget", "sku": "WDG-001", "price": 29.99, "category_id": "xxx"}'
```

## OpenAPI Specification

Interactive API documentation:
- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`
