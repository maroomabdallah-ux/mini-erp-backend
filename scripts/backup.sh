#!/bin/sh
set -eu

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
pg_dump -h postgres -U "${POSTGRES_USER:-mini_erp_user}" -d "${POSTGRES_DB:-mini_erp_db}" \
  --format=custom --file="/backups/mini_erp_${timestamp}.dump"
find /backups -type f -name 'mini_erp_*.dump' -mtime +30 -delete
