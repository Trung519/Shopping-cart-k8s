#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh

[[ "${1:-}" == "--admin-password-stdin" ]] || fail "admin password must be supplied through stdin"
admin_password="$(cat)"
run_id="${RUN_ID:-}"
[[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]] || fail "RUN_ID contains unsafe characters"
fixture_file="$FIXTURE_DIR/$run_id.json"
[[ -f "$fixture_file" ]] || { log "no fixture file for $run_id; cleanup is already complete"; exit 0; }
mkdir -p "$RESULT_DIR"
jq 'del(.password) | .users |= with_entries(.value |= map(del(.password)))' "$fixture_file" > "$RESULT_DIR/fixture-manifest.json"
admin_jar="$(mktemp)"
trap 'rm -f "$admin_jar"' EXIT
login_curl shopcart-admin "$admin_password" "$admin_jar"
failed=0

mapfile -t user_ids < <(jq -r '.users[][] | .id' "$fixture_file")
mapfile -t product_ids < <(jq -r '.products[].id' "$fixture_file")
ids_sql=""
if ((${#user_ids[@]})); then
  ids_sql="$(printf "'%s'," "${user_ids[@]}")"
  ids_sql="${ids_sql%,}"
  psql_orders "BEGIN; DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE customer_id IN ($ids_sql)); DELETE FROM orders WHERE customer_id IN ($ids_sql); COMMIT;" >/dev/null || failed=1
  psql_marketplace "DELETE FROM shops WHERE owner_user_id IN ($ids_sql);" >/dev/null || failed=1
fi

products_before_cleanup="$(psql_products "SELECT count(*) FROM products WHERE sku LIKE '${run_id}-%' OR name LIKE '${run_id} %';")"
if [[ "$products_before_cleanup" != 0 ]]; then
  for product_id in "${product_ids[@]}"; do
    [[ "$product_id" =~ ^[0-9a-fA-F-]{36}$ ]] || continue
    status="$(curl "${CURL_RESOLVE[@]}" -sS -o /dev/null -w '%{http_code}' -X DELETE -b "$admin_jar" \
      -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" "$BASE_URL/api/v2/products/$product_id")"
    # The database post-check below is authoritative. An expired admin session
    # must not make an otherwise complete, idempotent cleanup look incomplete.
    [[ "$status" == 204 || "$status" == 404 ]] || true
  done
fi
psql_products "DELETE FROM products WHERE sku LIKE '${run_id}-%' OR name LIKE '${run_id} %';" >/dev/null || failed=1

valid_user_ids=()
for user_id in "${user_ids[@]}"; do
  [[ "$user_id" =~ ^[0-9a-fA-F-]{36}$ ]] && valid_user_ids+=("$user_id")
done

if ((${#valid_user_ids[@]})); then
  printf '%s\n' "${valid_user_ids[@]}" | kubectl --context "$CONTEXT" -n shopping-cart-data exec -i redis-cart-0 -- sh -lc \
    'while read -r user_id; do for db in 0 2; do redis-cli -a "$REDIS_PASSWORD" -n "$db" DEL "cart:$user_id" >/dev/null; done; done' \
    >/dev/null 2>&1 || failed=1
fi

mapfile -t session_keys < <(kubectl --context "$CONTEXT" -n shopping-cart-data exec redis-cart-0 -- sh -lc \
  'redis-cli -a "$REDIS_PASSWORD" -n 2 --scan --pattern "bff:session:*"' 2>/dev/null || true)
for session_key in "${session_keys[@]}"; do
  session_value="$(kubectl --context "$CONTEXT" -n shopping-cart-data exec redis-cart-0 -- sh -lc \
    "redis-cli -a \"\$REDIS_PASSWORD\" -n 2 GET '$session_key'" 2>/dev/null || true)"
  for user_id in "${user_ids[@]}"; do
    if [[ "$session_value" == *"$user_id"* ]]; then
      kubectl --context "$CONTEXT" -n shopping-cart-data exec redis-cart-0 -- sh -lc \
        "redis-cli -a \"\$REDIS_PASSWORD\" -n 2 DEL '$session_key' >/dev/null" >/dev/null 2>&1 || failed=1
      break
    fi
  done
done

kc_pod="$(kubectl --context "$CONTEXT" -n shopping-cart-identity get pod -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')"
kubectl --context "$CONTEXT" -n shopping-cart-identity exec "$kc_pod" -- sh -lc \
  '/opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null' >/dev/null 2>&1 || failed=1
mapfile -t existing_keycloak_ids < <(kubectl --context "$CONTEXT" -n shopping-cart-identity exec "$kc_pod" -- sh -lc \
  "/opt/keycloak/bin/kcadm.sh get users -r shopping-cart -q username=perf-${run_id} -q max=500" 2>/dev/null | jq -r '.[].id')
if ((${#existing_keycloak_ids[@]})); then
  printf '%s\n' "${existing_keycloak_ids[@]}" | kubectl --context "$CONTEXT" -n shopping-cart-identity exec -i "$kc_pod" -- sh -lc \
    'while read -r user_id; do /opt/keycloak/bin/kcadm.sh delete "users/$user_id" -r shopping-cart >/dev/null 2>&1 || true; done' \
    >/dev/null 2>&1 || true
fi

remaining_orders="$(psql_orders "SELECT count(*) FROM orders WHERE customer_id IN (${ids_sql:-''});")"
remaining_products="$(psql_products "SELECT count(*) FROM products WHERE sku LIKE '${run_id}-%' OR name LIKE '${run_id} %';")"
remaining_shops="$(psql_marketplace "SELECT count(*) FROM shops WHERE owner_user_id IN (${ids_sql:-''});")"
[[ "$remaining_orders" == 0 && "$remaining_products" == 0 && "$remaining_shops" == 0 ]] || failed=1

if [[ -f "$RESULT_DIR/baseline-counts.json" ]]; then
  final_orders="$(psql_orders 'SELECT count(*) FROM orders;')"
  final_products="$(psql_products 'SELECT count(*) FROM products;')"
  final_shops="$(psql_marketplace 'SELECT count(*) FROM shops;')"
  jq -n --argjson orders "$final_orders" --argjson products "$final_products" --argjson shops "$final_shops" \
    '{orders:$orders,products:$products,shops:$shops}' > "$RESULT_DIR/final-counts.json"
  jq -e --slurp '.[0] == .[1]' "$RESULT_DIR/baseline-counts.json" "$RESULT_DIR/final-counts.json" >/dev/null || failed=1
fi

if [[ "$failed" == 0 ]]; then
  printf '%s\n' "$(date -u +%FT%TZ)" > "$RESULT_DIR/cleanup.ok"
  rm -f "$fixture_file"
  log "cleaned and verified fixture $run_id"
else
  printf '%s\n' "$(date -u +%FT%TZ)" > "$RESULT_DIR/cleanup.incomplete"
  fail "cleanup or post-cleanup verification failed; fixture manifest was preserved"
fi
