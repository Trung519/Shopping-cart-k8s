# Shopping Cart Infrastructure Repository

**Repository Type:** Implementation

## Overview

This repository contains the **actual Kubernetes infrastructure implementation** for the Shopping Cart GitOps demo application. It is one of 5 repositories in the multi-repo architecture:

- **shopping-cart-frontend** - React application (separate repo)
- **shopping-cart-product-catalog** - Python service (separate repo)
- **shopping-cart-cart** - Go service (separate repo)
- **shopping-cart-order** - Java service (separate repo)
- **shopping-cart-infrastructure** - This repository (Kubernetes manifests, Helm charts)

## Purpose

This repository provides:

1. **Data Layer Infrastructure** - PostgreSQL and Redis StatefulSets
2. **Vault Integration** - Dynamic database credentials and secure secrets management
3. **Helm Charts** - Application service deployment templates
4. **Argo CD Applications** - GitOps deployment configuration
5. **External Secrets** - Vault integration for credential management
6. **Namespace Definitions** - Two-tier namespace model

**Planned:** RabbitMQ message queue for asynchronous order processing and event-driven architecture (see [Message Queue Implementation Plan](docs/plans/message-queue-implementation.md))

## Architecture Reference

For detailed architecture documentation, design decisions, and GitOps patterns, see **[docs/architecture.md](docs/architecture.md)**.

## Runtime Ownership

The shared data layer, Keycloak, ExternalSecrets, and Istio Gateway API resources
have moved to the sibling `shopping-integration/helmchart`. Environment values and
secret references live in the private sibling `config-secret-secure` repository.
This repository retains Argo CD definitions, LDAP, CI helpers, and historical
operations documentation.

## Two-Tier Namespace Model

### shopping-cart-data
- PostgreSQL/RepMgr/Pgpool for products and orders
- Payment PostgreSQL, Redis cart, and RabbitMQ
- ExternalSecrets and persistent storage

### shopping-cart-apps
- Application deployments (frontend, product-catalog, cart, order)
- Application ConfigMaps and Secrets
- Istio sidecars and DestinationRules

## Prerequisites

- k3d-manager cluster with required components:
  - Istio service mesh
  - HashiCorp Vault
  - External Secrets Operator (ESO)
  - Argo CD
- kubectl configured
- Vault initialized and unsealed

## Deployment

### 1. Deploy Shared Runtime

```bash
cd ../shopping-integration
KUBE_CONTEXT=k3d-lab-k8s ./scripts/install-platform.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/bootstrap-vault.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-integration.sh
```

See `../shopping-integration/docs/helm-migration-runbook.md` for backup, restore,
verification, GitOps activation, and rollback steps.

### 2. Deploy via Argo CD (GitOps)

```bash
# Apply AppProject
kubectl apply -f argocd/projects/shopping-cart.yaml

# Deploy infrastructure (PostgreSQL + Redis)
kubectl apply -f argocd/applications/shopping-cart-infrastructure.yaml

# Deploy application services
kubectl apply -f argocd/applications/shopping-cart-dev.yaml

# Verify sync status
argocd app list
argocd app get shopping-cart-dev
```

## Resource Requirements

### Demo Environment (8GB System)
- **PostgreSQL Products:** 256Mi request / 512Mi limit
- **PostgreSQL Orders:** 256Mi request / 512Mi limit
- **Redis Cart:** 128Mi request / 256Mi limit
- **Redis Orders Cache:** 128Mi request / 256Mi limit
- **Total Data Layer:** ~768Mi request / ~1.5Gi limit

### Production Environment
Override resources in `chart/values-prod.yaml`:
- PostgreSQL: 1Gi - 2Gi per instance
- Redis: 512Mi - 1Gi per instance
- Enable persistent storage with appropriate StorageClass

## Vault Integration

### Database Secrets Engine
PostgreSQL credentials are generated dynamically by Vault:

```bash
# Vault configuration (automated by setup script)
vault secrets enable database

vault write database/config/postgresql-products \
  plugin_name=postgresql-database-plugin \
  allowed_roles="products-readonly" \
  connection_url="postgresql://{{username}}:{{password}}@postgresql-products.shopping-cart-data.svc.cluster.local:5432/products" \
  username="postgres" \
  password="$POSTGRES_PASSWORD"

vault write database/roles/products-readonly \
  db_name=postgresql-products \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"
```

