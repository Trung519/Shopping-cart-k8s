#!/usr/bin/env bash
set -euo pipefail
CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
KEY="$(security find-generic-password -a "$CONTEXT" -s shopping-cart-vault-unseal -w)"
kubectl --context "$CONTEXT" exec -n vault vault-0 -- vault operator unseal "$KEY" >/dev/null
unset KEY
echo "Vault is unsealed."

