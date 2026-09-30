# Vault Password Rotation Guide

## Overview

Vault's database secrets engine generates dynamic, short-lived credentials that automatically expire and rotate. This guide explains how password rotation works and how to test it.

## How Dynamic Credentials Work

### Credential Lifecycle

1. **Generation**: Application requests credentials from Vault
2. **Active Period**: Credentials work for the lease duration (default: 1 hour)
3. **Expiration**: Vault automatically revokes credentials after TTL expires
4. **Rotation**: Application requests new credentials before expiration

```
Time:     0m          30m          60m         90m
          |-----------|-----------|-----------|
Creds A:  [====== ACTIVE ======][EXPIRED]
Creds B:                    [Request] [====== ACTIVE ======]
```

### Key Concepts

**Lease Duration (TTL)**
- Default: 1 hour (3600 seconds)
- Maximum: 24 hours (configurable)
- Renewable: Yes (can extend before expiration)

**Automatic Revocation**
- Vault automatically revokes credentials after TTL
- PostgreSQL role is dropped from the database
- Old credentials immediately stop working

**Dynamic PostgreSQL Roles**
- Each credential set creates a new PostgreSQL user
- Username format: `v-root-<role>-<random>-<timestamp>`
- Password: 20-character random string
- Permissions: Defined by Vault role configuration

## Testing Password Rotation

### Quick Test

Run the automated rotation test:

```bash
bin/test-vault-rotation.sh
```

This script:
1. Generates initial credentials
2. Verifies they work with the database
3. Manually revokes the credentials (simulating expiration)
4. Confirms old credentials are rejected
5. Generates new credentials
6. Verifies new credentials work

**Expected Output:**
```
✅ Credential rotation is working correctly!

Test Results:
  1. ✅ Initial credentials generated and worked
  2. ✅ Credentials revoked (simulating expiration)
  3. ✅ Old credentials rejected after revocation
  4. ✅ New credentials generated with different values
  5. ✅ New credentials work with database
```

### Manual Testing

#### Step 1: Generate Initial Credentials

```bash
VAULT_TOKEN=$(kubectl get secret -n vault vault-root -o jsonpath='{.data.root_token}' | base64 -d)

kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read database/creds/products-readonly
"
```

Save the `username`, `password`, and `lease_id` from the output.

#### Step 2: Test Credentials

```bash
kubectl run -n shopping-cart-data test-creds --rm -i --restart=Never \
  --image=postgres:15-alpine \
  --command -- sh -c "PGPASSWORD='<password>' psql -h postgresql-products -U '<username>' -d products -c 'SELECT COUNT(*) FROM products;'"
```

Should return: `10`

#### Step 3: Revoke Credentials

```bash
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault lease revoke <lease_id>
"
```

Wait 3 seconds for revocation to propagate.

#### Step 4: Verify Revocation

Run the same test command from Step 2. You should see:

```
FATAL: password authentication failed for user "v-root-products-..."
```

This confirms Vault successfully revoked the credentials.

#### Step 5: Generate New Credentials

Repeat Step 1 to get new credentials. Note that the username and password will be different.

#### Step 6: Test New Credentials

Repeat Step 2 with the new credentials. Should successfully return `10` again.

## Production Implementation

### Option 1: Application-Managed Rotation

Applications request new credentials before expiration:

```python
import hvac
import psycopg2
from datetime import datetime, timedelta

class VaultDBConnection:
    def __init__(self, vault_addr, vault_token):
        self.vault_client = hvac.Client(url=vault_addr, token=vault_token)
        self.credentials = None
        self.expires_at = None

    def get_connection(self):
        # Refresh credentials if they expire in < 5 minutes
        if not self.credentials or datetime.now() > self.expires_at - timedelta(minutes=5):
            self.refresh_credentials()

        return psycopg2.connect(
            host='postgresql-products.shopping-cart-data.svc.cluster.local',
            database='products',
            user=self.credentials['username'],
            password=self.credentials['password']
        )

    def refresh_credentials(self):
        response = self.vault_client.read('database/creds/products-readonly')
        self.credentials = response['data']
        # Calculate expiration (1h TTL - 5min buffer)
        self.expires_at = datetime.now() + timedelta(seconds=response['lease_duration'])
```

### Option 2: External Secrets Operator

ESO automatically syncs credentials from Vault to Kubernetes secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: products-db-creds
  namespace: shopping-cart-apps
spec:
  refreshInterval: 30m  # Refresh every 30 minutes (well before 1h expiration)
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

**How it works:**
1. ESO requests credentials from Vault every 30 minutes
2. Updates the Kubernetes secret with new values
3. Applications reference the secret (gets updated automatically)
4. **Important**: Applications must handle connection pool refresh

**Application considerations:**
- Database connection pools cache connections with old credentials
- Must implement connection validation and refresh
- Example with SQLAlchemy:

