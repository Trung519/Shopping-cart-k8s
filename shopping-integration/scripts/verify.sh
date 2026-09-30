#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"

helm --kube-context "$CONTEXT" list -A
kubectl --context "$CONTEXT" get pods -n shopping-cart-data
kubectl --context "$CONTEXT" get pods -n shopping-cart-apps
kubectl --context "$CONTEXT" get pods -n shopping-cart-payment
kubectl --context "$CONTEXT" get pods -n shopping-cart-identity
kubectl --context "$CONTEXT" get gateway,httproute -A
kubectl --context "$CONTEXT" get externalsecret,clustersecretstore -A

if kubectl --context "$CONTEXT" get service -A -o name | grep -E -- '-nodeport|redis-orders-cache'; then
  echo "Unexpected legacy service remains." >&2
  exit 1
fi

kubectl --context "$CONTEXT" wait gateway/nginx-gateway -n shopping-cart-gateway --for=condition=Programmed --timeout=5m
echo "Helm releases, workloads, ExternalSecrets, and Gateway API resources are ready."

