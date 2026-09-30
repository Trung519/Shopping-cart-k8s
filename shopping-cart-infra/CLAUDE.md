# CLAUDE.md - Shopping Cart Infrastructure Repository

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **implementation repository** for Shopping Cart infrastructure. It contains actual Kubernetes manifests, Helm charts, and Argo CD configurations for deploying the data layer (PostgreSQL, Redis) and application services.

**Repository Type:** Infrastructure/Configuration (Kubernetes manifests, Helm, Argo CD)
**Related Blueprint Repository:** [shopping-cart](https://github.com/user/shopping-cart) - Contains architecture documentation and planning

## Repository Purpose

This repository is **one of five** in the multi-repo GitOps architecture:

1. **shopping-cart-frontend** - React application code
2. **shopping-cart-product-catalog** - Python service code
3. **shopping-cart-cart** - Go service code
4. **shopping-cart-order** - Java service code
5. **shopping-cart-infrastructure** - This repository (deployment manifests)

## Key Design Decisions

### Why PostgreSQL and Redis Together?
Both infrastructure components are in this repository because:
- Deployed to same namespace (`shopping-cart-data`)
- Share Vault/ESO integration patterns
- Coordinated lifecycle management
- Same team ownership (ops/platform)
- Avoids proliferation of tiny repos (6+ repos total)

### Two-Namespace Model
- `shopping-cart-data` - Infrastructure layer (StatefulSets, PVCs, secrets)
- `shopping-cart-apps` - Application layer (Deployments, Services)

Separation provides:
- Clear blast radius for infrastructure changes
- Different RBAC policies
- Independent resource quotas
- Network policy enforcement

### Vault Integration Pattern
**Database Credentials (Dynamic):**
- Vault database secrets engine generates time-limited credentials
- ExternalSecrets syncs credentials to Kubernetes secrets
- Applications consume standard K8s secrets (unaware of Vault)

**Static Secrets (Redis):**
- Stored in Vault KV secrets engine
- ExternalSecrets syncs to Kubernetes secrets
- Single source of truth in Vault

**Vault Integration Documentation:**
- [Vault Usage Guide](docs/vault-usage-guide.md) - Complete integration guide
- [Vault Password Rotation](docs/vault-password-rotation.md) - Rotation testing and best practices
- [Integration Test](bin/test-vault-integration.sh) - Automated Vault functionality test
- [Rotation Test](bin/test-vault-rotation.sh) - Password lifecycle validation

### Message Queue (RabbitMQ)

**Status**: Stages 1-2 Complete, Stage 3 (Python Client) Complete

**Objective**: Add RabbitMQ to `shopping-cart-data` namespace for asynchronous order processing and event-driven architecture.

**Key Benefits:**
- Decouple order creation from payment/email/fulfillment
- Fast user responses (< 100ms vs 500ms+ synchronous)
- Automatic retry on failures
- Independent service scaling
- Event-driven microservices communication

**Implementation Progress:**
1. **Stage 1**: RabbitMQ StatefulSet deployment ✅ COMPLETE
2. **Stage 2**: Vault integration for dynamic credentials ✅ COMPLETE
3. **Stage 3**: Client Library - Python ✅ COMPLETE (see below)
4. **Stage 3**: Client Library - Go (Planned for separate repo)
5. **Stage 3**: Client Library - Java (Planned for separate repo)
6. **Stage 4**: Monitoring & production readiness (Pending)

**Client Library - Python (COMPLETE):**

Located in separate repository: `rabbitmq-client-library/python/`

Features implemented:
- ✅ Configuration management with validation
- ✅ Connection management with Vault credential integration
- ✅ Publisher with confirmation support and JSON serialization
- ✅ Consumer with auto/manual acknowledgment
- ✅ Thread-safe connection pooling
- ✅ Circuit breaker pattern (CLOSED/OPEN/HALF_OPEN)
- ✅ Retry logic with exponential backoff (tenacity)
- ✅ Structured logging (structlog, JSON/console)
- ✅ Prometheus metrics (publish/consume latency, pool stats, etc.)
- ✅ Health checks (liveness, readiness, detailed status)
- ✅ Dead Letter Queue (DLQ) support
- ✅ 233 tests (224 unit + 9 performance benchmarks)

**Client Library - Go (Planned):**
- Will be in separate repository (`rabbitmq-client-go`) for Go module compatibility
- Independent versioning from Python library
- Native integration with Cart service (Go)

**Client Library - Java (Planned):**
- Will be in separate repository (`rabbitmq-client-java`) for Maven/Gradle compatibility
- Independent versioning from other libraries
- Native integration with Order service (Java/Spring Boot)

**Primary Use Cases:**
- Order processing pipeline (payment → email → fulfillment)
- Inventory updates → cache invalidation
- Cart abandonment notifications
- Cross-service event broadcasting

**Directory Structure (Deployed):**
```
data-layer/
└── rabbitmq/
    ├── statefulset.yaml       # RabbitMQ cluster
    ├── service.yaml           # AMQP + Management UI
    ├── configmap.yaml         # RabbitMQ configuration
    └── ...
```

See [Message Queue Implementation Plan](docs/plans/message-queue-implementation.md) for complete architecture and queue design.

## Repository Structure

```
shopping-cart-infrastructure/
├── bin/                            # Automation scripts
│   ├── build-and-push.sh           # Build/push container images to GHCR
│   ├── setup-service-repo.sh       # Automate GitHub repo creation
│   └── deploy-infra.sh             # Deploy infrastructure stack
├── docs/                           # Documentation
│   ├── container-image-workflow.md # GHCR image build/push guide
│   └── github-actions-webhook-setup.md  # CI/CD integration guide
├── examples/                       # Templates and examples
│   ├── dockerfiles/                # Multi-stage Dockerfiles (Node, Python, Java, Go)
│   ├── github-actions/             # GitHub Actions workflow templates
│   └── README.md                   # Quick start guide
├── data-layer/                     # Infrastructure manifests
│   ├── postgresql/
│   │   ├── products/               # Product catalog database
│   │   │   ├── statefulset.yaml
│   │   │   ├── service.yaml
│   │   │   ├── pvc.yaml
│   │   │   └── init-db.sql         # Schema initialization
│   │   └── orders/                 # Order service database
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       ├── pvc.yaml
│   │       └── init-db.sql
│   ├── redis/
│   │   ├── cart/                   # Shopping cart session storage
│   │   │   ├── statefulset.yaml
│   │   │   ├── service.yaml
│   │   │   └── pvc.yaml
│   │   └── orders-cache/           # Order service cache
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       └── pvc.yaml
│   └── secrets/
│       ├── postgres-products-secret.yaml   # ESO → Vault DB engine
│       ├── postgres-orders-secret.yaml     # ESO → Vault DB engine
│       ├── redis-cart-secret.yaml          # ESO → Vault KV
│       └── redis-orders-secret.yaml        # ESO → Vault KV
├── namespaces/
│   └── namespaces.yaml             # Namespace definitions
├── vault/
│   └── setup-database-secrets-engine.sh  # Vault DB secrets config
├── chart/                          # Helm chart for applications
│   ├── Chart.yaml
│   ├── values.yaml                 # Demo (8GB constraints)
│   ├── values-prod.yaml            # Production overrides
│   └── templates/
│       ├── product-catalog/        # Python service manifests
│       ├── cart/                   # Go service manifests
│       ├── order/                  # Java service manifests
│       └── frontend/               # React + Nginx manifests
└── argocd/
    ├── projects/
    │   └── shopping-cart.yaml      # AppProject definition
    └── applications/
        ├── shopping-cart-infrastructure.yaml  # Data layer app
        ├── shopping-cart-dev.yaml             # Dev environment
        └── shopping-cart-prod.yaml            # Prod environment
```

## Development Workflow

### 1. Infrastructure Changes (PostgreSQL/Redis)
```bash
# Modify manifest
vim data-layer/postgresql/products/statefulset.yaml

# Test locally
kubectl apply --dry-run=client -f data-layer/postgresql/products/

# Commit and push
git add data-layer/postgresql/products/statefulset.yaml
git commit -m "feat(postgres): increase product DB memory limit"
git push origin main

# Argo CD auto-syncs (if enabled) or manual sync
argocd app sync shopping-cart-infrastructure
```

### 2. Application Service Changes (via CI/CD)
Application repositories update this repo's Helm values:

```bash
# Triggered by shopping-cart-product-catalog Jenkins pipeline
# 1. Jenkins builds image: ghcr.io/user/product-catalog:abc123
# 2. Jenkins clones this repo
# 3. Jenkins updates Helm values
yq eval ".productCatalog.image.tag = 'abc123'" -i chart/values-dev.yaml
# 4. Jenkins commits and pushes
git commit -m "chore: update product-catalog to abc123"
git push origin main
# 5. Argo CD detects change and syncs application
```

### 3. Adding New Infrastructure Component
When adding a new database or cache:
1. Create directory under `data-layer/<component>/<instance>/`
2. Add StatefulSet, Service, PVC manifests
3. Create ExternalSecret in `data-layer/secrets/`
4. Update `vault/setup-database-secrets-engine.sh` if using Vault DB engine
5. Test deployment in dev namespace
6. Document in this file

## CI/CD Automation

### Documentation
This repository includes comprehensive CI/CD documentation:
- **`docs/container-image-workflow.md`** - Complete guide for building and pushing container images to GHCR
- **`docs/github-actions-webhook-setup.md`** - Step-by-step GitHub Actions and Jenkins webhook integration
- **`examples/README.md`** - Quick start guide with Dockerfiles and workflow templates

### Automation Scripts (`bin/`)

#### build-and-push.sh
Build and push container images locally for testing:

```bash
# Build only (local test)
./bin/build-and-push.sh product-catalog

# Build and push to GHCR
./bin/build-and-push.sh product-catalog latest --push

# Build with custom tag
./bin/build-and-push.sh shopping-cart v1.2.3 --push
```

**Features:**
- Creates temporary build context with sample app
- Auto-tags with git SHA
- Tests container locally before pushing
- Supports Node.js, Python, Java, Go service types

#### setup-service-repo.sh
Automate GitHub repository creation with complete CI/CD setup:

```bash
# Create new service repository with GitHub Actions
./bin/setup-service-repo.sh \
  --service product-catalog \
  --type nodejs \
  --jenkins-url https://jenkins.example.com/generic-webhook-trigger/invoke \
  --jenkins-token your-webhook-token

# Supported types: nodejs, python, java, go
```

**What it does:**
1. Creates GitHub repository using `gh` CLI
2. Copies appropriate Dockerfile template
3. Adds GitHub Actions workflow
4. Configures repository secrets (JENKINS_WEBHOOK_URL, JENKINS_WEBHOOK_TOKEN)
5. Creates sample application code
6. Enables GitHub Actions
7. Pushes initial commit

#### deploy-infra.sh
Deploy complete infrastructure stack:

```bash
# Deploy with Vault setup
./bin/deploy-infra.sh

# Deploy specific components
./bin/deploy-infra.sh --vault-only
./bin/deploy-infra.sh --postgres-only
```

### CI/CD Workflow

**Complete Pipeline:**
```
1. Developer pushes code to application repo (e.g., shopping-cart-product-catalog)
   ↓
2. GitHub Actions workflow triggers (build-push.yml)
   - Lints Dockerfile (Hadolint)
   - Scans for vulnerabilities (Trivy)
   - Builds multi-stage Docker image
   - Tags with multiple strategies:
     * main-abc1234 (branch-sha)
     * main (branch name)
     * latest (if main branch)
   - Pushes to GHCR (ghcr.io/user/product-catalog:main-abc1234)
   ↓
3. GitHub Actions triggers Jenkins webhook
   - Sends image tag, git SHA, commit message
   ↓
4. Jenkins pipeline executes
   - Clones this infrastructure repository
   - Updates Helm values: chart/values-dev.yaml
   - Updates image tag using yq
   - Commits and pushes to main branch
   ↓
5. Argo CD detects change
   - Syncs application with new image tag
   - Deploys to Kubernetes (shopping-cart-apps namespace)
```

### Example GitHub Actions Workflow
Located in `examples/github-actions/build-push.yml`:

```yaml
# Triggered on: push to main/develop, PRs, releases
# Jobs:
#   - lint: Hadolint + Trivy (PRs only)
#   - build-and-push: Build, tag, push to GHCR
#   - test-image: Health check validation
#   - trigger-jenkins: Webhook notification (main branch only)
```

### Example Dockerfiles
Located in `examples/dockerfiles/`:
- **Dockerfile.product-catalog** - Node.js with Alpine, multi-stage
- **Dockerfile.shopping-cart** - Python with slim image, Gunicorn
- **Dockerfile.order-service** - Java with Maven, JRE-only runtime
- **Dockerfile.payment-service** - Go with scratch base (~10MB)

## Configuration Management

### Resource Constraints
**Demo Environment (values.yaml):**
- Total system memory: 8GB
- Target allocation: ~1.2Gi requests, ~2.5Gi limits
- PostgreSQL: 256Mi request / 512Mi limit per instance
- Redis: 128Mi request / 256Mi limit per instance

**Production Environment (values-prod.yaml):**
```yaml
postgresql:
  products:
    resources:
      requests:
        memory: 1Gi
      limits:
        memory: 2Gi
  orders:
    resources:
      requests:
        memory: 1Gi
      limits:
        memory: 2Gi

redis:
  cart:
    resources:
      requests:
        memory: 512Mi
      limits:
        memory: 1Gi
```

### Persistent Storage
**Demo:** hostPath volumes (k3d)
**Production:** Cloud storage classes (AWS EBS, GCP Persistent Disk, Azure Disk)

Update PVC manifests with appropriate storageClassName.

## External Secrets Operator (ESO) Integration

### Architecture
```
Vault (Source of Truth)
  ↓
SecretStore (ESO cluster-wide config)
  ↓
ExternalSecret (per-namespace config)
  ↓
Kubernetes Secret (synced automatically)
  ↓
Pods (consume standard K8s secrets)
```

### ExternalSecret Patterns

**Dynamic Database Credentials:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-products-secret
  namespace: shopping-cart-data
spec:
  refreshInterval: 1h              # Rotate hourly
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: postgres-products-secret
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

**Static Secrets (Redis):**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: redis-cart-secret
  namespace: shopping-cart-data
spec:
  refreshInterval: 24h             # Check daily for updates
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: redis-cart-secret
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/redis/cart
        property: password
```

### Debugging ESO Issues
```bash
# Check SecretStore status
kubectl get secretstore -A
kubectl describe secretstore vault-backend -n shopping-cart-data

# Check ExternalSecret sync status
kubectl get externalsecret -n shopping-cart-data
kubectl describe externalsecret postgres-products-secret -n shopping-cart-data

# Check generated Kubernetes secret
kubectl get secret postgres-products-secret -n shopping-cart-data
kubectl describe secret postgres-products-secret -n shopping-cart-data

# ESO controller logs
kubectl logs -n external-secrets deployment/external-secrets-operator
```

## Vault Database Secrets Engine

### Configuration Script
`vault/setup-database-secrets-engine.sh` configures Vault to generate PostgreSQL credentials:

```bash
#!/usr/bin/env bash
# Configure Vault database secrets engine for PostgreSQL

vault secrets enable database

# Products database
vault write database/config/postgresql-products \
  plugin_name=postgresql-database-plugin \
  allowed_roles="products-readonly,products-readwrite" \
  connection_url="postgresql://{{username}}:{{password}}@postgresql-products.shopping-cart-data.svc.cluster.local:5432/products" \
  username="postgres" \
  password="${POSTGRES_PRODUCTS_PASSWORD}"

# Readonly role
vault write database/roles/products-readonly \
  db_name=postgresql-products \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Orders database (similar configuration)
vault write database/config/postgresql-orders \
  plugin_name=postgresql-database-plugin \
  allowed_roles="orders-readwrite" \
  connection_url="postgresql://{{username}}:{{password}}@postgresql-orders.shopping-cart-data.svc.cluster.local:5432/orders" \
  username="postgres" \
  password="${POSTGRES_ORDERS_PASSWORD}"

vault write database/roles/orders-readwrite \
  db_name=postgresql-orders \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"
```

### Testing Credential Generation
```bash
# Read credentials (Vault generates new user)
vault read database/creds/products-readonly
# Output:
# Key                Value
# ---                -----
# lease_id           database/creds/products-readonly/abc123
# lease_duration     1h
# lease_renewable    true
# password           A1a-randompassword
# username           v-root-products-readonly-abc123

# Verify in PostgreSQL
kubectl exec -n shopping-cart-data postgresql-products-0 -- psql -U v-root-products-readonly-abc123 -d products -c "\du"
```

## Argo CD Configuration

### AppProject (argocd/projects/shopping-cart.yaml)
Defines allowed source repos, destination namespaces, and resource types:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: shopping-cart
  namespace: argocd
spec:
  description: Shopping Cart microservices application

  # Allowed source repositories
  sourceRepos:
    - 'https://github.com/user/shopping-cart-infrastructure'

  # Allowed destination clusters and namespaces
  destinations:
    - namespace: shopping-cart-data
      server: https://kubernetes.default.svc
    - namespace: shopping-cart-apps
      server: https://kubernetes.default.svc

  # Allowed resource types (security: prevent cluster-admin escalation)
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace

  namespaceResourceWhitelist:
    - group: '*'
      kind: '*'
```

### Application (argocd/applications/shopping-cart-infrastructure.yaml)
Deploys data layer infrastructure:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: shopping-cart-infrastructure
  namespace: argocd
spec:
  project: shopping-cart

  source:
    repoURL: https://github.com/user/shopping-cart-infrastructure
    targetRevision: main
    path: data-layer

  destination:
    server: https://kubernetes.default.svc
    namespace: shopping-cart-data

  syncPolicy:
    automated:
      prune: true        # Delete resources not in git
      selfHeal: true     # Auto-fix manual changes
    syncOptions:
      - CreateNamespace=true
```

### Application (argocd/applications/shopping-cart-dev.yaml)
Deploys application services via Helm:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: shopping-cart-dev
  namespace: argocd
spec:
  project: shopping-cart

  source:
    repoURL: https://github.com/user/shopping-cart-infrastructure
    targetRevision: main
    path: chart
    helm:
      valueFiles:
        - values.yaml         # Demo environment

  destination:
    server: https://kubernetes.default.svc
    namespace: shopping-cart-apps

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Testing Infrastructure

### Local Development Testing
```bash
# Deploy k3d cluster with prerequisites
cd /path/to/k3d-manager
./scripts/k3d-manager deploy_cluster
./scripts/k3d-manager deploy_vault
./scripts/k3d-manager deploy_eso

# Switch to infrastructure repo
cd /path/to/shopping-cart-infra

# Deploy namespaces
kubectl apply -f namespaces/namespaces.yaml

# Configure Vault (manual for testing)
export POSTGRES_PRODUCTS_PASSWORD="testpass123"
export POSTGRES_ORDERS_PASSWORD="testpass456"
./vault/setup-database-secrets-engine.sh

# Deploy PostgreSQL
kubectl apply -f data-layer/postgresql/products/
kubectl apply -f data-layer/postgresql/orders/

# Deploy Redis
kubectl apply -f data-layer/redis/cart/
kubectl apply -f data-layer/redis/orders-cache/

# Deploy ExternalSecrets
kubectl apply -f data-layer/secrets/

# Verify deployments
kubectl get pods -n shopping-cart-data
kubectl get externalsecrets -n shopping-cart-data
kubectl get secrets -n shopping-cart-data
```

### Connectivity Testing
```bash
# Test PostgreSQL connectivity
kubectl run -n shopping-cart-data test-pg --rm -it --image=postgres:15-alpine -- \
  psql -h postgresql-products -U postgres -d products -c "SELECT version();"

# Test Redis connectivity
kubectl run -n shopping-cart-data test-redis --rm -it --image=redis:7-alpine -- \
  redis-cli -h redis-cart ping

# Test with ESO-generated credentials
PGUSER=$(kubectl get secret postgres-products-secret -n shopping-cart-data -o jsonpath='{.data.username}' | base64 -d)
PGPASS=$(kubectl get secret postgres-products-secret -n shopping-cart-data -o jsonpath='{.data.password}' | base64 -d)

kubectl run -n shopping-cart-data test-pg-eso --rm -it --image=postgres:15-alpine -- \
  env PGPASSWORD="$PGPASS" psql -h postgresql-products -U "$PGUSER" -d products -c "SELECT current_user;"
```

## Common Tasks

### Adding a New Database
1. Create directory: `data-layer/postgresql/<name>/`
2. Copy and modify manifests from existing database
3. Create init SQL script: `data-layer/postgresql/<name>/init-db.sql`
4. Add ExternalSecret: `data-layer/secrets/postgres-<name>-secret.yaml`
5. Update Vault script: `vault/setup-database-secrets-engine.sh`
6. Deploy and test

### Updating Helm Chart
1. Modify templates in `chart/templates/<service>/`
2. Update `chart/values.yaml` for demo constraints
3. Update `chart/values-prod.yaml` for production settings
4. Test with `helm template` and `--dry-run`
5. Commit and push (triggers Argo CD sync)

### Promoting to Production
```bash
# Copy dev image tags to prod values
IMAGE_TAG=$(yq eval '.productCatalog.image.tag' chart/values-dev.yaml)
yq eval ".productCatalog.image.tag = \"$IMAGE_TAG\"" -i chart/values-prod.yaml

git commit -am "chore: promote product-catalog $IMAGE_TAG to production"
git push origin main

# Manual sync for production (no auto-sync)
argocd app sync shopping-cart-prod
```

## Blueprint Repository Reference

For architecture documentation, see the blueprint repository:

- **Architecture Plan:** `docs/plans/hybrid-architecture-plan.md`
- **Implementation Priority:** `docs/implementation-priority.md`
- **Repository Setup:** `docs/repository-setup-guide.md`
- **CI/CD Guide:** `docs/cicd-guide.md`

## Security Best Practices

1. **Never commit secrets** - All credentials in Vault
2. **Use least privilege** - Database roles have minimal permissions
3. **Rotate credentials** - ESO refreshInterval for automatic rotation
4. **Network policies** - Restrict pod-to-pod communication
5. **TLS everywhere** - PostgreSQL and Redis should use TLS in production
6. **Audit logs** - Monitor Vault audit logs for secret access
7. **Immutable tags** - Never use `:latest` in production
8. **GitOps principles** - All changes via Git commits

## Troubleshooting

### StatefulSet Not Starting
```bash
# Check events
kubectl describe statefulset <name> -n shopping-cart-data

# Check PVC binding
kubectl get pvc -n shopping-cart-data

# Check pod status
kubectl describe pod <name>-0 -n shopping-cart-data

# View logs
kubectl logs -n shopping-cart-data <name>-0
```

### ExternalSecret Sync Failed
```bash
# Check ExternalSecret status
kubectl describe externalsecret <name> -n shopping-cart-data

# Common issues:
# - SecretStore not configured: kubectl get secretstore -A
# - Vault not reachable: kubectl exec -n <pod> -- curl https://vault.vault.svc:8200/v1/sys/health
# - Wrong Vault path: Check remoteRef.key in ExternalSecret
# - Missing Vault policy: Check Vault audit logs
```

### Argo CD Sync Issues
```bash
# Check app status
argocd app get shopping-cart-infrastructure

# View sync status
argocd app diff shopping-cart-infrastructure

# Manual sync with logs
argocd app sync shopping-cart-infrastructure --log-level debug

# Check Argo CD controller logs
kubectl logs -n argocd deployment/argocd-application-controller
```

## Code Style and Conventions

When making changes:
- **YAML formatting:** 2-space indentation, no tabs
- **Resource naming:** `<service>-<instance>` (e.g., `postgresql-products`)
- **Labels:** Use `app.kubernetes.io/*` standard labels
- **Namespace:** Always specify explicit namespace (no defaults)
- **Comments:** Explain "why" not "what" (code is self-documenting)
- **Commits:** Use conventional commits (feat:, fix:, chore:, docs:)

## License

MIT