```python
from sqlalchemy import create_engine, event
from sqlalchemy.pool import Pool

engine = create_engine(
    'postgresql://...',
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=1800    # Recycle connections every 30 minutes
)

@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    # Read fresh credentials from updated secret
    username = os.environ['DB_USERNAME']
    password = os.environ['DB_PASSWORD']
    # Connection uses fresh credentials
```

### Option 3: Vault Agent Sidecar

Vault Agent runs as a sidecar and handles credential renewal:

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
        vault.hashicorp.com/agent-inject-template-db-creds: |
          {{- with secret "database/creds/products-readonly" -}}
          export DB_USERNAME="{{ .Data.username }}"
          export DB_PASSWORD="{{ .Data.password }}"
          {{- end }}
    spec:
      containers:
      - name: app
        command: ["/bin/sh", "-c"]
        args:
          - source /vault/secrets/db-creds && ./start-app.sh
```

Vault Agent automatically:
- Renews credentials before expiration
- Updates the file with new credentials
- Application sources the file for fresh credentials

## Monitoring and Troubleshooting

### Check Active Leases

```bash
# List all leases for products-readonly role
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault list sys/leases/lookup/database/creds/products-readonly
"
```

### Check Lease Details

```bash
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault lease lookup <lease_id>
"
```

### Renew a Lease

```bash
# Extend lease by another increment (up to max TTL)
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault lease renew <lease_id>
"
```

### Check PostgreSQL Users

```bash
# List active Vault-generated users in PostgreSQL
kubectl run -n shopping-cart-data check-users --rm -i --restart=Never \
  --image=postgres:15-alpine \
  -- psql -h postgresql-products -U postgres -d products \
  -c "SELECT usename, valuntil FROM pg_user WHERE usename LIKE 'v-root-%' ORDER BY usename;"
```

**Expected output:**
```
                      usename                       |          valuntil
----------------------------------------------------+----------------------------
 v-root-products-ABC123...-1765546067              | 2025-01-08 10:34:27+00
 v-root-products-XYZ789...-1765546086              | 2025-01-08 10:34:46+00
```

### Common Issues

**Issue: Credentials not revoked after expiration**

Check if Vault can connect to PostgreSQL:
```bash
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault read database/config/postgresql-products
"
```

**Issue: Application continues to work with old credentials**

- Check if application is caching credentials
- Verify database connection pool is recycling connections
- Check if `valuntil` timestamp in PostgreSQL is correct

**Issue: Too many Vault-generated users accumulating**

This is normal behavior - old users remain until `valuntil` expires. PostgreSQL will clean them up automatically. To manually clean up:

```bash
kubectl run -n shopping-cart-data cleanup --rm -i --restart=Never \
  --image=postgres:15-alpine \
  -- psql -h postgresql-products -U postgres -d products \
  -c "SELECT usename FROM pg_user WHERE usename LIKE 'v-root-%' AND valuntil < NOW();"
```

## Security Best Practices

1. **Use short TTLs**: 1-hour default is good for most cases
2. **Implement credential refresh**: Don't wait for expiration
3. **Monitor lease usage**: Set up alerts for excessive lease creation
4. **Rotate regularly**: Even if credentials are long-lived, rotate them
5. **Audit access**: Enable Vault audit logging
6. **Separate roles**: Use different roles for read-only vs. write access

## Configuration Reference

### Current Settings

**Database Secrets Engine:**
- Mount path: `database/`
- Products role: `products-readonly`
- Orders role: `orders-readonly`

**Products Database Role:**
```
Default TTL: 1 hour
Max TTL: 24 hours
Creation statement:
  CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
```

### Adjusting TTL

To change default TTL to 30 minutes:

```bash
kubectl exec -n vault vault-0 -- sh -c "
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=$VAULT_TOKEN
vault write database/roles/products-readonly \
  db_name=postgresql-products \
  creation_statements=\"CREATE ROLE \\\"{{name}}\\\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \\\"{{name}}\\\";\" \
  default_ttl=30m \
  max_ttl=24h
"
```

## Related Documentation

- [Vault Usage Guide](vault-usage-guide.md) - Complete Vault integration guide
- [Integration Test](../bin/test-vault-integration.sh) - Basic Vault functionality test
- [Rotation Test](../bin/test-vault-rotation.sh) - Password rotation validation

## Testing Checklist

When deploying or updating Vault integration:

- [ ] Run integration test: `bin/test-vault-integration.sh`
- [ ] Run rotation test: `bin/test-vault-rotation.sh`
- [ ] Verify credentials expire after TTL
- [ ] Test application reconnection with new credentials
- [ ] Monitor Vault logs for revocation errors
- [ ] Check PostgreSQL for expired users cleanup
