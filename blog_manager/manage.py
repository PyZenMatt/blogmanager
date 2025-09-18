#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main() -> None:
    """
    Bootstrap robusto:
      - garantisce la project root in sys.path
      - imposta un default sicuro per DJANGO_SETTINGS_MODULE
    """
    # Directory che contiene questo manage.py (es. .../blog_manager)
    base_dir = Path(__file__).resolve().parent

    # Assicura che la package dir e la project root siano nel PYTHONPATH
    # (necessario quando lo script è invocato da directory diverse)
    package_dir = str(base_dir)
    project_root = str(base_dir.parent)
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # If not provided, point ENV_FILE to one level above `blog_manager` (project root)
    # This allows running `python manage.py <cmd>` from the package directory without
    # requiring users to set ENV_FILE manually when a project-level `.env` exists.
    if "ENV_FILE" not in os.environ:
        project_env = base_dir.parent / ".env"
        os.environ.setdefault("ENV_FILE", str(project_env))

    # Default settings selection:
    # - If DJANGO_SETTINGS_MODULE is explicitly set, respect it.
    # - Otherwise choose `settings.prod` when ENVIRONMENT=production or when
    #   the chosen ENV_FILE ends with '.prod', else fall back to `settings.dev`.
    explicit = os.getenv("DJANGO_SETTINGS_MODULE")
    if explicit:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", explicit)
    else:
        env_flag = os.environ.get("ENVIRONMENT", "").lower()
        env_file = os.environ.get("ENV_FILE", "")
        if env_flag in ("prod", "production") or str(env_file).endswith(".prod"):
            default_settings = "settings.prod"
        else:
            default_settings = "settings.dev"
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)

    try:
        from django.core.management import execute_from_command_line
    except Exception:  # messaggio di aiuto se il package non si trova
        hint = (
            "\n[Hint] Verifica che esista la cartella 'blog_manager' (package) "
            "accanto a questo manage.py, con __init__.py e la directory 'settings/'.\n"
            "Oppure imposta DJANGO_SETTINGS_MODULE, per esempio:\n"
            "  export DJANGO_SETTINGS_MODULE=.settings.dev\n"
        )
        raise
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
