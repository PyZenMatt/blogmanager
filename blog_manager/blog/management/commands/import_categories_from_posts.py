from django.core.management.base import BaseCommand
from django.utils.text import slugify
from blog.models import Post, Category
import re
import yaml


def extract_frontmatter(text: str):
    if not text:
        return None
    # Allow optional leading whitespace/newlines before the front-matter block
    m = re.search(r"^\s*---\s*\n(.*?)\n---\s*\n", text, flags=re.S | re.M)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return None


class Command(BaseCommand):
    help = "Import categories from posts' front-matter or content and create Category objects"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fields",
            default="categories",
            help=(
                "Comma-separated front-matter fields to inspect (e.g. 'cluster,subcluster' or 'categories'). "
                "When multiple fields are provided they will be combined into a hierarchical category name "
                "(e.g. cluster/subcluster)."
            ),
        )
        parser.add_argument(
            "--hierarchy",
            choices=["none", "slash", ">"],
            default="slash",
            help="How to interpret hierarchical categories (default: slash)",
        )
        parser.add_argument(
            "--auto-hashtags",
            action="store_true",
            help="Also detect categories from hashtag-like tokens (#cat) in content",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not persist changes, only report",
        )

    def handle(self, *args, **options):
        fields_arg = options["fields"] or "categories"
        fields = [f.strip() for f in fields_arg.split(',') if f.strip()]
        hierarchy = options["hierarchy"]
        auto_hashtags = options["auto_hashtags"]
        dry = options["dry_run"]

        # We'll process site-by-site to make import idempotent and avoid duplicates.
        posts = Post.objects.select_related('site').all()
        total_created = 0
        total_assigned = 0

        # Group posts per site for batch processing
        posts_by_site = {}
        for post in posts:
            posts_by_site.setdefault(post.site_id, []).append(post)

        for site_id, site_posts in posts_by_site.items():
            # map slug -> desired display name (keep first encountered name)
            desired = {}
            # map post_id -> list of slugs to assign
            assignments = {}

            for post in site_posts:
                fm = extract_frontmatter(post.content)
                cats = []

                if fm:
                    vals = []
                    for fld in fields:
                        if fld in fm and fm[fld] is not None:
                            v = fm[fld]
                            if isinstance(v, (list, tuple)) and v:
                                vals.extend([str(x).strip() for x in v if x])
                            else:
                                vals.append(str(v).strip())
                    if vals:
                        if len(vals) == 1:
                            cats = [vals[0]]
                        else:
                            cats = ["/".join(vals)]

                if not cats:
                    m = re.search(r'(?mi)^categories:\s*(.+)$', post.content or '')
                    if m:
                        cats = [s.strip() for s in re.split(r"[,;]\s*", m.group(1)) if s.strip()]

                if not cats and auto_hashtags:
                    tags = re.findall(r"#([A-Za-z0-9_\-/]+)", post.content or "")
                    cats = [t.replace('-', ' ').replace('_', ' ').strip() for t in tags]

                if not cats:
                    continue

                slugs_for_post = []
                for raw in cats:
                    if hierarchy == 'slash':
                        parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
                    elif hierarchy == '>':
                        parts = [p.strip() for p in re.split(r"\s*>\s*", raw) if p.strip()]
                    else:
                        parts = [raw.strip()]

                    accum = []
                    for i in range(len(parts)):
                        accum.append(parts[i])
                        name = "/".join(accum) if len(accum) > 1 else accum[0]
                        slug = slugify(name.replace('/', '-').replace('>', '-')).strip()
                        if not slug:
                            continue
                        # record desired name for this slug (first-wins)
                        desired.setdefault(slug, name)
                        slugs_for_post.append(slug)

                if slugs_for_post:
                    assignments.setdefault(post.pk, []).extend(slugs_for_post)

            if not desired:
                continue

            # Prefetch existing categories for the site
            existing = Category.objects.filter(site_id=site_id, slug__in=list(desired.keys()))
            existing_map = {c.slug: c for c in existing}

            # Determine which slugs need to be created
            to_create = []
            for slug, name in desired.items():
                if slug not in existing_map:
                    to_create.append(Category(site_id=site_id, slug=slug, name=name))

            # Bulk create missing categories (ignore conflicts to be safe in concurrent runs)
            if to_create and not dry:
                Category.objects.bulk_create(to_create, ignore_conflicts=True)
                total_created += len(to_create)

            # Re-fetch all categories for mapping
            all_cats = Category.objects.filter(site_id=site_id, slug__in=list(desired.keys()))
            slug_to_obj = {c.slug: c for c in all_cats}

            # Assign categories to posts in batch
            if not dry and assignments:
                # collect mapping post_id -> category objects
                for post in site_posts:
                    slugs = assignments.get(post.pk)
                    if not slugs:
                        continue
                    objs = []
                    for s in slugs:
                        obj = slug_to_obj.get(s)
                        if obj:
                            objs.append(obj)
                    if objs:
                        # avoid duplicates by using add with unique ids
                        post.categories.add(*objs)
                        total_assigned += len(objs)

        self.stdout.write(self.style.SUCCESS(f"Categories created: {total_created}, assigned: {total_assigned}"))