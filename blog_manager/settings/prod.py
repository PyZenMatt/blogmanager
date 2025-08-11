from .base import *

DEBUG = False
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
			"init_command": "SET sql_mode='STRICT_ALL_TABLES', time_zone='+00:00'",
		},
		"CONN_MAX_AGE": 60,            # keep-alive pooling
	}
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
