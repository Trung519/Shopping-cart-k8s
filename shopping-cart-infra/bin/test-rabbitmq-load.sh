#!/usr/bin/env bash
# RabbitMQ Load Test Helper
# Wrapper script with pre-configured environment for K8s cluster
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default configuration for K8s NodePort access
export RABBITMQ_HOST="${RABBITMQ_HOST:-localhost}"
export RABBITMQ_PORT="${RABBITMQ_PORT:-30672}"
export RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-demo}"
export RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-demo}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo -e "${BLUE}RabbitMQ Load Test Helper${NC}"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  quick         Quick test (50 msgs/sec for 5s)"
    echo "  burst         Burst test (1000 msgs/sec for 30s)"
    echo "  sustained     Sustained load (100 msgs/sec for 10 min)"
    echo "  stress        Stress test with ramp-up"
    echo "  trigger-alert Build queue to trigger alert (500 msgs/sec for 60s)"
    echo "  purge [queue] Purge all messages from queue (default: load-test-queue)"
    echo "  purge-count <n> [queue]  Purge first N messages from queue"
    echo "  purge-all     Purge messages from ALL queues (use with caution)"
    echo "  cleanup       Delete test queues and exchanges"
    echo "  status        Show RabbitMQ queue status"
    echo "  alerts        Show active Prometheus alerts"
    echo "  dashboard     Open Grafana dashboard (port-forward)"
    echo "  prometheus    Open Prometheus UI (port-forward)"
    echo ""
    echo "Options:"
    echo "  -d, --duration   Duration in seconds"
    echo "  -r, --rate       Messages per second"
    echo ""
    echo "Environment (auto-configured for K8s):"
    echo "  RABBITMQ_HOST=$RABBITMQ_HOST"
    echo "  RABBITMQ_PORT=$RABBITMQ_PORT"
    echo "  RABBITMQ_USERNAME=$RABBITMQ_USERNAME"
    echo ""
    echo "Examples:"
    echo "  $0 quick                    # Quick sanity test"
    echo "  $0 burst                    # Full burst test"
    echo "  $0 trigger-alert            # Build queue depth to trigger alert"
    echo "  $0 status                   # Check queue status"
    echo "  $0 purge                    # Purge all from load-test-queue"
    echo "  $0 purge myqueue            # Purge all from myqueue"
    echo "  $0 purge-count 100          # Purge first 100 from load-test-queue"
    echo "  $0 purge-count 50 myqueue   # Purge first 50 from myqueue"
}

