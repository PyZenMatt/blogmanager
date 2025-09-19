import hashlib
import re
from typing import Dict, Any, List, Optional
import yaml
from django.utils.text import slugify
from .models import Category


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


def create_categories_from_frontmatter(post, fields: List[str] = None, hierarchy: str = "slash") -> List[Category]:
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
            slug = slugify(name.replace("/", "-").replace(">", "-"))
            defaults = {"name": name}
            obj, created = Category.objects.get_or_create(site=post.site, slug=slug, defaults=defaults)
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

