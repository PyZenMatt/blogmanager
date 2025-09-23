from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import yaml
from .models import Post, Category
from django.utils.text import slugify as dj_slugify
from django.db.utils import DataError
import uuid

fm_re = re.compile(r'^\s*---\s*\n([\s\S]*?)\n---\s*\n', re.M)


def _extract_values_from_fm(fm_text):
    try:
        parsed = yaml.safe_load(fm_text) or {}
    except Exception:
        parsed = {}
        for line in (fm_text or '').splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                parsed[k.strip()] = v.strip()
    category_vals = []
    sub_vals = []
    if isinstance(parsed, dict):
        c = parsed.get('categories') or parsed.get('category')
        if c:
            if isinstance(c, list):
                category_vals.extend([str(x).strip() for x in c if x])
            else:
                category_vals.append(str(c).strip())
        s = parsed.get('subcluster') or parsed.get('subclusters')
        if s:
            if isinstance(s, list):
                sub_vals.extend([str(x).strip() for x in s if x])
            else:
                sub_vals.append(str(s).strip())
    return category_vals, sub_vals


@receiver(post_save, sender=Post)
def ensure_categories_from_post(sender, instance, created, **kwargs):
    """Ensure Category rows exist for clusters and cluster/subcluster pairs found in a Post's front-matter.

    This runs on every Post save. It's idempotent and uses get_or_create.
    """
    raw = instance.content or getattr(instance, 'body', '') or ''
    m = fm_re.search(raw)
    if not m:
        return
    fm_text = m.group(1)
    cats, subs = _extract_values_from_fm(fm_text)
    # Fallback: if no categories found, inspect instance.categories M2M (best-effort)
    if not cats:
        try:
            for cat in instance.categories.all():
                name = cat.name or ''
                if '/' in name:
                    cats.append(name.split('/')[0].strip())
                else:
                    cats.append(name.strip())
        except Exception:
            pass

    if not cats and not subs:
        return

    if not cats:
        cats = ['(no-category)']
    if not subs:
        subs = ['(no-subcluster)']

    site_id = getattr(instance.site, 'id', instance.site_id)

    for c in cats:
        name_c = c
        # Build a DB-safe slug: slugify, truncate to model field max_length and make unique per site
        try:
            max_len = Category._meta.get_field('slug').max_length or 50
        except Exception:
            max_len = 50

        base_slug = dj_slugify(name_c) or 'category'
        base_slug = base_slug[:max_len].strip('-')
        candidate = base_slug
        i = 2
        while Category.objects.filter(site_id=site_id, slug=candidate).exists():
            suffix = f"-{i}"
            cut = max_len - len(suffix)
            candidate = f"{base_slug[:cut].rstrip('-')}{suffix}"
            i += 1

        try:
            Category.objects.get_or_create(site_id=site_id, slug=candidate, defaults={'name': name_c})
        except DataError:
            # As a last-resort, create a much shorter slug with uuid suffix
            safe = (base_slug[: max_len - 9].rstrip('-') or 'cat') + '-' + uuid.uuid4().hex[:8]
            safe = safe[:max_len]
            try:
                Category.objects.get_or_create(site_id=site_id, slug=safe, defaults={'name': name_c})
            except Exception:
                # Give up silently — this is best-effort during massive imports
                pass
        for su in subs:
            name = f"{name_c}/{su}" if su and su != '(no-subcluster)' else name_c
            # same process for combined category/subcluster name
            try:
                max_len = Category._meta.get_field('slug').max_length or 50
            except Exception:
                max_len = 50

            base = dj_slugify(name) or 'category'
            base = base[:max_len].strip('-')
            cand = base
            j = 2
            while Category.objects.filter(site_id=site_id, slug=cand).exists():
                suffix = f"-{j}"
                cut = max_len - len(suffix)
                cand = f"{base[:cut].rstrip('-')}{suffix}"
                j += 1

            try:
                Category.objects.get_or_create(site_id=site_id, slug=cand, defaults={'name': name})
            except DataError:
                safe2 = (base[: max_len - 9].rstrip('-') or 'cat') + '-' + uuid.uuid4().hex[:8]
                safe2 = safe2[:max_len]
                try:
                    Category.objects.get_or_create(site_id=site_id, slug=safe2, defaults={'name': name})
                except Exception:
                    pass
from contextvars import ContextVar
from contextlib import suppress
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
## Do not import models at module level to avoid AppRegistryNotReady

# flag per evitare ricorsioni da salvataggi interni
_SKIP_EXPORT = ContextVar("skip_export", default=False)
logger = logging.getLogger("blog.exporter")
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
    # Caso: file già identico su disco (changed=False) ma exported_hash non settato => backfill hash
    if not changed and (getattr(p, "exported_hash", None) != content_hash):
        update_kwargs = {"exported_hash": content_hash}
        if file_path:
            update_kwargs["last_export_path"] = file_path
        if hasattr(PostModel, "last_exported_at"):
            update_kwargs["last_exported_at"] = timezone.now()
        PostModel.objects.filter(pk=p.pk).update(**update_kwargs)
        return
    if not changed:
        return
    update_kwargs = {"last_export_path": file_path, "exported_hash": content_hash}
    if hasattr(PostModel, "last_exported_at"):
        update_kwargs["last_exported_at"] = timezone.now()
    PostModel.objects.filter(pk=p.pk).update(**update_kwargs)

from django.apps import apps


@receiver(post_save, sender=None)
def trigger_export_on_publish(sender, instance, created, update_fields=None, **kwargs):
    # Dynamically get Post model using the app label (not the full module path).
    # AppConfig.name can be "blog" but the app label is usually "blog".
    Post = apps.get_model("blog", "Post")
    if sender != Post:
        return
    # evita loop da salvataggi interni
    if _SKIP_EXPORT.get():
        logger.debug("[signals] Skip export: _SKIP_EXPORT flag attivo per post id=%s", getattr(instance, 'pk', None))
        return
    # feature flag globale (es. in dev) per disattivare export automatico
    if not getattr(settings, "EXPORT_ENABLED", True):
        logger.debug("[signals] Export disabilitato da settings.EXPORT_ENABLED=False")
        return
    # se vengono modificati solo i meta, non esportare nuovamente
    if update_fields and set(update_fields).issubset(_EXPORT_META_FIELDS):
        logger.debug("[signals] Solo meta fields aggiornati (%s) => no export", update_fields)
        return
    # esporta solo se lo stato è published
    if getattr(instance, "status", None) != "published":
        logger.debug("[signals] Stato non published (status=%s) => no export", getattr(instance, 'status', None))
        return
    logger.debug("[signals] Pianifico export post id=%s slug=%s", getattr(instance, 'pk', None), getattr(instance, 'slug', None))
    # Chiamata sincrona: se spinge fallisce, non rompe il salvataggio del post.
    with suppress(Exception):
        from .exporter import export_post
        export_post(instance)
