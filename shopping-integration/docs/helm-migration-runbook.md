# Shopping Cart Helm Migration Runbook

## Scope

This runbook rebuilds only the shopping-cart namespaces on `k3d-lab-k8s`. It does
not recreate the k3d cluster and does not modify Rancher, the Istio control plane,
or Traefik. Application namespaces use Istio sidecars; data, Vault, and External
Secrets namespaces do not.

## Repository Layout

Place these repositories at the same level under `biglab-k8s`:

- `shopping-integration`: shared runtime and Istio Gateway API chart.
- `config-secret-secure`: environment values and Vault policy references.
- `shopping-cart-frontend`, `shopping-cart-basket`,
  `shopping-cart-product-catalog`, `shopping-cart-order`, and
  `shopping-cart-payment`: one `helmchart` per application.

Real secrets live only in Vault. Vault initialization material is stored in the
macOS Keychain by the bootstrap scripts and must never be pasted into Git or logs.

## Prerequisites

```bash
kubectl config get-contexts
kubectl --context k3d-lab-k8s get nodes
helm version
istioctl version
security find-generic-password -s shopping-cart-vault-unseal >/dev/null
```

Confirm that Gateway API CRDs and the Istio gateway class exist:

```bash
kubectl --context k3d-lab-k8s get crd gateways.gateway.networking.k8s.io
kubectl --context k3d-lab-k8s get gatewayclass istio
```

## Backup Before Destructive Work

Create a timestamped directory under
`config-secret-secure/.local/backups/`. Dump orders and products in custom archive
format, export RabbitMQ definitions, record row counts, then generate checksums.

Required validation before deletion:

```bash
pg_restore --list orders.dump >/dev/null
pg_restore --list products.dump >/dev/null
shasum -a 256 -c CHECKSUMS.txt
```

Redis cart data is treated as cache/session data and is not restored.

## Install Platform Services

Run from `shopping-integration`:

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/install-platform.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/bootstrap-vault.sh
```

The platform script installs:

- External Secrets Operator chart `2.8.0`.
- HashiCorp Vault chart `0.34.0`, standalone with a persistent volume.

After a Vault restart, unseal it without printing the key:

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/unseal-vault.sh
```

`bootstrap-vault.sh` enables Kubernetes authentication, creates the ESO policy and
role, and writes generated application secrets to Vault paths. Stripe and PayPal
remain disabled for local use.

## Destructive Cutover

Run this only after all backup checks pass:

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/wipe-shopping-cart.sh
```

The script deletes shopping-cart workloads and PVCs only. It does not delete the
cluster, Rancher, Istio, Traefik, ESO, or Vault.

## Install Shared Runtime

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-integration.sh
kubectl --context k3d-lab-k8s get externalsecret,clustersecretstore -A
kubectl --context k3d-lab-k8s get pods -n shopping-cart-data -w
```

This installs PostgreSQL/RepMgr/Pgpool, payment PostgreSQL, RabbitMQ, Redis cart,
Keycloak, namespaces, strict mTLS policies, Gateway API resources, ReferenceGrants,
and ExternalSecrets. The `redis-orders-cache` workload is intentionally removed.

## Restore Databases

```bash
KUBE_CONTEXT=k3d-lab-k8s \
  ./scripts/restore-databases.sh \
  ../config-secret-secure/.local/backups/<timestamp>
```

The restore script verifies checksums, discovers each RepMgr primary, restores the
archives, and applies `product-catalog-post-restore.sql`. That idempotent migration
adds the current product columns and converts legacy integer product IDs to stable
UUIDs when necessary.

## Install Applications

Build/import local images first when the image tags in local values are not
available from a registry. Then install all five charts:

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-apps.sh
```

All application configuration comes from `config-secret-secure/values/local`.
Templates contain no environment endpoint, namespace, image tag, or plaintext
credential. Application Secret templates render `ExternalSecret` resources only.

## Local Istio Access

The local environment exposes the Istio gateway without a port-forward. Its
Service uses NodePort `30080`, and the k3d server load balancer persistently maps
host `127.0.0.1:8080` to that NodePort. Open:

- `http://localhost:8080`
- `http://shopping-cart.localhost:8080`
- `http://keycloak.localhost:8080`
- `http://vault.localhost:8080`

