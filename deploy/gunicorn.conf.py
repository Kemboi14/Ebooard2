# =============================================================================
# Enwealth E-Board Portal — Gunicorn Configuration
# =============================================================================
# Used by:
#   - Dockerfile ENTRYPOINT (Docker / Docker Compose)
#   - deploy/enwealth.service (systemd / bare VPS)
#   - Procfile (Heroku / Railway / Render — CLI flags take precedence there)
#
# Reference: https://docs.gunicorn.org/en/stable/settings.html
# =============================================================================

import multiprocessing

# ---------------------------------------------------------------------------
# Server socket
# ---------------------------------------------------------------------------
bind = "0.0.0.0:8000"

# ---------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------
# A common starting point is (2 × CPU cores) + 1.
# Hard-coded to 4 here so the value is explicit and predictable across
# environments.  Override with the WEB_CONCURRENCY env var if needed:
#   WEB_CONCURRENCY=8 gunicorn -c deploy/gunicorn.conf.py config.wsgi:application
workers = int(__import__("os").environ.get("WEB_CONCURRENCY", 4))

# "sync" is the safest default and works well with Django's ORM.
# Switch to "gevent" or "gthread" only if you have profiled and confirmed
# that your workload is I/O-bound.
worker_class = "sync"

# Number of threads per worker (only relevant for gthread worker class).
# Kept at 1 for the sync worker to avoid any thread-safety surprises.
threads = 1

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
# Workers that take longer than `timeout` seconds to handle a single request
# are killed and restarted.  120 s accommodates large PDF uploads / exports.
timeout = 120

# How long to wait for the next request on a Keep-Alive connection.
keepalive = 5

# Seconds to wait for workers to finish serving requests after a SIGTERM.
graceful_timeout = 30

# ---------------------------------------------------------------------------
# Request recycling — prevents slow memory leaks from accumulating forever
# ---------------------------------------------------------------------------
# Each worker process is recycled after handling this many requests.
max_requests = 1000

# Random jitter added to max_requests so all workers don't restart at once.
max_requests_jitter = 50

# ---------------------------------------------------------------------------
# Preload application
# ---------------------------------------------------------------------------
# Load the Django app before forking workers.  This reduces per-worker startup
# time and memory usage (copy-on-write pages are shared across workers).
# NOTE: do NOT use preload_app with gevent/eventlet workers.
preload_app = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# "-" sends to stdout/stderr so Docker / systemd captures the output.
# For bare VPS installs the paths below are used instead; the logs/ directory
# must exist before starting the service:
#   mkdir -p /var/www/enwealth/logs
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# Include the timestamp in the access log
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)ss'

# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------
proc_name = "enwealth_gunicorn"

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# Limit the size of HTTP request line + headers to guard against slowloris /
# header-flooding attacks.  25 MB total body limit is enforced in Nginx.
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ---------------------------------------------------------------------------
# Server hooks (optional — uncomment to enable)
# ---------------------------------------------------------------------------
# def on_starting(server):
#     """Called just before the master process is initialized."""
#     pass
#
# def post_fork(server, worker):
#     """Called just after a worker has been forked."""
#     pass
#
# def worker_exit(server, worker):
#     """Called just after a worker has been exited."""
#     pass
