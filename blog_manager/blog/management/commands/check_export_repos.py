import os
from django.core.management.base import BaseCommand
from blog.models import Site


class Command(BaseCommand):
    help = "Verifica che ogni Site abbia working copy valida (repo_path) o fallback BLOG_REPO_BASE/<slug>."

    def handle(self, *args, **opts):
        from django.conf import settings
        base = getattr(settings, "BLOG_REPO_BASE", "")
        bad = 0
        for s in Site.objects.all().order_by("slug"):
            rp = (s.repo_path or "").strip()
            ok = bool(rp) and os.path.isdir(rp)
            fallback = os.path.join(base, s.slug) if base else ""
            fb_ok = bool(base) and os.path.isdir(fallback)
            if ok or fb_ok:
                msg = rp or f"[fallback] {fallback}"
                self.stdout.write(self.style.SUCCESS(f"OK  {s.slug:20s} -> {msg}"))
            else:
                bad += 1
                self.stdout.write(self.style.ERROR(f"BAD {s.slug:20s} -> repo mancante (configura repo_path o crea {fallback})"))
        if bad:
            raise SystemExit(1)