### Static Secrets (Redis)
Redis passwords stored in Vault KV:

```bash
vault kv put secret/redis/cart password="changeme"
vault kv put secret/redis/orders password="changeme"
```

### ExternalSecret Sync
ESO automatically syncs secrets from Vault to Kubernetes:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-products-secret
  namespace: shopping-cart-data
spec:
  refreshInterval: 1h
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

## CI/CD Integration

### Overview
This repository integrates with GitHub Actions and Jenkins for automated container image builds and deployments.

**Workflow:**
1. Application repo triggers GitHub Actions on push
2. GitHub Actions builds and pushes image to GHCR
3. GitHub Actions triggers Jenkins webhook
4. Jenkins updates this repo's Helm values
5. Argo CD syncs and deploys to Kubernetes

### Documentation
- **[Container Image Workflow Guide](docs/container-image-workflow.md)** - Complete guide for building and pushing images to GHCR
- **[GitHub Actions & Jenkins Webhook Setup](docs/github-actions-webhook-setup.md)** - Step-by-step integration instructions
- **[Container Image Versioning Policy](docs/versioning-policy.md)** - Semantic tag policy (`vMAJOR.MINOR.PATCH`) and bump rules

### Automation Scripts
Located in `bin/`:
- **`build-and-push.sh`** - Build and push container images locally for testing
- **`setup-service-repo.sh`** - Automate GitHub repository creation with Actions workflows
- **`deploy-infra.sh`** - Deploy complete infrastructure stack

### Example: Automated CI Pipeline
```bash
# Example: Product Catalog service CI pipeline
# 1. Build and push image: ghcr.io/user/product-catalog:abc123
# 2. Clone this repository
# 3. Update image tag in chart/values-dev.yaml
yq eval ".productCatalog.image.tag = 'abc123'" -i chart/values-dev.yaml
# 4. Commit and push
git commit -m "Update product-catalog to abc123"
git push origin main
# 5. Argo CD detects change and syncs
```

See the blueprint repository's `docs/cicd-guide.md` for additional CI/CD patterns.

## Monitoring and Health Checks

```bash
# Check data layer pods
kubectl get pods -n shopping-cart-data

# Check PostgreSQL connectivity
kubectl run -n shopping-cart-data test-pg --rm -it --image=postgres:15-alpine -- psql -h postgresql-products -U postgres -d products

# Check Redis connectivity
kubectl run -n shopping-cart-data test-redis --rm -it --image=redis:7-alpine -- redis-cli -h redis-cart ping

# Check ExternalSecret sync status
kubectl get externalsecrets -n shopping-cart-data
kubectl describe externalsecret postgres-products-secret -n shopping-cart-data

# Verify Argo CD sync
argocd app list
argocd app get shopping-cart-infrastructure
```

## Troubleshooting

### ExternalSecret Not Syncing
```bash
# Check SecretStore status
kubectl get secretstore -n shopping-cart-data
kubectl describe secretstore vault-backend -n shopping-cart-data

# Check ESO controller logs
kubectl logs -n external-secrets deployment/external-secrets

# Verify Vault connectivity from pod
kubectl run -n shopping-cart-data test-vault --rm -it --image=curlimages/curl -- curl -k https://vault.vault.svc.cluster.local:8200/v1/sys/health
```

### PostgreSQL Connection Issues
```bash
# Check StatefulSet status
kubectl describe statefulset postgresql-products -n shopping-cart-data

# Check PVC status
kubectl get pvc -n shopping-cart-data

# View logs
kubectl logs -n shopping-cart-data postgresql-products-0

# Test connection with generated credentials
kubectl get secret postgres-products-secret -n shopping-cart-data -o jsonpath='{.data.username}' | base64 -d
kubectl get secret postgres-products-secret -n shopping-cart-data -o jsonpath='{.data.password}' | base64 -d
```

