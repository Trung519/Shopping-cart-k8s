#!/usr/bin/env bash
# Deploy Shopping Cart Infrastructure
# Automated deployment and testing script

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

function print_success() { echo -e "${GREEN}✓ $1${NC}"; }
function print_error() { echo -e "${RED}✗ $1${NC}"; }
function print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Configuration
NAMESPACE_DATA="shopping-cart-data"
TIMEOUT="300s"
VAULT_DEPLOYED="${VAULT_DEPLOYED:-true}"
SKIP_VAULT_SETUP="${SKIP_VAULT_SETUP:-false}"

# Parse arguments
CLEANUP=false
DRY_RUN=false
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-vault)
            SKIP_VAULT_SETUP=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cleanup      Remove all deployed resources"
            echo "  --dry-run      Validate manifests without deploying"
            echo "  --skip-tests   Skip connectivity tests"
            echo "  --skip-vault   Skip Vault setup"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Cleanup function
function cleanup_infrastructure() {
    print_header "Cleaning Up Infrastructure"

    print_info "Deleting StatefulSets..."
    kubectl delete statefulset --all -n $NAMESPACE_DATA --force --grace-period=0 2>/dev/null || true

    print_info "Deleting PVCs..."
    kubectl delete pvc --all -n $NAMESPACE_DATA --force --grace-period=0 2>/dev/null || true

    print_info "Deleting Services..."
    kubectl delete svc --all -n $NAMESPACE_DATA 2>/dev/null || true

    print_info "Deleting ConfigMaps..."
    kubectl delete configmap --all -n $NAMESPACE_DATA 2>/dev/null || true

    print_info "Deleting Secrets..."
    kubectl delete secret --all -n $NAMESPACE_DATA 2>/dev/null || true

    print_info "Deleting Namespace..."
    kubectl delete namespace $NAMESPACE_DATA 2>/dev/null || true

    print_success "Cleanup complete"
    exit 0
}

# Dry-run validation
function dry_run_validation() {
    print_header "Dry-Run Validation"

    local failed=0

    print_info "Validating namespaces..."
    if kubectl apply --dry-run=client -f namespaces/ &> /dev/null; then
        print_success "Namespaces validation passed"
    else
        print_error "Namespaces validation failed"
        failed=1
    fi

    print_info "Validating PostgreSQL products..."
    if kubectl apply --dry-run=client -f data-layer/postgresql/products/ &> /dev/null; then
        print_success "PostgreSQL products validation passed"
    else
        print_error "PostgreSQL products validation failed"
        failed=1
    fi

    print_info "Validating PostgreSQL orders..."
    if kubectl apply --dry-run=client -f data-layer/postgresql/orders/ &> /dev/null; then
        print_success "PostgreSQL orders validation passed"
    else
        print_error "PostgreSQL orders validation failed"
        failed=1
    fi

    print_info "Validating Redis cart..."
    if kubectl apply --dry-run=client -f data-layer/redis/cart/ &> /dev/null; then
        print_success "Redis cart validation passed"
    else
        print_error "Redis cart validation failed"
        failed=1
    fi

    print_info "Validating Redis orders-cache..."
    if kubectl apply --dry-run=client -f data-layer/redis/orders-cache/ &> /dev/null; then
        print_success "Redis orders-cache validation passed"
    else
        print_error "Redis orders-cache validation failed"
        failed=1
    fi

    if [ $failed -eq 0 ]; then
        print_success "All validations passed!"
        exit 0
    else
        print_error "Some validations failed"
        exit 1
    fi
}

# Check prerequisites
function check_prerequisites() {
    print_header "Checking Prerequisites"

    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found"
        exit 1
    fi
    print_success "kubectl found"

    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    print_success "Cluster connectivity OK"

    CONTEXT=$(kubectl config current-context)
    print_info "Current context: $CONTEXT"
}

