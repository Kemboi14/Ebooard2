#!/usr/bin/env sh
# =============================================================================
# Enwealth E-Board Portal — Docker Entrypoint
# =============================================================================
# Runs database migrations then hands off to Gunicorn.
# This script is executed as the non-root `appuser` inside the container.
# =============================================================================

set -e

echo "==> [entrypoint] Running database migrations..."
python manage.py migrate --noinput

echo "==> [entrypoint] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --workers 4 \
    --worker-class sync \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keepalive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
