from .base import *  # noqa
from pathlib import Path
from core.db import build_database_config
from django.core.exceptions import ImproperlyConfigured

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
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Per sicurezza: SQLite in prod è esplicitamente opt-in
ALLOW_SQLITE_IN_PROD = env.bool("ALLOW_SQLITE_IN_PROD", default=False)
DB_ENGINE = env("DB_ENGINE", default="mysql").lower()
if DB_ENGINE == "sqlite" and not ALLOW_SQLITE_IN_PROD:
    raise ImproperlyConfigured(
        "SQLite in produzione è disabilitato di default. Imposta ALLOW_SQLITE_IN_PROD=True per abilitarlo."
    )

# Config DB centralizzata (mysql|sqlite)
DATABASES = {
    "default": build_database_config(env, BASE_DIR, default_engine="mysql"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
