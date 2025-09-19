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

        posts = Post.objects.select_related('site').all()
        total_created = 0
        total_assigned = 0

        for post in posts:
            site = post.site
            fm = extract_frontmatter(post.content)
            cats = []

            # Collect values from provided front-matter fields. If multiple fields are provided
            # we combine them into a hierarchical name (e.g. 'cluster/subcluster').
            if fm:
                vals = []
                for fld in fields:
                    if fld in fm and fm[fld] is not None:
                        v = fm[fld]
                        # If the field is a sequence, join its items (choose first if multiple)
                        if isinstance(v, (list, tuple)) and v:
                            # flatten lists into string entries
                            vals.extend([str(x).strip() for x in v if x])
                        else:
                            vals.append(str(v).strip())
                # If multiple front-matter fields were present, build a single hierarchical name
                if vals:
                    # If fields correspond to multiple categories (e.g., categories list), keep them separate
                    if len(vals) == 1:
                        cats = [vals[0]]
                    else:
                        # join with slash to indicate hierarchy
                        cats = ["/".join(vals)]

            # fallback: if none found using provided fields, try legacy 'categories' line
            if not cats:
                # try 'categories:' line
                m = re.search(r'(?mi)^categories:\s*(.+)$', post.content or '')
                if m:
                    cats = [s.strip() for s in re.split(r"[,;]\s*", m.group(1)) if s.strip()]

            # hashtags fallback
            if not cats and auto_hashtags:
                tags = re.findall(r"#([A-Za-z0-9_\-/]+)", post.content or "")
                cats = [t.replace('-', ' ').replace('_', ' ').strip() for t in tags]

            if not cats:
                continue

            created_objs = []
            for raw in cats:
                # raw might already contain hierarchy separators, normalize depending on requested hierarchy style
                if hierarchy == 'slash':
                    parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
                elif hierarchy == '>':
                    parts = [p.strip() for p in re.split(r"\s*>\s*", raw) if p.strip()]
                else:
                    parts = [raw.strip()]

                # create cumulative categories (parent, parent/child, ...)
                accum = []
                for i in range(len(parts)):
                    accum.append(parts[i])
                    name = "/".join(accum) if len(accum) > 1 else accum[0]
                    # slug: replace separators with hyphen
                    slug = slugify(name.replace('/', '-').replace('>', '-'))
                    defaults = {'name': name}
                    if dry:
                        obj = None
                        created = False
                        try:
                            obj = Category.objects.filter(site=site, slug=slug).first()
                        except Exception:
                            obj = None
                    else:
                        obj, created = Category.objects.get_or_create(site=site, slug=slug, defaults=defaults)
                    if created:
                        total_created += 1
                    if obj:
                        created_objs.append(obj)

            # assign categories to post (add only new ones)
            if not dry and created_objs:
                # ensure unique
                unique_objs = []
                seen = set()
                for o in created_objs:
                    if o and o.pk and o.pk not in seen:
                        unique_objs.append(o)
                        seen.add(o.pk)
                if unique_objs:
                    post.categories.add(*unique_objs)
                    total_assigned += len(unique_objs)

        self.stdout.write(self.style.SUCCESS(f"Categories created: {total_created}, assigned: {total_assigned}"))