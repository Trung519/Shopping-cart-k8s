#!/usr/bin/env bash
set -euo pipefail
CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
exec kubectl --context "$CONTEXT" port-forward -n shopping-cart-gateway svc/nginx-gateway-istio "$LOCAL_PORT:80"

