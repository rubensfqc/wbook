"""wbook settings — everything comes from .env (see .env.example)."""

import sys
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
SITE_URL = config("SITE_URL", default="http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.forms",
    "apps.core",
    "apps.accounts",
    "apps.clinic",
    "apps.agenda",
    "apps.landing",
    "apps.quotes",
    "apps.operator",
    "apps.dataio",
    "apps.website",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.core.middleware.DefaultLanguageMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.SubscriptionMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.site",
            ],
            "builtins": [
                "django.templatetags.i18n",
                "django.templatetags.static",
                "apps.core.templatetags.wb",
            ],
        },
    }
]
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

DB_ENGINE = config("DB_ENGINE", default="sqlite")
if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT", default="3306"),
            "OPTIONS": {"charset": "utf8mb4"},
            "CONN_MAX_AGE": 280,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / config("SQLITE_NAME", default="db.sqlite3"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrUsernameBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "website:home"
PASSWORD_RESET_TIMEOUT = 3 * 24 * 3600
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
LANGUAGES = [("pt-br", "Português"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "wbook_lang"
LANGUAGE_COOKIE_AGE = 365 * 24 * 3600
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_S3 = config("USE_S3", default=False, cast=bool)
if TESTING:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
elif USE_S3:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="sa-east-1")
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "apps.core.storage.HashedStaticStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "apps.core.storage.HashedStaticStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }

MAX_UPLOAD_MB = config("MAX_UPLOAD_MB", default=20, cast=int)
MAX_PHOTO_MB = config("MAX_PHOTO_MB", default=10, cast=int)
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
IP_HASH_SALT = config("IP_HASH_SALT", default="wbook-dev-salt")
CONSENT_VERSION = "2026-11"

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
if TESTING:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="wbook <wbook@gmail.com>")
SERVER_EMAIL = config("SERVER_EMAIL", default="wbook@gmail.com")
PLATFORM_CONTACT_EMAIL = config("PLATFORM_CONTACT_EMAIL", default="wbook@gmail.com")
ADMINS = [("wbook", a) for a in config("ADMINS", default="", cast=Csv()) if a]
EMAIL_TIMEOUT = 15

ADMIN_URL = config("ADMIN_URL", default="admin/")

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher", "django.contrib.auth.hashers.PBKDF2PasswordHasher"]

if not DEBUG and not TESTING:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
    SECURE_CONTENT_TYPE_NOSNIFF = True

ACTIVITY_LOG_FILE = config("ACTIVITY_LOG_FILE", default=str(BASE_DIR / "var" / "logs" / "activity.log"))
Path(ACTIVITY_LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(message)s"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "activity": (
            {"class": "logging.NullHandler"}
            if TESTING
            else {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": ACTIVITY_LOG_FILE,
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "plain",
            }
        ),
    },
    "loggers": {
        "wbook.activity": {"handlers": ["activity"], "level": "INFO", "propagate": False},
        "wbook": {"handlers": ["console"], "level": "INFO"},
    },
}
