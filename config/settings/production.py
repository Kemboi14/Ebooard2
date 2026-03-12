# =============================================================================
# Enwealth E-Board Portal — PRODUCTION SETTINGS
# =============================================================================
# Do NOT run collectstatic with DEBUG=True — always use this settings file
# for production deployments. Set DJANGO_SETTINGS_MODULE=config.settings.production
# in your environment or .env file before any management commands.
# =============================================================================

from decouple import Csv, config

from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# SITE_URL — override base.py default (used in email links, e-signature, etc.)
SITE_URL = config("SITE_URL")

# ---------------------------------------------------------------------------
# CSRF & trusted origins
# ---------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv())
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_USE_SESSIONS = False

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
# Tell browsers to enforce HTTPS for one full year, including sub-domains,
# and allow the domain to be submitted to the HSTS preload list.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Trust the X-Forwarded-Proto header set by Nginx / a load-balancer.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Redirect all plain-HTTP traffic to HTTPS at the Django level.
SECURE_SSL_REDIRECT = True

# Prevent browsers from MIME-sniffing responses away from the declared type.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Legacy IE XSS protection header (belt-and-suspenders; modern browsers ignore it).
SECURE_BROWSER_XSS_FILTER = True

# Deny framing from any origin at the Django level (Nginx also sets this).
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Static files — WhiteNoise compressed + hashed manifests
# ---------------------------------------------------------------------------
# STATIC_ROOT and MEDIA_ROOT are already defined in base.py.
# WhiteNoise serves static files directly from the WSGI process, compresses
# them with gzip/brotli, and attaches far-future cache headers via the
# content-hash suffix it injects into filenames.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Email — SMTP
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Enwealth E-Board <noreply@enwealth.co.ke>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------------
# Celery — Redis broker + result backend
# (base.py already reads these from env; re-declared here for explicitness)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Ensure the logs/ directory exists before starting the server:
#   mkdir -p /var/www/enwealth/logs   (VPS)  or
#   the Dockerfile / entrypoint already creates /app/logs (Docker)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        # ---- stdout / stderr captured by systemd / Docker ----
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # ---- general application log (INFO+) ----
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(BASE_DIR / "logs" / "django.log"),  # noqa: F405
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        # ---- error-only log (ERROR+) ----
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(BASE_DIR / "logs" / "error.log"),  # noqa: F405
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        # ---- email admins on ERROR (uses EMAIL_HOST above) ----
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file", "error_file"],
        "level": "INFO",
    },
    "loggers": {
        # Django internals — keep at INFO so runserver noise is reduced
        "django": {
            "handlers": ["console", "file", "error_file", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        # Django security warnings always go to the error log
        "django.security": {
            "handlers": ["error_file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        # Database query log (very verbose — only enable when debugging)
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Celery task log
        "celery": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Local app loggers
        "apps": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
