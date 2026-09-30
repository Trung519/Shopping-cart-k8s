#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh

[[ "${1:-}" == "--admin-password-stdin" ]] || fail "admin password must be supplied through stdin"
admin_password="$(cat)"
[[ -n "$admin_password" ]] || fail "empty admin password"
run_id="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
vus="${VUS:-5}"
profile="${PROFILE:-smoke}"
seed="${SEED:-20260802}"
mkdir -p "$FIXTURE_DIR" "$RESULT_DIR"
fixture_file="$FIXTURE_DIR/$run_id.json"
admin_jar="$(mktemp)"
approved_jar_dir="$(mktemp -d)"
trap 'rm -f "$admin_jar"; rm -rf "$approved_jar_dir"' EXIT

login_curl shopcart-admin "$admin_password" "$admin_jar"

category="$(curl "${CURL_RESOLVE[@]}" -fsS -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" \
  "$BASE_URL/api/v2/products/categories" | jq -er 'map(select(.is_active == true or .is_active == null))[0].slug')"
application_spread="$(jq -er '.applicationSpreadSeconds' "$ROOT_DIR/profiles/$profile.json")"
config_json="$(jq --arg category "$category" --argjson spread "$application_spread" \
  '. + {category:$category,applicationSpreadSeconds:$spread}' "$ROOT_DIR/config/test-data.json")"
product_price="$(jq -er '.productPrice' <<<"$config_json")"
product_stock="$(jq -er '.productStock' <<<"$config_json")"
baseline_orders="$(psql_orders 'SELECT count(*) FROM orders;')"
baseline_products="$(psql_products 'SELECT count(*) FROM products;')"
baseline_shops="$(psql_marketplace 'SELECT count(*) FROM shops;')"
jq -n --argjson orders "$baseline_orders" --argjson products "$baseline_products" --argjson shops "$baseline_shops" \
  '{orders:$orders,products:$products,shops:$shops}' > "$RESULT_DIR/baseline-counts.json"

ceil_share() { local n="$1" pct="$2"; awk -v n="$n" -v pct="$pct" 'BEGIN {v=n*pct; print (v<1 ? 1 : int(v+0.999999))}'; }
browse_n="$(ceil_share "$vus" .45)"
cart_n="$(ceil_share "$vus" .20)"
buy_n="$(ceil_share "$vus" .10)"
checkout_n="$(ceil_share "$vus" .10)"
seller_n="$(ceil_share "$vus" .10)"
application_n="$(ceil_share "$vus" .05)"
product_n="$(awk -v n="$vus" 'BEGIN {print (n<20 ? 20 : n)}')"
password="Perf-$(openssl rand -hex 12)!"
users_json='{"browse":[],"cart":[],"buyNow":[],"cartCheckout":[],"sellerProduct":[],"sellerApplication":[]}'
declare -A user_ids

jq -n --arg runId "$run_id" --argjson seed "$seed" --arg password "$password" --argjson config "$config_json" --argjson users "$users_json" \
  '{runId:$runId,seed:$seed,password:$password,config:$config,users:$users,products:[],shops:[],orders:[]}' > "$fixture_file"
chmod 600 "$fixture_file"

create_user() {
  local bucket="$1" index="$2" roles="$3" username response id payload
  username="perf-${run_id}-${bucket}-${index}"
  payload="$(jq -nc --arg username "$username" --arg email "$username@perf.local" --arg password "$password" --argjson roles "$roles" \
    '{username:$username,email:$email,name:"Performance Fixture",password:$password,roles:$roles}')"
  response="$(mktemp)"
  api_post "$admin_jar" /api/v2/accounts/users "$payload" 201 "$response"
  id="$(jq -r '.data.id // .id' "$response")"
  [[ "$id" != null && -n "$id" ]] || fail "could not create fixture user $username"
  login_curl "$username" "$password" "$approved_jar_dir/$bucket-$index.cookies"
  users_json="$(jq --arg bucket "$bucket" --arg id "$id" --arg username "$username" --arg password "$password" \
    '.[$bucket] += [{id:$id,username:$username,password:$password}]' <<<"$users_json")"
  jq --argjson users "$users_json" '.users=$users' "$fixture_file" > "$fixture_file.tmp"
  mv "$fixture_file.tmp" "$fixture_file"
  chmod 600 "$fixture_file"
  user_ids["$bucket-$index"]="$id"
  rm -f "$response"
}

