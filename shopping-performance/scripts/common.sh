#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://shopping-cart.localhost:8080}"
PUBLIC_HOST="${PUBLIC_HOST:-shopping-cart.localhost}"
KEYCLOAK_HOST="${KEYCLOAK_HOST:-keycloak.localhost}"
HOST_IP="$(getent hosts host.docker.internal | awk 'NR == 1 {print $1}')"
[[ -n "$HOST_IP" ]] || HOST_IP="127.0.0.1"
CURL_RESOLVE=(--resolve "${PUBLIC_HOST}:8080:${HOST_IP}" --resolve "${KEYCLOAK_HOST}:8080:${HOST_IP}")
CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="/work"
FIXTURE_DIR="$ROOT_DIR/.local/fixtures"
RESULT_DIR="$ROOT_DIR/.local/results/${RUN_ID:-manual}"

log() { printf '[performance] %s\n' "$*"; }
fail() { printf '[performance] ERROR: %s\n' "$*" >&2; exit 1; }

login_curl() {
  local username="$1" password="$2" jar="$3" html action
  html="$(mktemp)"
  curl "${CURL_RESOLVE[@]}" --retry 5 --retry-all-errors --retry-delay 1 -fsSL -c "$jar" -b "$jar" "$BASE_URL/api/v2/auth/login" -o "$html"
  action="$(python3 - "$html" <<'PY'
import html
import sys
from html.parser import HTMLParser

class Parser(HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        if tag == 'form' and self.action is None:
            self.action = dict(attrs).get('action')

p = Parser()
p.feed(open(sys.argv[1], encoding='utf-8').read())
if not p.action:
    raise SystemExit('OIDC form not found')
print(html.unescape(p.action))
PY
  )"
  local auth_html="$(mktemp)"
  curl "${CURL_RESOLVE[@]}" --retry 5 --retry-all-errors --retry-delay 1 -fsSL -c "$jar" -b "$jar" \
    --data-urlencode "username=$username" --data-urlencode "password=$password" \
    --data-urlencode credentialId= "$action" -o "$auth_html"
  if grep -q 'name="password-new"' "$auth_html"; then
    local update_action
    update_action="$(python3 - "$auth_html" <<'PY'
import html
import sys
from html.parser import HTMLParser

class Parser(HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        if tag == "form" and self.action is None:
            self.action = dict(attrs).get("action")

p = Parser()
p.feed(open(sys.argv[1], encoding="utf-8").read())
print(html.unescape(p.action or ""))
PY
    )"
    curl "${CURL_RESOLVE[@]}" --retry 5 --retry-all-errors --retry-delay 1 -fsSL -c "$jar" -b "$jar" \
      --data-urlencode "password-new=$password" --data-urlencode "password-confirm=$password" \
      --data-urlencode submitAction=Submit "$update_action" -o /dev/null
  fi
  rm -f "$auth_html"
  local me_body="$(mktemp)"
  curl "${CURL_RESOLVE[@]}" --retry 5 --retry-all-errors --retry-delay 1 -sS -b "$jar" -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" "$BASE_URL/api/v2/auth/me" -o "$me_body"
  if ! jq -e '.data.username | ascii_downcase == "'"${username,,}"'"' "$me_body" >/dev/null; then
    printf '[performance] login_session_failed user=%s response=' "$username" >&2
    jq -c '{keys:keys,data:(.data // null),message:(.message // null),error:(.error // null)}' "$me_body" >&2 || true
    rm -f "$me_body"
    return 1
  fi
  rm -f "$me_body"
  rm -f "$html"
}

api_post() {
  local jar="$1" path="$2" payload="$3" expected="$4" output="$5" code
  code="$(curl "${CURL_RESOLVE[@]}" -sS -o "$output" -w '%{http_code}' -b "$jar" -c "$jar" -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" \
    -H 'Content-Type: application/json' -d "$payload" "$BASE_URL$path")"
  [[ "$code" == "$expected" ]] || { printf '[performance] api_post_failed path=%s status=%s\n' "$path" "$code" >&2; cat "$output" >&2; return 1; }
}

api_patch() {
  local jar="$1" path="$2" payload="$3" expected="$4" output="$5" code
  code="$(curl "${CURL_RESOLVE[@]}" -sS -o "$output" -w '%{http_code}' -b "$jar" -c "$jar" -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" \
    -X PATCH -H 'Content-Type: application/json' -d "$payload" "$BASE_URL$path")"
  [[ "$code" == "$expected" ]] || { printf '[performance] api_patch_failed path=%s status=%s\n' "$path" "$code" >&2; cat "$output" >&2; return 1; }
}

psql_orders() {
  kubectl --context "$CONTEXT" -n shopping-cart-data exec postgresql-orders-0 -- sh -lc \
    "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d orders -v ON_ERROR_STOP=1 -Atc \"$1\""
}

psql_products() {
  kubectl --context "$CONTEXT" -n shopping-cart-data exec postgresql-products-0 -- sh -lc \
    "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" /opt/bitnami/postgresql/bin/psql -U postgres -d products -v ON_ERROR_STOP=1 -Atc \"$1\""
}

psql_marketplace() {
  kubectl --context "$CONTEXT" -n shopping-cart-data exec postgresql-marketplace-0 -- sh -lc \
    "PGPASSWORD=\"\$SELLER_DB_PASSWORD\" psql -U \"\$SELLER_DB_USER\" -d \"\$SELLER_DB_NAME\" -v ON_ERROR_STOP=1 -Atc \"$1\""
}
