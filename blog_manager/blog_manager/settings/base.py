import os
import sys
from pathlib import Path

import environ

# Setup environ
env = environ.Env(DEBUG=(bool, False))
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
DEBUG = env.bool("DEBUG") if "DEBUG" in os.environ else False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS") if "ALLOWED_HOSTS" in os.environ else []
DATABASES = {
    "default": (
        env.db("DATABASE_URL")
        if "DATABASE_URL" in os.environ
        else {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    )
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
    "contact",
    "corsheaders",
    "blog",
    "anymail",
    "rest_framework",
    "django_filters",
    "cloudinary",
    "cloudinary_storage",
    "rest_framework.authtoken",
    "writer",
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

ROOT_URLCONF = "blog_manager.urls"

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
WSGI_APPLICATION = "blog_manager.wsgi.application"

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
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.core.mail": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
