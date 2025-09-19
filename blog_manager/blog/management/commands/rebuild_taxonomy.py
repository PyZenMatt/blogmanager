from django.core.management.base import BaseCommand
import re
from django.core.management.base import BaseCommand
import re
import yaml
from blog.models import Post, Category, Site

fm_re = re.compile(r'^\s*---\s*\n([\s\S]*?)\n---\s*\n', re.M)


class Command(BaseCommand):
    help = 'Rebuild Category objects from posts front-matter (clusters and subclusters)'

    def add_arguments(self, parser):
        parser.add_argument('--site', type=str, help='Site slug to process (optional)')
        parser.add_argument('--dry-run', action='store_true', dest='dry_run', help='Show what would be created without saving')

    def handle(self, *args, **options):
        site_slug = options.get('site')
        dry = options.get('dry_run')

        posts = Post.objects.all()
        site_obj = None
        if site_slug:
            try:
                site_obj = Site.objects.get(slug=site_slug)
                posts = posts.filter(site=site_obj)
            except Site.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Site with slug '{site_slug}' not found"))
                return

        created = []
        missing = set()

        for p in posts:
            raw = p.content or getattr(p, 'body', '') or ''
            m = fm_re.search(raw)
            if not m:
                continue
            fm_text = m.group(1)
            try:
                fm = yaml.safe_load(fm_text) or {}
            except Exception:
                fm = {}
                for line in fm_text.splitlines():
                    if ':' in line:
                        k, v = line.split(':', 1)
                        fm[k.strip()] = v.strip()

            category_vals = []
            sub_vals = []

            # categories keys (primary)
            for key in ('categories', 'category'):
                if key in fm and fm[key]:
                    c = fm[key]
                    if isinstance(c, list):
                        category_vals.extend([str(x).strip() for x in c if x])
                    else:
                        category_vals.append(str(c).strip())

            # subcluster keys
            for key in ('subcluster', 'subclusters'):
                if key in fm and fm[key]:
                    s = fm[key]
                    if isinstance(s, list):
                        sub_vals.extend([str(x).strip() for x in s if x])
                    else:
                        sub_vals.append(str(s).strip())

            # fallback to post.categories M2M
            if not category_vals and hasattr(p, 'categories'):
                try:
                    for cat in p.categories.all():
                        name = cat.name or ''
                        if '/' in name:
                            category_vals.append(name.split('/')[0].strip())
                        else:
                            category_vals.append(name.strip())
                except Exception:
                    pass

            if not category_vals and not sub_vals:
                continue

            if not category_vals:
                category_vals = ['(no-category)']
            if not sub_vals:
                sub_vals = ['(no-subcluster)']

            for cval in category_vals:
                name_cl = cval
                slug_cl = name_cl.replace(' ', '-').lower()
                site_id = site_obj.id if site_obj is not None else p.site_id
                if dry:
                    missing.add((site_id, name_cl))
                else:
                    obj, created_flag = Category.objects.get_or_create(site_id=site_id, slug=slug_cl, defaults={'name': name_cl})
                    if created_flag:
                        created.append(obj)

                for su in sub_vals:
                    name = f"{name_cl}/{su}" if su and su != '(no-subcluster)' else name_cl
                    slug = name.replace(' ', '-').lower()
                    if dry:
                        missing.add((site_id, name))
                    else:
                        obj, created_flag = Category.objects.get_or_create(site_id=site_id, slug=slug, defaults={'name': name})
                        if created_flag:
                            created.append(obj)

        if dry:
            self.stdout.write(self.style.WARNING(f"Would create {len(missing)} categories (dry-run):"))
            for s, n in sorted(missing):
                self.stdout.write(f" site={s} name={n}")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {len(created)} new categories"))