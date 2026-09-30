# Vault Integration Usage Guide

## Overview

Vault is configured with:
- SNI-based access via Istio Gateway
- Database secrets engine for dynamic PostgreSQL credentials
- 1-hour TTL with automatic rotation

## Accessing Vault

### 1. Via Istio Gateway (Recommended)

Vault is accessible through the Istio ingress gateway at `vault.dev.local.me`:

```bash
# Get the ingress gateway IP
INGRESS_IP=$(kubectl get svc -n istio-system istio-ingressgateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Access Vault API (using Host header)
curl -H "Host: vault.dev.local.me" http://$INGRESS_IP/v1/sys/health

# Or add to /etc/hosts (requires sudo)
echo "$INGRESS_IP vault.dev.local.me" | sudo tee -a /etc/hosts

# Then access directly
curl http://vault.dev.local.me/v1/sys/health
```

### 2. Via kubectl port-forward

```bash
kubectl port-forward -n vault vault-0 8200:8200

# Access at http://localhost:8200
```

### 3. From within the cluster

```bash
# Vault is accessible at:
http://vault.vault.svc.cluster.local:8200
```

## Getting Dynamic Database Credentials

### Method 1: Using Vault CLI (from Vault pod)

```bash
# Get the root token
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

# Generate credentials for products database
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read database/creds/products-readonly
"

# Generate credentials for orders database
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read database/creds/orders-readonly
"
```

**Output example:**
```
Key                Value
---                -----
lease_id           database/creds/products-readonly/abc123...
lease_duration     1h
lease_renewable    true
password           Yvo5g4cHpMMiW8zW-uBF
username           v-root-products-HEQendCBueO6BKx3QCv1-1765500854
```

### Method 2: Using Vault API

```bash
# Get root token
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

# Request credentials via API
curl -H "X-Vault-Token: $VAULT_TOKEN" \
     -H "Host: vault.dev.local.me" \
     http://10.211.55.14/v1/database/creds/products-readonly | jq
```

## Testing Database Connectivity with Dynamic Credentials

```bash
#!/bin/bash

# Get Vault token
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

# Request credentials
CREDS=$(kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read -format=json database/creds/products-readonly
")

# Extract username and password
DB_USER=$(echo "$CREDS" | jq -r '.data.username')
DB_PASS=$(echo "$CREDS" | jq -r '.data.password')

echo "Generated credentials:"
echo "  Username: $DB_USER"
echo "  Password: ${DB_PASS:0:8}..."

# Test connection
kubectl run -n shopping-cart-data test-vault-creds --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --env="PGPASSWORD=$DB_PASS" \
  -- psql -h postgresql-products -U "$DB_USER" -d products -c "SELECT COUNT(*) FROM products;"
```

## Using Credentials in Applications

### Option 1: Direct Vault Integration (Recommended for production)

Applications can request credentials directly from Vault:

```python
# Python example
import hvac

client = hvac.Client(url='http://vault.vault.svc.cluster.local:8200')
client.token = os.environ['VAULT_TOKEN']

# Get database credentials
creds = client.read('database/creds/products-readonly')
db_username = creds['data']['username']
db_password = creds['data']['password']

# Connect to database
conn = psycopg2.connect(
    host='postgresql-products.shopping-cart-data.svc.cluster.local',
    database='products',
    user=db_username,
    password=db_password
)
```

### Option 2: External Secrets Operator (ESO)

Create an ExternalSecret to sync credentials to Kubernetes secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: products-db-creds
  namespace: shopping-cart-apps
spec:
  refreshInterval: 30m  # Refresh every 30 minutes
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: products-db-secret
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: database/creds/products-readonly
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/products-readonly
        property: password
```

Then use in your deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-catalog
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: products-db-secret
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: products-db-secret
              key: password
```

### Option 3: Vault Agent Injector (Sidecar pattern)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-catalog
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "products-readonly"
        vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/products-readonly"
    spec:
      containers:
      - name: app
        # Credentials available at /vault/secrets/db-creds
```

## Credential Lifecycle

### Lease Duration
- **Default TTL**: 1 hour
- **Max TTL**: 24 hours
- **Renewable**: Yes

### Automatic Rotation

Credentials are automatically rotated when:
1. Lease expires (after 1 hour)
2. Application requests new credentials
3. Old credentials are automatically revoked

### Manual Revocation

```bash
# Revoke a specific lease
kubectl exec -n vault vault-0 -- vault lease revoke database/creds/products-readonly/LEASE_ID

# Revoke all credentials for a role
kubectl exec -n vault vault-0 -- vault lease revoke -prefix database/creds/products-readonly
```

## Available Database Roles

| Role | Database | Permissions | TTL |
|------|----------|-------------|-----|
| `products-readonly` | products | SELECT only | 1h |
| `orders-readonly` | orders | SELECT only | 1h |

## Vault Configuration Details

### Database Connections

**Products Database:**
```
Connection: postgresql://postgres@postgresql-products.shopping-cart-data.svc.cluster.local:5432/products
Role: products-readonly
Creation Statement: CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
```

**Orders Database:**
```
Connection: postgresql://postgres@postgresql-orders.shopping-cart-data.svc.cluster.local:5432/orders
Role: orders-readonly
Creation Statement: CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
```

## Troubleshooting

### Check Vault Status

```bash
# Check if Vault is sealed
kubectl exec -n vault vault-0 -- vault status

# Check database secrets engine
kubectl exec -n vault vault-0 -- vault secrets list
```

### Test Database Connectivity

```bash
# Test PostgreSQL products database
kubectl run -n shopping-cart-data test-pg --rm -it --image=postgres:15-alpine \
  -- psql -h postgresql-products -U postgres -d products -c "SELECT 1;"

# Test PostgreSQL orders database
kubectl run -n shopping-cart-data test-pg --rm -it --image=postgres:15-alpine \
  -- psql -h postgresql-orders -U postgres -d orders -c "SELECT 1;"
```

### Check Vault Logs

```bash
kubectl logs -n vault vault-0 --tail=100
```

### Verify Istio Gateway

```bash
# Check Gateway
kubectl get gateway -n vault

# Check VirtualService
kubectl get virtualservice -n vault

# Test access
curl -H "Host: vault.dev.local.me" http://10.211.55.14/v1/sys/health
```

## Security Best Practices

1. **Never use root token in production**
   - Create specific policies for applications
   - Use AppRole or Kubernetes auth method

2. **Rotate credentials regularly**
   - Use short TTLs (1 hour is good)
   - Implement automatic renewal in applications

3. **Limit permissions**
   - Use read-only roles for read-only operations
   - Create separate roles for write operations

4. **Enable audit logging**
   ```bash
   kubectl exec -n vault vault-0 -- vault audit enable file file_path=/vault/logs/audit.log
   ```

5. **Use TLS in production**
   - Configure Vault with TLS certificates
   - Update Istio Gateway for HTTPS

## Next Steps

1. **Deploy ExternalSecrets** for automatic credential sync
2. **Configure Vault policies** for application-specific access
3. **Enable Kubernetes auth** method for pod authentication
4. **Set up monitoring** for Vault metrics and audit logs
5. **Configure backup** for Vault data
