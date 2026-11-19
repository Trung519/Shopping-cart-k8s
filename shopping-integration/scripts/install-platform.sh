#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$ROOT_DIR/config-secret-secure}"

# Install CRDs before their controllers and wait before moving to the next component.
GATEWAY_API_URL="https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.3.0/standard-install.yaml"
kubectl --context "$CONTEXT" apply --server-side -f "$GATEWAY_API_URL"
kubectl --context "$CONTEXT" wait --for=condition=Established --timeout=5m -f "$GATEWAY_API_URL"

helm repo add istio https://istio-release.storage.googleapis.com/charts --force-update
helm repo update istio
helm upgrade --install istio-base istio/base \
  --kube-context "$CONTEXT" \
  --namespace istio-system \
  --create-namespace \
  --version 1.30.3 \
  --set defaultRevision=default \
  --wait --timeout 10m
kubectl --context "$CONTEXT" wait --for=condition=Established --timeout=5m \
  crd/virtualservices.networking.istio.io crd/telemetries.telemetry.istio.io
helm upgrade --install istiod istio/istiod \
  --kube-context "$CONTEXT" \
  --namespace istio-system \
  --version 1.30.3 \
  -f "$ROOT_DIR/charts/platform/istio/istiod-values.yaml" \
  --wait --timeout 10m
kubectl --context "$CONTEXT" rollout status deployment/istiod -n istio-system --timeout=5m

kubectl --context "$CONTEXT" create namespace argocd --dry-run=client -o yaml | \
  kubectl --context "$CONTEXT" apply --server-side -f -
kubectl --context "$CONTEXT" apply --server-side -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.3/manifests/install.yaml
kubectl --context "$CONTEXT" wait --for=condition=Established --timeout=5m \
  crd/applications.argoproj.io crd/applicationsets.argoproj.io crd/appprojects.argoproj.io
kubectl --context "$CONTEXT" patch service argocd-server -n argocd --type=strategic \
  -p '{"spec":{"type":"NodePort","ports":[{"port":80,"nodePort":30082},{"port":443,"nodePort":30443}]}}'
kubectl --context "$CONTEXT" rollout status deployment -n argocd -l app.kubernetes.io/part-of=argocd --timeout=10m
kubectl --context "$CONTEXT" rollout status statefulset -n argocd -l app.kubernetes.io/part-of=argocd --timeout=10m

kubectl --context "$CONTEXT" create namespace argo-rollouts --dry-run=client -o yaml | \
  kubectl --context "$CONTEXT" apply --server-side -f -
kubectl --context "$CONTEXT" apply --server-side -n argo-rollouts \
  -f https://raw.githubusercontent.com/argoproj/argo-rollouts/v1.10.1/manifests/install.yaml
kubectl --context "$CONTEXT" wait --for=condition=Established --timeout=5m \
  crd/rollouts.argoproj.io crd/analysisruns.argoproj.io \
  crd/analysistemplates.argoproj.io crd/clusteranalysistemplates.argoproj.io crd/experiments.argoproj.io
kubectl --context "$CONTEXT" rollout status deployment/argo-rollouts -n argo-rollouts --timeout=10m

helm repo add external-secrets https://charts.external-secrets.io --force-update
helm repo add hashicorp https://helm.releases.hashicorp.com --force-update
helm repo update

helm upgrade --install external-secrets external-secrets/external-secrets \
  --kube-context "$CONTEXT" \
  --namespace external-secrets \
  --create-namespace \
  --version 2.8.0 \
  -f "$CONFIG_DIR/values/local/01-external-secrets.yaml" \
  --wait --timeout 10m

helm upgrade --install vault hashicorp/vault \
  --kube-context "$CONTEXT" \
  --namespace vault \
  --create-namespace \
  --version 0.34.0 \
  -f "$CONFIG_DIR/values/local/02-vault.yaml" \
  --wait=false

kubectl --context "$CONTEXT" rollout status deployment/external-secrets -n external-secrets --timeout=5m
kubectl --context "$CONTEXT" wait pod/vault-0 -n vault --for=jsonpath='{.status.phase}'=Running --timeout=5m

