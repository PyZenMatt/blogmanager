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


# regex to detect YAML front-matter at start of body
FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter_from_body(body: str) -> dict:
    """Return parsed front-matter dict if present at start of body, else {}."""
    import yaml
    if not body:
        return {}
    m = FRONTMATTER_RE.match(body)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


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


def _select_date(post):
    for attr in ("published_at", "updated_at", "created_at"):
        val = getattr(post, attr, None)
        if val:
            return val
    return timezone.now()


def _front_matter(post, site):
    import yaml
    # prefer title from front-matter if present in the body
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    fm_body = _extract_frontmatter_from_body(body)

    data = {
        "layout": "post",
        "title": fm_body.get("title") or getattr(post, "title", "") or "",
        # omit slug from exported front-matter: filename controls the slug
        "date": _select_date(post).strftime("%Y-%m-%d %H:%M:%S"),
        "categories": sorted([c.slug for c in getattr(post, 'categories', []).all()]) if hasattr(getattr(post, 'categories', None), 'all') else [],
        "tags": [],
        "canonical": getattr(post, "canonical_url", "") or "",
        # description is derived from post.content/description field if present
        "description": getattr(post, "description", "") or "",
    }

    # Use proper YAML serialization instead of manual string building
    yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return f"---\n{yaml_content}---\n"


def render_markdown(post, site):
    # Build front-matter (prefers title in body front-matter)
    fm = _front_matter(post, site)
    # Strip trivial leading front-matter from body to avoid duplicates like '---\ntitle:...---'
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    body = _strip_trivial_leading_frontmatter(body)
    if not body.endswith("\n"):
        body = body + "\n"
    return fm + "\n" + body


def build_post_relpath(post, site):
    date = _select_date(post)
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    posts_dir = (getattr(site, "posts_dir", None) or "_posts").strip("/")
    filename = f"{date.strftime('%Y-%m-%d')}-{slug}.md"
    
    # Build hierarchical path based on categories and subcluster
    path_parts = [posts_dir]
    
    # Get categories from post.categories (M2M relation)
    categories = []
    if hasattr(post, 'categories') and hasattr(post.categories, 'all'):
        categories = [c.slug for c in post.categories.all()]
    
    # Extract subcluster from front-matter if present
    subcluster = _extract_subcluster_from_post(post)
    
    # Build path: _posts/[cluster]/[subcluster]/filename
    if categories:
        # Use first category as main cluster
        cluster = categories[0]
        path_parts.append(cluster)
        
        if subcluster:
            path_parts.append(subcluster)
    
    path_parts.append(filename)
    return os.path.normpath("/".join(path_parts))


def _extract_subcluster_from_post(post):
    """Extract subcluster from post front-matter or content."""
    import re
    import yaml
    
    content = getattr(post, "content", "") or getattr(post, "body", "") or ""
    
    # Look for front-matter at the beginning of content
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        return None
    
    try:
        fm_data = yaml.safe_load(fm_match.group(1))
        if isinstance(fm_data, dict):
            subcluster = fm_data.get('subcluster')
            if subcluster:
                # Handle both string and list formats
                if isinstance(subcluster, list) and subcluster:
                    return subcluster[0]
                elif isinstance(subcluster, str):
                    return subcluster
    except Exception:
        pass
    
    return None


def compute_canonical_url(post, site):
    if getattr(post, "canonical_url", None):
        return post.canonical_url
    base_url = getattr(site, "base_url", "") or ""
    date = _select_date(post)
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    if not (base_url and date and slug):
        return None
    base_url = base_url.rstrip("/")
    return f"{base_url}/{date.year:04d}/{date.month:02d}/{date.day():02d}/{slug}.html"


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
        if repo_exists:
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

    # 1) Contenuto e percorso relativo (rispetta site.posts_dir)
    if hasattr(post, "render_relative_path"):
        rel_path = post.render_relative_path()
    else:
        rel_path = build_post_relpath(post, site)

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
    if hasattr(post, "render_markdown"):
        content = post.render_markdown()
    else:
        fm = f"---\ntitle: {getattr(post, 'title', '')}\n---\n"
        body = getattr(post, 'content', '') or getattr(post, 'body', '') or ''
        if not body.endswith("\n"):
            body = body + "\n"
        content = fm + "\n" + body

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

    # 2) Decisione scrittura
    need_write = (getattr(post, "export_hash", None) != new_hash) or (not os.path.exists(abs_path)) or (not _is_tracked(repo_dir, rel_path))
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