check_rabbitmq() {
    echo -e "${GREEN}Checking RabbitMQ connection...${NC}"
    if curl -s -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
        "http://${RABBITMQ_HOST}:15672/api/overview" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ RabbitMQ is accessible${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Cannot reach RabbitMQ Management API at ${RABBITMQ_HOST}:15672${NC}"
        echo "  Trying AMQP port ${RABBITMQ_PORT}..."
        return 0
    fi
}

show_status() {
    echo -e "${BLUE}=== RabbitMQ Queue Status ===${NC}"
    echo ""

    # Try kubectl first
    if kubectl get pods -n shopping-cart-data 2>/dev/null | grep -q rabbitmq; then
        kubectl exec -n shopping-cart-data rabbitmq-0 -- \
            rabbitmqctl list_queues name messages consumers --formatter=pretty_table 2>/dev/null || \
        kubectl exec -n shopping-cart-data rabbitmq-0 -- \
            rabbitmqctl list_queues name messages consumers
    else
        # Fall back to management API
        curl -s -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
            "http://${RABBITMQ_HOST}:15672/api/queues" 2>/dev/null | \
            python3 -c "
import sys, json
try:
    queues = json.load(sys.stdin)
    print(f\"{'Queue':<40} {'Messages':>10} {'Consumers':>10}\")
    print('-' * 62)
    for q in queues:
        print(f\"{q['name']:<40} {q.get('messages',0):>10} {q.get('consumers',0):>10}\")
except:
    print('Unable to fetch queue status')
" 2>/dev/null || echo "Unable to connect to RabbitMQ"
    fi
}

show_alerts() {
    echo -e "${BLUE}=== Prometheus RabbitMQ Alerts ===${NC}"
    echo ""

    # Query Prometheus directly via kubectl exec (no port-forward needed)
    local prom_pod=$(kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -z "$prom_pod" ]]; then
        echo -e "${YELLOW}Prometheus pod not found in monitoring namespace${NC}"
        return 1
    fi

    # Fetch alerts via kubectl exec
    kubectl exec -n monitoring "$prom_pod" -- \
        wget -qO- 'http://localhost:9090/api/v1/rules?type=alert' 2>/dev/null | \
        python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"{'Alert Name':<35} {'State':>10} {'Severity':>10}  {'Details'}\")
print('-' * 80)
for group in data.get('data', {}).get('groups', []):
    if 'rabbitmq' in group.get('name', '').lower():
        for rule in group.get('rules', []):
            if rule.get('type') == 'alerting':
                name = rule.get('name', '')[:34]
                state = rule.get('state', 'unknown')
                severity = rule.get('labels', {}).get('severity', '-')
                alerts = rule.get('alerts', [])
                if alerts:
                    for a in alerts:
                        queue = a.get('labels', {}).get('queue', '')
                        detail = f'queue={queue}' if queue else ''
                        print(f\"{name:<35} {state:>10} {severity:>10}  {detail}\")
                else:
                    print(f\"{name:<35} {state:>10} {severity:>10}\")
"
}

open_dashboard() {
    echo -e "${BLUE}Opening Grafana Dashboard...${NC}"
    echo ""
    echo "Starting port-forward to Grafana..."
    echo "Open in browser: http://localhost:3000"
    echo "Dashboard: RabbitMQ Overview"
    echo ""
    echo "Press Ctrl+C to stop"
    kubectl port-forward -n monitoring svc/grafana 3000:3000
}

open_prometheus() {
    echo -e "${BLUE}Opening Prometheus UI...${NC}"
    echo ""
    echo "Starting port-forward to Prometheus..."
    echo "Open in browser: http://localhost:9090/alerts"
    echo ""
    echo "Press Ctrl+C to stop"
    kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
}

purge_queue() {
    local queue="${1:-load-test-queue}"
    echo -e "${BLUE}Purging queue: ${queue}${NC}"

    if kubectl get pods -n shopping-cart-data 2>/dev/null | grep -q rabbitmq; then
        # Get message count before purge
        local before=$(kubectl exec -n shopping-cart-data rabbitmq-0 -- \
            rabbitmqctl list_queues name messages --quiet 2>/dev/null | awk -v q="$queue" '$1==q {print $2}')

        # Purge the queue
        kubectl exec -n shopping-cart-data rabbitmq-0 -- \
            rabbitmqctl purge_queue "$queue" 2>/dev/null

        echo -e "${GREEN}✓ Purged ${before:-0} messages from ${queue}${NC}"
    else
        # Use management API
        curl -s -X DELETE -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
            "http://${RABBITMQ_HOST}:15672/api/queues/%2F/${queue}/contents" && \
            echo -e "${GREEN}✓ Purged messages from ${queue}${NC}" || \
            echo -e "${YELLOW}Failed to purge ${queue}${NC}"
    fi
}

purge_count() {
    local count="${1:-10}"
    local queue="${2:-load-test-queue}"

    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
        echo -e "${YELLOW}Error: count must be a positive integer${NC}"
        return 1
    fi

    echo -e "${BLUE}Purging first ${count} messages from queue: ${queue}${NC}"

    # Get current message count
    local before=$(kubectl exec -n shopping-cart-data rabbitmq-0 -- \
        rabbitmqctl list_queues name messages --quiet 2>/dev/null | awk -v q="$queue" '$1==q {print $2}' 2>/dev/null || echo "0")

    if [[ "$before" == "0" ]]; then
        echo -e "${YELLOW}Queue ${queue} is empty${NC}"
        return 0
    fi

    # Use Management API to get and ack N messages (removes them)
    # ack_requeue_false = acknowledge and don't requeue (effectively deletes)
    local purged=$(curl -s -X POST -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
        -H "content-type: application/json" \
        -d "{\"count\": ${count}, \"ackmode\": \"ack_requeue_false\", \"encoding\": \"auto\"}" \
        "http://${RABBITMQ_HOST}:15672/api/queues/%2F/${queue}/get" 2>/dev/null | \
        python3 -c "import sys,json; msgs=json.load(sys.stdin); print(len(msgs) if isinstance(msgs, list) else 0)" 2>/dev/null || echo "0")

    # Get count after
    local after=$(kubectl exec -n shopping-cart-data rabbitmq-0 -- \
        rabbitmqctl list_queues name messages --quiet 2>/dev/null | awk -v q="$queue" '$1==q {print $2}' 2>/dev/null || echo "0")

    echo -e "${GREEN}✓ Purged ${purged} messages from ${queue}${NC}"
    echo -e "   Before: ${before}, After: ${after}"
}

purge_all_queues() {
    echo -e "${YELLOW}⚠ WARNING: This will purge ALL messages from ALL queues!${NC}"
    echo ""
    read -p "Are you sure? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Aborted."
        return 1
    fi

    echo ""
    echo -e "${BLUE}Purging all queues...${NC}"

    if kubectl get pods -n shopping-cart-data 2>/dev/null | grep -q rabbitmq; then
        # Get list of queues with message counts
        kubectl exec -n shopping-cart-data rabbitmq-0 -- \
            rabbitmqctl list_queues name messages --quiet 2>/dev/null | while read -r queue messages; do
            if [[ -n "$queue" && "$messages" -gt 0 ]] 2>/dev/null; then
                echo -n "  Purging $queue ($messages messages)... "
                kubectl exec -n shopping-cart-data rabbitmq-0 -- \
                    rabbitmqctl purge_queue "$queue" 2>/dev/null && echo "done" || echo "failed"
            fi
        done
        echo -e "${GREEN}✓ All queues purged${NC}"
    else
        # Use management API
        curl -s -u "${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}" \
            "http://${RABBITMQ_HOST}:15672/api/queues" 2>/dev/null | \
            python3 -c "
import sys, json, urllib.request, base64

queues = json.load(sys.stdin)
auth = base64.b64encode('${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}'.encode()).decode()

for q in queues:
    name = q['name']
    messages = q.get('messages', 0)
    if messages > 0:
        url = f\"http://${RABBITMQ_HOST}:15672/api/queues/%2F/{name}/contents\"
        req = urllib.request.Request(url, method='DELETE')
        req.add_header('Authorization', f'Basic {auth}')
        try:
            urllib.request.urlopen(req)
            print(f'  Purged {name} ({messages} messages)')
        except Exception as e:
            print(f'  Failed to purge {name}: {e}')
"
        echo -e "${GREEN}✓ All queues purged${NC}"
    fi
}

# Parse command
COMMAND="${1:-}"
shift || true

case "$COMMAND" in
    quick)
        check_rabbitmq
        echo ""
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" burst -d 5 -r 50 "$@"
        ;;
    burst)
        check_rabbitmq
        echo ""
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" burst "$@"
        ;;
    sustained)
        check_rabbitmq
        echo ""
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" sustained "$@"
        ;;
    stress)
        check_rabbitmq
        echo ""
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" stress "$@"
        ;;
    trigger-alert)
        check_rabbitmq
        echo ""
        echo -e "${YELLOW}Building queue depth to trigger RabbitMQQueueDepthHigh alert...${NC}"
        echo "This will publish ~30,000 messages without consumers."
        echo ""
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" burst -d 60 -r 500 "$@"
        ;;
    purge)
        purge_queue "${1:-load-test-queue}"
        ;;
    purge-count)
        if [[ -z "$1" ]]; then
            echo -e "${YELLOW}Usage: $0 purge-count <count> [queue]${NC}"
            exit 1
        fi
        purge_count "$1" "${2:-load-test-queue}"
        ;;
    purge-all)
        purge_all_queues
        ;;
    cleanup)
        exec "$SCRIPT_DIR/load-test-rabbitmq.sh" cleanup
        ;;
    status)
        show_status
        ;;
    alerts)
        show_alerts
        ;;
    dashboard)
        open_dashboard
        ;;
    prometheus)
        open_prometheus
        ;;
    -h|--help|help|"")
        usage
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo ""
        usage
        exit 1
        ;;
esac