Create the host mapping once when rebuilding the k3d cluster:

```bash
k3d cluster edit lab-k8s \
  --port-add 127.0.0.1:8080:30080@loadbalancer
```

The resource is named `nginx-gateway`, but Istio provisions its Envoy data plane.
The frontend container still uses Nginx only for SPA/static delivery. `HTTPRoute`
owns API routing and cart/payment path rewriting; no parallel `VirtualService` is
created.

## Verification

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/verify.sh
helm --kube-context k3d-lab-k8s list -A
kubectl --context k3d-lab-k8s get gateway,httproute -A
kubectl --context k3d-lab-k8s get peerauthentication -A
```

Expected results:

- App, payment, and identity pods report `2/2` where sidecars are enabled.
- Data, Vault, and ESO pods are Ready without injected sidecars.
- Every ExternalSecret is `SecretSynced=True` and the store is `Valid=True`.
- Gateway is `Programmed=True`; routes are `Accepted=True` and
  `ResolvedRefs=True`.
- Products and cart return HTTP 200. Orders/payment may return 403/401 without a
  token, which proves routing reached application security.
- Pgpool SQL returns `1`, Redis returns `PONG`, and RabbitMQ diagnostics return
  `Ping succeeded`.
- The only expected application NodePort is the local Istio gateway on `30080`;
  no legacy app NodePort or `redis-orders-cache` remains.

## Recover k3d Workers After Rancher Desktop Restart

If all StatefulSets disappear at once and both k3d agents are `NotReady`, inspect
the agent containerd log. This cluster has previously failed with
`failed to create fsnotify watcher: too many open files`, which prevents the CRI
plugin from loading.

Apply the runtime limit inside the Rancher Desktop VM through a privileged k3d
server container, then restart only the two workers:

```bash
docker exec k3d-lab-k8s-server-0 \
  sysctl -w fs.inotify.max_user_instances=8192
docker exec k3d-lab-k8s-server-0 \
  sysctl -w fs.inotify.max_user_watches=1048576
docker restart k3d-lab-k8s-agent-0 k3d-lab-k8s-agent-1
kubectl --context k3d-lab-k8s wait node --all \
  --for=condition=Ready --timeout=3m
```

After Vault starts, unseal it, refresh Kubernetes auth, and reconcile Helm. The
bootstrap operation is idempotent and does not rotate existing Vault secrets:

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/unseal-vault.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/bootstrap-vault.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-integration.sh
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-apps.sh
```

If Helm reports `.spec.replicas` ownership conflicts caused by an external field
manager, run the affected `helm upgrade` once with `--force-conflicts`. Do not use
`--force-replace`, because StatefulSets own persistent volumes.

Before committing, lint every chart with its local values, render it, perform a
server-side dry run, and run a secret scanner over all staged changes.

## Argo CD Activation

Applications under `shopping-cart-infra/argocd/applications` use multi-source
Helm: the chart comes from the application/integration repo and values come from
the private `config-secret-secure` repo. Auto-sync is intentionally absent.

Activate only after:

1. `shopping-integration` and `config-secret-secure` remotes exist and are pushed.
2. Argo CD has credentials for the private values repository.
3. A manual diff/render succeeds for every Application.
4. The destination cluster name is confirmed for the target environment.

After those checks, automated prune/self-heal may be enabled deliberately.

## Rollback

1. Disable Argo auto-sync and close traffic to the local Gateway when required.
2. Uninstall the five app releases and `shopping-integration` with explicit
   namespaces and context.
3. Reinstall the last known-good chart revisions, or reapply the previous Git
   revision of the legacy manifests only as an emergency fallback.
4. Restore `orders.dump` and `products.dump` after validating checksums.
5. Reimport RabbitMQ definitions when topology is missing.
6. Run the complete verification section before reopening traffic.

Never delete Vault PVCs during an application rollback. If Vault is sealed, use
`scripts/unseal-vault.sh`; do not initialize it again against an existing data PVC.
