from django.core.management.base import BaseCommand
import re
from blog.models import Post


PARTIAL_DATE_RE = re.compile(r'^\d{2}-\d{2}-')


class Command(BaseCommand):
    help = 'Audit slugs for suspicious patterns (partial dates, invalid chars, too long)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limit number of posts to scan (0 = all)')

    def handle(self, *args, **options):
        limit = options.get('limit') or 0
        qs = Post.objects.all().order_by('pk')
        if limit > 0:
            qs = qs[:limit]

        problems = []
        for p in qs:
            s = (p.slug or '')
            reasons = []
            if PARTIAL_DATE_RE.match(s):
                reasons.append('starts-with-partial-date')
            if len(s) > 75:
                reasons.append('too-long')
            # invalid chars: allow a-z0-9 and hyphen
            if re.search(r'[^a-z0-9-]', s):
                reasons.append('invalid-chars')
            if reasons:
                problems.append((p.pk, p.repo_filename or '<no-filename>', s, reasons))

        if not problems:
            self.stdout.write(self.style.SUCCESS('No slug issues found.'))
            return

        for pk, fname, slug, reasons in problems:
            self.stdout.write(self.style.ERROR(f'Post {pk} file={fname} slug={slug} reasons={reasons}'))

        # Exit with non-zero code to indicate issues found
        raise SystemExit(2)
