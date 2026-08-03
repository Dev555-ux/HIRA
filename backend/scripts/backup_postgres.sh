#!/usr/bin/env bash
# Nightly Postgres backup for the containerized DB (docker-compose.prod.yml).
# Replaces Railway's managed-Postgres-plugin backup toggle, which has no
# equivalent once Postgres runs in our own container — see
# documentation/DEPLOYMENT_AWS.md for the cron wiring.
#
# Run from backend/ on the EC2 host (not inside a container):
#   ./scripts/backup_postgres.sh
#
# Restore instructions: documentation/DEPLOYMENT_AWS.md, "Restoring a
# Postgres backup" — a plain-SQL pg_dump replays via `psql`, not `pg_restore`.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-/var/backups/hira-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/hira-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Read POSTGRES_USER/DB from .env so this stays in sync with
# docker-compose.prod.yml's postgres service without duplicating values.
# shellcheck disable=SC1091
set -a; source .env; set +a

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-hira}" "${POSTGRES_DB:-hira}" \
  | gzip > "$OUT_FILE"

echo "Backup written to $OUT_FILE"

# Prune backups older than RETENTION_DAYS.
find "$BACKUP_DIR" -name 'hira-*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete
