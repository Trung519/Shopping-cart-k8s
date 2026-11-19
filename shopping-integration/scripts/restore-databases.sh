#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/database-common.sh"
BACKUP_DIR="${1:?usage: restore-databases.sh BACKUP_DIR}"

restore_one() {
  local database="$1"
  local archive="$2"
  check_database_name "$database"
  # Stream archives to the selected container, without leaving dumps in /tmp.
  case "$INSTANCE" in
    postgresql-orders|postgresql-products)
      # Preserve the existing repmgr restore behaviour and database ownership.
      pod_exec "$POD" pg_restore --clean --if-exists --no-owner -d "$database" < "$archive"
      ;;
    *)
      # Recreate standalone databases with their original owners and grants.
      # Application connections must be stopped before a logical restore.
      pod_exec "$POD" pg_restore --exit-on-error --clean --if-exists --create -d postgres < "$archive"
      ;;
  esac
}

(cd "$BACKUP_DIR" && shasum -a 256 -c CHECKSUMS.txt)
# Check all expected archives before any database changes. Accept the legacy format
# only when no instance-named dumps exist.
shopt -s nullglob
archives=("$BACKUP_DIR/"*__*.dump)
if [[ ${#archives[@]} == 0 ]]; then
  [[ -f "$BACKUP_DIR/orders.dump" && -f "$BACKUP_DIR/products.dump" ]] || {
    echo "Missing orders.dump or products.dump" >&2
    exit 1
  }
  select_instance postgresql-orders
  restore_one orders "$BACKUP_DIR/orders.dump"
  select_instance postgresql-products
  restore_one products "$BACKUP_DIR/products.dump"
else
  for instance in "${INSTANCES[@]}"; do
    archives=("$BACKUP_DIR/${instance}__"*.dump)
    if [[ ${#archives[@]} == 0 ]]; then
      echo "No archives for $instance" >&2
      exit 1
    fi
  done
  # Globals are recovery references; chart/Vault bootstrap owns login credentials,
  # so globals are not applied automatically.
  for instance in "${INSTANCES[@]}"; do
    select_instance "$instance"
    for archive in "$BACKUP_DIR/${instance}__"*.dump; do
      database="${archive##*/}"
      database="${database#"${instance}__"}"
      database="${database%.dump}"
      restore_one "$database" "$archive"
    done
  done
fi

select_instance postgresql-products
pod_exec "$POD" psql -X -v ON_ERROR_STOP=1 -d products < "$SCRIPT_DIR/product-catalog-post-restore.sql"

echo "Database archives restored successfully."