# Deploy namespaces
function deploy_namespaces() {
    print_header "Deploying Namespaces"

    kubectl apply -f namespaces/namespaces.yaml
    print_success "Namespaces created"

    # Verify namespaces exist
    kubectl get namespace $NAMESPACE_DATA &> /dev/null
    print_success "Namespace $NAMESPACE_DATA verified"
}

# Deploy PostgreSQL
function deploy_postgresql() {
    print_header "Deploying PostgreSQL Databases"

    print_info "Deploying PostgreSQL products..."
    kubectl apply -f data-layer/postgresql/products/secret.yaml
    kubectl apply -f data-layer/postgresql/products/configmap.yaml
    kubectl apply -f data-layer/postgresql/products/service.yaml
    kubectl apply -f data-layer/postgresql/products/statefulset.yaml
    print_success "PostgreSQL products deployed"

    print_info "Deploying PostgreSQL orders..."
    kubectl apply -f data-layer/postgresql/orders/secret.yaml
    kubectl apply -f data-layer/postgresql/orders/configmap.yaml
    kubectl apply -f data-layer/postgresql/orders/service.yaml
    kubectl apply -f data-layer/postgresql/orders/statefulset.yaml
    print_success "PostgreSQL orders deployed"
}

# Deploy Redis
function deploy_redis() {
    print_header "Deploying Redis Caches"

    print_info "Deploying Redis cart..."
    kubectl apply -f data-layer/redis/cart/secret.yaml
    kubectl apply -f data-layer/redis/cart/service.yaml
    kubectl apply -f data-layer/redis/cart/statefulset.yaml
    print_success "Redis cart deployed"

    print_info "Deploying Redis orders-cache..."
    kubectl apply -f data-layer/redis/orders-cache/secret.yaml
    kubectl apply -f data-layer/redis/orders-cache/service.yaml
    kubectl apply -f data-layer/redis/orders-cache/statefulset.yaml
    print_success "Redis orders-cache deployed"
}

# Wait for pods
function wait_for_pods() {
    print_header "Waiting for Pods to be Ready"

    print_info "Waiting for PostgreSQL products (timeout: $TIMEOUT)..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=products -n $NAMESPACE_DATA --timeout=$TIMEOUT 2>/dev/null; then
        print_success "PostgreSQL products ready"
    else
        print_error "PostgreSQL products failed to become ready"
        kubectl get pods -n $NAMESPACE_DATA
        kubectl describe pod -l app.kubernetes.io/instance=products -n $NAMESPACE_DATA
        return 1
    fi

    print_info "Waiting for PostgreSQL orders (timeout: $TIMEOUT)..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=orders -n $NAMESPACE_DATA --timeout=$TIMEOUT 2>/dev/null; then
        print_success "PostgreSQL orders ready"
    else
        print_error "PostgreSQL orders failed to become ready"
        kubectl get pods -n $NAMESPACE_DATA
        kubectl describe pod -l app.kubernetes.io/instance=orders -n $NAMESPACE_DATA
        return 1
    fi

    print_info "Waiting for Redis cart (timeout: $TIMEOUT)..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cart -n $NAMESPACE_DATA --timeout=$TIMEOUT 2>/dev/null; then
        print_success "Redis cart ready"
    else
        print_error "Redis cart failed to become ready"
        kubectl get pods -n $NAMESPACE_DATA
        kubectl describe pod -l app.kubernetes.io/instance=cart -n $NAMESPACE_DATA
        return 1
    fi

    print_info "Waiting for Redis orders-cache (timeout: $TIMEOUT)..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=orders-cache -n $NAMESPACE_DATA --timeout=$TIMEOUT 2>/dev/null; then
        print_success "Redis orders-cache ready"
    else
        print_error "Redis orders-cache failed to become ready"
        kubectl get pods -n $NAMESPACE_DATA
        kubectl describe pod -l app.kubernetes.io/instance=orders-cache -n $NAMESPACE_DATA
        return 1
    fi

    print_success "All pods are ready!"
}

