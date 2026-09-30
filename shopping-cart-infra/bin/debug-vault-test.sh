#!/bin/bash
set -e

echo "=== Generating Vault Credentials ==="
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

CREDS=$(kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read -format=json database/creds/products-readonly
")

echo "Vault response:"
echo "$CREDS" | jq .

DB_USER=$(echo "$CREDS" | jq -r '.data.username')
DB_PASS=$(echo "$CREDS" | jq -r '.data.password')

echo ""
echo "Extracted credentials:"
echo "Username: $DB_USER"
echo "Password: ${DB_PASS:0:10}..."

echo ""
echo "=== Testing Database Connection with Vault Credentials ==="
kubectl run -n shopping-cart-data test-vault-final --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --command -- sh -c "PGPASSWORD='$DB_PASS' psql -h postgresql-products -U '$DB_USER' -d products -c 'SELECT COUNT(*) FROM products;'"
