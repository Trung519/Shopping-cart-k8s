# ShopCart Full System Test Report

- Run ID: `20260802-085902`
- Cluster: `k3d-lab-k8s`
- Policy: isolated fixtures, cleanup after run, report-only
- Evidence: `/Users/phamquangtrung/biglab-k8s/shopping-integration/.local/full-system-test/20260802-085902` (local, gitignored)

## Summary

| PASS | FAIL | BLOCKED | NOT_IMPLEMENTED |
|---:|---:|---:|---:|
| 59 | 6 | 0 | 14 |

## Findings

| Priority | Test | Finding |
|---|---|---|
| P0 | `checkout-create` | POST http://shopping-cart.localhost:8080/api/v2/cart/checkout returned 500, expected 200 |
| P0 | `checkout-decrements-stock` | Expected stock 2 after checkout, got 5 |
| P0 | `order-idor` | GET http://shopping-cart.localhost:8080/api/v2/orders/ returned 503, expected 403 |
| P1 | `order-admin-list` | GET http://shopping-cart.localhost:8080/api/v2/orders/admin returned 503, expected 200 |
| P1 | `order-invalid-transition` | PATCH http://shopping-cart.localhost:8080/api/v2/orders//status returned 301, expected 400 |
| P1 | `order-owner-detail` | GET http://shopping-cart.localhost:8080/api/v2/orders/ returned 503, expected 200 |

## Complete Matrix

