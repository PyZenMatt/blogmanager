from django.core.management.base import BaseCommand
from blog.link_resolver import LinkResolver
from django.apps import apps


class Command(BaseCommand):
    help = "Lint internal links in site posts"

    def add_arguments(self, parser):
        parser.add_argument('--site', required=True, help='Site slug to process')
        parser.add_argument('--fail-on-warn', action='store_true', help='Exit non-zero if any warnings')

    def handle(self, *args, **options):
        site_slug = options.get('site')
        Site = apps.get_model('blog', 'Site')
        Post = apps.get_model('blog', 'Post')
        try:
            site = Site.objects.get(slug=site_slug)
        except Site.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Site with slug '{site_slug}' not found"))
            return

        errors_total = 0
        for p in Post.objects.filter(site=site):
            body = getattr(p, 'content', '') or getattr(p, 'body', '') or ''
            _, errors = LinkResolver.resolve(body, site)
            if errors:
                errors_total += len(errors)
                self.stdout.write(self.style.WARNING(f"Post {p.slug}:"))
                for e in errors:
                    self.stdout.write(f"  - {e}")

        if errors_total:
            msg = f"Found {errors_total} link issues"
            if options.get('fail_on_warn'):
                self.stderr.write(self.style.ERROR(msg))
                raise SystemExit(2)
            else:
                self.stdout.write(self.style.WARNING(msg))
        else:
            self.stdout.write(self.style.SUCCESS("No link issues found"))
