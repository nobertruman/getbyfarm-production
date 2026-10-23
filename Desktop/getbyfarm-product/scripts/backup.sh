#!/bin/sh
# Nightly Postgres backup. Usage (from the repo root on the server):  ./scripts/backup.sh
# Cron example (2:30am daily):  30 2 * * * cd /opt/getbyfarm && ./scripts/backup.sh >> backups/backup.log 2>&1
# Copy backups OFF this server too (object storage / another host): a backup on the same disk isn't a backup.
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
FILE="backups/getbyfarm-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$FILE"
echo "Wrote $FILE ($(du -h "$FILE" | cut -f1))"
# Keep 14 days locally.
find backups -name 'getbyfarm-*.sql.gz' -mtime +14 -delete
