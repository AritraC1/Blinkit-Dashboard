#!/bin/sh
# Container entrypoint: prepare runtime dirs, wait for the DB, migrate, then start the server.
set -e

# These directories are excluded from the image by .dockerignore, so recreate them
mkdir -p data/processed ml_artifacts

# Wait for Postgres when DATABASE_URL is set (Django itself resolves the connection)
if [ -n "$DATABASE_URL" ]; then
  echo "Waiting for the database..."
  until python - <<'PYEOF'
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

import django

django.setup()

from django.db import connection

connection.ensure_connection()
PYEOF
  do
    echo "Database unavailable - retrying in 2 seconds..."
    sleep 2
  done
  echo "Database is up."
fi

# Apply migrations on startup (set SKIP_MIGRATIONS=1 to run them manually instead)
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
