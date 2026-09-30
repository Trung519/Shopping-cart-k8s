# API Reference — Shopping Cart Frontend

The frontend communicates with three backend services via `/api/*` prefix paths. In development,
Vite proxies these paths (see `vite.config.ts`). In production, nginx proxies them directly to
Kubernetes service DNS names (see `nginx.conf`). Authenticated requests include a Bearer token from Keycloak; unauthenticated paths (e.g. product listing) may omit it.

## Backend Services

| Service | Path prefix | nginx proxy target |
|---|---|---|
| Order Service | `/api/orders` | `order-service.shopping-cart-apps.svc.cluster.local:8081` |
| Product Catalog | `/api/products` | `product-catalog.shopping-cart-apps.svc.cluster.local:8082` |
| Basket Service | `/api/cart` | `basket-service.shopping-cart-apps.svc.cluster.local:8083` |

> The `VITE_*_SERVICE_URL` env vars in `.env.local` should remain relative `/api/...` paths
> to stay compatible with the Vite dev proxy and nginx prod proxy. Setting absolute URLs
> bypasses the proxy and introduces CORS issues.

## Order Service

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/orders` | List orders for authenticated user |
| `GET` | `/api/orders/:id` | Get order details |
| `POST` | `/api/orders` | Create order from current basket |
| `PUT` | `/api/orders/:id/cancel` | Cancel an order |

## Product Catalog

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/products` | List products (supports `?search=`, `?page=`, `?size=`) |
| `GET` | `/api/products/:id` | Get product details |

## Basket Service

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/cart` | Get current basket |
| `POST` | `/api/cart/items` | Add item to basket |
| `PUT` | `/api/cart/items/:id` | Update item quantity |
| `DELETE` | `/api/cart/items/:id` | Remove item from basket |
| `DELETE` | `/api/cart` | Clear basket |

## Auth Headers

Authenticated requests include:
```
Authorization: Bearer <keycloak-access-token>
```

Injected automatically by the Axios request interceptor in `src/services/api.ts`, which reads
the access token via `getAccessToken()` from `src/config/auth.ts`. Unauthenticated paths
(e.g. `GET /api/products`) omit the header when no token is present.

## Error Handling

- `401` — token expired or invalid; the Axios response interceptor logs the error and rejects
  the promise. Re-auth must be triggered manually (no automatic refresh in current implementation).
  See `src/services/api.ts`.
- `403` — insufficient permissions; error propagated to the calling component
- `5xx` — TanStack Query retries once (`retry: 1`, configured in `src/main.tsx`)
