from django.core.management.base import BaseCommand
from blog.models import Post
from blog.exporter import export_post
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Riprova export/push per tutti i post pubblicati con export_hash potenzialmente desincronizzato."

    def handle(self, *args, **opts):
        qs = Post.objects.filter(is_published=True).order_by("-updated_at")
        ok = 0
        for p in qs:
            try:
                export_post(p)
                ok += 1
            except Exception as e:
                logger.error("Export fallito per id=%s slug=%s: %s", p.id, p.slug, e)
        self.stdout.write(self.style.SUCCESS(f"Processed: {ok} posts"))
