import re
from typing import List, Tuple
from django.utils.text import slugify
from blog.models import Post


def _normalize_slug_for_comparison(slug: str) -> str:
    """Normalize slug for comparison by applying Django's slugify to handle special characters."""
    if not slug:
        return ""
    # Apply Django's slugify to normalize special characters like apostrophes
    return slugify(slug)


def validate_repo_filenames(site_slug: str | None = None) -> List[Tuple[int, str, str, str]]:
    """Validate Post.repo_filename entries.

    Returns a list of tuples (post_id, slug, repo_filename, reason). Empty list means valid.
    """
    qs = Post.objects.all()
    if site_slug:
        qs = qs.filter(site__slug=site_slug)

    bad = []
    for p in qs:
        rf = p.repo_filename or ""
        if not rf:
            bad.append((p.pk, p.slug, rf, "missing"))
            continue
        
        # Jekyll standard format: _posts/.../YYYY-MM-DD-slug.md or _posts/.../YYYY-M-D-slug.md
        # Support subdirectories within _posts and flexible date format (1 or 2 digits for month/day)
        m = re.match(r"^_posts/(?:.+/)?(\d{4}-\d{1,2}-\d{1,2})-(.+)\.md$", rf)
        if not m:
            # Check if it's using incorrect DD-MM-YYYY format (should be flagged as invalid)
            alt_format_check = re.match(r"^_posts/(?:.+/)?(\d{1,2}-\d{1,2}-\d{4})-(.+)\.md$", rf)
            if alt_format_check:
                bad.append((p.pk, p.slug, rf, "invalid_date_format_use_YYYY-MM-DD"))
            else:
                bad.append((p.pk, p.slug, rf, "invalid_format"))
            continue
            
        # Valid Jekyll format: compare slug with filename slug part
        fname_slug = m.group(2)
        
        # Normalize both slugs for comparison to handle special characters
        normalized_post_slug = _normalize_slug_for_comparison(p.slug)
        normalized_fname_slug = _normalize_slug_for_comparison(fname_slug)
        
        if normalized_fname_slug != normalized_post_slug:
            bad.append((p.pk, p.slug, rf, f"slug_mismatch:{fname_slug}"))

    return bad
