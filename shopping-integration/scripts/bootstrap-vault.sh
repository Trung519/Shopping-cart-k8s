#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
KEYCHAIN_ACCOUNT="$CONTEXT"
UNSEAL_SERVICE="shopping-cart-vault-unseal"
ROOT_SERVICE="shopping-cart-vault-root"

vault_exec() {
  local token="$1"
  shift
  kubectl --context "$CONTEXT" exec -n vault vault-0 -- env VAULT_TOKEN="$token" VAULT_ADDR=http://127.0.0.1:8200 vault "$@"
}

status_json="$(kubectl --context "$CONTEXT" exec -n vault vault-0 -- vault status -format=json 2>/dev/null || true)"
initialized="$(jq -r '.initialized // false' <<<"$status_json")"

if [[ "$initialized" != "true" ]]; then
  init_json="$(kubectl --context "$CONTEXT" exec -n vault vault-0 -- vault operator init -key-shares=1 -key-threshold=1 -format=json)"
  unseal_key="$(jq -r '.unseal_keys_b64[0]' <<<"$init_json")"
  root_token="$(jq -r '.root_token' <<<"$init_json")"
  security add-generic-password -U -a "$KEYCHAIN_ACCOUNT" -s "$UNSEAL_SERVICE" -w "$unseal_key" >/dev/null
  security add-generic-password -U -a "$KEYCHAIN_ACCOUNT" -s "$ROOT_SERVICE" -w "$root_token" >/dev/null
  unset init_json unseal_key root_token
fi

unseal_key="$(security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$UNSEAL_SERVICE" -w)"
root_token="$(security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$ROOT_SERVICE" -w)"

status_json="$(kubectl --context "$CONTEXT" exec -n vault vault-0 -- vault status -format=json 2>/dev/null || true)"
sealed="$(jq -r '.sealed' <<<"$status_json")"
if [[ "$sealed" == "true" ]]; then
  kubectl --context "$CONTEXT" exec -n vault vault-0 -- vault operator unseal "$unseal_key" >/dev/null
fi

vault_exec "$root_token" secrets enable -path=secret kv-v2 >/dev/null 2>&1 || true
vault_exec "$root_token" auth enable kubernetes >/dev/null 2>&1 || true
vault_exec "$root_token" write auth/kubernetes/config \
  kubernetes_host=https://kubernetes.default.svc:443 \
  token_reviewer_jwt=@/var/run/secrets/kubernetes.io/serviceaccount/token \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt >/dev/null

policy='path "secret/data/shopping-cart/*" { capabilities = ["read"] }
path "secret/metadata/shopping-cart/*" { capabilities = ["read", "list"] }'
printf '%s\n' "$policy" | kubectl --context "$CONTEXT" exec -i -n vault vault-0 -- env VAULT_TOKEN="$root_token" VAULT_ADDR=http://127.0.0.1:8200 vault policy write shopping-cart-eso - >/dev/null

vault_exec "$root_token" write auth/kubernetes/role/external-secrets \
  bound_service_account_names=external-secrets \
  bound_service_account_namespaces=external-secrets \
  policies=shopping-cart-eso \
  ttl=1h >/dev/null

seed_secret() {
  local path="$1"
  shift
  if ! vault_exec "$root_token" kv get "secret/$path" >/dev/null 2>&1; then
    vault_exec "$root_token" kv put "secret/$path" "$@" >/dev/null
  fi
}

seed_secret shopping-cart/shared/auth "jwtSecret=$(openssl rand -base64 48 | tr -d '\n')"
seed_secret shopping-cart/shared/service-auth "token=$(openssl rand -base64 48 | tr -d '\n')"
seed_secret shopping-cart/apps/commerce-bff "sessionSecret=$(openssl rand -base64 48 | tr -d '\n')" "oidcClientSecret=$(openssl rand -base64 48 | tr -d '\n')"
seed_secret shopping-cart/apps/account-service "keycloakClientSecret=$(openssl rand -base64 48 | tr -d '\n')"
seed_secret shopping-cart/data/rabbitmq username=shopping-cart "password=$(openssl rand -base64 32 | tr -d '\n')" "erlangCookie=$(openssl rand -hex 32)"
seed_secret shopping-cart/data/redis-cart "password=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/data/postgresql-orders username=postgres "password=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/data/postgresql-products username=postgres "password=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/data/postgresql-payment username=postgres "password=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/data/postgresql-marketplace "adminPassword=$(openssl rand -base64 32 | tr -d '\n')" "sellerPassword=$(openssl rand -base64 32 | tr -d '\n')" "inventoryPassword=$(openssl rand -base64 32 | tr -d '\n')" "checkoutPassword=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/identity/keycloak adminUsername=admin "adminPassword=$(openssl rand -base64 32 | tr -d '\n')" databaseUsername=keycloak "databasePassword=$(openssl rand -base64 32 | tr -d '\n')"
seed_secret shopping-cart/payment/encryption "key=$(openssl rand -base64 32 | tr -d '\n')"

unset unseal_key root_token
echo "Vault initialized, unsealed, and seeded; credentials are stored only in Vault and macOS Keychain."
