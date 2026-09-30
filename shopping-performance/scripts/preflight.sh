#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh

[[ "$CONTEXT" == "k3d-lab-k8s" ]] || fail "refusing context $CONTEXT"
[[ "$BASE_URL" == "http://shopping-cart.localhost:8080" ]] || fail "BASE_URL must remain local"
command -v kubectl >/dev/null || fail "kubectl unavailable"

kubectl --context "$CONTEXT" get namespace shopping-cart-apps >/dev/null
kubectl --context "$CONTEXT" -n shopping-cart-gateway wait gateway/nginx-gateway --for=condition=Programmed --timeout=60s >/dev/null
kubectl --context "$CONTEXT" -n vault exec vault-0 -- vault status -format=json | jq -e '.initialized == true and .sealed == false' >/dev/null

ready="$(kubectl --context "$CONTEXT" -n shopping-cart-apps get pods -o json | jq '[.items[] | select(.status.phase == "Running") | select(all(.status.containerStatuses[]?; .ready == true))] | length')"
total="$(kubectl --context "$CONTEXT" -n shopping-cart-apps get pods -o json | jq '[.items[] | select(.metadata.deletionTimestamp == null)] | length')"
[[ "$total" -gt 0 && "$ready" == "$total" ]] || fail "application pods are not all Ready ($ready/$total)"

curl "${CURL_RESOLVE[@]}" -fsS -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" "$BASE_URL/" >/dev/null
curl "${CURL_RESOLVE[@]}" -fsS -H "Host: $PUBLIC_HOST" -H "X-Forwarded-Host: $PUBLIC_HOST:8080" "$BASE_URL/api/v2/products?page=1&page_size=1" | jq -e '.items or .data' >/dev/null
mkdir -p "$RESULT_DIR"
kubectl --context "$CONTEXT" get pods -A -o wide > "$RESULT_DIR/baseline-pods.txt"
kubectl --context "$CONTEXT" get pvc -A > "$RESULT_DIR/baseline-pvc.txt"
printf '%s\n' "$(date -u +%FT%TZ)" > "$RESULT_DIR/preflight.ok"
log "preflight passed for $CONTEXT"
