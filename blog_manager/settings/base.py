"""Impostazioni base.

La flag EXPORT_ENABLED ora è controllata via variabile d'ambiente EXPORT_ENABLED
 (default True) per evitare confusione con override hardcoded in dev/prod.
"""
import os
import sys
from pathlib import Path
import environ

# Setup environ
env = environ.Env(DEBUG=(bool, False), EXPORT_ENABLED=(bool, True))
# Carica .env
environ.Env.read_env(os.getenv("ENV_FILE", ".env"))

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("SECRET_KEY")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=None) or []
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=None) or []
CLOUDINARY_URL = env("CLOUDINARY_URL", default=None)
GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)
EMAIL_HOST = env("EMAIL_HOST", default=None)
EMAIL_PORT = env.int("EMAIL_PORT", default=None) or 587
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default=None)
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default=None)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=None)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=None)
JEKYLL_REPO_BASE = env("JEKYLL_REPO_BASE", default=None)
DEBUG = env.bool("DEBUG") if "DEBUG" in os.environ else False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS") if "ALLOWED_HOSTS" in os.environ else []
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "blogmanager",
        "USER": "teo",
        "PASSWORD": "OilPainter@25!",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        },
    }
}
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=None) or []
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=None) or []
CLOUDINARY_URL = env("CLOUDINARY_URL", default=None)
GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)
EMAIL_HOST = env("EMAIL_HOST", default=None)
EMAIL_PORT = env.int("EMAIL_PORT", default=None) or 587
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default=None)
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default=None)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=None)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=None)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # App di progetto (usare il path all'AppConfig per garantire ready() e label corretti)
    "blog",
    "contact.apps.ContactConfig",
    "writer.apps.WriterConfig",
    # Terze parti
    "corsheaders",
    "anymail",
    "rest_framework",
    "django_filters",
    "cloudinary",
    "cloudinary_storage",
    "rest_framework.authtoken",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
MIDDLEWARE.insert(0, "writer.middleware.LoginRateLimitMiddleware")


MIDDLEWARE.append("core.middleware.exception_logging.VerboseExceptionLoggingMiddleware")

ROOT_URLCONF = "urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "blog_manager" / "writer" / "templates",
            BASE_DIR / "blog_manager" / "writer",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
LOGIN_URL = "writer:login"
LOGIN_REDIRECT_URL = "writer:post_new"
LOGOUT_REDIRECT_URL = "writer:login"
WSGI_APPLICATION = "wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAdminUser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
    },
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

# Feature flag export (ora dopo aver caricato env)
EXPORT_ENABLED = env.bool("EXPORT_ENABLED", default=True)
BLOG_REPO_BASE = env("BLOG_REPO_BASE", default="")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", '
                '"message": %(message)s}'
            ),
        },
        "simple": {"format": "%(levelname)s %(name)s %(message)s"},
        "verbose": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(module)s:%(lineno)d %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.core.mail": {
            "handlers": ["console"], "level": "DEBUG", "propagate": True,
        },
        "django.db.backends": {"level": "WARNING"},
        "core.rest.exceptions": {"level": "INFO"},
    # Debug exporter dettagliato
    "blog.exporter": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
