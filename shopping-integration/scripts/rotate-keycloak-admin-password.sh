#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
KEYCLOAK_NAMESPACE="shopping-cart-identity"
VAULT_NAMESPACE="vault"
ROOT_SERVICE="shopping-cart-vault-root"
ADMIN_KEYCHAIN_SERVICE="shopping-cart-keycloak-admin"

keycloak_pod="$(kubectl --context "$CONTEXT" get pod -n "$KEYCLOAK_NAMESPACE" -l app.kubernetes.io/name=keycloak --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
vault_pod="$(kubectl --context "$CONTEXT" get pod -n "$VAULT_NAMESPACE" -l app.kubernetes.io/name=vault -o jsonpath='{.items[0].metadata.name}')"
root_token="$(security find-generic-password -a "$CONTEXT" -s "$ROOT_SERVICE" -w)"
new_password="$(openssl rand -base64 36 | tr -d '\n')"

kubectl --context "$CONTEXT" exec -n "$KEYCLOAK_NAMESPACE" "$keycloak_pod" -- sh -lc \
  '/opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null'
kubectl --context "$CONTEXT" exec -n "$KEYCLOAK_NAMESPACE" "$keycloak_pod" -- \
  /opt/keycloak/bin/kcadm.sh set-password -r master --username admin --new-password "$new_password" >/dev/null

kubectl --context "$CONTEXT" exec -n "$VAULT_NAMESPACE" "$vault_pod" -- \
  env VAULT_TOKEN="$root_token" VAULT_ADDR=http://127.0.0.1:8200 \
  vault kv patch secret/shopping-cart/identity/keycloak adminPassword="$new_password" >/dev/null

kubectl --context "$CONTEXT" annotate externalsecret keycloak -n "$KEYCLOAK_NAMESPACE" \
  force-sync="$(date +%s)" --overwrite >/dev/null

for _ in $(seq 1 30); do
  synced_password="$(kubectl --context "$CONTEXT" get secret keycloak-secrets -n "$KEYCLOAK_NAMESPACE" -o jsonpath='{.data.KEYCLOAK_ADMIN_PASSWORD}' | base64 --decode)"
  if [[ "$synced_password" == "$new_password" ]]; then
    break
  fi
  sleep 2
done
if [[ "${synced_password:-}" != "$new_password" ]]; then
  echo "ExternalSecret did not synchronize the rotated password in time." >&2
  exit 1
fi

kubectl --context "$CONTEXT" rollout restart deployment/keycloak -n "$KEYCLOAK_NAMESPACE" >/dev/null
kubectl --context "$CONTEXT" rollout status deployment/keycloak -n "$KEYCLOAK_NAMESPACE" --timeout=180s >/dev/null

keycloak_pod="$(kubectl --context "$CONTEXT" get pod -n "$KEYCLOAK_NAMESPACE" -l app.kubernetes.io/name=keycloak --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
kubectl --context "$CONTEXT" wait -n "$KEYCLOAK_NAMESPACE" --for=condition=Ready "pod/$keycloak_pod" --timeout=120s >/dev/null
kubectl --context "$CONTEXT" exec -n "$KEYCLOAK_NAMESPACE" "$keycloak_pod" -- sh -lc \
  '/opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null'

security add-generic-password -U \
  -a "$CONTEXT" \
  -s "$ADMIN_KEYCHAIN_SERVICE" \
  -w "$new_password" >/dev/null

unset root_token new_password synced_password
echo "Keycloak admin password rotated in Keycloak and Vault. No credential was printed."