| Status | Test | Result |
|---|---|---|
| PASS | `baseline-helm` | Capture Helm releases |
| PASS | `baseline-pods` | Capture pods, images and restart counts |
| PASS | `baseline-storage` | Capture PVC state |
| PASS | `baseline-row-counts` | Captured products/orders/items/shops/cart-session counts |
| PASS | `infra-gateway` | Gateway and HTTPRoutes are programmed |
| PASS | `infra-secrets` | ExternalSecrets and ClusterSecretStore are ready |
| PASS | `infra-mtls` | PeerAuthentication and sidecars are present |
| PASS | `infra-rabbitmq` | RabbitMQ events exchange exists |
| PASS | `infra-vault` | Vault is initialized and unsealed |
| PASS | `gateway-storefront` | GET http://shopping-cart.localhost:8080/ returned 200 |
| PASS | `gateway-keycloak` | GET http://keycloak.localhost:8080/realms/shopping-cart/.well-known/openid-configuration returned 200 |
| PASS | `api-unauth-cart` | GET http://shopping-cart.localhost:8080/api/v2/cart returned 401 |
| PASS | `test-bff` | Commerce BFF Go tests |
| PASS | `test-account` | Account service Go tests |
| PASS | `test-seller` | Seller service Go tests |
| PASS | `test-basket` | Basket unit tests |
| PASS | `test-payment-go` | Non-runtime payment Go tests |
| PASS | `test-frontend` | Frontend type-check and unit tests |
| PASS | `build-frontend` | Frontend production build |
| PASS | `test-ui-deployed` | Playwright against deployed UI on Chromium, Firefox, WebKit and iPhone 13 |
| PASS | `test-catalog` | Catalog Python unit tests in isolated container |
| PASS | `test-order` | Order Maven tests with pinned local RabbitMQ client |
| PASS | `test-payment-java` | Runtime payment Java tests with pinned local RabbitMQ client |
| PASS | `helm-shopping-cart-frontend` | Helm lint/template shopping-cart-frontend/helmchart |
| PASS | `helm-commerce-bff` | Helm lint/template commerce-bff/helmchart |
| PASS | `helm-account-service` | Helm lint/template account-service/helmchart |
| PASS | `helm-seller-service` | Helm lint/template seller-service/helmchart |
| PASS | `helm-shopping-cart-basket` | Helm lint/template shopping-cart-basket/helmchart |
| PASS | `helm-shopping-cart-product-catalog` | Helm lint/template shopping-cart-product-catalog/helmchart |
| PASS | `helm-shopping-cart-order` | Helm lint/template shopping-cart-order/helmchart |
| PASS | `helm-shopping-cart-payment` | Helm lint/template shopping-cart-payment/helmchart |
| PASS | `helm-integration` | Helm lint/template integration |
| PASS | `auth-admin` | Admin OIDC login |
| PASS | `auth-invalid-callback` | POST http://shopping-cart.localhost:8080/api/v2/auth/callback returned 400 |
| PASS | `fixture-users` | Created isolated buyer and two sellers |
| PASS | `auth-buyer` | buyer OIDC login |
| PASS | `auth-seller-a` | seller-a OIDC login |
| PASS | `auth-seller-b` | seller-b OIDC login |
| PASS | `seller-a-approval` | Seller A apply and approve |
| PASS | `seller-b-approval` | Seller B apply and approve |
| PASS | `seller-role-refresh` | Seller A receives role after re-login |
| PASS | `catalog-reject-free-text-category` | POST http://shopping-cart.localhost:8080/api/v2/products returned 422 |
| PASS | `category-seller-create-forbidden` | POST http://shopping-cart.localhost:8080/api/v2/products/categories returned 403 |
| PASS | `seller-create-product` | POST http://shopping-cart.localhost:8080/api/v2/products returned 201 |
| PASS | `catalog-duplicate-sku` | POST http://shopping-cart.localhost:8080/api/v2/products returned 409 |
| PASS | `seller-b-cross-edit` | PATCH http://shopping-cart.localhost:8080/api/v2/products/810a270d-c4b3-4207-9392-5a6490517452 returned 403 |
| PASS | `seller-b-cross-delete` | DELETE http://shopping-cart.localhost:8080/api/v2/products/810a270d-c4b3-4207-9392-5a6490517452 returned 403 |
| PASS | `catalog-search` | GET http://shopping-cart.localhost:8080/api/v2/products?search=E2E&page_size=20 returned 200 |
| PASS | `catalog-filter-owner` | GET http://shopping-cart.localhost:8080/api/v2/products?seller_id=57b2378b-62d1-43ba-9c7d-5dee35c0ba40&page_size=20 returned 200 |
| PASS | `cart-empty` | GET http://shopping-cart.localhost:8080/api/v2/cart returned 200 |
| PASS | `cart-add` | POST http://shopping-cart.localhost:8080/api/v2/cart/items returned 201 |
| PASS | `cart-update` | PUT http://shopping-cart.localhost:8080/api/v2/cart/items/45a33f77-d397-4f27-9750-1d2f17b28d57 returned 200 |
| PASS | `cart-invalid-product` | POST http://shopping-cart.localhost:8080/api/v2/cart/items returned 404 |
| PASS | `cart-isolation` | GET http://shopping-cart.localhost:8080/api/v2/cart returned 200 |
| FAIL | `checkout-create` | POST http://shopping-cart.localhost:8080/api/v2/cart/checkout returned 500, expected 200 |
| FAIL | `checkout-decrements-stock` | Expected stock 2 after checkout, got 5 |
| FAIL | `order-owner-detail` | GET http://shopping-cart.localhost:8080/api/v2/orders/ returned 503, expected 200 |
| FAIL | `order-idor` | GET http://shopping-cart.localhost:8080/api/v2/orders/ returned 503, expected 403 |
| FAIL | `order-admin-list` | GET http://shopping-cart.localhost:8080/api/v2/orders/admin returned 503, expected 200 |
| FAIL | `order-invalid-transition` | PATCH http://shopping-cart.localhost:8080/api/v2/orders//status returned 301, expected 400 |
| PASS | `resilience-bff-restart` | BFF restart retains Redis-backed session |
| PASS | `perf-catalog` | 20 concurrent catalog reads return without 5xx |
| PASS | `logs-no-crash` | No recent panic/OOM/traceback in app logs |
| NOT_IMPLEMENTED | `ui-buyer-addresses` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-inventory` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-orders` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-promotions` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-messages` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-finance` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-seller-settings` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-admin-returns` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-admin-finance` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-admin-analytics` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `ui-admin-audit` | Route is wired to WorkspacePlaceholderPage |
| NOT_IMPLEMENTED | `checkout-payment-integration` | Checkout does not call payment-service |
| NOT_IMPLEMENTED | `seller-order-splitting` | Orders are not split or filtered by seller |
| NOT_IMPLEMENTED | `shipping-adapter` | Shipping choices are display-only local mocks |
| PASS | `final-pods` | No workload became unready during test |
| PASS | `cleanup-row-counts` | Fixture cleanup restored baseline database row counts; Redis session count is informational |

## Traceability Notes

- Storefront: frontend routes -> commerce-bff -> catalog/cart/order services.
- Identity and roles: Keycloak -> BFF Redis session -> forwarded user headers and bearer token.
- Seller: seller-service/PostgreSQL marketplace -> catalog seller ownership/PostgreSQL products.
- Checkout: basket -> order-service/PostgreSQL orders -> RabbitMQ `events`; payment is currently not integrated.
- Platform: Helm -> External Secrets/Vault -> Istio Gateway and STRICT mTLS.

## Cleanup

Fixture users, shops, products and orders were targeted by recorded IDs and run prefix. Baseline/final evidence is retained locally; credentials and cookies are excluded from this report.
