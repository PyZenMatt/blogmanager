from django.core.management.base import BaseCommand
from django.utils.text import slugify
from blog.models import Author


class Command(BaseCommand):
    help = "Normalize Author.slug values and ensure uniqueness (appends numeric suffixes if needed)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show changes that would be made without saving them.",
        )

    def handle(self, *args, **options):
        dry = options.get("dry_run", False)
        seen = {}
        changed = 0
        for author in Author.objects.order_by('id'):
            base = slugify(author.name or '') or f'author-{author.id}'
            candidate = base
            i = 2
            # If the slug is already used by another record with different pk, find a unique one
            while True:
                existing = Author.objects.filter(slug=candidate).exclude(pk=author.pk).first()
                if not existing and candidate not in seen:
                    break
                candidate = f"{base}-{i}"
                i += 1

            if candidate != (author.slug or ''):
                self.stdout.write(f"Author {author.pk}: '{author.slug}' -> '{candidate}'")
                if not dry:
                    author.slug = candidate
                    author.save(update_fields=['slug'])
                changed += 1
            seen[candidate] = True

        self.stdout.write(self.style.SUCCESS(f"Done. Slugs changed: {changed} (dry={dry})"))
