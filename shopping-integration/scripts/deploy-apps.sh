#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$ROOT_DIR/config-secret-secure}"

CHARTS_DIR="$ROOT_DIR/charts/apps"

# Release name == chart directory name under charts/apps.
deploy() {
  local release="$1"
  local namespace="$2"
  local values_file="$3"
  helm dependency build "$CHARTS_DIR/$release" >/dev/null
  helm upgrade --install "$release" "$CHARTS_DIR/$release" \
    --kube-context "$CONTEXT" \
    --namespace "$namespace" \
    --create-namespace \
    -f "$CONFIG_DIR/values/local/$values_file" \
    --wait --timeout 10m
}

deploy frontend shopping-cart-apps 20-frontend.yaml
deploy basket-service shopping-cart-apps 21-basket-service.yaml
deploy product-catalog shopping-cart-apps 22-product-catalog.yaml
deploy order-service shopping-cart-apps 23-order-service.yaml
deploy payment-service shopping-cart-payment 24-payment-service.yaml
deploy account-service shopping-cart-apps 26-account-service.yaml
deploy seller-service shopping-cart-apps 27-seller-service.yaml
deploy commerce-bff shopping-cart-apps 25-commerce-bff.yaml