# Show deployment status
function show_status() {
    print_header "Deployment Status"

    print_info "Pods:"
    kubectl get pods -n $NAMESPACE_DATA -o wide

    echo ""
    print_info "Services:"
    kubectl get svc -n $NAMESPACE_DATA

    echo ""
    print_info "PVCs:"
    kubectl get pvc -n $NAMESPACE_DATA

    echo ""
    print_info "ConfigMaps:"
    kubectl get configmap -n $NAMESPACE_DATA

    echo ""
    print_info "Secrets:"
    kubectl get secrets -n $NAMESPACE_DATA
}

# Test database connectivity
function test_connectivity() {
    print_header "Testing Database Connectivity"

    print_info "Testing PostgreSQL products..."
    if kubectl exec -n $NAMESPACE_DATA postgresql-products-0 -- psql -U postgres -d products -c "SELECT version();" &> /dev/null; then
        print_success "PostgreSQL products connection OK"
    else
        print_error "PostgreSQL products connection failed"
        return 1
    fi

    print_info "Testing PostgreSQL orders..."
    if kubectl exec -n $NAMESPACE_DATA postgresql-orders-0 -- psql -U postgres -d orders -c "SELECT version();" &> /dev/null; then
        print_success "PostgreSQL orders connection OK"
    else
        print_error "PostgreSQL orders connection failed"
        return 1
    fi

    print_info "Testing Redis cart..."
    if kubectl exec -n $NAMESPACE_DATA redis-cart-0 -- redis-cli -a REPLACE_WITH_LOCAL_SECRET ping 2>/dev/null | grep -q PONG; then
        print_success "Redis cart connection OK"
    else
        print_error "Redis cart connection failed"
        return 1
    fi

    print_info "Testing Redis orders-cache..."
    if kubectl exec -n $NAMESPACE_DATA redis-orders-cache-0 -- redis-cli -a REPLACE_WITH_LOCAL_SECRET ping 2>/dev/null | grep -q PONG; then
        print_success "Redis orders-cache connection OK"
    else
        print_error "Redis orders-cache connection failed"
        return 1
    fi
}

# Test database schema
function test_schema() {
    print_header "Testing Database Schemas"

    print_info "Checking PostgreSQL products schema..."
    PRODUCT_COUNT=$(kubectl exec -n $NAMESPACE_DATA postgresql-products-0 -- psql -U postgres -d products -tAc "SELECT COUNT(*) FROM products;" 2>/dev/null)
    print_success "Products table has $PRODUCT_COUNT rows"

    CATEGORY_COUNT=$(kubectl exec -n $NAMESPACE_DATA postgresql-products-0 -- psql -U postgres -d products -tAc "SELECT COUNT(*) FROM categories;" 2>/dev/null)
    print_success "Categories table has $CATEGORY_COUNT rows"

    print_info "Checking PostgreSQL orders schema..."
    ORDER_COUNT=$(kubectl exec -n $NAMESPACE_DATA postgresql-orders-0 -- psql -U postgres -d orders -tAc "SELECT COUNT(*) FROM orders;" 2>/dev/null)
    print_success "Orders table has $ORDER_COUNT rows"

    ORDER_ITEM_COUNT=$(kubectl exec -n $NAMESPACE_DATA postgresql-orders-0 -- psql -U postgres -d orders -tAc "SELECT COUNT(*) FROM order_items;" 2>/dev/null)
    print_success "Order items table has $ORDER_ITEM_COUNT rows"
}

