#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
NAMESPACE="${KEYCLOAK_NAMESPACE:-shopping-cart-identity}"
REALM="${KEYCLOAK_REALM:-shopping-cart}"
CLIENT_ID="${OIDC_CLIENT_ID:-commerce-bff}"
REDIRECT_URI="${OIDC_REDIRECT_URI:-http://shopping-cart.localhost:8080/api/v2/auth/callback}"
POST_LOGOUT_REDIRECT_URI="${OIDC_POST_LOGOUT_REDIRECT_URI:-http://shopping-cart.localhost:8080/*}"
ADMIN_KEYCHAIN_SERVICE="shopping-cart-marketplace-admin"

keycloak_pod="$(kubectl --context "$CONTEXT" get pod -n "$NAMESPACE" -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')"
client_secret="$(kubectl --context "$CONTEXT" get secret -n shopping-cart-apps commerce-bff-secrets -o jsonpath='{.data.OIDC_CLIENT_SECRET}' | base64 --decode)"
account_client_secret="$(kubectl --context "$CONTEXT" get secret -n shopping-cart-apps account-service-secrets -o jsonpath='{.data.KEYCLOAK_CLIENT_SECRET}' | base64 --decode)"

kubectl --context "$CONTEXT" exec -n "$NAMESPACE" "$keycloak_pod" -- sh -lc \
  '/opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null'

kcadm() {
  kubectl --context "$CONTEXT" exec -i -n "$NAMESPACE" "$keycloak_pod" -- /opt/keycloak/bin/kcadm.sh "$@"
}

roles=(platform-admin user-admin seller-reviewer catalog-moderator order-operator finance-operator support-agent seller-owner seller-manager seller-staff buyer)
for role in "${roles[@]}"; do
  if ! kcadm get "roles/$role" -r "$REALM" >/dev/null 2>&1; then
    kcadm create roles -r "$REALM" -s "name=$role" >/dev/null
  fi
done

client_uuid="$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id --format csv --noquotes | head -n 1)"
client_payload="$(jq -cn \
  --arg clientId "$CLIENT_ID" \
  --arg secret "$client_secret" \
  --arg redirect "$REDIRECT_URI" \
  --arg postLogoutRedirect "$POST_LOGOUT_REDIRECT_URI" \
  '{clientId:$clientId,name:"ShopCart Commerce BFF",enabled:true,publicClient:false,secret:$secret,standardFlowEnabled:true,directAccessGrantsEnabled:false,serviceAccountsEnabled:true,redirectUris:[$redirect],webOrigins:["+"],attributes:{"post.logout.redirect.uris":$postLogoutRedirect}}')"
if [[ -z "$client_uuid" ]]; then
  printf '%s' "$client_payload" | kcadm create clients -r "$REALM" -f - >/dev/null
  client_uuid="$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id --format csv --noquotes | head -n 1)"
else
  printf '%s' "$client_payload" | kcadm update "clients/$client_uuid" -r "$REALM" -f - >/dev/null
fi

country_mapper_id="$(kcadm get "clients/$client_uuid/protocol-mappers/models" -r "$REALM" | jq -r '.[] | select(.name == "country_id") | .id' | head -n 1)"
country_mapper_payload='{"name":"country_id","protocol":"openid-connect","protocolMapper":"oidc-usermodel-attribute-mapper","consentRequired":false,"config":{"user.attribute":"country_id","claim.name":"country_id","jsonType.label":"String","access.token.claim":"true","id.token.claim":"true","userinfo.token.claim":"true","introspection.token.claim":"true","multivalued":"false"}}'
if [[ -z "$country_mapper_id" ]]; then
  printf '%s' "$country_mapper_payload" | kcadm create "clients/$client_uuid/protocol-mappers/models" -r "$REALM" -f - >/dev/null
else
  printf '%s' "$country_mapper_payload" | kcadm update "clients/$client_uuid/protocol-mappers/models/$country_mapper_id" -r "$REALM" -f - >/dev/null
fi

account_client_id="account-service"
account_client_uuid="$(kcadm get clients -r "$REALM" -q "clientId=$account_client_id" --fields id --format csv --noquotes | head -n 1)"
account_client_payload="$(jq -cn \
  --arg clientId "$account_client_id" \
  --arg secret "$account_client_secret" \
  '{clientId:$clientId,name:"ShopCart Account Service",enabled:true,publicClient:false,secret:$secret,standardFlowEnabled:false,directAccessGrantsEnabled:false,serviceAccountsEnabled:true}')"
if [[ -z "$account_client_uuid" ]]; then
  printf '%s' "$account_client_payload" | kcadm create clients -r "$REALM" -f - >/dev/null
else
  printf '%s' "$account_client_payload" | kcadm update "clients/$account_client_uuid" -r "$REALM" -f - >/dev/null
fi
kcadm add-roles -r "$REALM" \
  --uusername "service-account-$account_client_id" \
  --cclientid realm-management \
  --rolename manage-users \
  --rolename view-users \
  --rolename view-realm \
  --rolename query-users >/dev/null

admin_username="shopcart-admin"
admin_id="$(kcadm get users -r "$REALM" -q "username=$admin_username" --fields id --format csv --noquotes | head -n 1)"
if [[ -z "$admin_id" ]]; then
  temporary_password="$(openssl rand -base64 24 | tr -d '\n')"
  kcadm create users -r "$REALM" -s "username=$admin_username" -s enabled=true -s emailVerified=true -s firstName=ShopCart -s lastName=Admin -s email=admin@shopcart.local >/dev/null
  security add-generic-password -U -a "$CONTEXT" -s "$ADMIN_KEYCHAIN_SERVICE" -w "$temporary_password" >/dev/null
  unset temporary_password
fi
bootstrap_password="$(security find-generic-password -a "$CONTEXT" -s "$ADMIN_KEYCHAIN_SERVICE" -w)"
kcadm set-password -r "$REALM" --username "$admin_username" --new-password "$bootstrap_password" >/dev/null
kcadm add-roles -r "$REALM" --uusername "$admin_username" --rolename platform-admin --rolename buyer >/dev/null

unset client_secret client_payload account_client_secret account_client_payload bootstrap_password
echo "Keycloak marketplace client, roles, and bootstrap admin are configured. Credentials were not printed."
