#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
if [[ "${CONFIRM_WIPE:-}" != "shopping-cart" ]]; then
  echo "Refusing to wipe. Set CONFIRM_WIPE=shopping-cart after verifying backups." >&2
  exit 1
fi

for namespace in shopping-cart-apps shopping-cart-data shopping-cart-payment shopping-cart-identity shopping-cart-gateway identity; do
  kubectl --context "$CONTEXT" delete namespace "$namespace" --ignore-not-found --wait=false
done

for namespace in shopping-cart-apps shopping-cart-data shopping-cart-payment shopping-cart-identity shopping-cart-gateway identity; do
  while kubectl --context "$CONTEXT" get namespace "$namespace" >/dev/null 2>&1; do
    sleep 2
  done
done

echo "Shopping-cart workloads and PVCs were removed. Cluster platform namespaces were preserved."

