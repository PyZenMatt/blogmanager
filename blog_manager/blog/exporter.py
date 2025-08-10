"""
Exporter module for rendering Markdown with Jekyll-compatible front matter.
"""
import yaml
from blog.models import Post
from utils.seo import slugify


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
        'title': post.title,
        'date': post.published_at.isoformat() if hasattr(post, 'published_at') and post.published_at else None,
        'slug': slugify(post.title),
        'description': getattr(post, 'description', None),
        'tags': [t.name for t in getattr(post, 'tags', [])],
        'categories': [c.name for c in getattr(post, 'categories', [])],
        # Usa sempre URL esterni per le immagini
        'image': getattr(post, 'image', None),
        'canonical': getattr(post, 'canonical_url', None),
        'meta_title': getattr(post, 'meta_title', None),
        'meta_description': getattr(post, 'meta_description', None),
        'meta_keywords': getattr(post, 'meta_keywords', None),
        'og_title': getattr(post, 'og_title', None),
        'og_description': getattr(post, 'og_description', None),
        'og_image': getattr(post, 'og_image', None),
        'noindex': getattr(post, 'noindex', False),
    }
    # Remove None values
    front_matter = {k: v for k, v in front_matter.items() if v is not None}
    yaml_front = yaml.dump(front_matter, allow_unicode=True, sort_keys=False)

    # Compose markdown
    body = getattr(post, 'body', '')
    # Se in futuro si vuole gestire la strategia commit, qui si può aggiungere la logica
    markdown = f"---\n{yaml_front}---\n\n{body}\n"
    return markdown
