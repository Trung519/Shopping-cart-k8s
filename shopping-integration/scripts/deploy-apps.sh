#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$ROOT_DIR/config-secret-secure}"
GLOBAL_VALUES="$CONFIG_DIR/values/local/00-global.yaml"

deploy() {
  local release="$1"
  local repo="$2"
  local namespace="$3"
  local values_file="$4"
  helm upgrade --install "$release" "$ROOT_DIR/$repo/helmchart" \
    --kube-context "$CONTEXT" \
    --namespace "$namespace" \
    --create-namespace \
    -f "$GLOBAL_VALUES" \
    -f "$CONFIG_DIR/values/local/$values_file" \
    --wait --timeout 10m
}

deploy frontend shopping-cart-frontend shopping-cart-apps 20-frontend.yaml
deploy basket-service shopping-cart-basket shopping-cart-apps 21-basket-service.yaml
deploy product-catalog shopping-cart-product-catalog shopping-cart-apps 22-product-catalog.yaml
deploy order-service shopping-cart-order shopping-cart-apps 23-order-service.yaml
deploy payment-service shopping-cart-payment shopping-cart-payment 24-payment-service.yaml
deploy account-service account-service shopping-cart-apps 26-account-service.yaml
deploy seller-service seller-service shopping-cart-apps 27-seller-service.yaml
deploy commerce-bff commerce-bff shopping-cart-apps 25-commerce-bff.yaml
