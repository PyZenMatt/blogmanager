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

    # Assicura che la project root sia nel PYTHONPATH
    # (necessario quando lo script è invocato da directory diverse)
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    # Default: settings di sviluppo, sovrascrivibile da env
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        os.getenv("DJANGO_SETTINGS_MODULE", "blog_manager.settings.prod"),
    )

    try:
        from django.core.management import execute_from_command_line
    except Exception:  # messaggio di aiuto se il package non si trova
        hint = (
            "\n[Hint] Verifica che esista la cartella 'blog_manager' (package) "
            "accanto a questo manage.py, con __init__.py e la directory 'settings/'.\n"
            "Oppure imposta DJANGO_SETTINGS_MODULE, per esempio:\n"
            "  export DJANGO_SETTINGS_MODULE=blog_manager.settings.dev\n"
        )
        raise
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
