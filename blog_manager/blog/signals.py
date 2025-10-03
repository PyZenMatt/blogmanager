from django.db.models.signals import post_save
from django.dispatch import receiver
import re
import yaml
from .models import Post, Category
from django.utils.text import slugify as dj_slugify
from django.db.utils import DataError
import uuid
import hashlib

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
    
    This uses the new normalized category structure to avoid duplicates.
    Associates categories from front-matter to post.categories M2M relation for hierarchical export.
    This runs on every Post save and is idempotent.
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
        cats = ['uncategorized']
    if not subs:
        subs = [None]  # Use None instead of string for no subcluster

    site_id = getattr(instance.site, 'id', instance.site_id)
    
    # Collect unique (cluster, subcluster) tuples to create categories
    category_specs = set()
    
    for c in cats:
        cluster_name = c.strip()
        cluster_slug = dj_slugify(cluster_name) or 'uncategorized'
        
        # Add the cluster itself as a category
        category_specs.add((cluster_slug, cluster_name, None, None))
        
        # Add cluster/subcluster combinations
        for s in subs:
            if s and s.strip():
                subcluster_name = s.strip()
                subcluster_slug = dj_slugify(subcluster_name)
                full_name = f"{cluster_name}/{subcluster_name}"
                category_specs.add((cluster_slug, cluster_name, subcluster_slug, full_name))
    
    # Bulk create/get categories using the new normalized structure
    categories_to_associate = []
    
    for cluster_slug, cluster_name, subcluster_slug, full_name in category_specs:
        display_name = full_name if full_name else cluster_name
        
        # Create backwards-compatible slug for the slug field
        if subcluster_slug:
            compat_slug = f"{cluster_slug}-{subcluster_slug}"
        else:
            compat_slug = cluster_slug

        # Defensive: ensure compat_slug fits DB column limits (MySQL enforces VARCHAR length)
        # If too long, truncate and append a short hash to preserve uniqueness.
        MAX_COMPAT_SLUG = 200
        def _short_hash(s: str, length: int = 8) -> str:
            return hashlib.sha1(s.encode('utf-8')).hexdigest()[:length]

        if len(compat_slug) > MAX_COMPAT_SLUG:
            truncated = compat_slug[: (MAX_COMPAT_SLUG - 1 - 8)]  # leave room for '-' and hash
            compat_slug = f"{truncated}-{_short_hash(compat_slug)}"
        
        try:
            cat_obj, cat_created = Category.objects.get_or_create(
                site_id=site_id, 
                cluster_slug=cluster_slug,
                subcluster_slug=subcluster_slug,
                defaults={
                    'name': display_name,
                    'slug': compat_slug,  # Keep for backwards compatibility
                }
            )
            categories_to_associate.append(cat_obj)
            
        except Exception as e:
            # Log the error but don't break the save process
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create category {cluster_slug}/{subcluster_slug}: {e}")
    
    # Associate categories with post through M2M relation
    if categories_to_associate:
        try:
            # Get current categories to avoid unnecessary database hits
            current_category_ids = set(instance.categories.values_list('id', flat=True))
            new_category_ids = set(cat.id for cat in categories_to_associate)
            
            # Only add categories that aren't already associated
            categories_to_add = [cat for cat in categories_to_associate if cat.id not in current_category_ids]
            
            if categories_to_add:
                instance.categories.add(*categories_to_add)
        except Exception:
            # Best-effort: if M2M association fails, don't break the save process
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
