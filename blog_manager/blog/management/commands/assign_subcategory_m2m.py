from django.core.management.base import BaseCommand
import re
from blog.models import Post, Category, Site
from blog.utils import extract_frontmatter


class Command(BaseCommand):
    help = "Assign posts to subcategory Category objects based on front-matter and tags"

    def add_arguments(self, parser):
        parser.add_argument('--site', type=str, help='Site slug to process (optional)')
        parser.add_argument('--dry-run', action='store_true', dest='dry_run', help='Do not persist changes')

    def handle(self, *args, **options):
        site_slug = options.get('site')
        dry = options.get('dry_run')

        cats = Category.objects.filter(name__contains='/')
        if site_slug:
            try:
                site = Site.objects.get(slug=site_slug)
                cats = cats.filter(site=site)
            except Site.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Site with slug '{site_slug}' not found"))
                return

        total_assigned = 0
        total_checked = 0

        # Build a map of parents -> list of subcategories
        parents = {}
        for sub in cats.order_by('site__id', 'name'):
            if '/' not in sub.name:
                continue
            parent_name, sub_part = [p.strip() for p in sub.name.split('/', 1)]
            parents.setdefault((sub.site.id, parent_name), []).append((sub, sub_part))

        total_checked = len(parents)
        for (site_id, parent_name), sub_items in parents.items():
            site_obj = sub_items[0][0].site
            # candidate posts in same site
            candidates = list(Post.objects.filter(site=site_obj))
            # For exclusivity, first remove any existing subcategory links for this parent
            if not dry:
                subs_to_remove = Category.objects.filter(site=site_obj, name__startswith=parent_name + '/')
                for p in candidates:
                    p.categories.remove(*list(subs_to_remove))

            # compute matches per post across this parent's sub_items
            assign_counts = 0
            for p in candidates:
                matches = []
                fm = extract_frontmatter(getattr(p, 'content', '') or '')
                # tokens from Post.tags
                tfield = (getattr(p, 'tags', '') or '')
                tokens = re.split(r"[,\n\r]+", tfield) if tfield else []
                for (sub_obj, sub_part) in sub_items:
                    matched = False
                    # strong match: front-matter categories contains full stored name
                    cats_fm = fm.get('categories') if isinstance(fm, dict) else None
                    if cats_fm:
                        if isinstance(cats_fm, (list, tuple)):
                            for c in cats_fm:
                                if c and str(c).strip() == sub_obj.name:
                                    matched = True
                                    break
                        else:
                            if str(cats_fm).strip() == sub_obj.name:
                                matched = True
                    if matched:
                        matches.append(sub_obj)
                        continue

                    # check cluster/subcluster structured fields
                    cluster_val = fm.get('cluster') if isinstance(fm, dict) else None
                    sub_val = fm.get('subcluster') if isinstance(fm, dict) else None
                    if cluster_val:
                        if isinstance(cluster_val, dict):
                            for clu, subs_v in cluster_val.items():
                                clu = str(clu).strip()
                                if isinstance(subs_v, (list, tuple)):
                                    for sv in subs_v:
                                        if sv and (clu + '/' + str(sv).strip() == sub_obj.name or str(sv).strip() == sub_part):
                                            matched = True
                                            break
                                    if matched:
                                        break
                                elif subs_v and (clu + '/' + str(subs_v).strip() == sub_obj.name or str(subs_v).strip() == sub_part):
                                    matched = True
                                    break
                        elif isinstance(cluster_val, (list, tuple)):
                            for clu in cluster_val:
                                if clu and (str(clu).strip() in (sub_part, parent_name, sub_obj.name)):
                                    matched = True
                                    break
                        elif isinstance(cluster_val, str):
                            clu = cluster_val.strip()
                            if sub_val:
                                if isinstance(sub_val, (list, tuple)):
                                    for sv in sub_val:
                                        if sv and (clu + '/' + str(sv).strip() == sub_obj.name or str(sv).strip() == sub_part):
                                            matched = True
                                            break
                                else:
                                    if clu + '/' + str(sub_val).strip() == sub_obj.name or str(sub_val).strip() == sub_part:
                                        matched = True
                            else:
                                if clu in (sub_part, parent_name, sub_obj.name):
                                    matched = True
                    if matched:
                        matches.append(sub_obj)
                        continue

                    # tag-based weaker match: front-matter tags or Post.tags tokens
                    tags_fm = fm.get('tags') if isinstance(fm, dict) else None
                    if tags_fm:
                        if isinstance(tags_fm, (list, tuple)):
                            for t in tags_fm:
                                if t and str(t).strip() == sub_part:
                                    matched = True
                                    break
                        else:
                            if str(tags_fm).strip() == sub_part:
                                matched = True
                    if not matched and tokens:
                        for tok in tokens:
                            if tok and tok.strip() == sub_part:
                                matched = True
                                break
                    if matched:
                        matches.append(sub_obj)

                # If the post matched exactly one subcategory for this parent, assign it
                if len(matches) == 1:
                    target = matches[0]
                    # remove parent category link if present so the post only appears under the subcategory
                    parent_cat = Category.objects.filter(site=site_obj, name=parent_name).first()
                    if not dry:
                        p.categories.add(target)
                        if parent_cat and p.categories.filter(pk=parent_cat.pk).exists():
                            p.categories.remove(parent_cat)
                    assign_counts += 1

            if assign_counts:
                total_assigned += assign_counts
                self.stdout.write(self.style.SUCCESS(f"Site={site_obj.slug} parent={parent_name} assigned={assign_counts}"))

        self.stdout.write(self.style.SUCCESS(f"Checked {total_checked} subcategories, total assigned: {total_assigned}"))
