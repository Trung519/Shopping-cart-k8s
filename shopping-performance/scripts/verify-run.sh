#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh

summary="$RESULT_DIR/summary.json"
metrics="$RESULT_DIR/cluster-metrics.csv"
[[ -f "$summary" ]] || fail "summary.json is missing"

requested="$(jq -r '.metrics.shopcart_orders_requested.count // 0' "$summary")"
verified="$(jq -r '.metrics.shopcart_orders_verified.count // 0' "$summary")"
duplicates="$(jq -r '.metrics.shopcart_duplicate_orders.count // 0' "$summary")"
business="$(jq -r '.metrics.shopcart_business_success.value // 0' "$summary")"
[[ "$requested" -gt 0 && "$requested" == "$verified" ]] || fail "orders requested/verified mismatch ($requested/$verified)"
[[ "$duplicates" == 0 ]] || fail "duplicate orders detected: $duplicates"
awk -v value="$business" 'BEGIN {exit !(value >= 0.99)}' || fail "business success below 99%: $business"

if [[ -f "$metrics" ]] && [[ "$(wc -l < "$metrics")" -gt 2 ]]; then
  baseline_restarts="$(awk -F, 'NR==2 {print $5}' "$metrics")"
  final_restarts="$(awk -F, 'END {print $5}' "$metrics")"
  min_ready="$(awk -F, 'NR>1 {if (min=="" || $4<min) min=$4} END {print min+0}' "$metrics")"
  expected_ready="$(awk -F, 'NR==2 {print $4}' "$metrics")"
  [[ "$final_restarts" == "$baseline_restarts" ]] || fail "pod restart count changed ($baseline_restarts -> $final_restarts)"
  [[ "$min_ready" == "$expected_ready" ]] || fail "Ready pod count dipped ($expected_ready -> $min_ready)"
fi

printf '%s\n' "$(date -u +%FT%TZ)" > "$RESULT_DIR/verification.ok"
log "verified run $RUN_ID: orders=$verified business=$business duplicates=$duplicates"
