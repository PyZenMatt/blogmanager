from django.core.management.base import BaseCommand
import re

from blog.utils.export_validator import validate_repo_filenames


class Command(BaseCommand):
    help = "Validate that Post.repo_filename matches expected _posts/YYYY-MM-DD-<slug>.md pattern"

    def add_arguments(self, parser):
        parser.add_argument("--site", dest="site", help="Limit to site slug")

    def handle(self, *args, **options):
        site = options.get("site")
        bad = validate_repo_filenames(site_slug=site)
        if bad:
            for b in bad:
                self.stdout.write(f"Post {b[0]} slug={b[1]!r} repo_filename={b[2]!r} reason={b[3]}")
            raise SystemExit(2)
        self.stdout.write("All repo_filename values validated.")