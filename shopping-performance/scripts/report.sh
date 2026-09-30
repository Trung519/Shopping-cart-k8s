#!/usr/bin/env bash
set -euo pipefail
source /work/scripts/common.sh

summary="$RESULT_DIR/summary.json"
report="$RESULT_DIR/report.md"

python3 - "$summary" "$report" "$RESULT_DIR" "$RUN_ID" "${PROFILE:-unknown}" <<'PY'
import csv
import json
import sys
from pathlib import Path

summary_path, report_path, result_path, run_id, profile = sys.argv[1:]
result = Path(result_path)
summary = json.loads(Path(summary_path).read_text()) if Path(summary_path).exists() else {"metrics": {}}
metrics = summary.get("metrics", {})

def exit_code(name, fallback=125):
    path = result / name
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return fallback

def value(name, field, fallback=0):
    return metrics.get(name, {}).get(field, fallback)

k6_exit = exit_code('k6.exit')
verification_exit = exit_code('verification.exit')
cleanup_exit = exit_code('cleanup.exit')
status = 'PASS'
if cleanup_exit != 0:
    status = 'CLEANUP_FAILED'
elif k6_exit != 0 or verification_exit != 0:
    status = 'FAILED'

restart_delta = 'n/a'
min_ready = 'n/a'
csv_path = result / 'cluster-metrics.csv'
if csv_path.exists():
    rows = list(csv.DictReader(csv_path.open()))
    if rows:
        restart_delta = int(rows[-1]['app_restarts']) - int(rows[0]['app_restarts'])
        min_ready = min(int(row['app_ready']) for row in rows)

flow_rows = []
for flow in ('browse', 'cart', 'buy_now', 'cart_checkout', 'seller_product', 'seller_application'):
    metric = metrics.get(f'shopcart_flow_duration{{flow:{flow}}}', {})
    flow_rows.append((flow, metric.get('p(95)', 'n/a')))

lines = [
    f'# ShopCart Performance Report: `{run_id}`', '',
    f'**Status:** `{status}`  ',
    f'**Profile:** `{profile}`', '',
    '| Metric | Result |', '|---|---:|',
    f"| Total HTTP requests | `{value('http_reqs', 'count')}` |",
    f"| HTTP failure rate | `{100 * value('http_req_failed', 'value'):.2f}%` |",
    f"| Business success rate | `{100 * value('shopcart_business_success', 'value'):.2f}%` |",
    f"| HTTP request p95 | `{value('http_req_duration', 'p(95)', 'n/a')}` ms |",
    f"| Orders requested | `{value('shopcart_orders_requested', 'count')}` |",
    f"| Orders verified | `{value('shopcart_orders_verified', 'count')}` |",
    f"| Inventory verifications | `{value('shopcart_inventory_verified', 'count')}` |",
    f"| Duplicate orders | `{value('shopcart_duplicate_orders', 'count')}` |",
    f'| Pod restart delta | `{restart_delta}` |',
    f'| Minimum Ready pods | `{min_ready}` |',
    f'| k6 exit code | `{k6_exit}` |',
    f'| Verification exit code | `{verification_exit}` |',
    f'| Cleanup exit code | `{cleanup_exit}` |', '',
    '## Business Flow p95', '', '| Flow | p95 |', '|---|---:|',
]
lines.extend(f'| `{flow}` | `{p95}` ms |' for flow, p95 in flow_rows)
if profile == 'smoke':
    lines.extend(['', 'Smoke validates correctness only. Capacity requires a successful staged load profile.'])
elif status == 'PASS':
    lines.extend(['', 'This staged load profile met every configured threshold and post-run verification.'])
else:
    lines.extend(['', 'Capacity is not certified because this staged load profile failed one or more thresholds or post-run verifications.'])
Path(report_path).write_text('\n'.join(lines) + '\n')
PY
log "wrote $report"