# Setup Vault
function setup_vault() {
    print_header "Setting up Vault Database Secrets Engine"

    # Check if Vault is available
    if ! kubectl get namespace vault &> /dev/null; then
        print_error "Vault namespace not found - skipping Vault setup"
        print_info "Deploy Vault first: ./scripts/k3d-manager deploy_vault"
        return 0
    fi

    # Check if Vault pod is running
    if ! kubectl get pod -n vault -l app.kubernetes.io/name=vault &> /dev/null; then
        print_error "Vault pod not found - skipping Vault setup"
        return 0
    fi

    # Get Vault root token
    if [ -z "${VAULT_TOKEN:-}" ]; then
        print_info "Attempting to get Vault root token from k3d-manager..."
        if [ -f "../k3d-manager/scratch/vault_root_token" ]; then
            export VAULT_TOKEN=$(cat ../k3d-manager/scratch/vault_root_token)
            print_success "Vault token loaded"
        else
            print_error "VAULT_TOKEN not set and cannot find token file"
            print_info "Set VAULT_TOKEN manually or skip with --skip-vault"
            return 1
        fi
    fi

    # Set Vault address
    export VAULT_ADDR="${VAULT_ADDR:-http://vault.vault.svc.cluster.local:8200}"
    print_info "Using Vault at: $VAULT_ADDR"

    # Run setup script
    print_info "Running Vault setup script..."
    if ./vault/setup-database-secrets-engine.sh; then
        print_success "Vault setup complete"
    else
        print_error "Vault setup failed"
        return 1
    fi
}

# Deploy ExternalSecrets (if ESO is available)
function deploy_externalsecrets() {
    print_header "Deploying ExternalSecrets"

    # Check if ESO is installed
    if ! kubectl get crd externalsecrets.external-secrets.io &> /dev/null; then
        print_error "ExternalSecrets CRD not found - skipping"
        print_info "Deploy ESO first: ./scripts/k3d-manager deploy_eso"
        return 0
    fi

    print_info "Deploying ExternalSecrets..."
    kubectl apply -f data-layer/secrets/
    print_success "ExternalSecrets deployed"

    # Wait a moment for sync
    sleep 5

    print_info "Checking ExternalSecret status..."
    kubectl get externalsecrets -n $NAMESPACE_DATA
}

# Main deployment flow
function main() {
    if [ "$CLEANUP" = true ]; then
        cleanup_infrastructure
        exit 0
    fi

    if [ "$DRY_RUN" = true ]; then
        dry_run_validation
        exit 0
    fi

    check_prerequisites
    deploy_namespaces
    deploy_postgresql
    deploy_redis
    wait_for_pods
    show_status

    if [ "$SKIP_TESTS" = false ]; then
        test_connectivity
        test_schema
    fi

    if [ "$SKIP_VAULT_SETUP" = false ]; then
        setup_vault
        deploy_externalsecrets
    fi

    print_header "Deployment Summary"
    echo -e "${GREEN}✓ Infrastructure deployment complete!${NC}"
    echo ""
    echo "Deployed components:"
    echo "  - PostgreSQL products database (10 products, 9 categories)"
    echo "  - PostgreSQL orders database (3 orders, 3 items)"
    echo "  - Redis cart cache"
    echo "  - Redis orders cache"
    echo ""
    if [ "$SKIP_VAULT_SETUP" = false ]; then
        echo "Vault configuration:"
        echo "  - Database secrets engine enabled"
        echo "  - PostgreSQL roles configured"
        echo "  - Redis passwords stored"
        echo ""
    fi
    echo "Next steps:"
    echo "  1. View pods: kubectl get pods -n $NAMESPACE_DATA"
    echo "  2. View logs: kubectl logs -n $NAMESPACE_DATA <pod-name>"
    if [ "$SKIP_VAULT_SETUP" = false ]; then
        echo "  3. Check ExternalSecrets: kubectl get externalsecrets -n $NAMESPACE_DATA"
        echo "  4. Verify Vault creds: vault read database/creds/products-readonly"
    fi
    echo "  5. Deploy Argo CD applications"
    echo ""
    echo "To cleanup: $0 --cleanup"
}

# Run main
main
