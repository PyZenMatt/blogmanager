from django.core.management.base import BaseCommand, CommandError
from django.apps import apps

class Command(BaseCommand):
    help = "Run render_markdown for a single Post and print result (for debug)."

    def add_arguments(self, parser):
        parser.add_argument("post_id", type=int, help="ID del Post da esportare")

    def handle(self, *args, **options):
        from blog.exporter import render_markdown
        Post = apps.get_model("blog", "Post")
        post_id = options["post_id"]
        try:
            p = Post.objects.select_related("site").get(pk=post_id)
        except Post.DoesNotExist:
            raise CommandError(f"Post {post_id} non trovato")
        changed, h, rel = render_markdown(p, p.site)
        self.stdout.write(f"changed={changed} hash={h} path={rel}")
