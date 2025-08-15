from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Assicurati che il pacchetto sia esattamente "blog_manager.blog"
    name = "blog_manager.blog"

    def ready(self):
        # Register signals
        from . import signals  # noqa: F401
