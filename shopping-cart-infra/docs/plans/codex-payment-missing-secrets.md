# Codex Task: Add Missing Secret Manifests to shopping-cart-payment

**Branch:** `fix/payment-missing-secrets` (create from `main`)
**Repo:** `https://github.com/wilddog64/shopping-cart-payment`
**Priority:** HIGH — payment-service is stuck in `CreateContainerConfigError`
**Scope:** Two files in `shopping-cart-payment` only — no other repos, no cluster work

---

## Context

`payment-service` on the Ubuntu k3s cluster fails with `CreateContainerConfigError`.
The deployment manifest (`k8s/base/deployment.yaml`) references two Secrets by name,
but neither Secret exists in `k8s/base/` — there is no `secret.yaml` and
`kustomization.yaml` does not list one.

Secrets required by the deployment (verified by reading `k8s/base/deployment.yaml`):

| Secret Name | Keys Used | `optional`? |
|---|---|---|
| `payment-db-credentials` | `username`, `password` | NO — blocks startup |
| `payment-encryption-secret` | `encryption-key` | NO — blocks startup |
| `payment-gateway-secrets` | `stripe-api-key`, `paypal-client-id`, `paypal-client-secret` | YES — skip for now |

---

## Task

### Step 1 — Create `k8s/base/secret.yaml`

Add a new file `k8s/base/secret.yaml` with dev-safe placeholder credentials.
**These are development-only values.** The comment in the file must say so explicitly.

```yaml
---
# WARNING: Development-only placeholder credentials.
# In production, these must be supplied by Vault via ExternalSecrets.
# Do NOT use these values in any non-dev environment.
apiVersion: v1
kind: Secret
metadata:
  name: payment-db-credentials
  namespace: shopping-cart-payment
  labels:
    app.kubernetes.io/name: payment-service
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: shopping-cart
type: Opaque
stringData:
  username: "payment_user"
  password: "CHANGE_ME_IN_PRODUCTION"
---
# WARNING: Development-only placeholder encryption key.
# In production, this must be a 256-bit AES key from Vault.
apiVersion: v1
kind: Secret
metadata:
  name: payment-encryption-secret
  namespace: shopping-cart-payment
  labels:
    app.kubernetes.io/name: payment-service
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: shopping-cart
type: Opaque
stringData:
  encryption-key: "CHANGE_ME_32_BYTE_DEV_KEY_000000"
```

### Step 2 — Update `k8s/base/kustomization.yaml`

Add `secret.yaml` to the `resources:` list. Current resources list:

```yaml
resources:
- serviceaccount.yaml
- configmap.yaml
- deployment.yaml
- service.yaml
- networkpolicy.yaml
- hpa.yaml
```

After your change:

```yaml
resources:
- serviceaccount.yaml
- configmap.yaml
- secret.yaml
- deployment.yaml
- service.yaml
- networkpolicy.yaml
- hpa.yaml
```

---

## Acceptance Criteria

- [ ] `k8s/base/secret.yaml` created with both `payment-db-credentials` and `payment-encryption-secret`
- [ ] Both secret names match exactly what the deployment references (`payment-db-credentials`, `payment-encryption-secret`)
- [ ] Both secrets have the exact key names the deployment uses (`username`, `password`, `encryption-key`)
- [ ] `k8s/base/kustomization.yaml` lists `- secret.yaml` under `resources:`
- [ ] No other files modified
- [ ] `kustomize build k8s/base` exits 0 (run to verify the manifests parse correctly — no cluster needed)

---

## Completion Report Format (REQUIRED)

```
## Done: payment-secret-manifest

### Commit
<paste: git log origin/fix/payment-missing-secrets --oneline -3>

### kustomize build output
<paste: kustomize build k8s/base | grep -E "^(kind|name):" | head -30>

### ArgoCD App Status (infra cluster)
N/A — no cluster work

### Pod Status (ubuntu-k3s)
N/A — no cluster work

### Notes
<any errors or observations>
```

---

## Do NOT

- Do not create a PR — Claude will do that
- Do not modify any other file (no deployment.yaml, no configmap.yaml, no networkpolicy.yaml)
- Do not add real credentials — placeholders only
- Do not push to `main` — push to `fix/payment-missing-secrets`
- Do not add `payment-gateway-secrets` — marked `optional: true` in deployment, not blocking