for ((i=1; i<=browse_n; i++)); do
  create_user browse "$i" '["buyer"]'
done
for ((i=1; i<=cart_n; i++)); do
  create_user cart "$i" '["buyer"]'
done
for ((i=1; i<=buy_n; i++)); do
  create_user buyNow "$i" '["buyer"]'
done
for ((i=1; i<=checkout_n; i++)); do
  create_user cartCheckout "$i" '["buyer"]'
done
for ((i=1; i<=seller_n; i++)); do
  create_user sellerProduct "$i" '["buyer"]'
done
for ((i=1; i<=application_n; i++)); do
  create_user sellerApplication "$i" '["buyer"]'
done

shops='[]'
for ((i=1; i<=seller_n; i++)); do
  seller_id="${user_ids[sellerProduct-$i]}"
  seller_jar="$approved_jar_dir/seller-$i.cookies"
  username="perf-${run_id}-sellerProduct-${i}"
  login_curl "$username" "$password" "$seller_jar"
  response="$(mktemp)"
  api_post "$seller_jar" /api/v2/sellers/applications \
    "$(jq -nc --arg name "${run_id}-approved-shop-$i" '{name:$name,description:"Performance approved seller"}')" 201 "$response"
  shop_id="$(jq -r '.data.id' "$response")"
  api_patch "$admin_jar" "/api/v2/sellers/applications/$shop_id" '{"status":"APPROVED","reason":"Performance fixture"}' 200 /dev/null
  shops="$(jq --arg id "$shop_id" --arg owner "$seller_id" '. += [{id:$id,ownerUserId:$owner}]' <<<"$shops")"
  jq --argjson shops "$shops" '.shops=$shops' "$fixture_file" > "$fixture_file.tmp"
  mv "$fixture_file.tmp" "$fixture_file"
  chmod 600 "$fixture_file"
  rm -f "$response"
done

products='[]'
for ((i=1; i<=product_n; i++)); do
  sku="${run_id}-product-$i"
  response="$(mktemp)"
  api_post "$admin_jar" /api/v2/products \
    "$(jq -nc --arg sku "$sku" --arg name "${run_id} Product $i" --arg category "$category" \
      --arg currency "$(jq -r '.currency' <<<"$config_json")" --argjson price "$product_price" --argjson quantity "$product_stock" \
      '{sku:$sku,name:$name,description:"Performance fixture",price:$price,currency:$currency,quantity:$quantity,category:$category,image_url:null}')" 201 "$response"
  product_id="$(jq -r '.id // .data.id' "$response")"
  products="$(jq --arg id "$product_id" --arg sku "$sku" --arg category "$category" --argjson price "$product_price" --argjson quantity "$product_stock" \
    '. += [{id:$id,sku:$sku,category:$category,price:$price,initialQuantity:$quantity}]' <<<"$products")"
  jq --argjson products "$products" '.products=$products' "$fixture_file" > "$fixture_file.tmp"
  mv "$fixture_file.tmp" "$fixture_file"
  chmod 600 "$fixture_file"
  rm -f "$response"
done

catalog_ready=0
last_product_id="$(jq -r '.[-1].id' <<<"$products")"
last_product_sku="$(jq -r '.[-1].sku' <<<"$products")"
for _ in $(seq 1 20); do
  detail_ok="$(curl "${CURL_RESOLVE[@]}" -sS -o /dev/null -w '%{http_code}' -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" \
    "$BASE_URL/api/v2/products/$last_product_id")"
  search_ok="$(curl "${CURL_RESOLVE[@]}" -fsS -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" \
    "$BASE_URL/api/v2/products?search=$last_product_sku&page_size=10" | jq --arg id "$last_product_id" '[.items[]? | select(.id == $id)] | length' || printf 0)"
  if [[ "$detail_ok" == 200 && "$search_ok" -gt 0 ]]; then
    catalog_ready=1
    break
  fi
  sleep 1
done
[[ "$catalog_ready" == 1 ]] || fail "catalog fixture did not become readable through detail and search APIs"

printf '%s\n' "$(date -u +%FT%TZ)" > "$RESULT_DIR/prepared.ok"
log "prepared fixture $run_id for $vus target VUs with seed $seed and category $category"
