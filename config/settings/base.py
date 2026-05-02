"""
Django settings for Enwealth project.
"""

import os
from pathlib import Path
from decouple import Csv, config
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config("SECRET_KEY")
AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_htmx",
    "crispy_forms",
    "crispy_tailwind",
    "django_celery_beat",
    "rest_framework",
    # Local apps
    "apps.accounts",
    "apps.agencies",
    "apps.esignature",
    "apps.dashboard",
    "apps.meetings",
    "apps.documents",
    "apps.voting",
    "apps.risk",
    "apps.policy",
    "apps.audit",
    "apps.evaluation",
    "apps.discussions",
    "apps.notifications",
    "apps.analytics",
    "apps.organization",
    "apps.calendar",
    "apps.recordings",
    "apps.messaging",
    "apps.survey",
    "apps.api",
    "apps.accessibility",
]

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/hour",
        "user": "200/hour",
    },
}

# ---------------------------------------------------------------------------
# E-Signature settings
# ---------------------------------------------------------------------------
ESIGNATURE_OTP_EXPIRY_MINUTES = 10
ESIGNATURE_MAX_FILE_SIZE_MB = 20
ESIGNATURE_ALLOWED_MIME_TYPES = ["application/pdf"]
# Full URL used in email links — override in production settings
SITE_URL = config("SITE_URL", default="http://localhost:8000")

ROOT_URLCONF = "config.urls"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.user_permissions",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "enwealth"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# External API Configuration
# OpenAI API for transcription and AI features
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_ORGANIZATION = os.environ.get("OPENAI_ORGANIZATION", "")

# Zoom API for meeting integration
ZOOM_API_KEY = os.environ.get("ZOOM_API_KEY", "")
ZOOM_API_SECRET = os.environ.get("ZOOM_API_SECRET", "")

# Microsoft Teams API for meeting integration
TEAMS_CLIENT_ID = os.environ.get("TEAMS_CLIENT_ID", "")
TEAMS_CLIENT_SECRET = os.environ.get("TEAMS_CLIENT_SECRET", "")
TEAMS_TENANT_ID = os.environ.get("TEAMS_TENANT_ID", "")

# Language Settings
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "en")
SUPPORTED_LANGUAGES = ["en", "fr", "sw", "ar", "pt"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

TIME_ZONE = "Africa/Nairobi"
USE_TZ = True
LANGUAGE_CODE = "en-us"
USE_I18N = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/auth/login/"

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# Celery (Redis broker running natively)
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/1"
)
CELERY_TIMEZONE = "Africa/Nairobi"
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Celery Beat periodic tasks - temporarily disabled for CSRF troubleshooting
try:
    from celery.schedules import crontab

    CELERY_BEAT_SCHEDULE = {
        "auto-close-resolutions": {
            "task": "apps.voting.tasks.auto_close_expired_resolutions",
            "schedule": 300,  # every 5 minutes
        },
        "send-meeting-reminders": {
            "task": "apps.meetings.tasks.send_upcoming_meeting_reminders",
            "schedule": crontab(hour=8, minute=0),  # 8am Nairobi daily
        },
        "database-backup": {
            "task": "apps.audit.tasks.run_database_backup",
            "schedule": crontab(hour=2, minute=0),  # 2am Nairobi daily
        },
    }
except ImportError:
    pass

SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=180, cast=int)  # 3 minutes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# CSRF and Session Security Settings - Enabled for production
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=Csv(),
)
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# OTP/MFA Settings
OTP_TOTP_ISSUER = "Enwealth Board Portal"
OTP_TOTP_DIGITS = 6
OTP_TOTP_VALIDITY = 30
OTP_TOTP_DRIFT = 1
OTP_LOGIN_URL = "/login/"
OTP_LOGIN_REDIRECT_URL = "/dashboard/"
OTP_ADMIN_REDIRECT_URL = "/admin/"

# Enable MFA for admin users
OTP_ADMIN_SITE_TITLE = "Enwealth Admin Portal"
OTP_ADMIN_SITE_HEADER = "Enwealth Administration"

# MFA Required Roles - Users in these roles must have MFA enabled
MFA_REQUIRED_ROLES = [
    "it_administrator",
    "company_secretary",
    "executive_management",
    "compliance_officer",
    "board_member",
]

# Enable MFA enforcement globally
OTP_MFA_REQUIRED = True
OTP_MFA_GRACE_PERIOD = 7  # Days to enable MFA after account creation

# Custom CSRF failure view
# CSRF_FAILURE_VIEW = 'accounts.csrf_failure_view.csrf_failure'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/django.log",
        },
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}
