from decouple import config, Csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config('SECRET_KEY')
AUTH_USER_MODEL = 'accounts.User'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_htmx',
    'crispy_forms',
    'crispy_tailwind',
    'django_celery_beat',
    # Local apps
    'apps.accounts',
    'apps.dashboard',
    'apps.meetings',
    'apps.documents',
    'apps.voting',
    'apps.risk',
    'apps.policy',
    'apps.audit',
    'apps.evaluation',
    'apps.discussions',
    'apps.notifications',
    'apps.analytics',
]

ROOT_URLCONF = 'config.urls'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.accounts.context_processors.user_permissions',
        ],
    },
}]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='enwealth_eboard'),
        'USER': config('DB_USER', default='enwealth_user'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

TIME_ZONE = 'Africa/Nairobi'
USE_TZ = True
LANGUAGE_CODE = 'en-us'
USE_I18N = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# Celery (Redis broker running natively)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')
CELERY_TIMEZONE = 'Africa/Nairobi'
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat periodic tasks - temporarily disabled for CSRF troubleshooting
try:
    from celery.schedules import crontab
    CELERY_BEAT_SCHEDULE = {
        'auto-close-resolutions': {
            'task': 'apps.voting.tasks.auto_close_expired_resolutions',
            'schedule': 300,  # every 5 minutes
        },
        'send-meeting-reminders': {
            'task': 'apps.meetings.tasks.send_upcoming_meeting_reminders',
            'schedule': crontab(hour=8, minute=0),  # 8am Nairobi daily
        },
        'database-backup': {
            'task': 'apps.audit.tasks.run_database_backup',
            'schedule': crontab(hour=2, minute=0),  # 2am Nairobi daily
        },
    }
except ImportError:
    pass

SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=3600, cast=int)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# CSRF Settings - temporarily disabled for development
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:8000,http://127.0.0.1:8000', cast=Csv())
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Temporarily disable CSRF for development
CSRF_USE_SESSIONS = False
CSRF_COOKIE_SECURE = False

# Session Settings
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# OTP/MFA Settings
OTP_TOTP_ISSUER = 'Enwealth Board Portal'
OTP_TOTP_DIGITS = 6
OTP_TOTP_VALIDITY = 30
OTP_TOTP_DRIFT = 1
OTP_LOGIN_URL = '/login/'
OTP_LOGIN_REDIRECT_URL = '/dashboard/'
OTP_ADMIN_REDIRECT_URL = '/admin/'

# Enable MFA for admin users
OTP_ADMIN_SITE_TITLE = 'Enwealth Admin Portal'
OTP_ADMIN_SITE_HEADER = 'Enwealth Administration'

# MFA Required Roles - Users in these roles must have MFA enabled
MFA_REQUIRED_ROLES = [
    'it_administrator',
    'company_secretary', 
    'executive_management',
    'compliance_officer',
    'board_member'
]

# Enable MFA enforcement globally
OTP_MFA_REQUIRED = True
OTP_MFA_GRACE_PERIOD = 7  # Days to enable MFA after account creation

# Custom CSRF failure view
# CSRF_FAILURE_VIEW = 'accounts.csrf_failure_view.csrf_failure'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {'level': 'INFO', 'class': 'logging.FileHandler',
                 'filename': BASE_DIR / 'logs/django.log'},
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console', 'file'], 'level': 'INFO'},
}
