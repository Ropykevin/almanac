#!/bin/sh
set -eu

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
