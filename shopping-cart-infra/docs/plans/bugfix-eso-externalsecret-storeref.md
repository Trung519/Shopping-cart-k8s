# Bugfix: ExternalSecret storeRef wrong kind + postgres Vault paths use unconfigured DB engine

**Branch:** `fix/eso-externalsecret-storeref` (create from main)
**Files:**
- `data-layer/secrets/redis-cart-externalsecret.yaml`
- `data-layer/secrets/redis-orders-cache-externalsecret.yaml`
- `data-layer/secrets/postgres-orders-externalsecret.yaml`
- `data-layer/secrets/postgres-products-externalsecret.yaml`
- `data-layer/secrets/postgres-payment-externalsecret.yaml`

---

## Before You Start

1. `git checkout -b fix/eso-externalsecret-storeref origin/main` in shopping-cart-infra
2. Read each target file before editing

---

## Problem

After `make up` + `make sync-apps`, all ExternalSecrets in `shopping-cart-data` and
`shopping-cart-payment` show `SecretSyncedError`. Two independent root causes:

**Root cause 1:** ExternalSecrets in `shopping-cart-data` use `kind: SecretStore`
(namespace-scoped), but no namespace-scoped SecretStore exists in that namespace.
Only a `ClusterSecretStore` named `vault-backend` is deployed by k3d-manager.
Fix: change `kind: SecretStore` → `kind: ClusterSecretStore` in all affected files.

**Root cause 2:** Postgres ExternalSecrets reference `database/creds/<role>` — Vault's
dynamic database secrets engine — which is not configured. The postgres init scripts
create only the `postgres` superuser; no Vault DB engine roles exist. These paths will
never resolve in the ACG sandbox.
Fix: switch all postgres ExternalSecrets to static KV paths (`secret/data/postgres/<db>`).
The matching Vault KV secrets are seeded by k3d-manager `bin/acg-up` (see companion
spec in k3d-manager `docs/plans/v1.0.3-bugfix-vault-kv-seeding.md`).

---

## Fix

### Change 1 — `redis-cart-externalsecret.yaml` line 21: fix storeRef kind

**Exact old line:**
```yaml
    kind: SecretStore
```
**Exact new line:**
```yaml
    kind: ClusterSecretStore
```

---

### Change 2 — `redis-orders-cache-externalsecret.yaml` line 19: fix storeRef kind

**Exact old line:**
```yaml
    kind: SecretStore
```
**Exact new line:**
```yaml
    kind: ClusterSecretStore
```

---

### Change 3 — `postgres-orders-externalsecret.yaml`: fix storeRef kind + vault path

**Exact old line (line 19):**
```yaml
    kind: SecretStore
```
**Exact new line:**
```yaml
    kind: ClusterSecretStore
```

**Exact old block (lines 41–47):**
```yaml
      remoteRef:
        key: database/creds/orders-readwrite
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/orders-readwrite
        property: password
```
**Exact new block:**
```yaml
      remoteRef:
        key: secret/data/postgres/orders
        property: username
    - secretKey: password
      remoteRef:
        key: secret/data/postgres/orders
        property: password
```

---

### Change 4 — `postgres-products-externalsecret.yaml`: fix storeRef kinds + vault paths

This file contains **two** ExternalSecrets. Both `kind: SecretStore` lines (21 and 72)
must change to `kind: ClusterSecretStore`. Both `database/creds/products-*` blocks
must change to static KV.

**Exact old line (line 21):**
```yaml
    kind: SecretStore
```
**Exact new line:**
```yaml
    kind: ClusterSecretStore
```

**Exact old block (lines 47–53):**
```yaml
      remoteRef:
        key: database/creds/products-readonly
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/products-readonly
        property: password
```
**Exact new block:**
```yaml
      remoteRef:
        key: secret/data/postgres/products
        property: username
    - secretKey: password
      remoteRef:
        key: secret/data/postgres/products
        property: password
```

**Exact old line (line 72):**
```yaml
    kind: SecretStore
```
**Exact new line:**
```yaml
    kind: ClusterSecretStore
```

**Exact old block (lines 94–100):**
```yaml
      remoteRef:
        key: database/creds/products-readwrite
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/products-readwrite
        property: password
```
**Exact new block:**
```yaml
      remoteRef:
        key: secret/data/postgres/products
        property: username
    - secretKey: password
      remoteRef:
        key: secret/data/postgres/products
        property: password
```

---

### Change 5 — `postgres-payment-externalsecret.yaml`: fix vault path only

This file already uses `kind: ClusterSecretStore` — only the vault path changes.

**Exact old block (lines 47–53):**
```yaml
      remoteRef:
        key: database/creds/payment-readwrite
        property: username
    - secretKey: password
      remoteRef:
        key: database/creds/payment-readwrite
        property: password
```
**Exact new block:**
```yaml
      remoteRef:
        key: secret/data/postgres/payment
        property: username
    - secretKey: password
      remoteRef:
        key: secret/data/postgres/payment
        property: password
```

---

## Files Changed

| File | Change |
|------|--------|
| `data-layer/secrets/redis-cart-externalsecret.yaml` | `kind: SecretStore` → `ClusterSecretStore` |
| `data-layer/secrets/redis-orders-cache-externalsecret.yaml` | `kind: SecretStore` → `ClusterSecretStore` |
| `data-layer/secrets/postgres-orders-externalsecret.yaml` | storeRef kind + `database/creds/…` → `secret/data/postgres/orders` |
| `data-layer/secrets/postgres-products-externalsecret.yaml` | 2× storeRef kind + 2× `database/creds/…` → `secret/data/postgres/products` |
| `data-layer/secrets/postgres-payment-externalsecret.yaml` | `database/creds/…` → `secret/data/postgres/payment` |

---

## Rules

- `yamllint` on all changed files — zero new errors
- No other files touched

---

## Definition of Done

- [ ] All 5 files updated exactly as specified above
- [ ] `yamllint data-layer/secrets/` passes with zero new errors
- [ ] Committed and pushed to `fix/eso-externalsecret-storeref`

**Commit message (exact):**
```
fix(eso): switch ExternalSecret storeRef to ClusterSecretStore; replace dynamic DB creds with static KV paths
```

---

## What NOT to Do

- Do NOT create a PR
- Do NOT skip pre-commit hooks (`--no-verify`)
- Do NOT modify any file other than the 5 listed above
- Do NOT commit to `main`
- Do NOT configure the Vault database engine — static KV is the correct approach for ACG sandbox
- Do NOT change the postgres admin `secret.yaml` files
