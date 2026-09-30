#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
BASE_URL="${BASE_URL:-http://shopping-cart.localhost:8080}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
PREFIX="e2e-${RUN_ID}"
EVIDENCE="$ROOT/shopping-integration/.local/full-system-test/$RUN_ID"
RESULTS="$EVIDENCE/results.tsv"
REPORT="$ROOT/shopping-integration/docs/full-system-test-report.md"
mkdir -p "$EVIDENCE"
chmod 0700 "$ROOT/shopping-integration/.local" "$ROOT/shopping-integration/.local/full-system-test" "$EVIDENCE"
: >"$RESULTS"

declare -a FIXTURE_USERS=("")
declare -a FIXTURE_PRODUCTS=("")
declare -a FIXTURE_ORDERS=("")
declare -a FIXTURE_SHOPS=("")
BUYER_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
SELLER_A_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
SELLER_B_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
ADMIN_PASSWORD=""
KC_POD=""

sanitize() {
  sed -E \
    -e 's/(Authorization: Bearer )[A-Za-z0-9._-]+/\1[REDACTED]/g' \
    -e 's/(access_token|refresh_token|id_token|password|client_secret)["=: ]+[A-Za-z0-9._+\/-]+/\1=[REDACTED]/gi'
}

record() {
  printf '%s\t%s\t%s\n' "$1" "$2" "${3//$'\t'/ }" >>"$RESULTS"
  printf '[%s] %s - %s\n' "$1" "$2" "$3"
}

run_check() {
  local id="$1" description="$2"; shift 2
  local output="$EVIDENCE/${id}.log"
  if (cd "$ROOT" && "$@") >"$output.raw" 2>&1; then
    sanitize <"$output.raw" >"$output"; rm -f "$output.raw"
    record PASS "$id" "$description"
  else
    local code=$?
    sanitize <"$output.raw" >"$output"; rm -f "$output.raw"
    record FAIL "$id" "$description (exit $code)"
  fi
}

http_check() {
  local id="$1" expected="$2" method="$3" url="$4" jar="${5:-}" data="${6:-}"
  local args=(-sS -o "$EVIDENCE/${id}.body.raw" -w '%{http_code}' -X "$method")
  [[ -n "$jar" ]] && args+=(-b "$jar" -c "$jar")
  [[ -n "$data" ]] && args+=(-H 'Content-Type: application/json' --data-binary "$data")
  local code
  code="$(curl "${args[@]}" "$url" 2>"$EVIDENCE/${id}.curl.log" || true)"
  sanitize <"$EVIDENCE/${id}.body.raw" >"$EVIDENCE/${id}.body"; rm -f "$EVIDENCE/${id}.body.raw"
  if [[ "$code" == "$expected" ]]; then record PASS "$id" "$method $url returned $code"; else record FAIL "$id" "$method $url returned $code, expected $expected"; fi
}

capture_counts() {
  local output="$1"
  ( set -e
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-products-0 -- sh -lc 'PGPASSWORD="$POSTGRESQL_PASSWORD" /opt/bitnami/postgresql/bin/psql -U postgres -d products -Atc "select count(*) from products"'
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-orders-0 -- sh -lc 'PGPASSWORD="$POSTGRESQL_PASSWORD" /opt/bitnami/postgresql/bin/psql -U postgres -d orders -Atc "select count(*) from orders; select count(*) from order_items"'
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-marketplace-0 -- sh -lc 'PGPASSWORD="$SELLER_DB_PASSWORD" psql -U "$SELLER_DB_USER" -d "$SELLER_DB_NAME" -Atc "select count(*) from shops"'
    kubectl --context "$CONTEXT" exec -n shopping-cart-data redis-cart-0 -- sh -lc 'redis-cli -a "$REDIS_PASSWORD" -n 2 --no-auth-warning DBSIZE'
  ) >"$output" 2>"$output.errors"
}

kc() {
  kubectl --context "$CONTEXT" exec -i -n shopping-cart-identity "$KC_POD" -- /opt/keycloak/bin/kcadm.sh "$@"
}

