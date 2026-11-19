#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${KUBE_CONTEXT:-k3d-lab-k8s}"
INSTANCES=(postgresql-orders postgresql-products postgresql-marketplace postgresql-payment postgres-keycloak)

# Passwords and usernames are resolved inside the database container, never locally.
pod_exec() {
  local pod="$1"
  shift
  kubectl --context "$CONTEXT" exec -i -n "$NAMESPACE" "$pod" -c "$CONTAINER" -- sh -c '
    export PGPASSWORD="${POSTGRESQL_PASSWORD:-${POSTGRES_PASSWORD:-}}"
    export PGUSER="${POSTGRES_USER:-postgres}"
    exec "$@"
  ' sh "$@"
}

find_primary() {
  local cluster="$1"
  local database="$2"
  local replicas="$3"
  local index result
  for ((index=0; index<replicas; index++)); do
    result="$(pod_exec "$cluster-$index" psql -X -d "$database" -Atc 'select pg_is_in_recovery()' 2>/dev/null || true)"
    if [[ "$result" == "f" ]]; then
      printf '%s-%s\n' "$cluster" "$index"
      return 0
    fi
  done
  echo "No primary found for $cluster" >&2
  return 1
}

select_instance() {
  INSTANCE="$1"
  NAMESPACE=shopping-cart-data
  CONTAINER=postgresql
  POD="$INSTANCE-0"
  case "$INSTANCE" in
    postgresql-orders|postgresql-products)
      POD="$(find_primary "$INSTANCE" postgres 2)"
      ;;
    postgresql-marketplace|postgresql-payment) ;;
    postgres-keycloak)
      NAMESPACE=shopping-cart-identity
      CONTAINER=postgres
      ;;
    *) echo "Unknown database instance: $INSTANCE" >&2; return 1 ;;
  esac
}

list_databases() {
  pod_exec "$POD" psql -X -v ON_ERROR_STOP=1 -d postgres -Atc \
    "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres' ORDER BY datname COLLATE \"C\""
}

# Database names become filenames and whitespace-delimited rowcount fields.
check_database_name() {
  if [[ ! "$1" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$ ]]; then
    echo "Unsupported database name for backup filename: $1" >&2
    return 1
  fi
}

rowcounts() {
  local database="$1"
  pod_exec "$POD" psql -X -qAt -v ON_ERROR_STOP=1 -v instance="$INSTANCE" -d "$database" <<'SQL'
SELECT format('SELECT %L || count(*)::text FROM %I.%I;',
              :'instance' || ' ' || current_database() || ' ' || format('%I.%I', n.nspname, c.relname) || ' ',
              n.nspname, c.relname)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT LIKE 'pg\_%'
  AND n.nspname <> 'information_schema'
ORDER BY n.nspname COLLATE "C", c.relname COLLATE "C"
\gexec
SQL
}
