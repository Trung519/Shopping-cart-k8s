#!/usr/bin/env bash
set -u

profile="${1:?profile is required}"
vus="${2:?VUS is required}"
run_id="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
seed="${SEED:-20260802}"
result_dir=".local/results/$run_id"
monitor_pid=""
k6_exit=125
verification_exit=125
cleanup_exit=125

mkdir -p "$result_dir"
printf '{"runId":"%s","profile":"%s"}\n' "$run_id" "$profile" > .local/active-run.json

finalize() {
  trap - EXIT INT TERM
  touch "$result_dir/.stop-monitor"
  if [[ -n "$monitor_pid" ]]; then
    wait "$monitor_pid" 2>/dev/null || true
  fi
  if [[ -f ".local/fixtures/$run_id.json" ]]; then
    make cleanup RUN_ID="$run_id" >/dev/null || cleanup_exit=$?
    [[ "$cleanup_exit" == 125 ]] && cleanup_exit=0
  else
    cleanup_exit=0
  fi
  printf '%s\n' "$k6_exit" > "$result_dir/k6.exit"
  printf '%s\n' "$verification_exit" > "$result_dir/verification.exit"
  printf '%s\n' "$cleanup_exit" > "$result_dir/cleanup.exit"
  make report RUN_ID="$run_id" PROFILE="$profile" >/dev/null || true
  printf '{"runId":"idle","profile":"idle"}\n' > .local/active-run.json
  if ((cleanup_exit != 0)); then exit 90; fi
  if ((k6_exit != 0)); then exit "$k6_exit"; fi
  if ((verification_exit != 0)); then exit "$verification_exit"; fi
}
trap finalize EXIT INT TERM

make up
make prepare RUN_ID="$run_id" VUS="$vus" PROFILE="$profile" SEED="$seed"
make monitor RUN_ID="$run_id" PROFILE="$profile" &
monitor_pid=$!
make k6-run RUN_ID="$run_id" PROFILE="$profile" || k6_exit=$?
[[ "$k6_exit" == 125 ]] && k6_exit=0
touch "$result_dir/.stop-monitor"
wait "$monitor_pid" 2>/dev/null || true
monitor_pid=""
make verify-run RUN_ID="$run_id" PROFILE="$profile" || verification_exit=$?
[[ "$verification_exit" == 125 ]] && verification_exit=0
