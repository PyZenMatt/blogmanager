"""
Exporter module for rendering Markdown with Jekyll-compatible front matter.
Also provides helpers to compute canonical URL and post file path.
"""

from datetime import datetime
from typing import Optional, Tuple

import yaml

from blog.utils.seo import slugify_title


def _date_parts(
    dt: Optional[datetime],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if dt is None:
        return None, None, None
    return dt.year, dt.month, dt.day


def build_post_relpath(post, site) -> str:
    """
    Build the Jekyll post path: _posts/YYYY-MM-DD-slug.md using site's posts_dir.
    """
    y, m, d = _date_parts(getattr(post, "published_at", None))
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    posts_dir = (getattr(site, "posts_dir", None) or "_posts").strip("/")
    if not (y and m and d and slug):
        # Fallback for drafts: place under _drafts/slug.md
        return f"_drafts/{slug or 'untitled'}.md"
    return f"{posts_dir}/{y:04d}-{m:02d}-{d:02d}-{slug}.md"


def compute_canonical_url(post, site) -> str | None:
    """
    Compute canonical URL if missing, using site's base_url and Jekyll permalinks pattern.
    Default pattern: /YYYY/MM/DD/slug.html
    """
    if getattr(post, "canonical_url", None):
        return post.canonical_url
    base_url = getattr(site, "base_url", "") or ""
    y, m, d = _date_parts(getattr(post, "published_at", None))
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    if not (base_url and y and m and d and slug):
        return None
    base_url = base_url.rstrip("/")
    return f"{base_url}/{y:04d}/{m:02d}/{d:02d}/{slug}.html"


def render_markdown(post, site):
    """
    Renders a Post object to Markdown with Jekyll-compatible YAML front matter.
    Args:
        post (Post): The post instance.
        site (dict): Site-wide settings (optional fields).
    Returns:
        str: Markdown string with YAML front matter.
    """
    # Prepare front matter fields
    front_matter = {
        "title": post.title,
        "date": (
            post.published_at.isoformat()
            if hasattr(post, "published_at") and post.published_at
            else None
        ),
        "slug": slugify_title(post.title),
        "description": getattr(post, "description", None),
        "tags": (
            [t.name for t in post.tags.all()]
            if hasattr(post.tags, "all")
            else post.tags
        ),
        "categories": (
            [c.name for c in post.categories.all()]
            if hasattr(post.categories, "all")
            else post.categories
        ),
        # Usa sempre URL esterni per le immagini
        "image": getattr(post, "image", None)
        or getattr(post, "og_image_url", None)
        or getattr(post, "background", None),
        "canonical": getattr(post, "canonical_url", None)
        or compute_canonical_url(post, site),
        "meta_title": getattr(post, "meta_title", None),
        "meta_description": getattr(post, "meta_description", None),
        "meta_keywords": getattr(post, "meta_keywords", None),
        "og_title": getattr(post, "og_title", None),
        "og_description": getattr(post, "og_description", None),
        "og_image": getattr(post, "og_image", None)
        or getattr(post, "og_image_url", None),
        "noindex": getattr(post, "noindex", False),
    }
    # Remove None values
    front_matter = {k: v for k, v in front_matter.items() if v is not None}
    yaml_front = yaml.dump(front_matter, allow_unicode=True, sort_keys=False)

    # Compose markdown
    body = getattr(post, "body", None)
    if body is None:
        body = getattr(post, "content", "")
    # Se in futuro si vuole gestire la strategia commit, qui si può aggiungere la logica
    markdown = f"---\n{yaml_front}---\n\n{body}\n"
    return markdown
