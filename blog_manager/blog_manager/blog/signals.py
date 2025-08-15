from contextvars import ContextVar
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
## Do not import models at module level to avoid AppRegistryNotReady

# flag per evitare ricorsioni da salvataggi interni
_SKIP_EXPORT = ContextVar("skip_export", default=False)
# campi meta che non devono triggerare un nuovo export
_EXPORT_META_FIELDS = {"last_export_path", "exported_hash", "last_exported_at"}

def _compute_export_path(post) -> str | None:
    if not post.published_at or not post.slug:
        return None
    posts_dir = getattr(post.site, "posts_dir", "_posts")
    filename = f"{post.published_at.strftime('%Y-%m-%d')}-{post.slug}.md"
    return f"{posts_dir}/{filename}"

def _do_export_and_update(post_id: int) -> None:
    from .models import Post as PostModel
    from .exporter import render_markdown

    p = PostModel.objects.select_related("site").get(pk=post_id)
    changed, content_hash, file_path = render_markdown(p, p.site)
    if not changed:
        return
    update_kwargs = {
        "last_export_path": file_path,
        "exported_hash": content_hash,
    }
    if hasattr(PostModel, "last_exported_at"):
        update_kwargs["last_exported_at"] = timezone.now()
    # aggiorna i meta senza triggerare altri segnali
    PostModel.objects.filter(pk=p.pk).update(**update_kwargs)

from django.apps import apps


@receiver(post_save, sender=None)
def trigger_export_on_publish(sender, instance, created, update_fields=None, **kwargs):
    # Dynamically get Post model using the app label (not the full module path).
    # AppConfig.name can be "blog_manager.blog" but the app label is usually "blog".
    Post = apps.get_model("blog", "Post")
    if sender != Post:
        return
    # evita loop da salvataggi interni
    if _SKIP_EXPORT.get():
        return
    # feature flag globale (es. in dev) per disattivare export automatico
    if not getattr(settings, "EXPORT_ENABLED", True):
        return
    # se vengono modificati solo i meta, non esportare nuovamente
    if update_fields and set(update_fields).issubset(_EXPORT_META_FIELDS):
        return
    # esporta solo se lo stato è published
    if getattr(instance, "status", None) != "published":
        return
    # avvia l’export dopo il commit
    transaction.on_commit(lambda: _do_export_and_update(instance.pk))
