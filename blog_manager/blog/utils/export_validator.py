import re
from typing import List, Tuple
from blog.models import Post


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
        
        # Support subdirectories within _posts/: 
        # Format 1: _posts/.../YYYY-MM-DD-slug.md (Jekyll standard)
        # Format 2: _posts/.../DD-MM-YYYY-slug.md (alternative format)
        # Format 3: _posts/.../other-slug-format.md (non-date prefixed)
        
        # First try Jekyll standard format: YYYY-MM-DD-slug.md
        m = re.match(r"^_posts/(?:.+/)?(\d{4}-\d{2}-\d{2})-(.+)\.md$", rf)
        if m:
            # Jekyll format: compare with the slug part after date
            fname_slug = m.group(2)
            if fname_slug != p.slug:
                bad.append((p.pk, p.slug, rf, f"slug_mismatch:{fname_slug}"))
            continue
            
        # Then try alternative date format or other formats
        m = re.match(r"^_posts/(?:.+/)?(.+)\.md$", rf)
        if m:
            # Extract the full filename part (could be DD-MM-YYYY-slug or just slug)
            full_filename_part = m.group(1)
            
            # If it doesn't match the post slug, it's a mismatch
            # But allow some flexibility for date-prefixed non-standard formats
            if full_filename_part != p.slug:
                # Check if it might be an alternative date format like DD-MM-YYYY-slug
                alt_date_match = re.match(r"^(\d{2}-\d{2}-\d{4})-(.+)$", full_filename_part)
                if alt_date_match:
                    # For alternative date format, the slug should match the part after the date
                    # OR the full filename part (to handle cases where slug includes the date)
                    alt_slug = alt_date_match.group(2)
                    if p.slug != alt_slug and p.slug != full_filename_part:
                        bad.append((p.pk, p.slug, rf, f"slug_mismatch:{alt_slug}"))
                else:
                    # Non-date format, should match exactly
                    bad.append((p.pk, p.slug, rf, f"slug_mismatch:{full_filename_part}"))
        else:
            bad.append((p.pk, p.slug, rf, "invalid_format"))

    return bad
