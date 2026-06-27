"""
Django settings for the APTRANSCO Transmission Dataset Collection Portal.

Configuration is environment-driven (12-factor): secrets and per-environment
values are read from the process environment, with a small, dependency-free
loader that also reads a local ``.env`` file for development convenience.

In development you can run with no environment set at all — sensible defaults
keep the dev experience zero-config. In production set ``DJANGO_DEBUG=False``
and provide ``DJANGO_SECRET_KEY``, ``DJANGO_ALLOWED_HOSTS`` and the database
credentials; the deployment checklist below then activates the secure-cookie /
HSTS / SSL-redirect settings automatically.

See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Minimal .env loader (no third-party dependency)
# ---------------------------------------------------------------------------
def _load_dotenv(path):
    """Populate os.environ from a KEY=VALUE .env file (does not overwrite
    variables already set in the real environment, so the OS/host always wins)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key, default=None):
    val = os.environ.get(key)
    if not val:
        return list(default or [])
    return [item.strip() for item in val.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", default=True)

# Dev keeps a deterministic insecure key for zero-config convenience; production
# (DEBUG=False) must supply a real secret or startup fails loudly.
_DEV_SECRET = "django-insecure-6wzg(sntab@yd+fwnqc4y@_oks7@qlo870vr^s@juku(b(8nxt"
SECRET_KEY = env("DJANGO_SECRET_KEY", _DEV_SECRET if DEBUG else None)
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable is required when DEBUG=False."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=[] if not DEBUG else ["*"])

# Needed for HTTPS POSTs (login, review, etc.) behind a domain in production.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'transmission',
    'masterdata',
    'datasets',
    'dashboard',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# WhiteNoise serves collected static files directly from the WSGI app, so the
# portal can be deployed without a separate static file server. It is optional:
# if the package isn't installed (e.g. a minimal dev box) the app still runs.
try:
    import whitenoise  # noqa: F401

    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES_STATIC_BACKEND = (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
except ImportError:
    STORAGES_STATIC_BACKEND = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": env("DJANGO_DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": env("DJANGO_DB_NAME", "data_portal"),
        "USER": env("DJANGO_DB_USER", "postgres"),
        # No hardcoded fallback — source the password from the environment / .env.
        "PASSWORD": env("DJANGO_DB_PASSWORD", ""),
        "HOST": env("DJANGO_DB_HOST", "localhost"),
        "PORT": env("DJANGO_DB_PORT", "5432"),
        # Reuse DB connections for the configured number of seconds (0 = close
        # after each request). A small value cuts per-request connect overhead.
        "CONN_MAX_AGE": int(env("DJANGO_DB_CONN_MAX_AGE", "60")),
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

# APTRANSCO operates in India; store in UTC (USE_TZ) and display in IST by default.
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Kolkata")

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Target of `manage.py collectstatic` for production serving.
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": STORAGES_STATIC_BACKEND},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

# Cap upload payloads. Inspections can carry many images, so allow a large
# multipart body but bound each field; tune via env for the deployment host.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    env("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(50 * 1024 * 1024))
)
DATA_UPLOAD_MAX_NUMBER_FILES = int(env("DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES", "500"))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    env("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024))
)
# Largest single image accepted by the upload view (bytes); see datasets/views.py.
MAX_IMAGE_UPLOAD_SIZE = int(env("DJANGO_MAX_IMAGE_UPLOAD_SIZE", str(25 * 1024 * 1024)))

# Authentication redirects (uses URL names from the included auth + app URLs).
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Map Django's ERROR message level to Bootstrap's "danger" alert class.
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: "danger"}


# ---------------------------------------------------------------------------
# Production hardening — only active when DEBUG is off, so dev is unaffected.
# ---------------------------------------------------------------------------
if not DEBUG:
    # Assume TLS is terminated by a reverse proxy that sets this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("DJANGO_SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"


# ---------------------------------------------------------------------------
# Logging — console by default; add a rotating file via DJANGO_LOG_FILE.
# ---------------------------------------------------------------------------
_LOG_LEVEL = env("DJANGO_LOG_LEVEL", "INFO").upper()
_LOG_FILE = env("DJANGO_LOG_FILE")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": _LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": _LOG_LEVEL,
            "propagate": False,
        },
    },
}

if _LOG_FILE:
    LOGGING["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": _LOG_FILE,
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "formatter": "verbose",
    }
    LOGGING["root"]["handlers"].append("file")
    LOGGING["loggers"]["django"]["handlers"].append("file")
