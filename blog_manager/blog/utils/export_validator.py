import re
from typing import List, Tuple
from blog.models import Post


def validate_repo_filenames(site_slug: str = None) -> List[Tuple[int, str, str, str]]:
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
        m = re.match(r"^_posts/(\d{4}-\d{2}-\d{2})-(.+)\.md$", rf)
        if not m:
            bad.append((p.pk, p.slug, rf, "invalid_format"))
            continue
        fname_slug = m.group(2)
        if fname_slug != p.slug:
            bad.append((p.pk, p.slug, rf, f"slug_mismatch:{fname_slug}"))

    return bad