### Redis Connection Issues
```bash
# Check StatefulSet status
kubectl describe statefulset redis-cart -n shopping-cart-data

# View logs
kubectl logs -n shopping-cart-data redis-cart-0

# Test authentication
kubectl run -n shopping-cart-data test-redis --rm -it --image=redis:7-alpine -- redis-cli -h redis-cart -a $(kubectl get secret redis-cart-secret -n shopping-cart-data -o jsonpath='{.data.password}' | base64 -d) ping
```

## Security Best Practices

1. **Never commit secrets** - All credentials managed by Vault and ESO
2. **Use network policies** - Restrict inter-service communication
3. **Enable TLS** - PostgreSQL and Redis should use TLS in production
4. **Rotate credentials** - Vault automatically rotates database credentials
5. **Audit access** - Monitor Vault audit logs for secret access
6. **Limit privileges** - Database roles should have minimal required permissions

## Development

### Local Testing
```bash
# Create k3d cluster with required components
./scripts/k3d-manager deploy_cluster
./scripts/k3d-manager deploy_vault
./scripts/k3d-manager deploy_eso

# Deploy Helm-managed infrastructure
../shopping-integration/scripts/install-platform.sh
../shopping-integration/scripts/bootstrap-vault.sh
../shopping-integration/scripts/deploy-integration.sh
```

### Configuration Changes
1. Modify manifests in this repository
2. Commit and push changes
3. Argo CD automatically syncs (if auto-sync enabled)
4. Or manually sync: `argocd app sync shopping-cart-infrastructure`

## Planned Enhancements

### Message Queue Infrastructure (RabbitMQ)

**Status**: Complete (Stages 1-4)

**Objective**: RabbitMQ message queue for asynchronous order processing and event-driven architecture.

**Benefits**:
- Faster user response times (order creation < 100ms vs 500ms+ synchronous)
- Automatic retry on failures
- Independent service scaling
- Better fault isolation
- Event-driven microservices communication

**Documentation**:
- [Message Schemas & Event Contracts](docs/message-schemas.md) - Event definitions, queue design
- [Message Queue Implementation Plan](docs/plans/message-queue-implementation.md) - Architecture and design
- [RabbitMQ Operations Guide](docs/rabbitmq-operations.md) - Cluster operations, scaling, backup
- [RabbitMQ Load Testing Guide](docs/rabbitmq-load-testing.md) - Load testing, alerting, queue management
- [Client Library Design](docs/rabbitmq-client-library-design.md) - Client library architecture

**Quick Start**:
```bash
# Check status
make status

# Run load test
make load-test-quick

# View alerts
make alerts

# Open management UIs
make grafana      # Grafana dashboard
make prometheus   # Prometheus metrics
make rabbitmq-ui  # RabbitMQ management
```

**Use Cases**:
- Order processing pipeline (payment, email, fulfillment)
- Inventory updates and cache invalidation
- Shopping cart abandonment notifications
- Cross-service event broadcasting

**Client Libraries**: See separate repositories:
- [rabbitmq-client-library](../rabbitmq-client-library) - Python implementation
- [rabbitmq-client-go](../rabbitmq-client-go) - Go implementation
- [rabbitmq-client-java](../rabbitmq-client-java) - Java implementation
- [rabbitmq-client-dotnet](../rabbitmq-client-dotnet) - .NET implementation

---

### Vault Integration Enhancements

**Current**: Dynamic PostgreSQL credentials, static Redis passwords

**Documentation**:
- [Vault Usage Guide](docs/vault-usage-guide.md) - Complete integration guide
- [Vault Password Rotation](docs/vault-password-rotation.md) - Rotation testing and best practices
- [Integration Test](bin/test-vault-integration.sh) - Automated Vault functionality test
- [Rotation Test](bin/test-vault-rotation.sh) - Password lifecycle validation

## License

Apache 2.0

## Related Repositories

- **Application Services:**
  - [shopping-cart-frontend](https://github.com/wilddog64/shopping-cart-frontend)
  - [shopping-cart-product-catalog](https://github.com/wilddog64/shopping-cart-product-catalog)
  - [shopping-cart-order](https://github.com/wilddog64/shopping-cart-order)
  - [shopping-cart-payment](https://github.com/wilddog64/shopping-cart-payment)
  - [shopping-cart-basket](https://github.com/wilddog64/shopping-cart-basket)
