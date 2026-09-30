# Tech Context: shopping-cart-infra

## Core Technologies

| Technology | Purpose |
|---|---|
| Kubernetes (k3s/k3d) | Container orchestration |
| Helm v3 | Application packaging (services chart) |
| Argo CD | GitOps continuous deployment |
| HashiCorp Vault | Secrets management (dynamic DB creds, KV static) |
| External Secrets Operator (ESO) | Vault → Kubernetes Secret syncing |
| Keycloak + OpenLDAP | Identity: OAuth2/OIDC, LDAP directory |
| RabbitMQ | Message queue (AMQP 0-9-1) with Prometheus plugin |
| PostgreSQL 15 | Relational DB (products + orders) |
| Redis 7 | Cache/session (cart + orders-cache) |
| GitHub Actions | CI: build/push container images, trigger Jenkins |
| Jenkins | CD: update Helm values, push to infra repo |

## Repository Structure

```
shopping-cart-infra/
├── bin/                     ← Automation scripts
│   ├── build-and-push.sh    ← Build/push images to GHCR
│   ├── setup-service-repo.sh ← Create GitHub repo with CI/CD
│   ├── deploy-infra.sh      ← Deploy full infrastructure stack
│   ├── test-vault-integration.sh
│   └── test-vault-rotation.sh
├── data-layer/              ← Infrastructure K8s manifests
│   ├── postgresql/
│   │   ├── products/        ← StatefulSet, Service, PVC, init-db.sql
│   │   └── orders/          ← StatefulSet, Service, PVC, init-db.sql
│   ├── redis/
│   │   ├── cart/            ← StatefulSet, Service, PVC
│   │   └── orders-cache/    ← StatefulSet, Service, PVC
│   ├── rabbitmq/            ← StatefulSet, Service, ConfigMap
│   └── secrets/             ← ExternalSecret definitions
├── namespaces/
│   └── namespaces.yaml      ← shopping-cart-data + shopping-cart-apps
├── vault/
│   └── setup-database-secrets-engine.sh ← Vault DB engine config
├── chart/                   ← Helm chart for application services
│   ├── Chart.yaml
│   ├── values.yaml          ← Demo (8GB RAM) constraints
│   ├── values-dev.yaml      ← Dev environment (CI updates image tags here)
│   ├── values-prod.yaml     ← Production overrides
│   └── templates/
│       ├── product-catalog/ ← Python service manifests
│       ├── cart/            ← Go service manifests
│       ├── order/           ← Java service manifests
│       └── frontend/        ← React + nginx manifests
├── argocd/
│   ├── projects/shopping-cart.yaml       ← AppProject
│   └── applications/
│       ├── shopping-cart-infrastructure.yaml ← data-layer app
│       ├── shopping-cart-dev.yaml            ← dev app (Helm)
│       └── shopping-cart-prod.yaml           ← prod app (Helm)
├── identity/                ← Keycloak + OpenLDAP manifests
├── jenkins/                 ← Jenkins configuration
├── docs/                    ← Architecture + operations docs
└── examples/                ← Dockerfile + GitHub Actions templates
```

## External Secrets Operator Pattern

```
Vault (source of truth)
  ↓ ESO SecretStore (cluster-wide Vault connection config)
  ↓ ExternalSecret (per-namespace: maps Vault path → K8s secret key)
  ↓ Kubernetes Secret (synced automatically on refreshInterval)
  ↓ Pod environment / volume mount
```

Refresh intervals:
- PostgreSQL dynamic credentials: `1h` (Vault DB engine generates time-limited users)
- Redis static credentials: `24h` (Vault KV, manual rotation)

## Resource Constraints (Demo)

Total cluster: 8GB RAM

| Component | CPU Request | Memory Request | CPU Limit | Memory Limit |
|---|---|---|---|---|
| PostgreSQL (each) | 100m | 256Mi | 500m | 512Mi |
| Redis (each) | 50m | 128Mi | 200m | 256Mi |
| RabbitMQ | 200m | 256Mi | 500m | 512Mi |

## CI/CD Pipeline Flow

```
1. Developer pushes to application repo
2. GitHub Actions: build → scan (Trivy) → push to GHCR
   Image tags: main-<sha>, main, latest
3. GitHub Actions triggers Jenkins webhook
4. Jenkins: clone infra repo → update values-dev.yaml image tag → push
5. Argo CD detects change → syncs cluster (shopping-cart-apps namespace)
```

## Key Commands

```bash
# Local dev: deploy with k3d
k3d cluster create test
kubectl apply -f namespaces/namespaces.yaml
./vault/setup-database-secrets-engine.sh
kubectl apply -f data-layer/postgresql/products/
kubectl apply -f data-layer/redis/cart/
kubectl apply -f data-layer/secrets/

# Validate manifests
kubectl apply --dry-run=client -f data-layer/postgresql/products/
helm template chart/ -f chart/values.yaml

# Argo CD operations
argocd app sync shopping-cart-infrastructure
argocd app get shopping-cart-dev
argocd app diff shopping-cart-dev

# Test ESO secrets
kubectl get externalsecret -n shopping-cart-data
kubectl get secret postgres-products-secret -n shopping-cart-data
```
