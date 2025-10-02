from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Min
from blog.models import Category, Post
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dedupe duplicate Category records, re-point M2M relations, and remove duplicates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--site-id",
            type=int,
            help="Only process categories for specific site ID",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        site_id = options.get("site_id")

        self.stdout.write(
            self.style.WARNING(f"Starting category dedupe (dry_run={dry_run})")
        )

        # Find duplicate categories grouped by (site, slug)
        duplicates_query = Category.objects.values('site', 'slug').annotate(
            count=Count('id'),
            min_id=Min('id')
        ).filter(count__gt=1)

        if site_id:
            duplicates_query = duplicates_query.filter(site=site_id)

        duplicates = list(duplicates_query)

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicate categories found"))
            return

        self.stdout.write(
            f"Found {len(duplicates)} sets of duplicate categories"
        )

        total_merged = 0
        total_deleted = 0

        for dup in duplicates:
            site = dup['site']
            slug = dup['slug']
            count = dup['count']
            canonical_id = dup['min_id']

            # Get all categories with this (site, slug) combination
            categories = Category.objects.filter(
                site=site, slug=slug
            ).order_by('id')

            canonical = categories.filter(id=canonical_id).first()
            duplicates_to_remove = categories.exclude(id=canonical_id)

            self.stdout.write(
                f"  Site {site}, slug '{slug}': {count} duplicates → "
                f"keeping ID {canonical_id} ({canonical.name if canonical else 'MISSING'})"
            )

            if not canonical:
                self.stdout.write(
                    self.style.ERROR(f"    ERROR: Canonical category ID {canonical_id} not found")
                )
                continue

            # Re-point M2M relations from duplicates to canonical
            for dup_cat in duplicates_to_remove:
                posts_using_dup = Post.objects.filter(categories=dup_cat)
                post_count = posts_using_dup.count()

                if post_count > 0:
                    self.stdout.write(
                        f"    Re-pointing {post_count} posts from ID {dup_cat.id} to canonical ID {canonical_id}"
                    )

                    if not dry_run:
                        with transaction.atomic():
                            # Add canonical category to all posts that use the duplicate
                            for post in posts_using_dup:
                                post.categories.add(canonical)
                                post.categories.remove(dup_cat)

                    total_merged += post_count

                # Delete the duplicate category
                if not dry_run:
                    dup_cat.delete()
                    self.stdout.write(f"    Deleted duplicate category ID {dup_cat.id}")

                total_deleted += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would merge {total_merged} post relations and delete {total_deleted} duplicate categories"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully merged {total_merged} post relations and deleted {total_deleted} duplicate categories"
                )
            )

        # Verify no duplicates remain
        if not dry_run:
            remaining_query = Category.objects.values('site', 'slug').annotate(
                count=Count('id')
            ).filter(count__gt=1)

            if site_id:
                remaining_query = remaining_query.filter(site=site_id)

            remaining = remaining_query.count()

            if remaining == 0:
                self.stdout.write(self.style.SUCCESS("✓ No duplicate categories remain"))
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ {remaining} duplicate category sets still exist")
                )