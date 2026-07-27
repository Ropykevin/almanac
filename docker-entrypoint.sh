#!/bin/sh
set -eu

# Build a safe DATABASE_URL from discrete parts (handles special chars in passwords).
# Prefer this over embedding the password in docker-compose.yml interpolation.
if [ -n "${DB_HOST:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  DATABASE_URL="$(
    DB_HOST="$DB_HOST" \
    DB_PORT="${DB_PORT:-5432}" \
    POSTGRES_USER="${POSTGRES_USER:-almanac}" \
    POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    POSTGRES_DB="${POSTGRES_DB:-almanac_africa_ai}" \
    python - <<'PY'
import os
from urllib.parse import quote_plus

user = quote_plus(os.environ["POSTGRES_USER"])
password = quote_plus(os.environ["POSTGRES_PASSWORD"])
host = os.environ["DB_HOST"]
port = os.environ.get("DB_PORT", "5432")
db = quote_plus(os.environ["POSTGRES_DB"])
print(f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}")
PY
  )"
  export DATABASE_URL
fi

echo "Waiting for database..."
python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
if not url:
    print("DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)

parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
host = parsed.hostname or "db"
port = parsed.port or 5432

for attempt in range(1, 61):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"Database reachable at {host}:{port}")
            sys.exit(0)
    except OSError as exc:
        print(f"  attempt {attempt}/60 — {host}:{port} not ready ({exc})")
        time.sleep(2)

print(f"Could not reach database at {host}:{port}", file=sys.stderr)
sys.exit(1)
PY

echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
workers="${WEB_CONCURRENCY:-2}"
bind="${GUNICORN_BIND:-0.0.0.0:8000}"
exec gunicorn \
  --bind "$bind" \
  --workers "$workers" \
  --access-logfile - \
  --error-logfile - \
  --timeout 120 \
  "wsgi:app"
