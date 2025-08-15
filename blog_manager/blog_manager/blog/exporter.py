# --- Jekyll helpers for publish.py ---
def build_post_relpath(post, site):
    """
    Build the Jekyll post path: _posts/YYYY-MM-DD-slug.md using site's posts_dir.
    """
    date = getattr(post, "published_at", None)
    if not date:
        return None
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    posts_dir = (getattr(site, "posts_dir", None) or "_posts").strip("/")
    return f"{posts_dir}/{date.strftime('%Y-%m-%d')}-{slug}.md"

def compute_canonical_url(post, site):
    """
    Compute canonical URL if missing, using site's base_url and Jekyll permalinks pattern.
    Default pattern: /YYYY/MM/DD/slug.html
    """
    if getattr(post, "canonical_url", None):
        return post.canonical_url
    base_url = getattr(site, "base_url", "") or ""
    date = getattr(post, "published_at", None)
    slug = getattr(post, "slug", None) or slugify_title(getattr(post, "title", ""))
    if not (base_url and date and slug):
        return None
    base_url = base_url.rstrip("/")
    return f"{base_url}/{date.year:04d}/{date.month:02d}/{date.day:02d}/{slug}.html"
import hashlib
import os
import subprocess
from datetime import datetime
from django.conf import settings
from typing import Optional, Tuple
try:
    from blog_manager.blog.utils.seo import slugify_title
except ImportError:
    import re
    def slugify_title(value):
        value = str(value).strip().lower()
        value = re.sub(r'[^a-z0-9]+', '-', value)
        value = re.sub(r'-+', '-', value)
        return value.strip('-')

def _front_matter(post, site):
    """
    YAML deterministico: niente campi volatili (no timestamp di export),
    chiavi ordinate stabilmente per evitare diff spurie.
    """
    # serializza solo campi “stabili” che servono al sito statico
    data = {
        "layout": "post",
        "title": post.title or "",
        "slug": post.slug or "",
        "date": (post.published_at or post.updated_at or post.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        "categories": sorted([c.slug for c in post.categories.all()]) if hasattr(post, "categories") else [],
        "tags": sorted([t.slug for t in post.tags.all()]) if hasattr(post, "tags") else [],
        "canonical": getattr(post, "canonical_url", "") or "",
        "description": getattr(post, "meta_description", "") or "",
        # NON mettere last_exported_at / build_ts qui
    }
    # dump manuale ordinato (no dipendenze nuove)
    lines = ["---"]
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            # scappa i due punti base
            sv = str(v).replace(":", "\\:")
            lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"

def _build_markdown(post, site):
    fm = _front_matter(post, site)
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    # normalizza newline finale
    if not body.endswith("\n"):
        body = body + "\n"
    return fm + "\n" + body

def _repo_base(site):
    # repo path per ogni sito: priorità al campo del DB, poi settings
    rp = getattr(site, "repo_path", None) or getattr(settings, "JEKYLL_REPO_BASE", None)
    if not rp:
        raise RuntimeError("Repo path non configurato: setta site.repo_path o settings.JEKYLL_REPO_BASE")
    return rp

def _safe_write(filepath, content):
    """
    Scrive solo se il contenuto cambia, in modo atomico.
    Ritorna True se ha scritto (cioè se c'era una differenza), False se identico.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old = f.read()
            if old == content:
                return False
        except Exception:
            # se non leggibile, procedi a riscrivere
            pass
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, filepath)
    return True
def _git_has_changes(repo_path, relpath):
    # Controlla se ci sono modifiche per quel file
    res = subprocess.run(
        ["git", "status", "--porcelain", "--", relpath],
        cwd=repo_path, capture_output=True, text=True
    )
    return bool(res.stdout.strip())

def _git_add_commit_push(repo_path, relpath, message):
    subprocess.run(["git", "add", "--", relpath], cwd=repo_path, check=True)
    # Commit solo se ci sono modifiche
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True)
    # push best-effort (se configurato)
    try:
        subprocess.run(["git", "push"], cwd=repo_path, check=True)
    except Exception:
        pass
    return True

def render_markdown(post, site):
    """
    Genera markdown deterministico per il post e lo salva nel repo Jekyll.
    Ritorna (changed: bool, content_hash: str, file_path: str)
    - changed=False  => nessuna scrittura/commit; evita commit vuoti e loop
    - changed=True   => contenuto aggiornato e commit se necessario
    """
    content = _build_markdown(post, site)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Se l'hash coincide con quello già esportato, short-circuit
    if getattr(post, "exported_hash", None) == content_hash:
        file_date = (post.published_at or post.updated_at or post.created_at).strftime("%Y-%m-%d")
        rel_path = f"{getattr(site, 'posts_dir', '_posts')}/{file_date}-{post.slug}.md"
        return (False, content_hash, rel_path)

    repo_path = _repo_base(site)
    file_date = (post.published_at or post.updated_at or post.created_at).strftime("%Y-%m-%d")
    rel_path = f"{getattr(site, 'posts_dir', '_posts')}/{file_date}-{post.slug}.md"
    abs_path = os.path.join(repo_path, rel_path)

    written = _safe_write(abs_path, content)
    if not written:
        # identico su disco: aggiorna hash e fine, niente commit
        return (False, content_hash, rel_path)

    # Commit condizionale
    _git_add_commit_push(repo_path, rel_path, f"Export post: {post.slug}")
    return (True, content_hash, rel_path)
