import hashlib
import re
from typing import Dict, Any, List, Optional
import yaml
from django.utils.text import slugify as dj_slugify
from .models import Category
from django.db.utils import DataError
import uuid
import logging

logger = logging.getLogger(__name__)


def build_jekyll_front_matter(post) -> Dict[str, Any]:
    # Minimale (espandere secondo il vostro schema)
    return {
        "title": getattr(post, "title", ""),
        "slug": getattr(post, "slug", ""),
        "date": getattr(post, "date", getattr(post, "published_at", None)),
        "categories": getattr(post, "categories", []) or [],
        "tags": getattr(post, "tags", []) or [],
        "status": getattr(post, "status", "draft"),
    }


def render_markdown_for_export(post) -> str:
    fm = build_jekyll_front_matter(post)
    # YAML deterministico: chiavi ordinate
    lines = ["---"]
    for k in sorted(fm.keys()):
        v = fm[k]
        if isinstance(v, (list, tuple)):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    # Compat: preferisci post.body; fallback a content_markdown se presente
    body_value = getattr(post, "body", None)
    if body_value is None:
        body_value = getattr(post, "content_markdown", "")  # per retro-compat
    body = (body_value or "").rstrip() + "\n"
    return "\n".join(lines) + "\n\n" + body


def content_hash(post) -> str:
    data = render_markdown_for_export(post).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


_FM_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", flags=re.S | re.M)


def extract_frontmatter(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    m = _FM_RE.search(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


_FILENAME_FALLBACK_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-(.+)$')


def slug_from_filename(filename: str, max_len: int = 75) -> str:
    """Extract slug candidate from a Jekyll-style filename anchoring the date prefix.

    Example: '2025-02-18-e-mc2-xyz.md' -> 'e-mc2-xyz'
    """
    if not filename:
        return ''
    base = filename.rsplit('/', 1)[-1]
    base = base.rsplit('.', 1)[0]
    m = _FILENAME_FALLBACK_RE.match(base)
    if m:
        candidate = m.group(1)
    else:
        candidate = base
    # Normalize
    cand = dj_slugify(candidate)[:max_len].strip('-') or candidate[:max_len]
    return cand


def create_categories_from_frontmatter(post, fields: Optional[List[str]] = None, hierarchy: str = "slash") -> List[Category]:
    """Create Category objects from a Post's front-matter and assign them to the post.

    Returns the list of Category instances created or found.
    """
    if fields is None:
        fields = ["categories", "cluster"]
    txt = getattr(post, "content", None) or ""
    fm = extract_frontmatter(txt)
    cats = []
    if fm:
        vals = []
        for fld in fields:
            if fld in fm and fm[fld] is not None:
                v = fm[fld]
                if isinstance(v, (list, tuple)) and v:
                    vals.extend([str(x).strip() for x in v if x])
                else:
                    vals.append(str(v).strip())
        if vals:
            if len(vals) == 1:
                cats = [vals[0]]
            else:
                cats = ["/".join(vals)]

    # fallback: legacy categories: line
    if not cats:
        m = re.search(r'(?mi)^categories:\s*(.+)$', txt)
        if m:
            cats = [s.strip() for s in re.split(r"[,;]\s*", m.group(1)) if s.strip()]

    if not cats:
        return []

    created_objs = []
    for raw in cats:
        if hierarchy == "slash":
            parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
        elif hierarchy == ">":
            parts = [p.strip() for p in re.split(r"\s*>\s*", raw) if p.strip()]
        else:
            parts = [raw.strip()]

        accum = []
        for i in range(len(parts)):
            accum.append(parts[i])
            name = "/".join(accum) if len(accum) > 1 else accum[0]

            # Build DB-safe slug: slugify, replace separators, truncate to field max_length and ensure uniqueness
            try:
                max_len = Category._meta.get_field('slug').max_length or 50
            except Exception:
                max_len = 50

            base = dj_slugify(name.replace("/", "-").replace(">", "-")) or 'category'
            base = base[:max_len].strip('-')
            candidate = base
            j = 2
            while Category.objects.filter(site=post.site, slug=candidate).exists():
                suffix = f"-{j}"
                cut = max_len - len(suffix)
                candidate = f"{base[:cut].rstrip('-')}{suffix}"
                j += 1

            defaults = {"name": name}
            try:
                obj, created = Category.objects.get_or_create(site=post.site, slug=candidate, defaults=defaults)
            except DataError:
                # fallback: short uuid-suffixed slug
                safe = (base[: max_len - 9].rstrip('-') or 'cat') + '-' + uuid.uuid4().hex[:8]
                safe = safe[:max_len]
                try:
                    obj, created = Category.objects.get_or_create(site=post.site, slug=safe, defaults=defaults)
                    logger.warning("create_categories_from_frontmatter: slug truncated/fallback used for name=%s site=%s", name, getattr(post.site, 'slug', None))
                except Exception:
                    logger.exception("Failed to create Category for name=%s site=%s", name, getattr(post.site, 'slug', None))
                    continue

            created_objs.append(obj)

    # assign unique categories to post
    if created_objs:
        unique = []
        seen = set()
        for o in created_objs:
            if o and o.pk and o.pk not in seen:
                unique.append(o)
                seen.add(o.pk)
        if unique:
            post.categories.add(*unique)

    return created_objs

