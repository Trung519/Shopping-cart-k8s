#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
KEYCHAIN_SERVICE="shopping-cart-marketplace-admin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

new_password="$(openssl rand -base64 36 | tr -d '\n')"
security add-generic-password -U \
  -a "$CONTEXT" \
  -s "$KEYCHAIN_SERVICE" \
  -w "$new_password" >/dev/null

"$SCRIPT_DIR/configure-keycloak-marketplace.sh"
unset new_password

echo "Marketplace admin password rotated. Retrieve it from macOS Keychain; it was not printed."