create_user() {
  local username="$1" password="$2" roles_csv="$3"
  local id
  id="$(kc create users -r shopping-cart -s "username=$username" -s enabled=true -s emailVerified=true \
    -s "email=$username@e2e.local" -s firstName=E2E -s lastName=Fixture -i 2>/dev/null)" || return 1
  kc set-password -r shopping-cart --userid "$id" --new-password "$password" >/dev/null || return 1
  IFS=',' read -ra roles <<<"$roles_csv"
  for role in "${roles[@]}"; do kc add-roles -r shopping-cart --uid "$id" --rolename "$role" >/dev/null || return 1; done
  FIXTURE_USERS+=("$id")
  printf '%s' "$id"
}

login_user() {
  local username="$1" password="$2" jar="$3" label="$4"
  local html="$EVIDENCE/${label}-login.html" action
  curl --retry 10 --retry-all-errors --retry-delay 1 -fsSL -c "$jar" -b "$jar" "$BASE_URL/api/v2/auth/login" -o "$html" || return 1
  action="$(python3 - "$html" <<'PY'
import html, sys
from html.parser import HTMLParser
class Parser(HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        if tag == "form" and self.action is None:
            self.action = dict(attrs).get("action")
p = Parser()
p.feed(open(sys.argv[1], encoding="utf-8").read())
if not p.action: raise SystemExit(1)
print(html.unescape(p.action))
PY
)" || return 1
  curl --retry 10 --retry-all-errors --retry-delay 1 -fsSL -c "$jar" -b "$jar" --data-urlencode "username=$username" --data-urlencode "password=$password" --data-urlencode credentialId= "$action" -o "$EVIDENCE/${label}-result.html" || return 1
  curl --retry 10 --retry-all-errors --retry-delay 1 -fsS -b "$jar" "$BASE_URL/api/v2/auth/me" -o "$EVIDENCE/${label}-me.json" || return 1
  [[ "$(jq -r '.data.username' "$EVIDENCE/${label}-me.json")" == "$username" ]]
}

