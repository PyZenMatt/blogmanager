from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from blog.exporter import render_markdown

class Command(BaseCommand):
    help = "Esegue export diagnostico per un Post e mostra info (hash, path, changed)."

    def add_arguments(self, parser):
        parser.add_argument("post_id", type=int, help="ID del Post da esportare")

    def handle(self, *args, **options):
        Post = apps.get_model("blog", "Post")
        post_id = options["post_id"]
        try:
            p = Post.objects.select_related("site").get(pk=post_id)
        except Post.DoesNotExist:
            raise CommandError(f"Post {post_id} non trovato")
        self.stdout.write(self.style.NOTICE(f"Post: id={p.id} slug={p.slug} status={p.status}"))
        self.stdout.write(f"published_at={p.published_at} exported_hash={p.exported_hash}")
        changed, h, rel = render_markdown(p, p.site)
        self.stdout.write(self.style.SUCCESS(f"render_markdown => changed={changed} hash={h[:10]} path={rel}"))
        # Rileggi l'oggetto per vedere se i meta sono stati aggiornati via signal
        p2 = Post.objects.get(pk=p.pk)
        self.stdout.write(
            f"Dopo export: exported_hash={p2.exported_hash} last_export_path={p2.last_export_path} last_exported_at={p2.last_exported_at}"  # noqa: E501
        )
        self.stdout.write("Nota: se changed=True ma nessun commit appare, controlla i log logger 'blog.exporter'.")
