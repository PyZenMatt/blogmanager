from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Finché l'app non viene fisicamente spostata restiamo sul path legacy
    name = "blog"
    label = "blog"

    def ready(self):  # pragma: no cover - side effects di registrazione segnali
        # Import lazy dei signals (evita import anticipato durante il discover)
        from . import signals  # noqa: F401

