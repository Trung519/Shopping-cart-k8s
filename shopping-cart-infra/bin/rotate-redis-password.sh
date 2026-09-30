#!/bin/bash
# rotate-redis-password.sh - Rotate Redis password via Vault
#
# This script:
# 1. Generates a new random password
# 2. Updates the password in Vault KV
# 3. Updates Redis with the new password (if accessible)
# 4. Triggers ExternalSecret refresh
# 5. Optionally restarts dependent services
#
# Prerequisites:
# - vault CLI configured and authenticated
# - kubectl configured with cluster access
# - Redis accessible via port-forward or directly
#
# Usage:
#   ./rotate-redis-password.sh [--instance cart|orders-cache] [--restart-services]
#
# Environment variables:
#   VAULT_ADDR       - Vault server address (default: http://vault.identity:8200)
#   VAULT_TOKEN      - Vault authentication token
#   REDIS_INSTANCE   - Redis instance name: cart, orders-cache (default: cart)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Defaults
REDIS_INSTANCE="${REDIS_INSTANCE:-cart}"
VAULT_ADDR="${VAULT_ADDR:-http://vault.identity.svc.cluster.local:8200}"
RESTART_SERVICES=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance)
            REDIS_INSTANCE="$2"
            shift 2
            ;;
        --restart-services)
            RESTART_SERVICES=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--instance cart|orders-cache] [--restart-services] [--dry-run]"
            echo ""
            echo "Options:"
            echo "  --instance NAME      Redis instance (cart, orders-cache)"
            echo "  --restart-services   Restart dependent services after rotation"
            echo "  --dry-run            Show what would be done without making changes"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate instance
case $REDIS_INSTANCE in
    cart)
        VAULT_PATH="secret/data/redis/cart"
        K8S_SECRET="redis-cart-secret"
        K8S_NAMESPACE="shopping-cart-data"
        REDIS_SERVICE="redis-cart"
        DEPENDENT_SERVICES=("basket-service")
        DEPLOYMENT_NAMESPACE="shopping-cart-apps"
        ;;
    orders-cache)
        VAULT_PATH="secret/data/redis/orders-cache"
        K8S_SECRET="redis-orders-cache-secret"
        K8S_NAMESPACE="shopping-cart-data"
        REDIS_SERVICE="redis-orders-cache"
        DEPENDENT_SERVICES=("order-service")
        DEPLOYMENT_NAMESPACE="shopping-cart-apps"
        ;;
    *)
        echo -e "${RED}Unknown Redis instance: $REDIS_INSTANCE${NC}"
        echo "Valid instances: cart, orders-cache"
        exit 1
        ;;
esac

echo -e "${GREEN}Redis Password Rotation${NC}"
echo "========================"
echo "Instance:    $REDIS_INSTANCE"
echo "Vault path:  $VAULT_PATH"
echo "K8s secret:  $K8S_SECRET"
echo ""

# Check prerequisites
if ! command -v vault &> /dev/null; then
    echo -e "${RED}Error: vault CLI not found${NC}"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

# Generate new password (32 chars, alphanumeric)
NEW_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
echo -e "${YELLOW}Generated new password${NC}"

if $DRY_RUN; then
    echo ""
    echo -e "${YELLOW}DRY RUN - No changes will be made${NC}"
    echo ""
    echo "Would execute:"
    echo "  1. vault kv put $VAULT_PATH password=<new-password>"
    echo "  2. Update Redis CONFIG SET requirepass"
    echo "  3. kubectl annotate externalsecret $REDIS_INSTANCE --overwrite force-sync=$(date +%s)"
    if $RESTART_SERVICES; then
        for svc in "${DEPENDENT_SERVICES[@]}"; do
            echo "  4. kubectl rollout restart deployment/$svc"
        done
    fi
    exit 0
fi

# Step 1: Get current password from Vault
echo -e "\n${GREEN}Step 1: Reading current password from Vault${NC}"
CURRENT_PASSWORD=$(vault kv get -field=password "$VAULT_PATH" 2>/dev/null || echo "")
if [ -z "$CURRENT_PASSWORD" ]; then
    echo -e "${YELLOW}No existing password found, this might be initial setup${NC}"
fi

# Step 2: Update password in Vault
echo -e "\n${GREEN}Step 2: Updating password in Vault${NC}"
vault kv put "$VAULT_PATH" password="$NEW_PASSWORD"
echo "  Vault updated successfully"

# Step 3: Update Redis password (if accessible)
echo -e "\n${GREEN}Step 3: Updating Redis password${NC}"

# Try to connect to Redis and update password
# Start port-forward in background
kubectl port-forward -n "$K8S_NAMESPACE" "svc/$REDIS_SERVICE" 16379:6379 &
PF_PID=$!
sleep 2

# Update Redis password
if [ -n "$CURRENT_PASSWORD" ]; then
    # Authenticate with current password, then change it
    redis-cli -p 16379 -a "$CURRENT_PASSWORD" CONFIG SET requirepass "$NEW_PASSWORD" 2>/dev/null && \
        echo "  Redis password updated" || \
        echo -e "${YELLOW}  Warning: Could not update Redis password directly${NC}"
else
    # No current password, set new one
    redis-cli -p 16379 CONFIG SET requirepass "$NEW_PASSWORD" 2>/dev/null && \
        echo "  Redis password set" || \
        echo -e "${YELLOW}  Warning: Could not set Redis password directly${NC}"
fi

# Kill port-forward
kill $PF_PID 2>/dev/null || true

# Step 4: Trigger ExternalSecret refresh
echo -e "\n${GREEN}Step 4: Triggering ExternalSecret refresh${NC}"
kubectl annotate externalsecret -n "$K8S_NAMESPACE" "${REDIS_INSTANCE}" \
    --overwrite force-sync="$(date +%s)"
echo "  ExternalSecret refresh triggered"

# Wait for sync
echo "  Waiting for secret sync..."
sleep 5

# Verify new secret
NEW_SECRET_PASSWORD=$(kubectl get secret -n "$K8S_NAMESPACE" "$K8S_SECRET" -o jsonpath='{.data.password}' | base64 -d)
if [ "$NEW_SECRET_PASSWORD" = "$NEW_PASSWORD" ]; then
    echo -e "  ${GREEN}Secret synced successfully${NC}"
else
    echo -e "  ${YELLOW}Warning: Secret may not have synced yet. Check ExternalSecret status.${NC}"
fi

# Step 5: Restart dependent services (optional)
if $RESTART_SERVICES; then
    echo -e "\n${GREEN}Step 5: Restarting dependent services${NC}"
    for svc in "${DEPENDENT_SERVICES[@]}"; do
        echo "  Restarting $svc in $DEPLOYMENT_NAMESPACE..."
        kubectl rollout restart deployment/"$svc" -n "$DEPLOYMENT_NAMESPACE" 2>/dev/null || \
            echo -e "  ${YELLOW}Warning: Could not restart $svc (may not exist)${NC}"
    done
fi

echo ""
echo -e "${GREEN}Password rotation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify applications can connect to Redis"
echo "  2. Check application logs for connection errors"
echo "  3. Run: kubectl get externalsecret -n $K8S_NAMESPACE $REDIS_INSTANCE"
