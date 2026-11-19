#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/database-common.sh"

if [[ $# != 1 ]]; then
  echo "usage: backup-databases.sh BACKUP_DIR | --rowcounts-only" >&2
  exit 1
fi

ROWCOUNTS_ONLY=false
if [[ "$1" == "--rowcounts-only" ]]; then
  ROWCOUNTS_ONLY=true
else
  BACKUP_DIR="$1"
  umask 077
  mkdir -p "$BACKUP_DIR"
  if [[ -n "$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "Backup directory must be empty: $BACKUP_DIR" >&2
    exit 1
  fi
  : > "$BACKUP_DIR/ROWCOUNTS.txt"
fi

for instance in "${INSTANCES[@]}"; do
  select_instance "$instance"
  databases="$(list_databases)"
  if [[ "$ROWCOUNTS_ONLY" == false ]]; then
    # Preserve roles/grants for recovery without exporting password hashes.
    pod_exec "$POD" pg_dumpall --globals-only --no-role-passwords \
      > "$BACKUP_DIR/${instance}__globals.sql"
  fi
  # Read names from fd 3: `kubectl exec -i` inside the loop would swallow stdin.
  while IFS= read -r -u 3 database; do
    [[ -n "$database" ]] || continue
    check_database_name "$database"
    if [[ "$ROWCOUNTS_ONLY" == true ]]; then
      rowcounts "$database"
    else
      echo "Backing up $instance / $database from $POD" >&2
      pod_exec "$POD" pg_dump -Fc -d "$database" > "$BACKUP_DIR/${instance}__${database}.dump"
      rowcounts "$database" >> "$BACKUP_DIR/ROWCOUNTS.txt"
    fi
  done 3<<< "$databases"
done

if [[ "$ROWCOUNTS_ONLY" == false ]]; then
  (cd "$BACKUP_DIR" && shasum -a 256 -- ./*.dump ./*__globals.sql ROWCOUNTS.txt > CHECKSUMS.txt)
  echo "Database backups, CHECKSUMS.txt and ROWCOUNTS.txt written to $BACKUP_DIR" >&2
fi
