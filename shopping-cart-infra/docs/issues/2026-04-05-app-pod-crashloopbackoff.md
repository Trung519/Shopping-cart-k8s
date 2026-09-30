# Issue: App Pod CrashLoopBackOff After Data Layer Deployment

**Date:** 2026-04-05
**Status:** PRs open
**Affects:** product-catalog, payment-service, frontend, order-service

---

## Summary

After deploying the data layer via ArgoCD sync, all four application pods enter CrashLoopBackOff (or Running/0 for order-service). Three distinct root causes were identified.

---

## Root Cause 1 — product-catalog: ExternalSecret key mismatch

**PR:** wilddog64/shopping-cart-infra#28

### Symptom
```
sqlalchemy.exc.OperationalError: password authentication failed for user "postgres"
ERROR: Application startup failed. Exiting.
```

### Root Cause
`postgres-products-apps-externalsecret.yaml` provided `DATABASE_USER`/`DATABASE_PASSWORD`, but `product_catalog/config.py` reads env vars via pydantic `Field(alias=...)`:
```python
db_username: str = Field(default="postgres", alias="DB_USERNAME")
db_password: str = Field(default="postgres", alias="DB_PASSWORD")
rabbitmq_username: str = Field(default="guest", alias="RABBITMQ_USERNAME")
```
App fell back to default `db_password="postgres"` → SCRAM-SHA-256 auth failure against PostgreSQL.

### Fix
Add `DB_USERNAME`, `DB_PASSWORD`, `RABBITMQ_USERNAME` to the ExternalSecret template data alongside the existing `DATABASE_USER`/`DATABASE_PASSWORD` keys.

---

## Root Cause 2 — payment-service: NetworkPolicy blocks DNS

**PR:** wilddog64/shopping-cart-payment#17

### Symptom
```
Caused by: java.net.UnknownHostException: postgresql-payment.shopping-cart-data.svc.cluster.local
```
The service `postgresql-payment` exists (ClusterIP `10.43.81.58`) — DNS resolution itself failed.

### Root Cause
`networkpolicy.yaml` has `default-deny-all` (empty podSelector → matches all pods) plus allow rules that select pods with `app.kubernetes.io/version: "1.0.0"`. The deployment pod template was missing this label:

```yaml
# NetworkPolicy allow-dns podSelector (requires all three labels)
matchLabels:
  app.kubernetes.io/name: payment-service
  app.kubernetes.io/part-of: shopping-cart
  app.kubernetes.io/version: "1.0.0"   # ← missing from pod template

# Deployment pod template labels (as deployed)
app.kubernetes.io/name: payment-service
app.kubernetes.io/component: backend
app.kubernetes.io/part-of: shopping-cart
pci-scope: "true"
# app.kubernetes.io/version: "1.0.0"   # ← absent
```

Result: `default-deny-all` matched the pods; `allow-dns`/`allow-to-postgresql`/`allow-to-rabbitmq` did not → all egress blocked including DNS.

### Fix
Add `app.kubernetes.io/version: "1.0.0"` to the pod template labels in `k8s/base/deployment.yaml`.

Additionally, `RABBITMQ_USERNAME`/`RABBITMQ_PASSWORD` were absent from the deployment env vars (defaulting to `guest`/`guest`). Fix adds them from `payment-db-credentials` secret, and the companion infra PR adds those keys to the ExternalSecret.

---

## Root Cause 3 — frontend: nginx EACCES on cache directory

**PR:** wilddog64/shopping-cart-frontend#13

### Symptom
```
nginx: [emerg] mkdir() "/var/cache/nginx/client_temp" failed (13: Permission denied)
```

### Root Cause
nginx runs as non-root (uid 101, fsGroup 101). `/var/cache/nginx` is owned by root in the base image. At startup nginx tries to create subdirectories under it and gets EACCES.

### Fix
Add an `emptyDir` volume mounted at `/var/cache/nginx`. The emptyDir inherits fsGroup 101 and is writable by the container process.

```yaml
volumeMounts:
  - name: nginx-cache
    mountPath: /var/cache/nginx
volumes:
  - name: nginx-cache
    emptyDir: {}
```

---

## Order-Service Note

order-service showed `Connection refused` to RabbitMQ in early logs — likely a timing issue (pod started before RabbitMQ was fully accepting connections). By the time the data layer was stable, order-service logs showed `Started OrderServiceApplication` and RabbitMQ logs confirmed successful authentication with user `rabbitmq`. No code fix required.

---

## Prevention

- ExternalSecret template keys must be audited against each app's actual env var names (aliases) — not assumed to match generic `username`/`password` keys.
- Deployment pod template labels must include all labels referenced by NetworkPolicy `podSelector` in the same namespace.
- nginx non-root deployments require an emptyDir for any directory nginx writes to at startup.
