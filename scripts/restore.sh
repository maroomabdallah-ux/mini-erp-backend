#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/restore.sh backups/mini_erp_TIMESTAMP.dump" >&2
  exit 2
fi
docker compose exec -T postgres pg_restore --clean --if-exists \
  -U "${POSTGRES_USER:-mini_erp_user}" -d "${POSTGRES_DB:-mini_erp_db}" < "$1"
