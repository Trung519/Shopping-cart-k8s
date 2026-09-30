# System Patterns: shopping-cart-infra

## GitOps Architecture

All cluster state is declared in this repository. No `kubectl apply` commands are run manually in production — every change flows through Git:

```
Git commit → Argo CD detects → Argo CD syncs cluster
```

`syncPolicy.automated.prune: true` removes resources deleted from Git.
`syncPolicy.automated.selfHeal: true` reverts manual `kubectl` changes.

## Two-Namespace Separation Pattern

```
shopping-cart-data (infrastructure layer)
├── StatefulSets: postgresql-products, postgresql-orders, redis-cart, redis-orders-cache, rabbitmq
├── PVCs: data volumes for all stateful components
└── Secrets: ESO-managed, Vault-sourced credentials

shopping-cart-apps (application layer)
├── Deployments: product-catalog, basket, order, frontend (via Helm)
├── Services: ClusterIP + NodePort for each application
└── ConfigMaps: application configuration
```

Benefits:
- Blast radius isolation: infra changes don't touch app manifests and vice versa
- Different RBAC policies (ops team manages data layer; dev CI manages app layer)
- Independent resource quotas per namespace
- Network policies can restrict app → data cross-namespace access

## Vault Integration Pattern

```
Vault Database Secrets Engine (PostgreSQL)
  → generates time-limited credentials per role
  → Vault path: database/creds/<role>

ESO ExternalSecret (refreshInterval: 1h)
  → reads Vault creds → creates/updates K8s Secret

Kubernetes Pod
  → mounts Secret as env vars: DB_USERNAME, DB_PASSWORD
  → unaware of Vault; consumes standard K8s secret
```

Redis uses Vault KV (static secrets) with 24h refresh:
```
Vault KV path: secret/data/redis/cart
  → ESO ExternalSecret → K8s Secret: redis-cart-secret
```

## Vault Database Secrets Engine Role Pattern

```sql
-- Role creation statement (Vault generates unique username per lease)
CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}'
  VALID UNTIL '{{expiration}}';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
```

Roles:
- `products-readonly` — product-catalog service (SELECT only)
- `products-readwrite` — future write operations
- `orders-readwrite` — order service (SELECT, INSERT, UPDATE, DELETE)

## Helm Chart Structure

The `chart/` directory is a single Helm chart managing all 4 application services:

```
chart/
├── templates/product-catalog/  ← Deployment, Service, HPA
├── templates/cart/             ← Deployment, Service, HPA
├── templates/order/            ← Deployment, Service, HPA
└── templates/frontend/         ← Deployment, Service (nginx)
```

Image tags are the primary value updated by CI:
```yaml
# values-dev.yaml (updated by Jenkins)
productCatalog:
  image:
    tag: main-abc1234   # Jenkins updates this field
```

## Argo CD Application Structure

Two Argo CD Applications:

1. **shopping-cart-infrastructure** — syncs `data-layer/` to `shopping-cart-data` namespace
   - Source: raw YAML manifests
   - Auto-sync enabled (prune + self-heal)

2. **shopping-cart-dev** — syncs `chart/` (Helm) to `shopping-cart-apps` namespace
   - Source: Helm chart with `values-dev.yaml`
   - Auto-sync enabled

3. **shopping-cart-prod** — syncs `chart/` (Helm) with `values-prod.yaml`
   - Manual sync only (no auto-sync in production)

## CI/CD Image Promotion Pattern

```bash
# Jenkins pipeline step (after building/pushing image):
IMAGE_TAG="main-${GIT_SHA}"

# Clone infra repo
git clone <infra-repo> infra
cd infra

# Update image tag using yq
yq eval ".productCatalog.image.tag = \"$IMAGE_TAG\"" -i chart/values-dev.yaml

# Commit and push
git commit -m "chore: update product-catalog to $IMAGE_TAG"
git push origin main

# Argo CD detects change within 3 minutes and syncs
```

## Resource Naming Convention

Format: `<service>-<instance>` (e.g., `postgresql-products`, `redis-cart`, `redis-orders-cache`)

Labels follow `app.kubernetes.io/*` standard:
```yaml
labels:
  app.kubernetes.io/name: postgresql
  app.kubernetes.io/instance: products
  app.kubernetes.io/component: database
  app.kubernetes.io/part-of: shopping-cart
```

## Adding a New Database — Checklist

1. `data-layer/postgresql/<name>/statefulset.yaml`
2. `data-layer/postgresql/<name>/service.yaml`
3. `data-layer/postgresql/<name>/pvc.yaml`
4. `data-layer/postgresql/<name>/init-db.sql`
5. `data-layer/secrets/postgres-<name>-secret.yaml` (ExternalSecret)
6. Add Vault role in `vault/setup-database-secrets-engine.sh`
7. Update this CLAUDE.md

## Security Principles

- Never commit secrets — all credentials live in Vault
- Least privilege database roles (readonly vs readwrite per service)
- Immutable image tags in production (never `:latest`)
- Network policies restrict pod-to-pod communication
- ESO `refreshInterval` ensures automatic credential rotation
- Vault audit logs track all secret access
