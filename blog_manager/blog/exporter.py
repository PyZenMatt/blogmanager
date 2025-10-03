import os
import hashlib
import subprocess
import shlex
from contextlib import suppress
from django.utils import timezone
from django.conf import settings
import logging
import shutil
import pwd
from blog.utils.export_validator import validate_repo_filenames

logger = logging.getLogger(__name__)

# --- Config env (senza nuove dipendenze) ---
GIT_BRANCH = os.environ.get("BLOG_EXPORT_GIT_BRANCH", "main")
GIT_USERNAME = os.environ.get("GIT_USERNAME", "x-access-token")
GIT_TOKEN = os.environ.get("GIT_TOKEN")  # PAT GitHub con repo scope

MASK = "****"

# ---- Backwards-compatible helpers expected by blog.services.publish ----
import re


def slugify_title(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")

# Use Django's slugify when available for consistent slugs
try:
    from django.utils.text import slugify as django_slugify
    def dj_slugify(v):
        return str(django_slugify(v or ""))
except Exception:
    def dj_slugify(v):
        return re.sub(r"[^a-z0-9]+", "-", str(v or "").strip().lower()).strip("-")


# regex to detect YAML front-matter at start of body
FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


class FrontMatterValidationError(Exception):
    """Raised when front-matter validation fails and should block export."""
    pass


def _validate_content_encoding(content: str) -> None:
    """Validate content meets encoding and line ending requirements."""
    if not content:
        return
    
    # Check for BOM
    if content.startswith('\ufeff'):
        raise FrontMatterValidationError("Content contains UTF-8 BOM which is not allowed")
    
    # Check for CRLF line endings in front-matter
    if '\r\n' in content[:1000]:  # Check first 1000 chars where FM would be
        raise FrontMatterValidationError("Content contains CRLF line endings; only LF is allowed")


def _extract_frontmatter_from_body(body: str) -> dict:
    """Return parsed front-matter dict if present at start of body, else {}.
    
    Raises FrontMatterValidationError if content fails validation.
    """
    import yaml
    if not body:
        return {}
    
    # Validate encoding and line endings
    _validate_content_encoding(body)
    
    m = FRONTMATTER_RE.match(body)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise FrontMatterValidationError(f"Invalid YAML in front-matter: {e}")
    except Exception as e:
        raise FrontMatterValidationError(f"Failed to parse front-matter: {e}")


def _strip_trivial_leading_frontmatter(body: str) -> str:
    """Strip leading front-matter if it's trivial (only title/slug) to avoid duplicated small FM blocks.

    If front-matter contains only keys in {'title', 'slug'} it will be removed. Otherwise body is returned unchanged.
    """
    if not body:
        return body
    m = FRONTMATTER_RE.match(body)
    if not m:
        return body
    try:
        import yaml
        data = yaml.safe_load(m.group(1)) or {}
    except Exception:
        return body
    if isinstance(data, dict) and set(data.keys()) <= {"title", "slug"}:
        return body[m.end():]
    return body


def _strip_leading_frontmatter(body: str) -> str:
    """Always strip a leading front-matter block from the body if present.

    We will merge any meaningful front-matter found in the body into the
    exported front-matter instead of leaving two separate blocks.
    """
    if not body:
        return body
    m = FRONTMATTER_RE.match(body)
    if not m:
        return body
    return body[m.end():]


def _select_date(post):
    for attr in ("published_at", "updated_at", "created_at"):
        val = getattr(post, attr, None)
        if val:
            return val
    return timezone.now()


def _validate_frontmatter_taxonomy(post, fm_body=None):
    """Validate and extract categories and subcluster from front-matter.
    
    Returns (cluster, subcluster, audit_msgs)
    Raises FrontMatterValidationError if validation fails.
    """
    audit = []
    
    if not fm_body or not isinstance(fm_body, dict):
        raise FrontMatterValidationError("No valid front-matter found - front-matter is required for export")
    
    # categories must be present and contain exactly one cluster
    fm_cats = fm_body.get('categories')
    if not fm_cats:
        raise FrontMatterValidationError("Missing required 'categories' field in front-matter")
    
    if isinstance(fm_cats, str):
        fm_cats = [fm_cats]
    elif not isinstance(fm_cats, (list, tuple)):
        raise FrontMatterValidationError(f"'categories' must be a list or string, got {type(fm_cats).__name__}")
    
    if len(fm_cats) != 1:
        raise FrontMatterValidationError(f"'categories' must contain exactly one cluster, got {len(fm_cats)} items")
    
    cluster_raw = fm_cats[0]
    if not cluster_raw or not str(cluster_raw).strip():
        raise FrontMatterValidationError("Empty cluster in 'categories' field")
    
    cluster = str(cluster_raw).strip()
    
    # Reject legacy cluster/subcluster format
    if '/' in cluster:
        raise FrontMatterValidationError(f"Invalid cluster '{cluster}' - clusters cannot contain '/' (use separate 'subcluster' field)")
    
    # Validate cluster slug format
    cluster_slug = dj_slugify(cluster)
    if not cluster_slug or cluster_slug != cluster:
        raise FrontMatterValidationError(f"Invalid cluster slug '{cluster}' - must be a valid slug (got '{cluster_slug}')")
    
    # Validate subcluster if present
    subcluster = None
    fm_sub = fm_body.get('subcluster')
    if fm_sub:
        if isinstance(fm_sub, (list, tuple)):
            if len(fm_sub) > 1:
                raise FrontMatterValidationError(f"'subcluster' field contains multiple values - only one allowed")
            subcluster_raw = fm_sub[0] if fm_sub else None
        else:
            subcluster_raw = fm_sub
        
        if subcluster_raw:
            subcluster = str(subcluster_raw).strip()
            if '/' in subcluster:
                raise FrontMatterValidationError(f"Invalid subcluster '{subcluster}' - cannot contain '/'")
            
            subcluster_slug = dj_slugify(subcluster)
            if not subcluster_slug or subcluster_slug != subcluster:
                raise FrontMatterValidationError(f"Invalid subcluster slug '{subcluster}' - must be a valid slug (got '{subcluster_slug}')")
            
            subcluster = subcluster_slug
    
    # TODO: Add taxonomy validation against known clusters/subclusters
    # For now, we accept any valid slug format
    
    audit.append(f"Validated FM taxonomy: cluster='{cluster}', subcluster='{subcluster or 'None'}'")        
    return (cluster, subcluster, audit)


def _front_matter(post, site):
    import yaml
    # prefer title from front-matter if present in the body
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    fm_body = _extract_frontmatter_from_body(body)

    # Start with server-controlled baseline. Intentionally do NOT include the
    # DB `post.title` here: we will export the title only when the author
    # explicitly provided it in the post body front-matter. This avoids
    # injecting the DB title into files created/updated on the repo side.
    data = {
        "layout": "post",
        # omit title unless present in body front-matter
        # omit slug from exported front-matter: filename controls the slug
        "date": _select_date(post).strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        cluster, detected_subcluster, audit_msgs = _validate_frontmatter_taxonomy(post, fm_body)
        
        # Log validation results
        for msg in audit_msgs:
            logger.info("[export][frontmatter] validation: %s", msg)
        
        # Set canonical categories format: single cluster only
        data["categories"] = [cluster]
        
        # Only include 'subcluster' key when present
        if detected_subcluster:
            data['subcluster'] = detected_subcluster
            
        logger.info("[export][frontmatter] post_id=%s cluster='%s' subcluster='%s'", 
                   getattr(post, 'id', None), cluster, detected_subcluster or 'None')
                   
    except FrontMatterValidationError as e:
        logger.error("[export][validator] Front-matter validation failed for post id=%s: %s", 
                    getattr(post, 'id', None), str(e))
        raise  # Re-raise to block export completely

    # Only include canonical URL if it's provided and non-empty
    canonical = getattr(post, "canonical_url", "") or ""
    if canonical and canonical.strip():
        data["canonical"] = canonical.strip()

    # Only include description if it's provided and non-empty
    description = getattr(post, "description", "") or ""
    if description and description.strip():
        data["description"] = description.strip()

    # Merge any extra keys from the body's front-matter into the exported
    # front-matter so we produce a single authoritative YAML block. We keep
    # server-controlled fields (date, categories) authoritative by setting
    # them after the merge.
    if isinstance(fm_body, dict):
        # start from fm_body to preserve arbitrary custom keys the author may have set
        merged = dict(fm_body)
        # ensure we don't export slug (filename controls slug)
        merged.pop("slug", None)
        # do NOT inject DB title: only keep title if author provided it in fm_body
        if "title" in merged and not merged.get("title"):
            # empty/falsey title provided in front-matter -> remove it
            merged.pop("title", None)
        
        # Clean up empty values from front-matter body as well
        for key in ["canonical", "description", "tags"]:
            if key in merged:
                value = merged[key]
                if not value or (isinstance(value, (list, tuple)) and len(value) == 0) or (isinstance(value, str) and not value.strip()):
                    merged.pop(key, None)

        # now overlay server-derived authoritative fields. Date and layout are
        # always authoritative; categories are also authoritative when present.
        # For other fields like canonical/description we treat server values as
        # fallback only: if the user provided them in front-matter we keep user
        # values (user wins).
        merged["layout"] = data["layout"]
        merged["date"] = data["date"]
        if "categories" in data:
            merged["categories"] = data["categories"]
        # Preserve server-derived subcluster if present (canonical mapping)
        if "subcluster" in data:
            merged["subcluster"] = data["subcluster"]
        if "canonical" not in merged and "canonical" in data:
            merged["canonical"] = data["canonical"]
        if "description" not in merged and "description" in data:
            merged["description"] = data["description"]
        data = merged

    # Use proper YAML serialization instead of manual string building
    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return f"---\n{yaml_content}---\n"


def render_markdown(post, site):
    # Build front-matter (prefers title in body front-matter)
    fm = _front_matter(post, site)
    # Strip any leading front-matter from body because we've merged it above.
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    body = _strip_leading_frontmatter(body)
    if not body.endswith("\n"):
        body = body + "\n"
    return fm + "\n" + body


def _normalize_leading_frontmatter(content: str) -> str:
    """Ensure there's a single YAML front-matter block at the top of the content.

    If multiple leading blocks exist, merge them with precedence to the later
    blocks (assumed authored by user) for user keys, while keeping server-
    authoritative keys (date, categories) from the exporter.
    Returns the normalized full content (single front-matter + body).
    """
    import yaml
    if not content:
        return content
    parts = []
    rest = content
    # Extract all consecutive front-matter blocks at start
    while True:
        m = FRONTMATTER_RE.match(rest)
        if not m:
            break
        parts.append(m.group(1))
        rest = rest[m.end():]

    if not parts:
        return content

    # merge parts: earlier parts first, later parts override earlier keys
    merged = {}
    for part in parts:
        try:
            data = yaml.safe_load(part) or {}
            if isinstance(data, dict):
                merged.update(data)
        except Exception:
            # if a block fails to parse, skip it (we'll warn at call site)
            continue

    # ensure server-authoritative fields remain as in our generated top-level
    # (we expect caller to compute these and re-insert as needed)
    fm_text = yaml.dump(merged, default_flow_style=False, allow_unicode=True, sort_keys=False)
    normalized = f"---\n{fm_text}---\n{rest.lstrip('\n') or ''}"
    return normalized


def build_post_relpath(post, site, fm_data=None):
    """Build relative path for post based on front-matter routing rules.
    
    Path format:
    - With subcluster: _posts/<cluster>/<subcluster>/YYYY-MM-DD-<slug>.md
    - Without subcluster: _posts/<cluster>/YYYY-MM-DD-<slug>.md
    
    Args:
        post: Post instance
        site: Site instance  
        fm_data: Pre-parsed front-matter dict (optional, will extract if not provided)
    
    Returns:
        str: Relative path for the post file
        
    Raises:
        FrontMatterValidationError: If front-matter validation fails
    """
    # Extract front-matter if not provided
    if fm_data is None:
        body = getattr(post, "content", "") or getattr(post, "body", "") or ""
        fm_data = _extract_frontmatter_from_body(body)
    
    # Validate and extract taxonomy from front-matter
    cluster, subcluster, audit_msgs = _validate_frontmatter_taxonomy(post, fm_data)
    
    # Log routing decision
    logger.info("[export][routing] post_id=%s cluster='%s' subcluster='%s'", 
               getattr(post, 'id', None), cluster, subcluster or 'None')
    
    # Build date component
    date = _select_date(post)
    
    # Build filename with date prefix
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    if not slug:
        raise FrontMatterValidationError("Post slug is required for filename generation")
    
    filename = f"{date.strftime('%Y-%m-%d')}-{slug}.md"
    
    # Build directory structure
    posts_dir = (getattr(site, "posts_dir", None) or "_posts").strip("/")
    path_parts = [posts_dir, cluster]
    
    if subcluster:
        path_parts.append(subcluster)
    
    path_parts.append(filename)
    
    rel_path = os.path.normpath("/".join(path_parts))
    
    logger.info("[export][routing] post_id=%s dest_path='%s'", 
               getattr(post, 'id', None), rel_path)
    
    return rel_path





def compute_canonical_url(post, site):
    if getattr(post, "canonical_url", None):
        return post.canonical_url
    base_url = getattr(site, "base_url", "") or ""
    date = _select_date(post)
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    if not (base_url and date and slug):
        return None
    base_url = base_url.rstrip("/")
    return f"{base_url}/{date.year:04d}/{date.month:02d}/{date.day:02d}/{slug}.html"


def _git(cwd, *args, check=True, quiet=False):
    cmd = ["git", *args]
    env = os.environ.copy()
    display = " ".join(shlex.quote(a) for a in cmd)
    if not quiet:
        logger.debug("[git] cwd=%s cmd=%s", cwd, display)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, env=env)


def _build_push_url(remote_https):
    if not remote_https.startswith("https://"):
        raise ValueError("Solo remoti HTTPS supportati (niente SSH su PA free).")
    token = os.environ.get("GIT_TOKEN") or GIT_TOKEN
    if not token:
        raise RuntimeError("GIT_TOKEN non configurato nell'ambiente.")
    host_and_path = remote_https[len("https://"):] if remote_https.startswith("https://") else remote_https
    return f"https://{GIT_USERNAME}:{token}@{host_and_path}"


def _is_tracked(cwd, relpath):
    r = _git(cwd, "ls-files", "--error-unmatch", relpath, check=False, quiet=True)
    return getattr(r, "returncode", 1) == 0


def _is_ahead(cwd, branch):
    _git(cwd, "fetch", "origin", branch, "--quiet", check=False, quiet=True)
    r = _git(cwd, "rev-list", "--count", f"origin/{branch}..HEAD", check=False, quiet=True)
    try:
        return int((r.stdout or "0").strip()) > 0
    except Exception:
        return False


def _working_tree_clean(cwd):
    r = _git(cwd, "status", "--porcelain", check=False, quiet=True)
    return (r.stdout or "").strip() == ""


def _handle_file_move(repo_dir, old_path, new_path):
    """Handle atomic file move when post routing changes.
    
    Args:
        repo_dir: Repository root directory
        old_path: Current file path (relative to repo_dir)
        new_path: New file path (relative to repo_dir)
        
    Returns:
        bool: True if file was moved, False if no move needed
    """
    if old_path == new_path:
        return False
        
    old_abs = os.path.join(repo_dir, old_path)
    new_abs = os.path.join(repo_dir, new_path)
    
    if not os.path.exists(old_abs):
        logger.info("[export][move] old_path='%s' does not exist, no move needed", old_path)
        return False
    
    if os.path.exists(new_abs):
        logger.warning("[export][move] collision: new_path='%s' already exists, removing old file", new_path)
        os.remove(old_abs)
        return True
    
    # Create destination directory if needed
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    
    # Atomic move
    os.rename(old_abs, new_abs)
    
    # Clean up empty directories in old path
    try:
        old_dir = os.path.dirname(old_abs)
        while old_dir != repo_dir and old_dir:
            if not os.listdir(old_dir):  # Directory is empty
                os.rmdir(old_dir)
                old_dir = os.path.dirname(old_dir)
            else:
                break
    except OSError:
        pass  # Directory not empty or other error, ignore
    
    logger.info("[export][move] moved: '%s' -> '%s'", old_path, new_path)
    return True


def _write_atomic(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def export_post(post):
    """
    Export robusto:
    - Scrive file se hash cambia OPPURE file manca OPPURE non è tracciato.
    - Se 'no change', ma il repo è ahead di origin, tenta solo push.
    - Aggiorna metadati (exported_hash, exported_at, last_export_path, last_commit_sha) solo dopo push OK.
    """
    site = getattr(post, "site", None)
    site_slug = getattr(site, "slug", getattr(site, "id", "?")) if site else "?"
    repo_dir = getattr(site, "repo_path", None) if site else None
    # DEBUG: dump environment useful to diagnose prod vs console differences
    try:
        git_path = shutil.which("git")
    except Exception:
        git_path = None
    try:
        repo_exists = bool(repo_dir and os.path.isdir(repo_dir))
    except Exception:
        repo_exists = False
    owner = None
    perms = None
    try:
        if repo_exists and repo_dir:
            st = os.stat(repo_dir)
            owner = pwd.getpwuid(st.st_uid).pw_name
            perms = oct(st.st_mode & 0o777)
    except Exception:
        owner = None
        perms = None
    token_present = bool(os.environ.get("GIT_TOKEN"))
    logger.debug("[export][diag] site=%s repo_path=%r repo_exists=%s owner=%s perms=%s BLOG_REPO_BASE=%r git=%r GIT_TOKEN=%s",
                 site_slug, repo_dir, repo_exists, owner, perms, getattr(settings, "BLOG_REPO_BASE", None), git_path, "****" if token_present else "<missing>")
    if (not repo_dir) and site and getattr(settings, "BLOG_REPO_BASE", None):
        candidate = os.path.join(settings.BLOG_REPO_BASE, site_slug)
        if os.path.isdir(candidate):
            logger.info("[export] Uso fallback BLOG_REPO_BASE per site=%s: %s", site_slug, candidate)
            repo_dir = candidate
    if (not site) or (not repo_dir) or (not os.path.isdir(repo_dir)):
        logger.error("[export] repo_dir invalido: site=%s repo_dir=%r (configura Site.repo_path o BLOG_REPO_BASE)", site_slug, repo_dir)
        return

    # 1) Build content and validate front-matter first
    try:
        # Prefer an instance-defined render_markdown if provided
        if hasattr(post, "render_markdown") and callable(getattr(post, "render_markdown")):
            content = post.render_markdown()
        else:
            content = render_markdown(post, site)
    except FrontMatterValidationError as e:
        logger.error("[export][validator] Front-matter validation failed for post id=%s: %s - export blocked", 
                    getattr(post, 'id', None), str(e))
        return
    except Exception as e:
        logger.error("[export][error] Failed to render content for post id=%s: %s - export blocked", 
                    getattr(post, 'id', None), str(e))
        return

    # 2) Determine new path based on validated front-matter
    try:
        body = getattr(post, "content", "") or getattr(post, "body", "") or ""
        fm_data = _extract_frontmatter_from_body(body)
        new_rel_path = build_post_relpath(post, site, fm_data)
    except FrontMatterValidationError as e:
        logger.error("[export][validator] Path building failed for post id=%s: %s - export blocked", 
                    getattr(post, 'id', None), str(e))
        return
    except Exception as e:
        logger.error("[export][error] Path building failed for post id=%s: %s - export blocked", 
                    getattr(post, 'id', None), str(e))
        return

    # 3) Handle file move if path changed
    old_rel_path = getattr(post, 'last_export_path', None)
    moved = False
    if old_rel_path and old_rel_path != new_rel_path:
        logger.info("[export][move] post_id=%s path_change: '%s' -> '%s'", 
                   getattr(post, 'id', None), old_rel_path, new_rel_path)
        try:
            moved = _handle_file_move(repo_dir, old_rel_path, new_rel_path)
        except Exception as e:
            logger.error("[export][move] Failed to move post id=%s from '%s' to '%s': %s", 
                        getattr(post, 'id', None), old_rel_path, new_rel_path, str(e))
            return

    # Use new path for all subsequent operations
    rel_path = new_rel_path

    # Security: ensure rel_path is truly relative and does not escape repo_dir
    if os.path.isabs(rel_path) or rel_path.startswith("..") or ".." + os.path.sep in rel_path:
        logger.error("[export] Invalid relative path detected: %r", rel_path)
        return

    rel_path = rel_path.replace("\\", "/")  # normalize windows separators
    abs_path = os.path.join(repo_dir, rel_path)

    # Pre-export validation: ensure filename follows _posts/YYYY-MM-DD-<slug>.md
    try:
        filename = os.path.basename(rel_path)
        mval = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", filename)
        if not mval:
            logger.error("[export][validator] Invalid filename '%s' for post id=%s; expected YYYY-MM-DD-<slug>.md. Export blocked.", rel_path, getattr(post, 'id', None))
            return
        fname_slug = mval.group(2)
        # If the filename-derived slug and DB slug differ, never auto-rename published posts
        if fname_slug != getattr(post, 'slug', None):
            if getattr(post, 'slug_locked', False):
                logger.error(
                    "[export][validator] Slug mismatch for published post id=%s site=%s: slug_db=%r slug_repo=%r repo_path=%s. Export blocked. Use rename+redirect or align front-matter.",
                    getattr(post, 'id', None), site_slug, getattr(post, 'slug', None), fname_slug, rel_path,
                )
                return
            else:
                logger.error(
                    "[export][validator] Slug mismatch for post id=%s site=%s: slug_db=%r slug_repo=%r repo_path=%s. Export blocked; update front-matter or filename.",
                    getattr(post, 'id', None), site_slug, getattr(post, 'slug', None), fname_slug, rel_path,
                )
                return
    except Exception:
        logger.exception("[export][validator] Unexpected validator error for post id=%s; aborting export.", getattr(post, 'id', None))
        return
    # Final normalization: coalesce multiple leading front-matter blocks
    try:
        normed = _normalize_leading_frontmatter(content)
        if normed != content:
            logger.warning("[export][normalize] Normalized multiple front-matter blocks for post id=%s", getattr(post, 'pk', None))
            content = normed
    except Exception:
        logger.exception("[export][normalize] Failed normalizing front-matter for post id=%s", getattr(post, 'pk', None))

    new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]

    # Run export_validator for this site before writing/pushing
    try:
        bad = validate_repo_filenames(site_slug=getattr(site, 'slug', None))
        if bad:
            # Filter only critical errors that should block export
            # Exclude 'missing' and 'slug_mismatch' as non-critical (missing is normal for new posts)
            critical_errors = [issue for issue in bad if not (issue[3].startswith('slug_mismatch') or issue[3] == 'missing')]
            if critical_errors:
                logger.error("[export][validator] Pre-export validation failed for site %s; aborting export. First issue: %s", getattr(site, 'slug', None), critical_errors[0])
                return
            else:
                # Only slug_mismatch and missing warnings - log but don't block
                logger.warning("[export][validator] Non-critical validation warnings for site %s: %s", getattr(site, 'slug', None), [issue[3] for issue in bad[:3]])
    except Exception:
        logger.exception("[export][validator] Validator crashed; aborting export for post id=%s", getattr(post, 'id', None))
        return

    # 4) Determine if write is needed
    need_write = (getattr(post, "export_hash", None) != new_hash) or (not os.path.exists(abs_path)) or (not _is_tracked(repo_dir, rel_path)) or moved
    
    if moved:
        logger.info("[export][decision] post_id=%s action=moved_and_update", getattr(post, 'id', None))
    elif need_write:
        if getattr(post, "export_hash", None) != new_hash:
            logger.info("[export][decision] post_id=%s action=update reason=content_changed", getattr(post, 'id', None))
        elif not os.path.exists(abs_path):
            logger.info("[export][decision] post_id=%s action=create reason=file_missing", getattr(post, 'id', None))
        elif not _is_tracked(repo_dir, rel_path):
            logger.info("[export][decision] post_id=%s action=add reason=not_tracked", getattr(post, 'id', None))
    else:
        logger.info("[export][decision] post_id=%s action=skip reason=no_changes", getattr(post, 'id', None))
        
    committed = False
    if need_write:
        logger.debug(
            "[export] Scrittura necessaria: changed=%s exists=%s tracked=%s",
            getattr(post, "export_hash", None) != new_hash,
            os.path.exists(abs_path),
            _is_tracked(repo_dir, rel_path),
        )
        _write_atomic(abs_path, content)
        try:
            # Use explicit `--` to avoid git interpreting paths as refs/options
            _git(repo_dir, "add", "--", rel_path)
        except subprocess.CalledProcessError:
            logger.exception("[export] git add fallito per %s", rel_path)
        commit_msg = f"chore(blog): export {getattr(post, 'slug', '?')} ({timezone.now().date()})"
        if not _working_tree_clean(repo_dir):
            try:
                _git(repo_dir, "commit", "-m", commit_msg)
                committed = True
            except subprocess.CalledProcessError:
                logger.exception("[export] git commit fallito per %s", rel_path)
        else:
            logger.debug("[export] Nessun delta dopo add: skip commit")
    else:
        logger.info("[export] Nessun cambiamento (hash invariato) per %s", rel_path)

    # 3) Push se necessario
    try:
        remote = _git(repo_dir, "remote", "get-url", "origin", check=True).stdout.strip()
        try:
            push_url = _build_push_url(remote)
        except ValueError:
            # remote is not HTTPS (eg. SSH). Try to push using the configured remote name
            logger.warning("[export] remote non-HTTPS rilevato, useremo il remote configurato 'origin' (richiede chiavi SSH o credential helper)")
            push_url = None

        # If we just committed (fresh repo) we should attempt push even if
        # origin/<branch> does not exist yet (rev-list may fail). Also attempt
        # push when HEAD is ahead or working tree not clean.
        if committed or _is_ahead(repo_dir, GIT_BRANCH) or not _working_tree_clean(repo_dir):
            logger.info("[export] Push verso origin/%s", GIT_BRANCH)
            # prepare push attempt function
            def _attempt_push(target):
                if target:
                    return _git(repo_dir, "push", target, f"HEAD:{GIT_BRANCH}")
                else:
                    return _git(repo_dir, "push", "origin", f"HEAD:{GIT_BRANCH}")

            # first try
            try:
                _attempt_push(push_url)
            except subprocess.CalledProcessError as e:
                out = (getattr(e, 'stdout', '') or "").strip()
                err = (getattr(e, 'stderr', '') or "").strip().replace(GIT_TOKEN or "", MASK)
                # if rejected because remote is ahead, try fast-forward merge then retry once
                if "non-fast-forward" in err or "failed to push some refs" in err or "Updates were rejected" in err:
                    logger.warning("[export] Push respinta per non-fast-forward; provo rebase (autostash) e ritento push")
                    try:
                        # fetch and try a rebase with autostash
                        _git(repo_dir, "fetch", "origin", GIT_BRANCH)
                        # try a normal rebase first, then fall back to --autostash
                        try:
                            _git(repo_dir, "rebase", f"origin/{GIT_BRANCH}")
                        except subprocess.CalledProcessError:
                            try:
                                _git(repo_dir, "rebase", "--autostash", f"origin/{GIT_BRANCH}")
                            except subprocess.CalledProcessError:
                                raise
                        # retry push
                        try:
                            _attempt_push(push_url)
                        except subprocess.CalledProcessError as e2:
                            out2 = (getattr(e2, 'stdout', '') or "").strip()
                            err2 = (getattr(e2, 'stderr', '') or "").strip().replace(GIT_TOKEN or "", MASK)
                            logger.error("[export] Retry push fallita rc=%s out=%s err=%s", getattr(e2, 'returncode', None), out2[:500], err2[:500])
                            # create diagnostic branch and push it so user can inspect conflicts
                            try:
                                diag_branch = f"export-conflict-{site_slug}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                                _git(repo_dir, "checkout", "-b", diag_branch)
                                if push_url:
                                    _git(repo_dir, "push", push_url, f"HEAD:{diag_branch}")
                                else:
                                    _git(repo_dir, "push", "origin", f"HEAD:{diag_branch}")
                                logger.error("[export] Created diagnostic branch %s and pushed for inspection", diag_branch)
                                # mark post export as failed in caller flow
                                return
                            except Exception:
                                logger.exception("[export] Impossibile creare/pushare branch diagnostico")
                                return
                    except subprocess.CalledProcessError:
                        logger.error("[export] Rebase fallito; creo branch diagnostico e abort export per evitare conflitti manuali")
                        try:
                            diag_branch = f"export-conflict-{site_slug}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                            _git(repo_dir, "checkout", "-b", diag_branch)
                            if push_url:
                                _git(repo_dir, "push", push_url, f"HEAD:{diag_branch}")
                            else:
                                _git(repo_dir, "push", "origin", f"HEAD:{diag_branch}")
                            logger.error("[export] Created diagnostic branch %s and pushed for inspection", diag_branch)
                        except Exception:
                            logger.exception("[export] Impossibile creare/pushare branch diagnostico dopo rebase fallito")
                        return
                else:
                    logger.error("[export] Push fallita rc=%s out=%s err=%s", getattr(e, 'returncode', None), out[:500], err[:500])
                    return
        else:
            logger.debug("[export] Niente da pushare (HEAD non ahead e WT pulito)")
    except subprocess.CalledProcessError as e:
        out = (getattr(e, 'stdout', '') or "").strip()
        err = (getattr(e, 'stderr', '') or "").strip().replace(GIT_TOKEN or "", MASK)
        logger.error("[export] Recupero remote fallito rc=%s out=%s err=%s", getattr(e, 'returncode', None), out[:500], err[:500])
        return

    # 4) Aggiorna metadati del Post solo dopo push OK (campi CONCRETI)
    try:
        changed = []
        if getattr(post, "exported_hash", "") != new_hash:
            post.exported_hash = new_hash
            changed.append("exported_hash")
        post.exported_at = timezone.now()
        changed.append("exported_at")
        post.last_export_path = rel_path
        changed.append("last_export_path")
        # Persist repo_filename for future imports/export validation
        try:
            # Persist repo_filename so future imports/exports can validate using the
            # actual filename. The DB column was added during the remediation steps.
            post.repo_filename = rel_path
            changed.append("repo_filename")
        except Exception:
            # If for any reason the field cannot be set (older DB), fall back to
            # in-memory attribute to preserve behavior until schema is reconciled.
            try:
                setattr(post, '_repo_filename', rel_path)
            except Exception:
                pass
        # commit HEAD
        try:
            rc = _git(repo_dir, "rev-parse", "HEAD", check=False, quiet=True)
            sha = (rc.stdout or "").strip()
            if sha:
                post.last_commit_sha = sha
                changed.append("last_commit_sha")
        except Exception:
            pass
        post.export_status = "success"
        changed.append("export_status")
        if changed:
            try:
                # Use QuerySet.update() to avoid firing model signals (post_save)
                post.__class__.objects.filter(pk=getattr(post, "pk", None)).update(**{f: getattr(post, f) for f in changed})
                logger.debug("[export] Metadati aggiornati (%s) per post id=%s (via update())", ",".join(changed), getattr(post, "id", None))
            except Exception:
                # Fallback to instance save if update fails for any reason
                try:
                    post.save(update_fields=changed)
                    logger.debug("[export] Metadati aggiornati (%s) per post id=%s (via save())", ",".join(changed), getattr(post, "id", None))
                except Exception:
                    logger.exception("[export] Impossibile aggiornare metadati per post %s", getattr(post, "id", None))
    except Exception:
        logger.exception("[export] Impossibile aggiornare metadati per post %s", getattr(post, "id", None))
