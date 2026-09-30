#!/usr/bin/env bash
# RabbitMQ Load Testing Script
# Usage: ./load-test-rabbitmq.sh [scenario] [duration]
#
# Scenarios:
#   burst     - High-volume burst test (1000 msgs/sec for 30s)
#   sustained - Sustained load test (100 msgs/sec for 10min)
#   stress    - Stress test with consumer lag simulation
#   recovery  - Test recovery after consumer failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
RABBITMQ_HOST="${RABBITMQ_HOST:-localhost}"
RABBITMQ_PORT="${RABBITMQ_PORT:-30672}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-guest}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
RABBITMQ_VHOST="${RABBITMQ_VHOST:-/}"

# Test configuration
EXCHANGE="load-test-exchange"
QUEUE="load-test-queue"
ROUTING_KEY="load.test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "RabbitMQ Load Testing Script"
    echo ""
    echo "Usage: $0 [scenario] [options]"
    echo ""
    echo "Scenarios:"
    echo "  burst       High-volume burst test (1000 msgs/sec for 30s)"
    echo "  sustained   Sustained load test (100 msgs/sec for 10min)"
    echo "  stress      Stress test with increasing load"
    echo "  recovery    Test recovery after consumer failure"
    echo "  cleanup     Clean up test queues and exchanges"
    echo ""
    echo "Options:"
    echo "  -d, --duration   Test duration in seconds (default varies by scenario)"
    echo "  -r, --rate       Messages per second (default varies by scenario)"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  RABBITMQ_HOST      RabbitMQ host (default: localhost)"
    echo "  RABBITMQ_PORT      RabbitMQ port (default: 30672)"
    echo "  RABBITMQ_USERNAME  Username (default: guest)"
    echo "  RABBITMQ_PASSWORD  Password (default: guest)"
    echo ""
    echo "Examples:"
    echo "  $0 burst                    # Run burst test with defaults"
    echo "  $0 sustained -d 300         # Run sustained test for 5 minutes"
    echo "  $0 stress -r 500            # Run stress test at 500 msgs/sec"
}

check_dependencies() {
    # Check if we have a RabbitMQ client library available
    if command -v python3 &> /dev/null; then
        if python3 -c "import pika" 2>/dev/null; then
            PUBLISHER="python"
            return 0
        fi
    fi

    if command -v go &> /dev/null; then
        PUBLISHER="go"
        return 0
    fi

    log_error "No RabbitMQ client available. Install Python pika or Go amqp library."
    exit 1
}

setup_test_infrastructure() {
    log_info "Setting up test infrastructure..."

    # Create exchange and queue using rabbitmqadmin or management API
    if command -v curl &> /dev/null; then
        local api_url="http://${RABBITMQ_HOST}:15672/api"
        local auth="${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}"

        # Create exchange
        curl -s -u "$auth" -X PUT "$api_url/exchanges/%2F/$EXCHANGE" \
            -H "content-type: application/json" \
            -d '{"type":"topic","durable":true}' || true

        # Create queue
        curl -s -u "$auth" -X PUT "$api_url/queues/%2F/$QUEUE" \
            -H "content-type: application/json" \
            -d '{"durable":true}' || true

        # Create binding
        curl -s -u "$auth" -X POST "$api_url/bindings/%2F/e/$EXCHANGE/q/$QUEUE" \
            -H "content-type: application/json" \
            -d "{\"routing_key\":\"$ROUTING_KEY\"}" || true

        log_info "Test infrastructure ready"
    else
        log_warn "curl not found, skipping infrastructure setup"
    fi
}

get_queue_stats() {
    if command -v curl &> /dev/null; then
        local api_url="http://${RABBITMQ_HOST}:15672/api"
        local auth="${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}"

        curl -s -u "$auth" "$api_url/queues/%2F/$QUEUE" 2>/dev/null | \
            python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Messages: {d.get('messages',0)}, Consumers: {d.get('consumers',0)}, Rate: {d.get('message_stats',{}).get('publish_details',{}).get('rate',0):.1f}/s\")" 2>/dev/null || \
            echo "Unable to get queue stats"
    fi
}

