# Commerce BFF

Browser-facing API for ShopCart. It owns the OIDC Authorization Code + PKCE flow,
stores tokens server-side in Redis, and exposes only a signed HttpOnly session cookie.

All browser traffic uses `/api/v2`; internal service URLs stay inside the mesh.

## Mock API (`/api/v2/mock/`)

A self-contained demo layer for UI work and DevOps labs (tracing, dashboards, chaos).
**Requests are mock, responses are canned**: they come from embedded fixtures plus per-user
state kept in Redis (`bff:mock:*`, TTL 24h). Nothing here touches order-service, payment-service
or any other real backend.

Off by default. Every response is tagged so it can never be mistaken for real traffic:
JSON `"mock": true`, header `X-Mock: true`, span attributes `mock=true` / `mock.scenario`,
a `mock_api_call` JSON log line carrying the `trace_id`, and a "Demo" badge in the UI.

| Env | Default | Meaning |
|-----|---------|---------|
| `MOCK_API_ENABLED` | `false` | Mount the module. When false the routes do not exist (404). |
| `MOCK_PAYMENT_DELAY_SECONDS` | `5` | Time from QR creation to payment success. |
| `MOCK_SHIPMENT_STEP_SECONDS` | `10` | Time between shipment steps after payment. |
| `MOCK_EVENT_INTERVAL_SECONDS` | `15` | Interval of live notification events on the SSE stream. |

State is derived from stored timestamps (no timers or goroutines), so it stays consistent
across replicas and restarts. Payment success emits one `mock.payment.callback` span linked to
the span of the request that created the payment, which models the async provider callback.

Endpoints (all need a session unless noted; admin routes need an admin role):

- Public: `GET /config`
- Buyer: `POST /payments` (momo, vnpay, zalopay, cod), `GET /payments/{id}`, `POST /payments/{id}/cancel`,
  `GET /shipments/{orderId}`, addresses CRUD (+`/{id}/default`), `GET /vouchers`, `POST /vouchers/apply`,
  `GET|POST /products/{id}/reviews`, `GET /products/{id}/extras`, `GET|POST /returns`,
  `GET /notifications`, `POST /notifications/read`, `GET /events` (SSE)
- Seller: `/seller/dashboard`, `/seller/orders`, `/seller/inventory`, `/seller/promotions`,
  `/seller/messages`, `/seller/finance`, `/seller/payouts`, `/seller/settings`
- Admin: `/admin/returns`, `/admin/finance`, `/admin/finance/settlements/{id}/approve`,
  `/admin/analytics`, `/admin/audit`

Chaos query parameters (capped at 10s; not applied to `/config`):

| Param | Example | Effect |
|-------|---------|--------|
| `delay` | `?delay=800ms` or `800` | Add latency before the handler runs. |
| `fail` | `?fail=0.3` | Return a 503 with this probability. |
| `outcome` | `POST /payments?outcome=fail` | The payment ends in FAILED instead of SUCCESS. |
| `payDelay` | `POST /payments?payDelay=12` | Override the payment delay for this payment (seconds). |

Tests: `go test -race ./...`; the Redis-backed contract and two-replica tests run when
`REDIS_TEST_ADDR` points at a Redis (for example `docker run -p 6379:6379 redis:7-alpine`).
