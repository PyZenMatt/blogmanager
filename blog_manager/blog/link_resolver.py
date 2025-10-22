import re
import html
import logging
from typing import Tuple, Optional
from django.conf import settings
from django.apps import apps

logger = logging.getLogger(__name__)

# Regex to capture shortcodes: [[type:target(#anchor)?|Text]]
SHORTCODE_RE = re.compile(r"\[\[\s*(post|path|ext)\s*:\s*([^\]#|]+?)(#[^\]|]+)?(?:\|([^\]]+))?\s*\]\]")


def _slugify_header(header: str) -> str:
    # Simple slugification to match Jekyll header anchors: lowercase, spaces -> '-', remove punctuation
    import re
    s = header.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


class LinkResolutionError(Exception):
    pass


class LinkResolver:
    @classmethod
    def parse_shortcodes(cls, body: str):
        # Normalize HTML entities
        body = html.unescape(body or "")
        for m in SHORTCODE_RE.finditer(body):
            typ = m.group(1)
            target = m.group(2).strip()
            anchor = m.group(3)[1:] if m.group(3) else None
            text = m.group(4) or None
            yield (m.group(0), typ, target, anchor, text)

    @classmethod
    def resolve(cls, body: str, current_site) -> Tuple[str, list]:
        """Resolve shortcodes in `body` for `current_site`.

        Returns tuple (resolved_body, errors)
        """
        errors = []
        out = body or ""

        for raw, typ, target, anchor, text in cls.parse_shortcodes(body):
            try:
                replacement = cls._resolve_one(typ, target, anchor, text, current_site)
            except LinkResolutionError as e:
                errors.append(str(e))
                replacement = raw  # leave untouched
            out = out.replace(raw, replacement)

        return out, errors

    @classmethod
    def _resolve_one(cls, typ, target, anchor, text, current_site) -> str:
        # post: target is slug (may include #anchor part already stripped)
        if typ == "ext":
            # text provided or not: produce markdown link [text](url)
            url = target.strip()
            link_text = text or url
            return f"[{link_text}]({url})"

        if typ == "path":
            # target is a path; emit relative link via Liquid as requested
            path = target.strip()
            link_text = text or path
            suffix = f"#{anchor}" if anchor else ""
            # using Liquid relative_url wrapper
            return f"[{link_text}]({{ '{{' }} '{path}{suffix}' | relative_url {{ '}}' }})"

        if typ == "post":
            slug = target.strip()
            # find Post with this slug in DB
            Post = apps.get_model("blog", "Post")
            qs = Post.objects.filter(slug=slug)
            if not qs.exists():
                raise LinkResolutionError(f"Unresolved post slug: {slug}")
            # Prefer post in current site if present
            post_obj = None
            same_site_qs = qs.filter(site=current_site)
            if same_site_qs.exists():
                if same_site_qs.count() > 1:
                    raise LinkResolutionError(f"Ambiguous slug '{slug}' in current site")
                post_obj = same_site_qs.first()
            else:
                if qs.count() > 1:
                    raise LinkResolutionError(f"Ambiguous slug '{slug}' across sites; cannot resolve")
                post_obj = qs.first()

            # build permalink path using exporter helper (returns _posts/... path).
            # Lazy import to avoid importing exporter at module import time.
            try:
                from .exporter import build_post_relpath
            except Exception:
                # fallback to app-level import (when called as blog.link_resolver shim)
                from blog_manager.blog.exporter import build_post_relpath

            # Spec requires permalink: /{cluster}/{subcluster?}/{slug}/
            rel = build_post_relpath(post_obj, post_obj.site)
            # build_post_relpath returns path like '_posts/cluster/subcluster/YYYY-MM-DD-slug.md'
            # Convert to permalink: remove leading _posts and date/extension
            parts = rel.split('/')
            # remove '_posts'
            if parts and parts[0] == '_posts':
                parts = parts[1:]
            # remove final filename date prefix and extension
            filename = parts.pop() if parts else ''
            # filename looks like YYYY-MM-DD-<slug>.md -> strip date and .md
            import re
            m = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$", filename)
            if not m:
                raise LinkResolutionError(f"Unexpected exported filename format for post slug '{slug}': {filename}")
            post_slug = m.group(1)
            permalink_parts = ["/"] + parts + [post_slug, ""]
            permalink = "/".join([p.strip('/') for p in permalink_parts if p is not None])
            if not permalink.startswith('/'):
                permalink = '/' + permalink
            if not permalink.endswith('/'):
                permalink = permalink + '/'

            # decide cross-site policy
            if post_obj.site_id == current_site.id:
                # relative via Liquid
                url_expr = f"{{ '{{' }} '{permalink}' | relative_url {{ '}}' }}"
            else:
                policy = getattr(settings, 'CROSS_SITE_POLICY', 'absolute')
                domain = getattr(post_obj.site, 'domain', None) or ''
                if policy == 'absolute':
                    if not domain:
                        raise LinkResolutionError(f"Target site for slug '{slug}' has no domain configured")
                    url_expr = f"https://{domain}{permalink}"
                else:
                    raise LinkResolutionError(f"Cross-site link to slug '{slug}' blocked by CROSS_SITE_POLICY")

            if anchor:
                anchor_slug = _slugify_header(anchor)
                url_final = f"{url_expr}#{anchor_slug}"
            else:
                url_final = url_expr

            link_text = text or post_obj.title or post_obj.slug
            return f"[{link_text}]({url_final})"

        raise LinkResolutionError(f"Unknown shortcode type: {typ}")
