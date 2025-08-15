from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
from .models import Post
from .exporter import export_post_to_jekyll
LOCK_TTL = 30  # secondi

@receiver(post_save, sender=Post)
def export_on_publish(sender, instance: Post, created, **kwargs):
    # Evita export su creazione draft e in fase adding
    if instance.status != "published" or instance._state.adding:
        return

    lock_key = f"export_lock:post:{instance.pk}"
    if not cache.add(lock_key, "1", LOCK_TTL):
        # Un export è già in corso per questo post
        return
    def _do_export():
        try:
            # Importante: non chiamare instance.save() qui.
            export_post_to_jekyll(instance)
        finally:
            cache.delete(lock_key)

    # Esegui dopo il commit della transazione, con lo stato consistente
    transaction.on_commit(_do_export)
from django.db.models.signals import post_save
from django.dispatch import receiver

from blog_manager.blog.models import Post
from blog_manager.blog.services.publish import publish_post


@receiver(post_save, sender=Post)
def auto_publish_on_status(sender, instance: Post, created, **kwargs):
    # Fire only when moving to published
    if instance.status == "published" and instance.published_at:
        try:
            publish_post(instance)
        except Exception:
            # Keep silent here; admin/user can use Re-publish
            pass
