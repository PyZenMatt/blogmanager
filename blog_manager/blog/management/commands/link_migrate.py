from django.core.management.base import BaseCommand
from blog.link_resolver import LinkResolver
from django.apps import apps
import difflib


class Command(BaseCommand):
    help = "Migrate hardcoded links to shortcodes"

    def add_arguments(self, parser):
        parser.add_argument('--site', required=True, help='Site slug to process')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        site_slug = options.get('site')
        Site = apps.get_model('blog', 'Site')
        Post = apps.get_model('blog', 'Post')
        try:
            site = Site.objects.get(slug=site_slug)
        except Site.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Site with slug '{site_slug}' not found"))
            return

        for p in Post.objects.filter(site=site):
            body = getattr(p, 'content', '') or getattr(p, 'body', '') or ''
            # naive migration: find occurrences of site.domain and convert to path shortcodes
            domain = getattr(site, 'domain', '')
            migrated = body
            if domain:
                migrated = migrated.replace(f"https://{domain}", "")
                migrated = migrated.replace(f"http://{domain}", "")

            if migrated != body:
                diff = '\n'.join(difflib.unified_diff(body.splitlines(), migrated.splitlines(), lineterm=''))
                self.stdout.write(f"Post {p.slug} -> diff:\n{diff}")
                if not options.get('dry_run'):
                    p.content = migrated
                    p.save()
