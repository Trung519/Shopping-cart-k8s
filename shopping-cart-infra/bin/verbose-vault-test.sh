#!/bin/bash
set -e

echo "=== Testing Vault Integration (Verbose Mode) ==="

# Get Vault token
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

# Generate products credentials
echo -e "\n1. Generating PRODUCTS credentials..."
PRODUCTS_CREDS=$(kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read -format=json database/creds/products-readonly
")

PRODUCTS_USER=$(echo "$PRODUCTS_CREDS" | jq -r '.data.username')
PRODUCTS_PASS=$(echo "$PRODUCTS_CREDS" | jq -r '.data.password')

echo "   Username: $PRODUCTS_USER"
echo "   Password: ${PRODUCTS_PASS:0:12}..."

# Test PRODUCTS database with FULL output capture
echo -e "\n2. Testing PRODUCTS database connection (full output)..."
echo "   Command: kubectl run -n shopping-cart-data test-vault-verbose-products --rm -i --restart=Never --image=postgres:15-alpine --command -- sh -c \"PGPASSWORD='$PRODUCTS_PASS' psql -h postgresql-products -U '$PRODUCTS_USER' -d products -c 'SELECT COUNT(*) FROM products;'\""
echo ""

PRODUCTS_FULL_OUTPUT=$(kubectl run -n shopping-cart-data test-vault-verbose-products --rm -i --restart=Never \
    --image=postgres:15-alpine \
    --command -- sh -c "PGPASSWORD='$PRODUCTS_PASS' psql -h postgresql-products -U '$PRODUCTS_USER' -d products -c 'SELECT COUNT(*) FROM products;'" 2>&1)

PRODUCTS_EXIT_CODE=$?

echo "Exit code: $PRODUCTS_EXIT_CODE"
echo -e "\nFull output:"
echo "---START---"
echo "$PRODUCTS_FULL_OUTPUT"
echo "---END---"

# Check for success
if echo "$PRODUCTS_FULL_OUTPUT" | grep -q "10"; then
    echo -e "\n✅ SUCCESS: Found count of 10 products"
else
    echo -e "\n❌ FAILURE: Did not find expected count"
fi

# Show what grep patterns would match
echo -e "\n3. Analyzing grep patterns..."
echo "   Pattern 'grep -A1 \"count\"' matches:"
echo "$PRODUCTS_FULL_OUTPUT" | grep -A1 "count" || echo "   (no matches)"

echo -e "\n   Pattern 'grep -q \"[0-9]\"' matches:"
if echo "$PRODUCTS_FULL_OUTPUT" | grep -q "[0-9]"; then
    echo "   YES - numeric values found"
    echo "$PRODUCTS_FULL_OUTPUT" | grep "[0-9]"
else
    echo "   NO - no numeric values found"
fi
