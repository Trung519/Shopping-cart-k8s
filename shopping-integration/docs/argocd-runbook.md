# Argo CD on the Local Cluster

Argo CD runs inside `k3d-lab-k8s` in the `argocd` namespace. The standard
in-cluster installation manages the current cluster through
`https://kubernetes.default.svc`; no external Docker container or manually
registered cluster credential is needed.

## Install

```bash
KUBE_CONTEXT=k3d-lab-k8s ./scripts/deploy-argocd.sh
```

The installation is pinned to Argo CD `v3.4.2` in `argocd/kustomization.yaml`.
The script waits for the CRDs, then creates the ShopCart AppProject. It uses
server-side apply because Argo CD CRDs are too large for normal client-side
apply.

## Open the UI

```bash
kubectl --context k3d-lab-k8s -n argocd port-forward svc/argocd-server 8081:443
```

Then open `https://localhost:8081`. Retrieve the generated initial admin
password only when needed; do not put it in Git, values files, or logs.

## Scope

The `shopping-cart` AppProject is limited to ShopCart namespaces and approved
GitHub repositories. No Argo CD Application is created by this installation,
so existing Helm releases remain unmanaged until a repository and explicit
Application manifest are approved.

## Remove

```bash
kubectl --context k3d-lab-k8s delete -k argocd
```

Remove Applications first if any have been added, so the intended workload
prune policy is reviewed separately.
