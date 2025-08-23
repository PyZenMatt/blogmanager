#!/usr/bin/env python3
# scripts/check_site_repo_paths.py
# Esegue lo stesso bootstrap di manage.py per caricare Django settings,
# poi interroga Site e mostra repo_path / fallback / esistenza / .git

import os
import sys
from pathlib import Path

# --- bootstrap come manage.py ---
project_root = Path(__file__).resolve().parents[1]  # assumes script is in ./scripts/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "settings.dev"),
)

import django
django.setup()

from django.conf import settings
from blog.models import Site

def exists_and_git(p: str):
    if not p:
        return (False, False)
    p = os.path.expanduser(p)
    exists = os.path.isdir(p)
    is_git = os.path.isdir(os.path.join(p, ".git")) if exists else False
    return exists, is_git

def main():
    base = getattr(settings, "BLOG_REPO_BASE", "") or ""
    print(f"BLOG_REPO_BASE = {base!r}\n")
    qs = Site.objects.all()
    if not qs.exists():
        print("No Site objects found in DB.")
        return
    for s in qs:
        slug = getattr(s, "slug", None)
        repo_path_field = (s.repo_path or "").strip() if getattr(s, "repo_path", None) is not None else ""
        fallback = os.path.join(base, slug) if base and slug else ""
        field_exists, field_is_git = exists_and_git(repo_path_field)
        fallback_exists, fallback_is_git = exists_and_git(fallback)
        chosen = None
        if repo_path_field and field_exists:
            chosen = repo_path_field
        elif fallback and fallback_exists:
            chosen = fallback
        print("="*60)
        print(f"Site id={s.pk} name={getattr(s,'name',None)!r} slug={slug!r}")
        print(f"  Site.repo_path         : {repo_path_field!r}")
        print(f"    exists: {field_exists}   is_git: {field_is_git}")
        print(f"  fallback (BLOG_REPO_BASE/{slug}) : {fallback!r}")
        print(f"    exists: {fallback_exists}   is_git: {fallback_is_git}")
        print(f"  -> system will use     : {chosen!r}")
    print("="*60)

if __name__ == '__main__':
    main()