run_python_publisher() {
    local rate=$1
    local duration=$2
    local message_size=${3:-256}

    python3 << EOF
import pika
import json
import time
import sys
from datetime import datetime

# Connection
credentials = pika.PlainCredentials('${RABBITMQ_USERNAME}', '${RABBITMQ_PASSWORD}')
parameters = pika.ConnectionParameters(
    host='${RABBITMQ_HOST}',
    port=${RABBITMQ_PORT},
    virtual_host='${RABBITMQ_VHOST}',
    credentials=credentials
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()

# Enable publisher confirms
channel.confirm_delivery()

# Prepare message
message_body = {
    'type': 'load-test',
    'timestamp': None,
    'sequence': 0,
    'payload': 'x' * ${message_size}
}

rate = ${rate}
duration = ${duration}
interval = 1.0 / rate if rate > 0 else 0
end_time = time.time() + duration

published = 0
errors = 0
start_time = time.time()

print(f"Starting load test: {rate} msgs/sec for {duration}s")

try:
    while time.time() < end_time:
        loop_start = time.time()

        message_body['timestamp'] = datetime.utcnow().isoformat()
        message_body['sequence'] = published

        try:
            channel.basic_publish(
                exchange='${EXCHANGE}',
                routing_key='${ROUTING_KEY}',
                body=json.dumps(message_body),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            published += 1
        except Exception as e:
            errors += 1

        # Rate limiting
        elapsed = time.time() - loop_start
        if elapsed < interval:
            time.sleep(interval - elapsed)

        # Progress update every 1000 messages
        if published % 1000 == 0:
            actual_rate = published / (time.time() - start_time)
            print(f"  Published: {published}, Rate: {actual_rate:.1f}/s, Errors: {errors}")

except KeyboardInterrupt:
    print("\nInterrupted by user")

finally:
    elapsed = time.time() - start_time
    actual_rate = published / elapsed if elapsed > 0 else 0

    print(f"\n=== Load Test Complete ===")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Published: {published}")
    print(f"Errors: {errors}")
    print(f"Actual rate: {actual_rate:.1f} msgs/sec")
    print(f"Target rate: {rate} msgs/sec")

    connection.close()
EOF
}

run_burst_test() {
    local rate=${1:-1000}
    local duration=${2:-30}

    log_info "=== Burst Test ==="
    log_info "Rate: $rate msgs/sec"
    log_info "Duration: ${duration}s"
    log_info "Expected messages: $((rate * duration))"
    echo ""

    setup_test_infrastructure

    log_info "Starting burst test..."
    run_python_publisher "$rate" "$duration"

    echo ""
    log_info "Queue stats after test:"
    get_queue_stats
}

run_sustained_test() {
    local rate=${1:-100}
    local duration=${2:-600}

    log_info "=== Sustained Load Test ==="
    log_info "Rate: $rate msgs/sec"
    log_info "Duration: ${duration}s ($((duration / 60)) minutes)"
    log_info "Expected messages: $((rate * duration))"
    echo ""

    setup_test_infrastructure

    log_info "Starting sustained test..."
    run_python_publisher "$rate" "$duration"

    echo ""
    log_info "Queue stats after test:"
    get_queue_stats
}

run_stress_test() {
    local max_rate=${1:-500}
    local duration=${2:-300}

    log_info "=== Stress Test ==="
    log_info "Max rate: $max_rate msgs/sec"
    log_info "Duration: ${duration}s"
    echo ""

    setup_test_infrastructure

    # Ramp up load in stages
    local stages=5
    local stage_duration=$((duration / stages))

    for i in $(seq 1 $stages); do
        local stage_rate=$((max_rate * i / stages))
        log_info "Stage $i/$stages: $stage_rate msgs/sec for ${stage_duration}s"
        run_python_publisher "$stage_rate" "$stage_duration"

        echo ""
        log_info "Queue stats after stage $i:"
        get_queue_stats
        echo ""

        # Brief pause between stages
        sleep 2
    done

    log_info "Stress test complete"
}

run_recovery_test() {
    log_info "=== Recovery Test ==="
    log_info "This test simulates consumer failure and recovery"
    echo ""

    setup_test_infrastructure

    # Phase 1: Build up messages
    log_info "Phase 1: Building up message backlog (no consumers)..."
    run_python_publisher 500 30

    echo ""
    log_info "Queue stats after backlog build:"
    get_queue_stats

    # Phase 2: Simulate consumer processing
    log_info ""
    log_info "Phase 2: In production, start consumers now to process backlog"
    log_info "Monitor queue depth in Grafana to verify recovery"
    log_info ""
    log_info "Expected behavior:"
    log_info "  1. Queue depth should decrease as consumers process messages"
    log_info "  2. Consumer rate should match or exceed publish rate"
    log_info "  3. Memory usage should stabilize"
}

cleanup() {
    log_info "Cleaning up test resources..."

    if command -v curl &> /dev/null; then
        local api_url="http://${RABBITMQ_HOST}:15672/api"
        local auth="${RABBITMQ_USERNAME}:${RABBITMQ_PASSWORD}"

        # Delete queue
        curl -s -u "$auth" -X DELETE "$api_url/queues/%2F/$QUEUE" || true

        # Delete exchange
        curl -s -u "$auth" -X DELETE "$api_url/exchanges/%2F/$EXCHANGE" || true

        log_info "Cleanup complete"
    else
        log_warn "curl not found, manual cleanup required"
    fi
}

# Parse arguments
SCENARIO="${1:-}"
DURATION=""
RATE=""

shift || true

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -r|--rate)
            RATE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run scenario
case "$SCENARIO" in
    burst)
        check_dependencies
        run_burst_test "${RATE:-1000}" "${DURATION:-30}"
        ;;
    sustained)
        check_dependencies
        run_sustained_test "${RATE:-100}" "${DURATION:-600}"
        ;;
    stress)
        check_dependencies
        run_stress_test "${RATE:-500}" "${DURATION:-300}"
        ;;
    recovery)
        check_dependencies
        run_recovery_test
        ;;
    cleanup)
        cleanup
        ;;
    "")
        usage
        exit 1
        ;;
    *)
        log_error "Unknown scenario: $SCENARIO"
        usage
        exit 1
        ;;
esac
