#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://shopping-cart.localhost:8080}"
CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
tmp_dir="$(mktemp -d)"
chmod 0700 "$tmp_dir"
order_id=""
product_id=""
stock_before=""
category_id=""

cleanup() {
  set +e
  curl -fsS -X DELETE -b "$tmp_dir/cookies" "$BASE_URL/api/v2/cart" >/dev/null 2>&1
  if [[ -n "$order_id" ]]; then
    kubectl --context "$CONTEXT" -n shopping-cart-data exec postgresql-orders-0 -- sh -lc \
      "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d orders -c \"DELETE FROM order_items WHERE order_id='${order_id}'; DELETE FROM orders WHERE id='${order_id}';\"" >/dev/null 2>&1
  fi
  if [[ -n "$product_id" && -n "$stock_before" ]]; then
    kubectl --context "$CONTEXT" -n shopping-cart-data exec postgresql-products-0 -- sh -lc \
      "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d products -c \"UPDATE products SET quantity=${stock_before} WHERE id='${product_id}';\"" >/dev/null 2>&1
  fi
  if [[ -n "$category_id" ]]; then
    curl -fsS -X DELETE -b "$tmp_dir/cookies" "$BASE_URL/api/v2/products/categories/$category_id" >/dev/null 2>&1
  fi
  rm -rf "$tmp_dir"
  unset password
}
trap cleanup EXIT

password="$(security find-generic-password -a "$CONTEXT" -s shopping-cart-marketplace-admin -w)"
curl -fsSL -c "$tmp_dir/cookies" -b "$tmp_dir/cookies" "$BASE_URL/api/v2/auth/login" -o "$tmp_dir/login.html"
form_action="$(python3 - "$tmp_dir/login.html" <<'PY'
import html, sys
from html.parser import HTMLParser
class Parser(HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        if tag == "form" and self.action is None:
            self.action = dict(attrs).get("action")
p = Parser(); p.feed(open(sys.argv[1], encoding="utf-8").read())
if not p.action: raise SystemExit("OIDC form not found")
print(html.unescape(p.action))
PY
)"
curl -fsSL -c "$tmp_dir/cookies" -b "$tmp_dir/cookies" \
  --data-urlencode username=shopcart-admin --data-urlencode "password=$password" \
  --data-urlencode credentialId= "$form_action" -o "$tmp_dir/login-result.html"
unset password
[[ "$(curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/auth/me" | jq -r '.data.roles | index("platform-admin") != null')" == true ]]
echo "PASS oidc-admin"

category_slug="e2e-category-$(date +%s)"
category_code="$(curl -sS -o "$tmp_dir/category.json" -w '%{http_code}' -b "$tmp_dir/cookies" \
  -H 'Content-Type: application/json' -d "{\"slug\":\"$category_slug\",\"name\":\"Danh mục E2E\",\"sort_order\":999}" \
  "$BASE_URL/api/v2/products/categories")"
[[ "$category_code" == 201 ]]
category_id="$(jq -r '.id' "$tmp_dir/category.json")"
echo "PASS admin-category-create"
curl -fsS -X DELETE -b "$tmp_dir/cookies" "$BASE_URL/api/v2/products/categories/$category_id" >/dev/null
category_id=""
echo "PASS admin-category-delete"

invalid_code="$(curl -sS -o "$tmp_dir/invalid.json" -w '%{http_code}' -b "$tmp_dir/cookies" \
  -H 'Content-Type: application/json' -d '{"sku":"E2E-INVALID-CATEGORY","name":"Invalid","price":1000,"currency":"VND","quantity":1,"category":"free-text-is-forbidden"}' \
  "$BASE_URL/api/v2/products")"
[[ "$invalid_code" == 422 ]]
echo "PASS reject-free-text-category"

curl -fsS -X DELETE -b "$tmp_dir/cookies" "$BASE_URL/api/v2/cart" >/dev/null
product_json="$(curl -fsS "$BASE_URL/api/v2/products?search=WEB-DUMMYJSON&page_size=100" | jq -c 'first(.items[] | select(.quantity >= 5))')"
product_id="$(jq -r '.id' <<<"$product_json")"
stock_before="$(jq -r '.quantity' <<<"$product_json")"
curl -fsS -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" -H 'Content-Type: application/json' \
  -d "{\"productId\":\"$product_id\",\"quantity\":2}" "$BASE_URL/api/v2/cart/items" >/dev/null
checkout_json="$(curl -fsS -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" -H 'Content-Type: application/json' \
  -d '{"shippingAddress":{"street":"1 E2E Street","city":"HCM","state":"Q1","postalCode":"700000","country":"VN"}}' \
  "$BASE_URL/api/v2/cart/checkout")"
order_id="$(jq -r '.data.orderId // .orderId' <<<"$checkout_json")"
stock_after="$(curl -fsS "$BASE_URL/api/v2/products/$product_id" | jq -r '.quantity')"
[[ "$stock_after" -eq $((stock_before - 2)) ]]
printf 'PASS checkout-stock-decrement product=%s before=%s after=%s order=%s\n' "$product_id" "$stock_before" "$stock_after" "$order_id"

echo "PASS cleanup-baseline (runs on exit)"
