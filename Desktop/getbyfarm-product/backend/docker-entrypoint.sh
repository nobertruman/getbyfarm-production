#!/bin/sh
# Applies database migrations, loads the starter catalogue (idempotent), then starts the server.
set -eu
echo "GetbyFarm backend starting (port ${PORT:-8000})"
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Applying migrations…"
  python manage.py migrate --noinput
  python manage.py createcachetable
  python manage.py seed_catalogue
fi
exec "$@"
