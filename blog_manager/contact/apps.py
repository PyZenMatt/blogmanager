from django.apps import AppConfig


class ContactConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Assicurati che il pacchetto sia esattamente "blog_manager.contact"
    name = "blog_manager.contact"
