#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$ROOT_DIR/config-secret-secure}"

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

