#!/usr/bin/env bash
# RabbitMQ Restore Script
# Imports definitions (exchanges, queues, bindings, users, policies)
#
# Usage:
#   ./bin/rabbitmq-restore.sh <backup-path>
#   ./bin/rabbitmq-restore.sh backups/rabbitmq/20241227-120000
#   ./bin/rabbitmq-restore.sh --list    # List available backups

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
NAMESPACE="${NAMESPACE:-shopping-cart-data}"
RABBITMQ_POD="${RABBITMQ_POD:-rabbitmq-0}"
BACKUP_DIR="${PROJECT_DIR}/backups/rabbitmq"

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
    echo -e "${BLUE}RabbitMQ Restore Script${NC}"
    echo ""
    echo "Usage: $0 <backup-path> [options]"
    echo ""
    echo "Options:"
    echo "  --list        List available backups"
    echo "  --dry-run     Show what would be restored without applying"
    echo "  --force       Skip confirmation prompt"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --list                              # List backups"
    echo "  $0 backups/rabbitmq/20241227-120000    # Restore from backup"
    echo "  $0 backups/rabbitmq/20241227-120000 --dry-run"
}

list_backups() {
    echo -e "${BLUE}=== Available Backups ===${NC}"
    echo ""

    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_warn "No backups directory found at $BACKUP_DIR"
        return 1
    fi

    # List backup directories
    for backup in "$BACKUP_DIR"/*/; do
        if [[ -f "${backup}definitions.json" ]]; then
            timestamp=$(basename "$backup")
            size=$(du -sh "$backup" 2>/dev/null | cut -f1)
            queues=$(jq -r '.queues | length // 0' "${backup}definitions.json" 2>/dev/null || echo "?")
            exchanges=$(jq -r '.exchanges | length // 0' "${backup}definitions.json" 2>/dev/null || echo "?")
            echo "  $timestamp  (${size}, ${queues} queues, ${exchanges} exchanges)"
        fi
    done

    # List archives
    echo ""
    echo "Archives:"
    ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  (none)"
}

# Parse arguments
BACKUP_PATH=""
DRY_RUN=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --list)
            list_backups
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --force)
            FORCE=true
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
        *)
            BACKUP_PATH="$arg"
            ;;
    esac
done

# Validate backup path
if [[ -z "$BACKUP_PATH" ]]; then
    log_error "Backup path is required"
    usage
    exit 1
fi

# Handle archive files
if [[ "$BACKUP_PATH" == *.tar.gz ]]; then
    log_info "Extracting archive: $BACKUP_PATH"
    EXTRACT_DIR=$(mktemp -d)
    tar -xzf "$BACKUP_PATH" -C "$EXTRACT_DIR"
    BACKUP_PATH="$EXTRACT_DIR/$(ls "$EXTRACT_DIR")"
    log_info "Extracted to: $BACKUP_PATH"
fi

# Validate backup directory
if [[ ! -d "$BACKUP_PATH" ]]; then
    log_error "Backup directory not found: $BACKUP_PATH"
    exit 1
fi

if [[ ! -f "$BACKUP_PATH/definitions.json" ]]; then
    log_error "definitions.json not found in backup"
    exit 1
fi

# Show backup info
log_info "=== RabbitMQ Restore ==="
log_info "Backup path: $BACKUP_PATH"
log_info "Namespace: $NAMESPACE"
log_info "Pod: $RABBITMQ_POD"
echo ""

# Show backup metadata
if [[ -f "$BACKUP_PATH/metadata.json" ]]; then
    log_info "Backup metadata:"
    cat "$BACKUP_PATH/metadata.json" | jq -r '
        "  Timestamp: \(.timestamp)",
        "  Original namespace: \(.namespace)",
        "  Original pod: \(.pod)"
    ' 2>/dev/null || cat "$BACKUP_PATH/metadata.json"
    echo ""
fi

# Show what will be restored
log_info "Definitions to restore:"
jq -r '
    "  Users: \(.users | length // 0)",
    "  Vhosts: \(.vhosts | length // 0)",
    "  Exchanges: \(.exchanges | length // 0)",
    "  Queues: \(.queues | length // 0)",
    "  Bindings: \(.bindings | length // 0)",
    "  Policies: \(.policies | length // 0)"
' "$BACKUP_PATH/definitions.json" 2>/dev/null || log_warn "Could not parse definitions"
echo ""

# Dry run - just show info
if [[ "$DRY_RUN" == "true" ]]; then
    log_info "[DRY RUN] Would restore definitions from: $BACKUP_PATH"
    log_info "[DRY RUN] No changes made"
    exit 0
fi

# Confirmation
if [[ "$FORCE" != "true" ]]; then
    echo -e "${YELLOW}⚠ WARNING: This will import definitions into RabbitMQ.${NC}"
    echo "  - Existing definitions with same names will be OVERWRITTEN"
    echo "  - This may affect running applications"
    echo ""
    read -p "Continue with restore? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
fi

# Check RabbitMQ is accessible
if ! kubectl get pod -n "$NAMESPACE" "$RABBITMQ_POD" &>/dev/null; then
    log_error "RabbitMQ pod $RABBITMQ_POD not found in namespace $NAMESPACE"
    exit 1
fi

# Copy definitions to pod
log_info "Copying definitions to pod..."
kubectl cp "$BACKUP_PATH/definitions.json" \
    "$NAMESPACE/$RABBITMQ_POD:/tmp/definitions.json"

# Import definitions
log_info "Importing definitions..."
if kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl import_definitions /tmp/definitions.json 2>/dev/null; then
    log_info "  ✓ Definitions imported successfully"
else
    log_error "  ✗ Failed to import definitions"
    exit 1
fi

# Cleanup temp file on pod
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- rm -f /tmp/definitions.json 2>/dev/null || true

# Verify restore
log_info "Verifying restore..."
echo ""

log_info "Current queues:"
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_queues name messages consumers 2>/dev/null | head -15

echo ""
log_info "Current exchanges:"
kubectl exec -n "$NAMESPACE" "$RABBITMQ_POD" -- \
    rabbitmqctl list_exchanges name type 2>/dev/null | head -15

echo ""
log_info "=== Restore Complete ==="
log_info "Definitions have been imported from: $BACKUP_PATH"
echo ""
log_warn "Note: Messages are NOT restored - only definitions (queues, exchanges, bindings)"
