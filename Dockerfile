# =============================================================================
# Enwealth E-Board Portal — Production Dockerfile
# Multi-stage build: builder installs deps, runtime image is lean.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder
# Install all Python dependencies into /install so the runtime image
# doesn't need build tools (gcc, libpq-dev, etc.)
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages into a dedicated prefix so we can copy them cleanly
COPY requirements/ /tmp/requirements/
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r /tmp/requirements/production.txt


# -----------------------------------------------------------------------------
# Stage 2: runtime
# Lean final image — only what is needed to run the application.
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Prevent Python from writing .pyc files and buffer stdout/stderr so logs
# appear immediately in Docker / systemd journal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

# Runtime system dependencies only (libpq for psycopg2, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /install

# ---------------------------------------------------------------------------
# Non-root user for security
# ---------------------------------------------------------------------------
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --shell /bin/bash --create-home appuser

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
WORKDIR /app

# Copy project source
COPY --chown=appuser:appuser . /app/

# Create runtime directories (logs, media, staticfiles) and fix ownership.
# The Dockerfile itself runs collectstatic so the staticfiles volume is
# pre-populated when the container starts.
RUN mkdir -p /app/logs /app/media /app/staticfiles \
    && chown -R appuser:appuser /app/logs /app/media /app/staticfiles

# Switch to non-root user for all subsequent commands
USER appuser

# Collect static assets so WhiteNoise / Nginx can serve them.
# DATABASE_URL / DB_* are not required at build time — collectstatic only
# reads settings, it does not touch the database.
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# ---------------------------------------------------------------------------
# Expose & entrypoint
# ---------------------------------------------------------------------------
EXPOSE 8000

# entrypoint.sh: run migrations then hand off to gunicorn.
# Using an inline script keeps the image self-contained.
COPY --chown=appuser:appuser deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
