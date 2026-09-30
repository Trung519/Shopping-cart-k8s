#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh
mkdir -p "$RESULT_DIR"
output="$RESULT_DIR/cluster-metrics.csv"
printf 'timestamp,node_cpu,node_memory,app_ready,app_restarts\n' > "$output"
stop_file="$RESULT_DIR/.stop-monitor"
rm -f "$stop_file"
trap 'rm -f "$stop_file"' EXIT
while [[ ! -f "$stop_file" ]]; do
  ts="$(date -u +%FT%TZ)"
  node="$(kubectl --context "$CONTEXT" top nodes --no-headers 2>/dev/null | awk '{gsub(/%/,"",$3); gsub(/%/,"",$5); cpu+=$3; mem+=$5} END {print cpu "," mem}')"
  app="$(kubectl --context "$CONTEXT" -n shopping-cart-apps get pods -o json 2>/dev/null | jq -r '[.items[] | select(.metadata.deletionTimestamp == null) | select(.status.phase == "Running") | select(all(.status.containerStatuses[]?; .ready == true))] | length')"
  restarts="$(kubectl --context "$CONTEXT" -n shopping-cart-apps get pods -o json 2>/dev/null | jq '[.items[].status.containerStatuses[]?.restartCount] | add // 0')"
  IFS=, read -r node_cpu node_memory <<<"$node"
  printf '%s,%s,%s,%s,%s\n' "$ts" "$node_cpu" "$node_memory" "$app" "$restarts" >> "$output"
  sleep 5
done
