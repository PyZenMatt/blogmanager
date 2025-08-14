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
