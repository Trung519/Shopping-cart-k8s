#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
BACKUP_DIR="${1:?usage: restore-databases.sh BACKUP_DIR}"

find_primary() {
  local cluster="$1"
  local database="$2"
  local replicas="$3"
  local index result
  for ((index=0; index<replicas; index++)); do
    result="$(kubectl --context "$CONTEXT" exec -n shopping-cart-data "$cluster-$index" -- sh -c 'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U postgres -d "'$database'" -Atc "select pg_is_in_recovery()"' 2>/dev/null || true)"
    if [[ "$result" == "f" ]]; then
      printf '%s-%s\n' "$cluster" "$index"
      return 0
    fi
  done
  return 1
}

restore_one() {
  local cluster="$1"
  local database="$2"
  local archive="$3"
  local primary
  primary="$(find_primary "$cluster" "$database" 2)"
  kubectl --context "$CONTEXT" cp "$archive" "shopping-cart-data/$primary:/tmp/restore.dump" -c postgresql
  kubectl --context "$CONTEXT" exec -n shopping-cart-data "$primary" -- sh -c \
    'PGPASSWORD="$POSTGRESQL_PASSWORD" pg_restore --clean --if-exists --no-owner -U postgres -d "'$database'" /tmp/restore.dump'
}

(cd "$BACKUP_DIR" && shasum -a 256 -c CHECKSUMS.txt)
restore_one postgresql-orders orders "$BACKUP_DIR/orders.dump"
restore_one postgresql-products products "$BACKUP_DIR/products.dump"

products_primary="$(find_primary postgresql-products products 2)"
kubectl --context "$CONTEXT" cp \
  "$(dirname "$0")/product-catalog-post-restore.sql" \
  "shopping-cart-data/$products_primary:/tmp/product-catalog-post-restore.sql" \
  -c postgresql
kubectl --context "$CONTEXT" exec -n shopping-cart-data "$products_primary" -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -v ON_ERROR_STOP=1 -U postgres -d products -f /tmp/product-catalog-post-restore.sql'

echo "Database archives restored successfully."
