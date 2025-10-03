from django.core.management.base import BaseCommand
from django.conf import settings
from blog.models import Site
import os
import yaml
import re

FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def _read_file(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def _write_file(path, content):
    tmp = f"{path}.tmp"
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(content)
    os.replace(tmp, path)


class Command(BaseCommand):
    help = "Normalize exported front-matter: ensure categories=[cluster] and subcluster separate. Use --dry-run to only report."

    def add_arguments(self, parser):
        parser.add_argument('--site', help='Slug of site to process (default: all exported sites)')
        parser.add_argument('--repo-base', help='Override BLOG_REPO_BASE', default=None)
        parser.add_argument('--dry-run', action='store_true', default=True, dest='dry_run', help='Do not rewrite files, only report')

    def handle(self, *args, **options):
        repo_base = options['repo_base'] or getattr(settings, 'BLOG_REPO_BASE', None)
        if not repo_base:
            self.stderr.write('BLOG_REPO_BASE not set; provide --repo-base')
            return

        sites = Site.objects.all()
        if options.get('site'):
            sites = sites.filter(slug=options['site'])

        report = []

        for site in sites:
            path = site.repo_path or os.path.join(repo_base, site.slug)
            if not os.path.isdir(path):
                self.stdout.write(self.style.WARNING(f"Skipping site {site.slug}: repo path not found {path}"))
                continue

            # Walk posts dir
            posts_dir = os.path.join(path, (site.posts_dir or '_posts').lstrip('/'))
            if not os.path.isdir(posts_dir):
                self.stdout.write(self.style.WARNING(f"No posts dir for {site.slug}: {posts_dir}"))
                continue

            for root, dirs, files in os.walk(posts_dir):
                for fname in files:
                    if not fname.endswith('.md'):
                        continue
                    fpath = os.path.join(root, fname)
                    content = _read_file(fpath)
                    m = FRONTMATTER_RE.match(content)
                    if not m:
                        continue
                    try:
                        fm = yaml.safe_load(m.group(1)) or {}
                    except Exception:
                        self.stdout.write(self.style.ERROR(f"Failed parse frontmatter: {fpath}"))
                        continue

                    # Detect legacy pattern: categories items containing '/'
                    cats = fm.get('categories') or []
                    if isinstance(cats, str):
                        cats = [cats]
                    legacy_items = [c for c in cats if isinstance(c, str) and '/' in c]
                    subcluster_present = 'subcluster' in fm
                    if legacy_items or (any('/' in str(c) for c in cats)):
                        report.append((fpath, legacy_items, subcluster_present))
                        self.stdout.write(self.style.WARNING(f"Legacy frontmatter: {fpath} -> legacy_items={legacy_items} subcluster_key={subcluster_present}"))
                        if not options['dry_run']:
                            # Normalize: build new fm
                            clusters = []
                            subcluster = None
                            for item in cats:
                                if not item:
                                    continue
                                if '/' in str(item):
                                    cl, sc = str(item).split('/', 1)
                                    clusters.append(cl.strip())
                                    subcluster = sc.strip()
                                else:
                                    clusters.append(item)
                            # prefer explicit subcluster key if present
                            if subcluster_present and not subcluster:
                                sc = fm.get('subcluster')
                                subcluster = sc[0] if isinstance(sc, (list, tuple)) else sc

                            new_fm = dict(fm)
                            new_fm['categories'] = [c for c in clusters if c and '/' not in c]
                            if subcluster:
                                new_fm['subcluster'] = subcluster
                            else:
                                new_fm.pop('subcluster', None)

                            yaml_content = yaml.dump(new_fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
                            new_content = f"---\n{yaml_content}---\n" + content[m.end():]
                            _write_file(fpath, new_content)
                            self.stdout.write(self.style.SUCCESS(f"Rewrote frontmatter: {fpath}"))

        self.stdout.write(self.style.SUCCESS(f"Done. {len(report)} files flagged."))
