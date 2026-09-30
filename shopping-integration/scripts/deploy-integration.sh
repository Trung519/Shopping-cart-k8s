#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$ROOT_DIR/config-secret-secure}"
CHART_DIR="$ROOT_DIR/shopping-integration/helmchart"

helm upgrade --install shopping-integration "$CHART_DIR" \
  --kube-context "$CONTEXT" \
  --namespace shopping-cart-data \
  --create-namespace \
  -f "$CONFIG_DIR/values/local/00-global.yaml" \
  -f "$CONFIG_DIR/values/local/10-shopping-integration.yaml" \
  --wait --timeout 20m

kubectl --context "$CONTEXT" label namespace shopping-cart-apps shopping-cart-payment shopping-cart-identity \
  istio-injection=enabled app.kubernetes.io/part-of=shopping-cart --overwrite
kubectl --context "$CONTEXT" label namespace shopping-cart-data shopping-cart-gateway \
  istio-injection=disabled app.kubernetes.io/part-of=shopping-cart --overwrite

kubectl --context "$CONTEXT" wait externalsecret --all --all-namespaces --for=condition=Ready --timeout=5m
