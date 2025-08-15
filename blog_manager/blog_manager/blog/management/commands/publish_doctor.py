from __future__ import annotations

import os
from typing import Optional

from django.core.management.base import BaseCommand, CommandError

<<<<<<< HEAD
from blog_manager.blog.utils import render_markdown_for_export
from blog_manager.blog.models import Site
from blog_manager.blog.services.github_checks import (
=======
from blog.utils import render_markdown_for_export
from blog.models import Site
from blog.services.github_checks import (
>>>>>>> fea98aad19a84b16cfa832b231cd983b87aef200
    check_branch,
    check_pages_workflow,
    check_permissions,
    check_repo_access,
    summarize,
)


class Command(BaseCommand):
    help = "Verifica end-to-end pubblicazione su GitHub Pages per uno o tutti i Site"

    def add_arguments(self, parser):
        parser.add_argument("--site", dest="site", help="Site id or name (slug)")
        parser.add_argument(
            "--all", action="store_true", help="Esegui per tutti i Site"
        )
        parser.add_argument("--verbose", action="store_true", help="Output dettagliato")

    def handle(self, *args, **options):
        site_selector: Optional[str] = options.get("site")
        for_all: bool = bool(options.get("all") or False)
        verbose: bool = bool(options.get("verbose") or False)

        if not site_selector and not for_all:
            raise CommandError("Specificare --site <id|name> oppure --all")

        sites = Site.objects.all()
        if site_selector and not for_all:
            try:
                if site_selector.isdigit():
                    sites = sites.filter(pk=int(site_selector))
                else:
                    sites = sites.filter(name=site_selector)
            except Exception:
                sites = sites.none()
        if not sites.exists():
            raise CommandError("Nessun Site trovato per i criteri indicati")

        had_error = False
        for site in sites:
            owner = site.repo_owner
            repo = site.repo_name
            branch = site.default_branch or "main"

            statuses = []
            token = os.environ.get(
                "GITHUB_TOKEN", ""
            )  # token dall'env (può essere vuoto per repo pubblici)
            # Repo access
            statuses.append(check_repo_access(token, owner, repo))
            # Permissions (assumiamo strategy direct per ora)
            statuses.append(check_permissions(token, owner, repo, need_pr=False))
            # Branch
            statuses.append(check_branch(token, owner, repo, branch))
            # Pages workflow
            statuses.append(check_pages_workflow(token, owner, repo))

            ok, report = summarize(statuses)
            header = f"Site: {site.name} ({owner}/{repo}@{branch})"
            self.stdout.write(header)
            self.stdout.write(report)

            # Static mapping checks
            missing = []
            if not site.posts_dir:
                missing.append("posts_dir")
            if not site.base_url:
                missing.append("base_url")
            if missing:
                ok = False
                self.stdout.write("❌ mapping: manca " + ", ".join(missing))
            else:
                self.stdout.write("✅ mapping: ok")

            # Dry-run exporter: create a dummy post-like object
            try:

                class Dummy:
                    title = "Doctor Check"
                    content = "This is a dry-run export."
                    published_at = None
                    tags = []
                    categories = []

                _ = render_markdown_for_export(Dummy())
                self.stdout.write("✅ exporter: ok")
            except Exception as e:
                ok = False
                self.stdout.write(f"❌ exporter: {e}")

            if not ok:
                had_error = True
            self.stdout.write("")

        if had_error:
            raise CommandError("Publish doctor: problemi rilevati")
        self.stdout.write(self.style.SUCCESS("Publish doctor: ✅ READY"))
