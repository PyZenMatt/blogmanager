import os
import hashlib
import subprocess
import shlex
from contextlib import suppress
from django.utils import timezone
from django.conf import settings
import logging

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


def _select_date(post):
    for attr in ("published_at", "updated_at", "created_at"):
        val = getattr(post, attr, None)
        if val:
            return val
    return timezone.now()


def _front_matter(post, site):
    # minimal deterministic front matter
    data = {
        "layout": "post",
        "title": getattr(post, "title", "") or "",
        "slug": getattr(post, "slug", "") or "",
        "date": _select_date(post).strftime("%Y-%m-%d %H:%M:%S"),
        "categories": sorted([c.slug for c in getattr(post, 'categories', []).all()]) if hasattr(getattr(post, 'categories', None), 'all') else [],
        "tags": [],
        "canonical": getattr(post, "canonical_url", "") or "",
        "description": getattr(post, "meta_description", "") or "",
    }
    lines = ["---"]
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            sv = str(v).replace(":", "\\:")
            lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_markdown(post, site):
    """Return deterministic markdown content for a post (front matter + body)."""
    fm = _front_matter(post, site)
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    if not body.endswith("\n"):
        body = body + "\n"
    return fm + "\n" + body


def build_post_relpath(post, site):
    date = _select_date(post)
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    posts_dir = (getattr(site, "posts_dir", None) or "_posts").strip("/")
    return f"{posts_dir}/{date.strftime('%Y-%m-%d')}-{slug}.md"


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
    """Wrapper git con stdout/stderr catturati e logging safe (maschera token)."""
    cmd = ["git", *args]
    env = os.environ.copy()
    display = " ".join(shlex.quote(a) for a in cmd)
    if not quiet:
        logger.debug("[git] cwd=%s cmd=%s", cwd, display)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, env=env)


def _build_push_url(remote_https):
    """Costruisce URL https con credenziali in linea SOLO per la push corrente."""
    if not remote_https.startswith("https://"):
        raise ValueError("Solo remoti HTTPS supportati (niente SSH su PA free).")
    token = os.environ.get("GIT_TOKEN") or GIT_TOKEN
    if not token:
        raise RuntimeError("GIT_TOKEN non configurato nell'ambiente.")
    # removeprefix fallback
    host_and_path = remote_https[len("https://"):] if remote_https.startswith("https://") else remote_https
    return f"https://{GIT_USERNAME}:{token}@{host_and_path}"


def _is_tracked(cwd, relpath):
    r = _git(cwd, "ls-files", "--error-unmatch", relpath, check=False, quiet=True)
    return getattr(r, "returncode", 1) == 0


def _is_ahead(cwd, branch):
    # Allinea info remoto
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
    - Aggiorna export_hash DOPO commit+push riusciti.
    """
    site = getattr(post, "site", None)
    site_slug = getattr(site, "slug", getattr(site, "id", "?")) if site else "?"
    repo_dir = getattr(site, "repo_path", None) if site else None
    if (not repo_dir) and site and getattr(settings, "BLOG_REPO_BASE", None):
        candidate = os.path.join(settings.BLOG_REPO_BASE, site_slug)
        if os.path.isdir(candidate):
            logger.info("[export] Uso fallback BLOG_REPO_BASE per site=%s: %s", site_slug, candidate)
            repo_dir = candidate
    if (not site) or (not repo_dir) or (not os.path.isdir(repo_dir)):
        logger.error("[export] repo_dir invalido: site=%s repo_dir=%r (configura Site.repo_path o BLOG_REPO_BASE)", site_slug, repo_dir)
        return

    # 1) Prepara contenuto Markdown e path relativo (es. '_posts/YYYY-MM-DD-slug.md')
    rel_path = None
    if hasattr(post, "render_relative_path"):
        rel_path = post.render_relative_path()
    else:
        date = getattr(post, "published_at", None) or getattr(post, "updated_at", None) or timezone.now()
        slug = getattr(post, "slug", None) or "post"
        rel_path = f"_posts/{date.strftime('%Y-%m-%d')}-{slug}.md"

    abs_path = os.path.join(repo_dir, rel_path)
    if hasattr(post, "render_markdown"):
        content = post.render_markdown()
    else:
        fm = f"---\ntitle: {getattr(post, 'title', '')}\n---\n"
        body = getattr(post, 'content', '') or getattr(post, 'body', '') or ''
        if not body.endswith("\n"):
            body = body + "\n"
        content = fm + "\n" + body

    new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]

    # 2) Decisione scrittura
    need_write = (getattr(post, "export_hash", None) != new_hash) or (not os.path.exists(abs_path)) or (not _is_tracked(repo_dir, rel_path))
    if need_write:
        logger.debug("[export] Scrittura necessaria: changed=%s exists=%s tracked=%s",
                     getattr(post, "export_hash", None) != new_hash, os.path.exists(abs_path), _is_tracked(repo_dir, rel_path))
        _write_atomic(abs_path, content)
        try:
            _git(repo_dir, "add", rel_path)
        except subprocess.CalledProcessError:
            logger.exception("[export] git add fallito per %s", rel_path)
        commit_msg = f"chore(blog): export {getattr(post, 'slug', '?')} ({timezone.now().date()})"
        if not _working_tree_clean(repo_dir):
            try:
                _git(repo_dir, "commit", "-m", commit_msg)
            except subprocess.CalledProcessError:
                logger.exception("[export] git commit fallito per %s", rel_path)
        else:
            logger.debug("[export] Nessun delta dopo add: skip commit")
    else:
        logger.info("[export] Nessun cambiamento (hash invariato) per %s", rel_path)

    # 3) Push se necessario
    try:
        remote = _git(repo_dir, "remote", "get-url", "origin", check=True).stdout.strip()
        push_url = _build_push_url(remote)
        if _is_ahead(repo_dir, GIT_BRANCH) or not _working_tree_clean(repo_dir):
            logger.info("[export] Push verso origin/%s", GIT_BRANCH)
            try:
                _git(repo_dir, "push", push_url, f"HEAD:{GIT_BRANCH}")
            except subprocess.CalledProcessError as e:
                out = (e.stdout or "").strip()
                err = (e.stderr or "").strip().replace(GIT_TOKEN or "", MASK)
                logger.error("[export] Push fallita rc=%s out=%s err=%s", getattr(e, 'returncode', None), out[:500], err[:500])
                return
        else:
            logger.debug("[export] Niente da pushare (HEAD non ahead e WT pulito)")
    except subprocess.CalledProcessError as e:
        out = (e.stdout or "").strip()
        err = (e.stderr or "").strip().replace(GIT_TOKEN or "", MASK)
        logger.error("[export] Recupero remote fallito rc=%s out=%s err=%s", getattr(e, 'returncode', None), out[:500], err[:500])
        return

    # 4) Persist export_hash SOLO dopo push OK
    if getattr(post, "export_hash", None) != new_hash:
        try:
            post.export_hash = new_hash
            if hasattr(post, 'updated_at'):
                post.updated_at = timezone.now()
            update_fields = ['export_hash'] + (['updated_at'] if hasattr(post, 'updated_at') else [])
            post.save(update_fields=update_fields)
            logger.debug("[export] export_hash aggiornato a %s per post id=%s", new_hash, getattr(post, 'id', None))
        except Exception:
            logger.exception("[export] Impossibile aggiornare export_hash per post %s", getattr(post, 'id', None))
