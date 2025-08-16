from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

def build_database_config(env, base_dir: Path, default_engine: str = "mysql"):
    """
    Ritorna un dict DATABASES['default'] in base a DB_ENGINE (mysql|sqlite).
    Nessuna nuova dipendenza; usa django-environ già presente nel progetto.
    """
    engine = env("DB_ENGINE", default=default_engine).lower()

    if engine == "sqlite":
        name = env("SQLITE_NAME", default="prod.sqlite3")
        db_path = base_dir / "data" / name
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(db_path),
            "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=0),
            "OPTIONS": {"timeout": env.int("SQLITE_TIMEOUT", default=20)},
            "ATOMIC_REQUESTS": True,
        }

    if engine == "mysql":
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", default="127.0.0.1"),
            "PORT": env("DB_PORT", default="3306"),
            "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=60),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            "ATOMIC_REQUESTS": True,
        }

    raise ImproperlyConfigured(f"Unsupported DB_ENGINE '{engine}'. Use 'mysql' or 'sqlite'.")
