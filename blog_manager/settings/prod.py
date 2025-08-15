from .base import *  # noqa

DEBUG = False
# --- DRF: JSON only in prod, no browsable API ---
REST_FRAMEWORK.update({
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
    },
})

# --- CORS/CSRF ristretti ai domini Jekyll (da .env) ---
import os
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Security headers minime
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
REFERRER_POLICY = "same-origin"
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
EMAIL_BACKEND = "anymail.backends.mailersend.EmailBackend"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REFERRER_POLICY = "strict-origin"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
GITHUB_TOKEN = env("GITHUB_TOKEN", default=None)

# EXPORT_ENABLED letto da env in base.py; non sovrascrivere qui.
# MySQL via env; utf8mb4 + STRICT + conn pooling
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_NAME"),
        "USER": env("MYSQL_USER"),
        "PASSWORD": env("MYSQL_PASSWORD"),
        "HOST": env("MYSQL_HOST"),
        "PORT": env("MYSQL_PORT"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "use_unicode": True,
            # Ensure connection uses utf8mb4 and a compatible collation, enable strict mode
            # SET NAMES forces client/connection character set so emoji won't raise
            "init_command": (
                "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci; "
                "SET sql_mode='STRICT_ALL_TABLES'; "
                "SET time_zone='+00:00'"
            ),
        },
        "CONN_MAX_AGE": 60,  # keep-alive pooling
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
