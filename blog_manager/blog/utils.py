import hashlib
from typing import Dict, Any

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
    """
    Le funzioni content_hash, render_markdown_for_export e build_jekyll_front_matter sono ora in __init__.py
    Importale da blog_manager.blog.utils
    """
