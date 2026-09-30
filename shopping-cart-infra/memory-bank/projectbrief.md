# Project Brief: shopping-cart-infra

## What This Project Does

`shopping-cart-infra` is the **implementation repository** for the Shopping Cart platform's Kubernetes infrastructure. It contains all Kubernetes manifests, Helm charts, and Argo CD configurations for deploying the data layer (PostgreSQL, Redis, RabbitMQ) and application services to Kubernetes.

This is the GitOps single source of truth: all infrastructure changes flow through this repository, and Argo CD syncs the cluster state from it.

## Goals

1. Provide a fully declarative, GitOps-managed infrastructure for the Shopping Cart platform
2. Manage all stateful data components (PostgreSQL, Redis, RabbitMQ) as Kubernetes StatefulSets
3. Integrate with HashiCorp Vault via External Secrets Operator for zero-plaintext-credential deployments
4. Automate CI/CD: GitHub Actions → Jenkins → this repo → Argo CD → cluster
5. Support both demo (8GB RAM k3d) and production environments via Helm values overrides

## Scope

- Kubernetes namespace management (`shopping-cart-data`, `shopping-cart-apps`)
- PostgreSQL StatefulSets (products DB + orders DB) with Vault-generated credentials via ESO
- Redis StatefulSets (cart cache + orders cache) with Vault KV credentials via ESO
- RabbitMQ StatefulSet with Vault dynamic credentials
- ExternalSecret definitions for all credential syncing
- Vault database secrets engine configuration script
- Helm chart for application services (product-catalog, basket, order, frontend)
- Argo CD AppProject + Application manifests for GitOps sync
- CI/CD automation scripts and Dockerfile/workflow templates in `examples/`
- Identity stack: Keycloak + OpenLDAP in `identity` namespace

## Platform Role

One of five repositories in the Shopping Cart multi-repo architecture:
1. `shopping-cart-frontend` — React SPA
2. `shopping-cart-product-catalog` — Python/FastAPI
3. `shopping-cart-basket` — Go/Gin
4. `shopping-cart-order` — Java/Spring Boot
5. **`shopping-cart-infra` (this repo)** — Kubernetes infrastructure + GitOps

## Two-Namespace Model

- `shopping-cart-data` — StatefulSets, PVCs, secrets (infrastructure layer)
- `shopping-cart-apps` — Deployments, Services (application layer)

Separation provides clear blast radius, different RBAC policies, independent resource quotas, and network policy enforcement.
