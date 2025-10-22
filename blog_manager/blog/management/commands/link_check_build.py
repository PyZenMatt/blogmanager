from django.core.management.base import BaseCommand
from django.apps import apps
from django.conf import settings
import subprocess
import os


class Command(BaseCommand):
    help = "Export site and run a Jekyll build, then check for 404s (requires jekyll installed)"

    def add_arguments(self, parser):
        parser.add_argument('--site', required=True, help='Site slug to process')

    def handle(self, *args, **options):
        site_slug = options.get('site')
        Site = apps.get_model('blog', 'Site')
        try:
            site = Site.objects.get(slug=site_slug)
        except Site.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Site with slug '{site_slug}' not found"))
            return

        # Trigger export for the site (naive: call existing sync/export management command if present)
        self.stdout.write(self.style.NOTICE("Exporting site (placeholder)"))

        # Locate repo and run jekyll build
        repo_path = getattr(site, 'repo_path', None) or settings.BLOG_REPO_BASE
        if not repo_path:
            self.stderr.write(self.style.ERROR("Site repo path not configured"))
            return

        if not os.path.exists(repo_path):
            self.stderr.write(self.style.ERROR(f"Repo path {repo_path} not found"))
            return

        # Run jekyll build (requires environment) — caller is responsible for having jekyll
        try:
            subprocess.check_call(['jekyll', 'build', '-s', repo_path, '-d', os.path.join(repo_path, '_site')])
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Jekyll build failed: {e}"))
            return

        # TODO: scan generated _site for 404s — placeholder success
        self.stdout.write(self.style.SUCCESS("Jekyll build completed (manual 404 checks needed)"))
