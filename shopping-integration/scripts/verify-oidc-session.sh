#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://shopping-cart.localhost:8080}"
KEYCHAIN_ACCOUNT="${KUBE_CONTEXT:-k3d-lab-k8s}"
KEYCHAIN_SERVICE="shopping-cart-marketplace-admin"
tmp_dir="$(mktemp -d)"
chmod 0700 "$tmp_dir"
trap 'rm -rf "$tmp_dir"; unset password' EXIT

password="$(security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w)"

curl -fsSL \
  -c "$tmp_dir/cookies" \
  -b "$tmp_dir/cookies" \
  "$BASE_URL/api/v2/auth/login?returnTo=%2Fadmin" \
  -o "$tmp_dir/login.html"
echo "oidc_login_form=ok"

form_action="$(python3 - "$tmp_dir/login.html" <<'PY'
import html
import sys
from html.parser import HTMLParser

class FormParser(HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        if tag == "form" and self.action is None:
            self.action = dict(attrs).get("action")

parser = FormParser()
with open(sys.argv[1], encoding="utf-8") as source:
    parser.feed(source.read())
if not parser.action:
    raise SystemExit("Keycloak login form was not found")
print(html.unescape(parser.action))
PY
)"
python3 - "$form_action" <<'PY'
import sys
from urllib.parse import urlparse
parsed = urlparse(sys.argv[1])
print(f"oidc_form_target={parsed.scheme}://{parsed.netloc}{parsed.path}")
PY

curl -fsSL \
  -c "$tmp_dir/cookies" \
  -b "$tmp_dir/cookies" \
  --data-urlencode "username=shopcart-admin" \
  --data-urlencode "password=$password" \
  --data-urlencode "credentialId=" \
  "$form_action" \
  -o "$tmp_dir/result.html"
echo "oidc_callback=ok"

session_json="$(curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/auth/me")"
echo "oidc_me=ok"
username="$(jq -r '.data.username' <<<"$session_json")"
roles="$(jq -r '.data.roles | sort | join(",")' <<<"$session_json")"
printf 'oidc_identity username=%s roles=%s\n' "$username" "$roles"
[[ "$username" == "shopcart-admin" ]]
grep -q 'platform-admin' <<<"$roles"

users_count="$(curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/accounts/users" | jq '.data | length')"
echo "account_api=ok"

cart_items="$(curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/cart" | jq '.data.items | length')"
echo "basket_oauth=ok"

curl -fsS "$BASE_URL/api/v2/products?search=phone&page_size=20" >"$tmp_dir/products.json"
search_matches="$(jq '.total' "$tmp_dir/products.json")"
[[ "$search_matches" -gt 0 ]]
echo "catalog_search=ok"

curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/cart" >"$tmp_dir/cart-before.json"
product_id="$(jq -r --slurpfile cart "$tmp_dir/cart-before.json" '.items | map(.id) - ($cart[0].data.items | map(.productId)) | .[0] // empty' "$tmp_dir/products.json")"
[[ -n "$product_id" ]]
jq -nc --arg productId "$product_id" '{productId:$productId,quantity:1}' >"$tmp_dir/add-item.json"
curl -fsS -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" \
  -H 'Content-Type: application/json' \
  --data-binary "@$tmp_dir/add-item.json" \
  "$BASE_URL/api/v2/cart/items" >"$tmp_dir/cart-added.json"
item_id="$(jq -r --arg productId "$product_id" '.data.items[] | select(.productId == $productId) | .id' "$tmp_dir/cart-added.json" | head -n 1)"
unit_price="$(jq -r --arg productId "$product_id" '.data.items[] | select(.productId == $productId) | .unitPrice' "$tmp_dir/cart-added.json" | head -n 1)"
[[ -n "$item_id" && "$unit_price" != "null" ]]
curl -fsS -X DELETE -b "$tmp_dir/cookies" \
  "$BASE_URL/api/v2/cart/items/$item_id" >"$tmp_dir/cart-cleaned.json"
echo "cart_write=ok"

seller_status_code="$(curl -sS -o "$tmp_dir/seller.json" -w '%{http_code}' -b "$tmp_dir/cookies" "$BASE_URL/api/v2/sellers/me")"
if [[ "$seller_status_code" == "204" ]]; then
  curl -fsS -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" \
    -H 'Content-Type: application/json' \
    -d '{"name":"ShopCart Official","description":"Gian hàng vận hành dùng để kiểm thử marketplace local."}' \
    "$BASE_URL/api/v2/sellers/applications" >"$tmp_dir/seller.json"
elif [[ "$seller_status_code" != "200" ]]; then
  echo "Unexpected seller profile status: $seller_status_code" >&2
  exit 1
fi
seller_id="$(jq -r '.data.id' "$tmp_dir/seller.json")"
seller_status="$(jq -r '.data.status' "$tmp_dir/seller.json")"
if [[ "$seller_status" == "PENDING" || "$seller_status" == "APPROVED" ]]; then
  curl -fsS -X PATCH -b "$tmp_dir/cookies" \
    -H 'Content-Type: application/json' \
    -d '{"status":"APPROVED","reason":""}' \
    "$BASE_URL/api/v2/sellers/applications/$seller_id" >"$tmp_dir/seller-reviewed.json"
  seller_status="$(jq -r '.data.status' "$tmp_dir/seller-reviewed.json")"
fi
[[ "$seller_status" == "APPROVED" ]]
seller_role_count="$(curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/accounts/users" | jq --arg username "$username" '[.data[] | select(.username == $username and (.roles | index("seller-owner")))] | length')"
[[ "$seller_role_count" == "1" ]]
echo "seller_workflow=ok"

curl -fsS -b "$tmp_dir/cookies" "$BASE_URL/api/v2/orders/admin" >"$tmp_dir/admin-orders.json"
admin_orders_count="$(jq 'if type == "array" then length else .data | length end' "$tmp_dir/admin-orders.json")"
pending_orders_count="$(jq 'if type == "array" then [.[] | select(.status == "PENDING")] | length else [.data[] | select(.status == "PENDING")] | length end' "$tmp_dir/admin-orders.json")"
[[ "$admin_orders_count" -gt 0 ]]
echo "admin_orders_api=ok"

printf 'oidc_session=ok username=%s roles=%s managed_users=%s\n' "$username" "$roles" "$users_count"
printf 'marketplace_contracts=ok cart_items=%s search_matches=%s seller_status=%s\n' "$cart_items" "$search_matches" "$seller_status"
printf 'order_operations=ok total=%s pending=%s\n' "$admin_orders_count" "$pending_orders_count"

curl -fsS -X POST -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" \
  "$BASE_URL/api/v2/auth/logout" >"$tmp_dir/logout.json"
logout_url="$(jq -r '.data.logoutUrl' "$tmp_dir/logout.json")"
[[ "$logout_url" == *"/protocol/openid-connect/logout?"* ]]
curl -fsSL -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" \
  "$logout_url" -o "$tmp_dir/logged-out.html"
me_after_logout_status="$(curl -sS -o "$tmp_dir/me-after-logout.json" -w '%{http_code}' -b "$tmp_dir/cookies" "$BASE_URL/api/v2/auth/me")"
[[ "$me_after_logout_status" == "401" ]]
curl -fsSL -b "$tmp_dir/cookies" -c "$tmp_dir/cookies" \
  "$BASE_URL/api/v2/auth/login" -o "$tmp_dir/login-after-logout.html"
grep -q '<form' "$tmp_dir/login-after-logout.html"
echo "oidc_logout_switch_account=ok"
