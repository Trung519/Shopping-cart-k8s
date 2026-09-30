# Copilot Instructions — Shopping Cart Infra

## Repository Overview

Shared infrastructure for the Shopping Cart platform:
- **`/.github/workflows/build-push-deploy.yml`** — reusable CI workflow called by all 5 app repos
- **`/.github/workflows/validate.yml`** — CI: yamllint + kubeconform + kustomize build on every PR
- **`/argocd/`** — ArgoCD Applications, AppProject, config
- **`/data-layer/`** — PostgreSQL, Redis, RabbitMQ StatefulSets + ESO ExternalSecrets
- **`/identity/`** — Keycloak + OpenLDAP (Kustomize overlays)
- **`/namespaces/`** — Namespace definitions
- **`/docs/`** — architecture, CI/CD, RabbitMQ, Vault, and issue documentation

---

## Architecture Guardrails

### Reusable Workflow — Handle With Care
- `build-push-deploy.yml` is called by all 5 app repos — a breaking change here breaks all of them
- Always pin action versions to a tag (`@v4`, `@v5`) — never `@main` or `@latest`
- The workflow accepts `PACKAGES_TOKEN` as an optional secret — never make it required without updating all 5 callers
- `continue-on-error: true` on Trivy scan and kustomization update steps is intentional — do not remove
- `GH_TOKEN=${{ secrets.PACKAGES_TOKEN }}` forwarded as Docker build secret — required for GitHub Packages auth

### Kustomization Updates
- App image tags are in each app repo's `k8s/<app>/base/kustomization.yaml` — updated by CI in the app repo, not here
- `identity/ldap/` and `identity/keycloak/` use Kustomize overlays managed in this repo

### GitOps Principle
- ArgoCD watches this repo for changes to `argocd/`, `data-layer/`, `identity/`, and `namespaces/` manifests
- Never apply manifests directly to the cluster — always go through ArgoCD
- Exception: the initial `secrets` namespace bootstrap resources (`vault-bridge`, `ClusterSecretStore`) may be applied by k3d-manager `bin/acg-up` before ArgoCD reconciliation; do not treat the entire `data-layer/secrets/` tree as excluded from ArgoCD

### Manifest CI (validate.yml)
- Every PR runs yamllint + kubeconform + kustomize-build
- kubeconform uses `--ignore-missing-schemas` for CRDs (ESO, ArgoCD Application)
- yamllint has `indentation: disable` — pre-existing debt; kubeconform handles structural correctness

### ESO ExternalSecret Rules
- `storeRef.kind` must be `ClusterSecretStore` — no namespace-scoped SecretStore is deployed on the remote k3s cluster; using `kind: SecretStore` will cause `SecretSyncedError` on every ExternalSecret
- `remoteRef.key` paths must match what `bin/acg-up` seeds in Vault KV: `secret/data/redis/cart`, `secret/data/redis/orders-cache`, `secret/data/postgres/orders`, `secret/data/postgres/products`, `secret/data/postgres/payment`, `secret/data/rabbitmq/default`, `secret/data/payment/encryption`, `secret/data/payment/stripe`, `secret/data/payment/paypal`
- `refreshInterval` must be `24h` for static KV credentials — `1h` is for rotating dynamic creds only; the ACG sandbox does not run the Vault DB engine
- Do not use `database/creds/<role>` paths in `remoteRef.key` — the Vault DB engine is not configured on ACG sandbox; those paths do not exist
- Do not hardcode credentials in `spec.target.template.data` — all credential values (including RabbitMQ) must come from Vault KV via `data[].remoteRef`; hardcoded values bypass ESO/Vault and cannot be rotated
- Every ExternalSecret must set `spec.target.template.metadata.labels` on the generated Secret — use the same `app.kubernetes.io/*` label set as the ExternalSecret resource itself

### RabbitMQ Credentials
- RabbitMQ StatefulSet must set `RABBITMQ_DEFAULT_USER` and `RABBITMQ_DEFAULT_PASS` from `rabbitmq-credentials` secret (managed by `rabbitmq-externalsecret.yaml` in `shopping-cart-data`)
- App-namespace ExternalSecrets that include RabbitMQ env keys (`RABBITMQ_USERNAME`, `RABBITMQ_PASSWORD`, `RABBITMQ_USER`) must source them from `secret/data/rabbitmq/default` via `remoteRef` — never hardcode `guest` or any other value in the template
- The Vault KV path `secret/data/rabbitmq/default` is seeded by `bin/acg-up` in k3d-manager; if it is missing, the ExternalSecret will fail to sync

---

## Security Rules (treat violations as bugs)

### Supply Chain (OWASP A08)
- All GitHub Actions steps must pin to a version tag — never `@main` or `@latest`
- Docker image references in `k8s/` manifests must use pinned SHA or version tags, not `latest`
- Never add a new action without pinning its SHA or version tag

### Secrets (OWASP A02)
- Never hardcode tokens, passwords, or registry credentials in workflow files
- `PACKAGES_TOKEN` must always be passed as a secret input, never as a plain env var
- Vault secrets are managed by ESO — never add raw secrets to `k8s/` manifests

### Least Privilege (OWASP A01)
- Workflow `permissions` must be scoped to minimum required (`contents: write`, `packages: write` only where needed)
- New ServiceAccounts must not use `cluster-admin` — use namespace-scoped Role + RoleBinding

---

## Workflow Change Protocol

When modifying `build-push-deploy.yml`:
1. Test the change in isolation before merging
2. After merge, update the SHA reference in all 5 calling workflows:
   - `shopping-cart-order/.github/workflows/ci.yml`
   - `shopping-cart-payment/.github/workflows/ci.yaml`
   - `shopping-cart-product-catalog/.github/workflows/ci.yml`
   - `shopping-cart-frontend/.github/workflows/ci.yml`
   - `shopping-cart-basket/.github/workflows/go-ci.yml`
3. Each caller pins to a full 40-char SHA — never a branch name

---

## Completion Report Requirements

Before marking any task complete, the agent must provide:
- Confirmation no action version was unpinned
- Confirmation `continue-on-error` gates were not removed
- List of exact files modified
- If `build-push-deploy.yml` was changed: SHA and list of callers updated

---

## What NOT To Do

- Do not remove `continue-on-error: true` from Trivy scan or kustomization update steps
- Do not make `PACKAGES_TOKEN` a required secret — it must remain optional
- Do not add `latest` image tags to production `kustomization.yaml` files
- Do not apply k8s manifests directly — ArgoCD is the only deployment mechanism
- Do not add new workflows that duplicate the reusable workflow's function