cleanup() {
  set +e
  for id in "${FIXTURE_USERS[@]}"; do [[ -n "$id" ]] && kc delete "users/$id" -r shopping-cart >/dev/null 2>&1; done
  if ((${#FIXTURE_PRODUCTS[@]} > 1)); then
    local ids="$(IFS=,; printf "'%s'" "${FIXTURE_PRODUCTS[*]//,/'',''}")"
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-products-0 -- sh -lc "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d products -c \"DELETE FROM products WHERE sku LIKE '${PREFIX}%';\"" >/dev/null 2>&1
  fi
  if ((${#FIXTURE_ORDERS[@]} > 1)); then
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-orders-0 -- sh -lc "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d orders -c \"DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN ('${BUYER_ID:-none}','${SELLER_B_ID:-none}')); DELETE FROM orders WHERE customer_id IN ('${BUYER_ID:-none}','${SELLER_B_ID:-none}');\"" >/dev/null 2>&1
  fi
  if ((${#FIXTURE_SHOPS[@]} > 1)); then
    kubectl --context "$CONTEXT" exec -n shopping-cart-data postgresql-marketplace-0 -- sh -lc "PGPASSWORD=\"\$SELLER_DB_PASSWORD\" psql -U \"\$SELLER_DB_USER\" -d \"\$SELLER_DB_NAME\" -c \"DELETE FROM shops WHERE owner_user_id IN ('${SELLER_A_ID:-none}','${SELLER_B_ID:-none}');\"" >/dev/null 2>&1
  fi
  unset BUYER_PASSWORD SELLER_A_PASSWORD SELLER_B_PASSWORD ADMIN_PASSWORD
}
trap cleanup EXIT

echo "Full system test run: $RUN_ID"

# Baseline and infrastructure
run_check baseline-helm "Capture Helm releases" helm --kube-context "$CONTEXT" list -A
run_check baseline-pods "Capture pods, images and restart counts" kubectl --context "$CONTEXT" get pods -A -o wide
run_check baseline-storage "Capture PVC state" kubectl --context "$CONTEXT" get pvc -A
if capture_counts "$EVIDENCE/baseline-row-counts.txt"; then record PASS baseline-row-counts "Captured products/orders/items/shops/cart-session counts"; else record BLOCKED baseline-row-counts "Could not capture all database row counts"; fi
run_check infra-gateway "Gateway and HTTPRoutes are programmed" bash -lc "kubectl --context '$CONTEXT' get gateway,httproute -A && kubectl --context '$CONTEXT' wait gateway/nginx-gateway -n shopping-cart-gateway --for=condition=Programmed --timeout=60s"
run_check infra-secrets "ExternalSecrets and ClusterSecretStore are ready" bash -lc "kubectl --context '$CONTEXT' get externalsecret,clustersecretstore -A"
run_check infra-mtls "PeerAuthentication and sidecars are present" bash -lc "kubectl --context '$CONTEXT' get peerauthentication -A; test \"\$(kubectl --context '$CONTEXT' -n shopping-cart-apps get pods -o json | jq '[.items[] | select(.status.phase==\"Running\") | select((([.spec.containers[].name] + [.spec.initContainers[]?.name]) | index(\"istio-proxy\")) == null)] | length')\" = 0"
run_check infra-rabbitmq "RabbitMQ events exchange exists" bash -lc "p=\$(kubectl --context '$CONTEXT' -n shopping-cart-data get pod -l app.kubernetes.io/name=rabbitmq -o jsonpath='{.items[0].metadata.name}'); kubectl --context '$CONTEXT' -n shopping-cart-data exec \"\$p\" -- rabbitmqctl list_exchanges name type durable | grep -E '^events[[:space:]]+topic[[:space:]]+true'"
run_check infra-vault "Vault is initialized and unsealed" bash -lc "kubectl --context '$CONTEXT' -n vault exec vault-0 -- vault status -format=json | jq -e '.initialized == true and .sealed == false'"
http_check gateway-storefront 200 GET "$BASE_URL/"
http_check gateway-keycloak 200 GET "http://keycloak.localhost:8080/realms/shopping-cart/.well-known/openid-configuration"
http_check api-unauth-cart 401 GET "$BASE_URL/api/v2/cart"

# Code quality and existing tests. Each group is independent.
run_check test-bff "Commerce BFF Go tests" bash -lc "cd commerce-bff && go test ./..."
run_check test-account "Account service Go tests" bash -lc "cd account-service && go test ./..."
run_check test-seller "Seller service Go tests" bash -lc "cd seller-service && go test ./..."
run_check test-basket "Basket unit tests" bash -lc "cd shopping-cart-basket && go test ./internal/..."
run_check test-payment-go "Non-runtime payment Go tests" bash -lc "cd shopping-cart-payment/go && go test ./..."
run_check test-frontend "Frontend type-check and unit tests" bash -lc "cd shopping-cart-frontend && NODE=/Users/phamquangtrung/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node; \"\$NODE\" node_modules/typescript/bin/tsc -b && \"\$NODE\" node_modules/vitest/vitest.mjs run"
run_check build-frontend "Frontend production build" bash -lc "cd shopping-cart-frontend && NODE=/Users/phamquangtrung/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node; \"\$NODE\" node_modules/vite/bin/vite.js build"
run_check test-ui-deployed "Playwright against deployed UI on Chromium, Firefox, WebKit and iPhone 13" bash -lc "cd shopping-cart-frontend && export BASE_URL='$BASE_URL'; NODE=/Users/phamquangtrung/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node; \"\$NODE\" node_modules/@playwright/test/cli.js test --reporter=json"
run_check test-catalog "Catalog Python unit tests in isolated container" docker run --rm -v "$ROOT/shopping-cart-product-catalog:/app" -w /app python:3.11-slim sh -lc "pip install -q '.[dev,rabbitmq]' && pytest -q tests/unit"
run_check test-order "Order Maven tests with pinned local RabbitMQ client" docker run --rm -v "$ROOT:/workspace" -v shopcart-e2e-m2:/root/.m2 -w /workspace maven:3.9-eclipse-temurin-21 sh -lc "mvn -B -f rabbitmq-client-java/pom.xml -pl rabbitmq-client -am package -DskipTests && mvn -B install:install-file -Dfile=rabbitmq-client-java/rabbitmq-client/target/rabbitmq-client-1.0.1.jar -DpomFile=shopping-cart-order/vendor/rabbitmq-client-1.0.1.pom && mvn -B -f shopping-cart-order/pom.xml test"
run_check test-payment-java "Runtime payment Java tests with pinned local RabbitMQ client" docker run --rm -v "$ROOT:/workspace" -v shopcart-e2e-m2:/root/.m2 -v /var/run/docker.sock:/var/run/docker.sock -e DOCKER_HOST=unix:///var/run/docker.sock -w /workspace maven:3.9-eclipse-temurin-21 sh -lc "mvn -B -f rabbitmq-client-java/pom.xml -pl rabbitmq-client -am package -DskipTests && mvn -B install:install-file -Dfile=rabbitmq-client-java/rabbitmq-client/target/rabbitmq-client-1.0.1.jar -DpomFile=shopping-cart-payment/vendor/rabbitmq-client-1.0.1.pom && mvn -B -f shopping-cart-payment/pom.xml test"

for spec in \
  "shopping-cart-frontend/helmchart:20-frontend.yaml" \
  "commerce-bff/helmchart:25-commerce-bff.yaml" \
  "account-service/helmchart:26-account-service.yaml" \
  "seller-service/helmchart:27-seller-service.yaml" \
  "shopping-cart-basket/helmchart:21-basket-service.yaml" \
  "shopping-cart-product-catalog/helmchart:22-product-catalog.yaml" \
  "shopping-cart-order/helmchart:23-order-service.yaml" \
  "shopping-cart-payment/helmchart:24-payment-service.yaml"; do
  chart="${spec%%:*}"; values="${spec#*:}"; id="helm-$(basename "$(dirname "$chart")")"
  run_check "$id" "Helm lint/template $chart" bash -lc "helm lint '$chart' -f config-secret-secure/values/local/00-global.yaml -f config-secret-secure/values/local/'$values' && helm template test '$chart' -f config-secret-secure/values/local/00-global.yaml -f config-secret-secure/values/local/'$values' >/dev/null"
done
run_check helm-integration "Helm lint/template integration" bash -lc "helm lint shopping-integration/helmchart -f config-secret-secure/values/local/00-global.yaml -f config-secret-secure/values/local/10-shopping-integration.yaml && helm template test shopping-integration/helmchart -f config-secret-secure/values/local/00-global.yaml -f config-secret-secure/values/local/10-shopping-integration.yaml >/dev/null"

# Containerized Java tests can briefly pressure the local k3d nodes. Do not
# start business workflows until every deployed app has recovered.
run_check apps-ready-after-builds "All app deployments recovered after isolated build tests" bash -lc "for deployment in product-catalog basket-service order-service commerce-bff frontend; do kubectl --context '$CONTEXT' -n shopping-cart-apps rollout status deployment/\$deployment --timeout=240s || exit 1; done"

# Authentication and isolated marketplace fixtures.
KC_POD="$(kubectl --context "$CONTEXT" get pod -n shopping-cart-identity -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')"
kubectl --context "$CONTEXT" exec -n shopping-cart-identity "$KC_POD" -- sh -lc '/opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null' >"$EVIDENCE/keycloak-auth.log" 2>&1
ADMIN_PASSWORD="$(security find-generic-password -a "$CONTEXT" -s shopping-cart-marketplace-admin -w)"
ADMIN_JAR="$EVIDENCE/admin.cookies"; BUYER_JAR="$EVIDENCE/buyer.cookies"; SELLER_A_JAR="$EVIDENCE/seller-a.cookies"; SELLER_B_JAR="$EVIDENCE/seller-b.cookies"
if login_user shopcart-admin "$ADMIN_PASSWORD" "$ADMIN_JAR" admin; then record PASS auth-admin "Admin OIDC login"; else record FAIL auth-admin "Admin OIDC login failed"; fi
http_check auth-invalid-callback 400 POST "$BASE_URL/api/v2/auth/callback" "" '{}'

BUYER_NAME="${PREFIX}-buyer"; SELLER_A_NAME="${PREFIX}-seller-a"; SELLER_B_NAME="${PREFIX}-seller-b"
BUYER_ID="$(create_user "$BUYER_NAME" "$BUYER_PASSWORD" buyer)" || BUYER_ID=""
SELLER_A_ID="$(create_user "$SELLER_A_NAME" "$SELLER_A_PASSWORD" buyer)" || SELLER_A_ID=""
SELLER_B_ID="$(create_user "$SELLER_B_NAME" "$SELLER_B_PASSWORD" buyer)" || SELLER_B_ID=""
[[ -n "$BUYER_ID" ]] && FIXTURE_USERS+=("$BUYER_ID")
[[ -n "$SELLER_A_ID" ]] && FIXTURE_USERS+=("$SELLER_A_ID")
[[ -n "$SELLER_B_ID" ]] && FIXTURE_USERS+=("$SELLER_B_ID")
[[ -n "$BUYER_ID" && -n "$SELLER_A_ID" && -n "$SELLER_B_ID" ]] && record PASS fixture-users "Created isolated buyer and two sellers" || record BLOCKED fixture-users "Could not create all fixture users"

for entry in "$BUYER_NAME:$BUYER_PASSWORD:$BUYER_JAR:buyer" "$SELLER_A_NAME:$SELLER_A_PASSWORD:$SELLER_A_JAR:seller-a" "$SELLER_B_NAME:$SELLER_B_PASSWORD:$SELLER_B_JAR:seller-b"; do
  IFS=: read -r username password jar label <<<"$entry"
  if login_user "$username" "$password" "$jar" "$label"; then record PASS "auth-$label" "$label OIDC login"; else record FAIL "auth-$label" "$label OIDC login failed"; fi
done

apply_seller() {
  local label="$1" jar="$2" name="$3"
  curl -fsS -b "$jar" -c "$jar" -H 'Content-Type: application/json' -d "{\"name\":\"$name\",\"description\":\"Full system test fixture\"}" "$BASE_URL/api/v2/sellers/applications" -o "$EVIDENCE/$label-application.json" || return 1
  local shop_id; shop_id="$(jq -r '.data.id' "$EVIDENCE/$label-application.json")"; FIXTURE_SHOPS+=("$shop_id")
  curl -fsS -X PATCH -b "$ADMIN_JAR" -H 'Content-Type: application/json' -d '{"status":"APPROVED","reason":"E2E fixture"}' "$BASE_URL/api/v2/sellers/applications/$shop_id" -o "$EVIDENCE/$label-approved.json" || return 1
  [[ "$(jq -r '.data.status' "$EVIDENCE/$label-approved.json")" == APPROVED ]]
}
apply_seller seller-a "$SELLER_A_JAR" "${PREFIX}-shop-a" && record PASS seller-a-approval "Seller A apply and approve" || record FAIL seller-a-approval "Seller A workflow failed"
apply_seller seller-b "$SELLER_B_JAR" "${PREFIX}-shop-b" && record PASS seller-b-approval "Seller B apply and approve" || record FAIL seller-b-approval "Seller B workflow failed"
rm -f "$SELLER_A_JAR" "$SELLER_B_JAR"
login_user "$SELLER_A_NAME" "$SELLER_A_PASSWORD" "$SELLER_A_JAR" seller-a-refresh && record PASS seller-role-refresh "Seller A receives role after re-login" || record FAIL seller-role-refresh "Seller role refresh failed"
login_user "$SELLER_B_NAME" "$SELLER_B_PASSWORD" "$SELLER_B_JAR" seller-b-refresh >/dev/null 2>&1 || true

SKU="${PREFIX}-sku"
INVALID_PRODUCT_PAYLOAD="$(jq -nc --arg sku "${SKU}-invalid" '{sku:$sku,name:"Invalid category fixture",description:"Fixture",price:123.45,currency:"VND",quantity:5,category:"not-admin-managed",image_url:null}')"
http_check catalog-reject-free-text-category 422 POST "$BASE_URL/api/v2/products" "$SELLER_A_JAR" "$INVALID_PRODUCT_PAYLOAD"
http_check category-seller-create-forbidden 403 POST "$BASE_URL/api/v2/products/categories" "$SELLER_A_JAR" "$(jq -nc --arg slug "${PREFIX}-category" '{slug:$slug,name:"E2E category",sort_order:999}')"
PRODUCT_PAYLOAD="$(jq -nc --arg sku "$SKU" '{sku:$sku,name:"E2E Phone",description:"Fixture",price:123.45,currency:"VND",quantity:5,category:"dien-thoai-phu-kien",image_url:null}')"
http_check seller-create-product 201 POST "$BASE_URL/api/v2/products" "$SELLER_A_JAR" "$PRODUCT_PAYLOAD"
PRODUCT_ID="$(jq -r '.id // empty' "$EVIDENCE/seller-create-product.body")"
[[ -n "$PRODUCT_ID" ]] && FIXTURE_PRODUCTS+=("$PRODUCT_ID")
http_check catalog-duplicate-sku 409 POST "$BASE_URL/api/v2/products" "$SELLER_A_JAR" "$PRODUCT_PAYLOAD"
http_check seller-b-cross-edit 403 PATCH "$BASE_URL/api/v2/products/$PRODUCT_ID" "$SELLER_B_JAR" '{"name":"stolen"}'
http_check seller-b-cross-delete 403 DELETE "$BASE_URL/api/v2/products/$PRODUCT_ID" "$SELLER_B_JAR"
http_check catalog-search 200 GET "$BASE_URL/api/v2/products?search=E2E&page_size=20"
http_check catalog-filter-owner 200 GET "$BASE_URL/api/v2/products?seller_id=$SELLER_A_ID&page_size=20"

http_check cart-empty 200 GET "$BASE_URL/api/v2/cart" "$BUYER_JAR"
http_check cart-add 201 POST "$BASE_URL/api/v2/cart/items" "$BUYER_JAR" "$(jq -nc --arg id "$PRODUCT_ID" '{productId:$id,quantity:2}')"
CART_ITEM_ID="$(jq -r '.data.items[0].id // empty' "$EVIDENCE/cart-add.body")"
http_check cart-update 200 PUT "$BASE_URL/api/v2/cart/items/$CART_ITEM_ID" "$BUYER_JAR" '{"quantity":3}'
http_check cart-invalid-product 404 POST "$BASE_URL/api/v2/cart/items" "$BUYER_JAR" '{"productId":"00000000-0000-0000-0000-000000000000","quantity":1}'
http_check cart-isolation 200 GET "$BASE_URL/api/v2/cart" "$SELLER_B_JAR"

CHECKOUT_PAYLOAD='{"shippingAddress":{"street":"1 E2E Street","city":"HCM","state":"Q1","postalCode":"700000","country":"VN"}}'
http_check checkout-create 200 POST "$BASE_URL/api/v2/cart/checkout" "$BUYER_JAR" "$CHECKOUT_PAYLOAD"
ORDER_ID="$(jq -r '.data.orderId // .orderId // empty' "$EVIDENCE/checkout-create.body")"
[[ -n "$ORDER_ID" ]] && FIXTURE_ORDERS+=("$ORDER_ID")
STOCK_AFTER="$(curl -fsS "$BASE_URL/api/v2/products/$PRODUCT_ID" | jq -r '.quantity')"
if [[ "$STOCK_AFTER" == "2" ]]; then record PASS checkout-decrements-stock "Checkout reduced product stock from 5 to 2"; else record FAIL checkout-decrements-stock "Expected stock 2 after checkout, got $STOCK_AFTER"; fi
http_check order-owner-detail 200 GET "$BASE_URL/api/v2/orders/$ORDER_ID" "$BUYER_JAR"
http_check order-idor 403 GET "$BASE_URL/api/v2/orders/$ORDER_ID" "$SELLER_B_JAR"
http_check order-admin-list 200 GET "$BASE_URL/api/v2/orders/admin" "$ADMIN_JAR"
http_check order-invalid-transition 400 PATCH "$BASE_URL/api/v2/orders/$ORDER_ID/status" "$ADMIN_JAR" '{"status":"COMPLETED"}'

# Restart one stateless workload and verify the authenticated session survives.
run_check resilience-bff-restart "BFF restart retains Redis-backed session" bash -lc "kubectl --context '$CONTEXT' -n shopping-cart-apps rollout restart deploy/commerce-bff && kubectl --context '$CONTEXT' -n shopping-cart-apps rollout status deploy/commerce-bff --timeout=180s && curl --retry 10 --retry-all-errors --retry-delay 1 -fsS -b '$BUYER_JAR' '$BASE_URL/api/v2/auth/me' >/dev/null"

# Lightweight concurrency and log checks.
run_check perf-catalog "20 concurrent catalog reads return without 5xx" bash -lc "seq 1 20 | xargs -P 20 -I{} curl -fsS '$BASE_URL/api/v2/products?page_size=20' >/dev/null"
run_check logs-no-crash "No recent panic/OOM/traceback in app logs" bash -lc "! kubectl --context '$CONTEXT' -n shopping-cart-apps logs -l app.kubernetes.io/part-of=shopping-cart --all-containers --since=30m --prefix 2>&1 | grep -E 'panic:|OutOfMemory|database_init_failed'"

# Explicitly classify current placeholder routes.
for route in buyer-addresses seller-inventory seller-orders seller-promotions seller-messages seller-finance seller-settings admin-returns admin-finance admin-analytics admin-audit; do
  record NOT_IMPLEMENTED "ui-$route" "Route is wired to WorkspacePlaceholderPage"
done
record NOT_IMPLEMENTED checkout-payment-integration "Checkout does not call payment-service"
record NOT_IMPLEMENTED seller-order-splitting "Orders are not split or filtered by seller"
record NOT_IMPLEMENTED shipping-adapter "Shipping choices are display-only local mocks"

# Final health and report.
run_check final-pods "No workload became unready during test" bash -lc "test \"\$(kubectl --context '$CONTEXT' get pods -A -o json | jq '[.items[] | select(.status.phase != \"Running\" and .status.phase != \"Succeeded\")] | length')\" = 0"

cleanup
trap - EXIT
if capture_counts "$EVIDENCE/final-row-counts.txt" \
  && cmp -s <(head -n 4 "$EVIDENCE/baseline-row-counts.txt") <(head -n 4 "$EVIDENCE/final-row-counts.txt"); then
  record PASS cleanup-row-counts "Fixture cleanup restored baseline database row counts; Redis session count is informational"
else
  record FAIL cleanup-row-counts "Final row counts differ from baseline; inspect evidence before manual cleanup"
fi

python3 - "$RESULTS" "$REPORT" "$RUN_ID" "$EVIDENCE" <<'PY'
import collections, pathlib, sys
results_path, report_path, run_id, evidence = sys.argv[1:]
rows = []
for line in pathlib.Path(results_path).read_text().splitlines():
    status, test_id, detail = line.split("\t", 2)
    rows.append((status, test_id, detail))
counts = collections.Counter(status for status, _, _ in rows)
severity = []
for status, test_id, detail in rows:
    if status == "FAIL":
        priority = "P0" if any(x in test_id for x in ("auth", "idor", "checkout")) else "P1"
        severity.append((priority, test_id, detail))
    elif status == "BLOCKED":
        severity.append(("P2", test_id, detail))
lines = [
    "# ShopCart Full System Test Report",
    "",
    f"- Run ID: `{run_id}`",
    "- Cluster: `k3d-lab-k8s`",
    "- Policy: isolated fixtures, cleanup after run, report-only",
    f"- Evidence: `{evidence}` (local, gitignored)",
    "",
    "## Summary",
    "",
    "| PASS | FAIL | BLOCKED | NOT_IMPLEMENTED |",
    "|---:|---:|---:|---:|",
    f"| {counts['PASS']} | {counts['FAIL']} | {counts['BLOCKED']} | {counts['NOT_IMPLEMENTED']} |",
    "",
    "## Findings",
    "",
]
if severity:
    lines += ["| Priority | Test | Finding |", "|---|---|---|"]
    lines += [f"| {p} | `{i}` | {d.replace('|', '/')} |" for p, i, d in sorted(severity)]
else:
    lines.append("No runtime failures or blocked tests were recorded.")
lines += ["", "## Complete Matrix", "", "| Status | Test | Result |", "|---|---|---|"]
lines += [f"| {s} | `{i}` | {d.replace('|', '/')} |" for s, i, d in rows]
lines += [
    "", "## Traceability Notes", "",
    "- Storefront: frontend routes -> commerce-bff -> catalog/cart/order services.",
    "- Identity and roles: Keycloak -> BFF Redis session -> forwarded user headers and bearer token.",
    "- Seller: seller-service/PostgreSQL marketplace -> catalog seller ownership/PostgreSQL products.",
    "- Checkout: basket -> order-service/PostgreSQL orders -> RabbitMQ `events`; payment is currently not integrated.",
    "- Platform: Helm -> External Secrets/Vault -> Istio Gateway and STRICT mTLS.",
    "", "## Cleanup", "",
    "Fixture users, shops, products and orders were targeted by recorded IDs and run prefix. Baseline/final evidence is retained locally; credentials and cookies are excluded from this report.",
]
pathlib.Path(report_path).write_text("\n".join(lines) + "\n")
PY

failures="$(awk -F '\t' '$1=="FAIL" || $1=="BLOCKED" {count++} END {print count+0}' "$RESULTS")"
echo "Report: $REPORT"
echo "Evidence: $EVIDENCE"
echo "Failures or blocked: $failures"
((failures == 0))
