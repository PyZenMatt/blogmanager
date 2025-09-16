from django.core.management.base import BaseCommand
from django.db import transaction
from blog.models import Post
from blog.utils import content_hash


class Command(BaseCommand):
    help = "Backfill last_published_hash for published posts"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do not write changes")
        parser.add_argument("--force", action="store_true", help="Force backfill for all published posts even without evidence of prior publish")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        qs = Post.objects.filter(status="published")
        updated = 0
        total = qs.count()
        self.stdout.write(f"Found {total} published posts")
        for p in qs.iterator():
            # Only backfill when we have evidence of a prior publish (last_commit_sha, last_export_path, exported_at)
            evidence = bool(getattr(p, "last_commit_sha", None) or getattr(p, "last_export_path", None) or getattr(p, "exported_at", None))
            if not evidence and not options.get("force", False):
                self.stdout.write(f"Skipping post id={p.pk} (no evidence of prior publish). Use --force to override")
                continue
            h = content_hash(p)
            if (not getattr(p, "last_published_hash", None)) or (p.last_published_hash != h):
                self.stdout.write(f"Will update post id={p.pk} hash {h}")
                if not dry_run:
                    with transaction.atomic():
                        Post.objects.filter(pk=p.pk).update(last_published_hash=h)
                updated += 1
        self.stdout.write(f"Updated {updated} posts (dry_run={dry_run})")