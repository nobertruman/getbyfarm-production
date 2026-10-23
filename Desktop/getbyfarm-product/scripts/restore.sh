#!/bin/sh
# Restore a backup into the running database. DESTRUCTIVE: replaces current data.
#   ./scripts/restore.sh backups/getbyfarm-YYYYMMDD-HHMMSS.sql.gz
set -eu
cd "$(dirname "$0")/.."
[ $# -eq 1 ] || { echo "usage: $0 <backup.sql.gz>"; exit 1; }
printf "This REPLACES the live database with %s. Type 'restore' to continue: " "$1"; read -r ok
[ "$ok" = "restore" ] || { echo "aborted"; exit 1; }
DC="docker compose --env-file .env.production -f docker-compose.prod.yml"
$DC stop backend
$DC exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c "$1" | $DC exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$DC start backend
echo "Restored."
