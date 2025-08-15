from django.apps import AppConfig
from . import signals  # noqa: F401


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Assicurati che il pacchetto sia esattamente "blog_manager.blog"
    name = "blog_manager.blog"

    def ready(self):
        # importa e registra i segnali
        from . import signals  # noqa: F401

