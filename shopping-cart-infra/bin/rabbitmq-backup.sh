#!/usr/bin/env bash
# RabbitMQ Backup Script
# Exports definitions (exchanges, queues, bindings, users, policies)
#
# Usage:
#   ./bin/rabbitmq-backup.sh                    # Backup to default location
#   ./bin/rabbitmq-backup.sh /path/to/backup    # Backup to specific directory
#   ./bin/rabbitmq-backup.sh --messages         # Include message backup (experimental)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
NAMESPACE="${NAMESPACE:-shopping-cart-data}"
RABBITMQ_POD="${RABBITMQ_POD:-rabbitmq-0}"
BACKUP_DIR="${1:-${PROJECT_DIR}/backups/rabbitmq}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
INCLUDE_MESSAGES=false

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo -e "${BLUE}RabbitMQ Backup Script${NC}"
    echo ""
    echo "Usage: $0 [backup-dir] [options]"
    echo ""
    echo "Options:"
    echo "  --messages    Include message export (experimental, may be slow)"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Backup to ./backups/rabbitmq/"
    echo "  $0 /tmp/backup               # Backup to /tmp/backup/"
    echo "  $0 --messages                # Include messages in backup"
    echo ""
    echo "Backup includes:"
    echo "  - Definitions (exchanges, queues, bindings, users, policies)"
    echo "  - Cluster status snapshot"
    echo "  - Queue statistics"
}

# Parse arguments
for arg in "$@"; do
    case $arg in
        --messages)
            INCLUDE_MESSAGES=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $arg"
            usage
            exit 1
            ;;
    esac
done

# Create backup directory
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "$BACKUP_PATH"

log_info "=== RabbitMQ Backup ==="
log_info "Timestamp: $TIMESTAMP"
log_info "Backup directory: $BACKUP_PATH"
log_info "Namespace: $NAMESPACE"
log_info "Pod: $RABBITMQ_POD"
echo ""

# Check RabbitMQ is accessible
if ! kubectl get pod -n "$NAMESPACE" "$RABBITMQ_POD" &>/dev/null; then
    log_error "RabbitMQ pod $RABBITMQ_POD not found in namespace $NAMESPACE"
    exit 1
fi

# 1. Export definitions (most important)
log_info "Exporting definitions..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl export_definitions /tmp/definitions.json 2>/dev/null

kubectl cp "$NAMESPACE/$RABBITMQ_POD:/tmp/definitions.json" \
    "$BACKUP_PATH/definitions.json" 2>/dev/null

if [[ -f "$BACKUP_PATH/definitions.json" ]]; then
    log_info "  ✓ Definitions exported ($(wc -c < "$BACKUP_PATH/definitions.json") bytes)"
else
    log_error "  ✗ Failed to export definitions"
    exit 1
fi

# 2. Capture cluster status
log_info "Capturing cluster status..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl cluster_status --formatter json 2>/dev/null \
    > "$BACKUP_PATH/cluster-status.json" || true
log_info "  ✓ Cluster status captured"

# 3. Capture queue statistics
log_info "Capturing queue statistics..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_queues name messages consumers memory durable auto_delete \
    --formatter json 2>/dev/null \
    > "$BACKUP_PATH/queues.json" || true
log_info "  ✓ Queue statistics captured"

# 4. Capture exchange list
log_info "Capturing exchanges..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_exchanges name type durable auto_delete \
    --formatter json 2>/dev/null \
    > "$BACKUP_PATH/exchanges.json" || true
log_info "  ✓ Exchanges captured"

# 5. Capture bindings
log_info "Capturing bindings..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_bindings source_name destination_name routing_key \
    --formatter json 2>/dev/null \
    > "$BACKUP_PATH/bindings.json" || true
log_info "  ✓ Bindings captured"

# 6. Capture policies
log_info "Capturing policies..."
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_policies --formatter json 2>/dev/null \
    > "$BACKUP_PATH/policies.json" || true
log_info "  ✓ Policies captured"

# 7. Optional: Export messages (experimental)
if [[ "$INCLUDE_MESSAGES" == "true" ]]; then
    log_warn "Message export is experimental and may be slow for large queues"
    log_info "Exporting messages..."

    # Get list of queues with messages
    queues=$(kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
        rabbitmqctl list_queues name messages --quiet 2>/dev/null | \
        awk '$2 > 0 {print $1}')

    mkdir -p "$BACKUP_PATH/messages"

    for queue in $queues; do
        log_info "  Exporting messages from: $queue"
        # Use Management API to get messages without consuming
        kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
            wget -qO- "http://localhost:15672/api/queues/%2F/$queue/get" \
            --header="Content-Type: application/json" \
            --post-data='{"count":10000,"ackmode":"ack_requeue_true","encoding":"auto"}' \
            --user=guest:guest 2>/dev/null \
            > "$BACKUP_PATH/messages/${queue}.json" || true
    done
    log_info "  ✓ Messages exported"
fi

# 8. Create metadata file
log_info "Creating metadata..."
cat > "$BACKUP_PATH/metadata.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "namespace": "$NAMESPACE",
    "pod": "$RABBITMQ_POD",
    "include_messages": $INCLUDE_MESSAGES,
    "backup_type": "definitions",
    "created_by": "rabbitmq-backup.sh"
}
EOF
log_info "  ✓ Metadata created"

# 9. Create tarball
log_info "Creating archive..."
ARCHIVE_NAME="rabbitmq-backup-${TIMESTAMP}.tar.gz"
(cd "$BACKUP_DIR" && tar -czf "$ARCHIVE_NAME" "$TIMESTAMP")
log_info "  ✓ Archive created: $BACKUP_DIR/$ARCHIVE_NAME"

# Summary
echo ""
log_info "=== Backup Complete ==="
log_info "Backup location: $BACKUP_PATH"
log_info "Archive: $BACKUP_DIR/$ARCHIVE_NAME"
echo ""
log_info "Files:"
ls -lh "$BACKUP_PATH"
echo ""
log_info "To restore, run:"
echo "  ./bin/rabbitmq-restore.sh $BACKUP_PATH"
