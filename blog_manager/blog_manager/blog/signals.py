from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
from .models import Post
from .exporter import export_post_to_jekyll
from django.utils import timezone
from .utils import content_hash
LOCK_TTL = 30  # secondi

@receiver(post_save, sender=Post)
def export_on_publish(sender, instance: Post, created, **kwargs):
    # Evita export su creazione draft e in fase adding

    if instance.status != "published" or instance._state.adding:
        return

    lock_key = f"export_lock:post:{instance.pk}"
    if not cache.add(lock_key, "1", LOCK_TTL):
        return
    def _do_export():
        try:
            # Salta se contenuto invariato rispetto all'ultimo export
            hx = content_hash(instance)
            if hx and hx == (instance.exported_hash or ""):
                return
            new_hx = export_post_to_jekyll(instance)
            # Update senza segnali (no loop)
            Post.objects.filter(pk=instance.pk).update(
                exported_hash=new_hx,
                last_exported_at=timezone.now(),
            )
        finally:
            cache.delete(lock_key)

    if getattr(settings, "EXPORT_ENABLED", True):
        transaction.on_commit(_do_export)
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
