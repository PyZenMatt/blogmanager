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
import logging
from datetime import datetime
from django.conf import settings
from typing import Optional, Tuple
try:
    from blog.utils.seo import slugify_title
except ImportError:
    import re
    def slugify_title(value):
        value = str(value).strip().lower()
        value = re.sub(r'[^a-z0-9]+', '-', value)
        value = re.sub(r'-+', '-', value)
        return value.strip('-')

def _select_date(post):
    """Return a datetime for filename/front matter.
    Preference: published_at, updated_at, created_at; fallback now() if all missing."""
    for attr in ("published_at", "updated_at", "created_at"):
        val = getattr(post, attr, None)
        if val:
            return val
    from django.utils import timezone as _tz
    return _tz.now()

def _front_matter(post, site):
    """
    YAML deterministico: niente campi volatili (no timestamp di export),
    chiavi ordinate stabilmente per evitare diff spurie.
    """
    # serializza solo campi “stabili” che servono al sito statico
    import re

    def _collect_tags(p):
        """Ritorna lista di slug tag in modo robusto.
        Supporta:
        - ManyToMany/Taggit (ha .all())
        - Campo testuale CSV/newline (come nel model corrente: TextField)
        - Assenza del campo
        """
        raw = getattr(p, "tags", None)
        if raw is None:
            return []
        # Taggit / M2M like
        if hasattr(raw, "all"):
            try:
                items = []
                for x in raw.all():
                    slug = getattr(x, "slug", None) or getattr(x, "name", None)
                    if slug:
                        items.append(str(slug).strip())
                return sorted({i for i in items if i})
            except Exception:
                return []
        # Stringa semplice
        if isinstance(raw, str):
            parts = [s.strip() for s in re.split(r"[\n,]+", raw) if s.strip()]
            # slugify basica per consistenza se manca slugify_title
            norm = []
            for part in parts:
                try:
                    s = slugify_title(part)
                except Exception:
                    s = part.lower().replace(" ", "-")
                norm.append(s)
            return sorted({n for n in norm if n})
        return []

    data = {
        "layout": "post",
        "title": post.title or "",
        "slug": post.slug or "",
        "date": _select_date(post).strftime("%Y-%m-%d %H:%M:%S"),
        "categories": sorted([c.slug for c in post.categories.all()]) if hasattr(post, "categories") else [],
        # tags può essere un TextField CSV/newline oppure un M2M/Taggit
        "tags": _collect_tags(post),
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

logger = logging.getLogger("blog.exporter")

def _repo_base(site):
    # repo path per ogni sito: priorità al campo del DB, poi settings
    rp = getattr(site, "repo_path", None) or getattr(settings, "JEKYLL_REPO_BASE", None)
    if not rp:
        raise RuntimeError("Repo path non configurato: setta site.repo_path o settings.JEKYLL_REPO_BASE")
    if not os.path.isdir(rp):
        logger.warning("Repo path %s non esiste come directory", rp)
    elif not os.path.isdir(os.path.join(rp, ".git")):
        logger.warning("La directory %s non sembra essere un repository git (manca .git)", rp)
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
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain", "--", relpath],
            cwd=repo_path, capture_output=True, text=True, check=False
        )
        changed = bool(res.stdout.strip())
        logger.debug("git status per %s => %s", relpath, res.stdout.strip())
        return changed
    except Exception as e:
        logger.exception("Impossibile verificare cambiamenti git per %s: %s", relpath, e)
        return True  # fallback: prova comunque a committare

def _git_add_commit_push(repo_path, relpath, message):
    logger.info("[export] Aggiungo file %s e preparo commit", relpath)
    # git add
    try:
        res = subprocess.run(["git", "add", "--", relpath], cwd=repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error("[export][git add] non-zero exit (%s) for %s: stdout=%s stderr=%s", res.returncode, relpath, res.stdout, res.stderr)
            return False
        logger.debug("[export][git add] stdout=%s stderr=%s", res.stdout, res.stderr)
    except Exception as e:
        logger.exception("git add fallito per %s: %s", relpath, e)
        return False
    # Commit solo se ci sono modifiche (evita commit vuoti che possono causare loop)
    if _git_has_changes(repo_path, relpath):
        try:
            res = subprocess.run(["git", "commit", "-m", message], cwd=repo_path, capture_output=True, text=True)
            if res.returncode != 0:
                logger.error("[export][git commit] non-zero exit (%s) for %s: stdout=%s stderr=%s", res.returncode, relpath, res.stdout, res.stderr)
                return False
            logger.info("[export] Commit creato: %s", message)
            logger.debug("[export][git commit] stdout=%s stderr=%s", res.stdout, res.stderr)
        except Exception as e:
            logger.exception("Commit fallito per %s: %s", relpath, e)
            return False
    else:
        logger.info("[export] Nessuna modifica da committare per %s", relpath)
    # push best-effort (se configurato)
    try:
        res = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning("[export][git push] non-zero exit (%s) for repo %s: stdout=%s stderr=%s", res.returncode, repo_path, res.stdout, res.stderr)
        else:
            logger.debug("[export] Push eseguito: stdout=%s stderr=%s", res.stdout, res.stderr)
    except Exception as e:
        logger.warning("Push non riuscito (ignorato): %s", e)
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
    logger.debug("[export] Calcolato hash %s per post id=%s slug=%s", content_hash[:10], getattr(post, 'id', None), getattr(post, 'slug', None))

    # Se l'hash coincide con quello già esportato, short-circuit
    if getattr(post, "exported_hash", None) == content_hash:
        file_date = _select_date(post).strftime("%Y-%m-%d")
        rel_path = f"{getattr(site, 'posts_dir', '_posts')}/{file_date}-{post.slug}.md"
        logger.info("[export] Nessun cambiamento (hash invariato) per %s", rel_path)
        return (False, content_hash, rel_path)

    repo_path = _repo_base(site)
    file_date = _select_date(post).strftime("%Y-%m-%d")
    rel_path = f"{getattr(site, 'posts_dir', '_posts')}/{file_date}-{post.slug}.md"
    abs_path = os.path.join(repo_path, rel_path)

    written = _safe_write(abs_path, content)
    logger.debug("[export] Scrittura %s => written=%s", abs_path, written)
    if not written:
        # identico su disco: aggiorna hash e fine, niente commit
        logger.info("[export] Contenuto identico su disco, nessun commit per %s", rel_path)
        return (False, content_hash, rel_path)

    # Commit condizionale: _git_add_commit_push ora verifica se ci sono cambiamenti
    try:
        ok = _git_add_commit_push(repo_path, rel_path, f"Export post: {post.slug}")
        if not ok:
            logger.warning("[export] git add/commit/push non riuscito per %s", rel_path)
    except Exception as e:
        logger.exception("[export] Errore inatteso durante commit/push per %s: %s", rel_path, e)
        return (True, content_hash, rel_path)
    return (True, content_hash, rel_path)
