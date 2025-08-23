from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from types import SimpleNamespace
import os
import shlex
import hashlib


class Command(BaseCommand):
    help = "Debug exporter: show diagnostics and run export_post with simulated git (no real push)."

    def add_arguments(self, parser):
        parser.add_argument("post_id", type=int, help="ID del Post da esportare")
        parser.add_argument(
            "--simulate-push", action="store_true", help="Simula il push (non esegue push reale)."
        )

    def handle(self, *args, **options):
        Post = apps.get_model("blog", "Post")
        post_id = options["post_id"]
        simulate_push = options.get("simulate_push", False)

        try:
            p = Post.objects.select_related("site").get(pk=post_id)
        except Post.DoesNotExist:
            raise CommandError(f"Post {post_id} non trovato")

        from blog import exporter

        self.stdout.write(self.style.NOTICE(f"Post: id={p.id} slug={p.slug} status={p.status}"))
        self.stdout.write(f"published_at={p.published_at} exported_hash={p.exported_hash}")

        # Diagnostics: render content, compute hash, path
        content = exporter.render_markdown(p, p.site)
        new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:10]
        rel_path = exporter.build_post_relpath(p, p.site)
        self.stdout.write(self.style.SUCCESS(f"render_markdown => hash={new_hash} path={rel_path}"))

        # Resolve repo_dir like exporter
        site = getattr(p, "site", None)
        repo_dir = getattr(site, "repo_path", None) if site else None
        if (not repo_dir) and site and getattr(exporter.settings, "BLOG_REPO_BASE", None):
            candidate = os.path.join(exporter.settings.BLOG_REPO_BASE, getattr(site, "slug", ""))
            if os.path.isdir(candidate):
                repo_dir = candidate
        self.stdout.write(f"repo_dir resolved: {repo_dir}")

        # Prepare fake git functions
        orig_git = getattr(exporter, "_git", None)
        orig_build = getattr(exporter, "_build_push_url", None)

        def fake_git(cwd, *args, check=True, quiet=False):
            cmd = "git " + " ".join(shlex.quote(a) for a in args)
            self.stdout.write(f"[fake_git] cwd={cwd} cmd={cmd}")
            # emulate common outputs
            stdout = ""
            stderr = ""
            returncode = 0
            if len(args) >= 1 and args[0] == "ls-files":
                # simulate not tracked
                return SimpleNamespace(stdout="", stderr="", returncode=1)
            if len(args) >= 1 and args[0] == "status":
                return SimpleNamespace(stdout="", stderr="", returncode=0)
            if len(args) >= 1 and args[0] == "rev-list":
                return SimpleNamespace(stdout="0\n", stderr="", returncode=0)
            if len(args) >= 2 and args[0] == "remote" and args[1] == "get-url":
                return SimpleNamespace(stdout="https://github.com/example/repo.git\n", stderr="", returncode=0)
            if len(args) >= 1 and args[0] == "rev-parse":
                return SimpleNamespace(stdout="deadbeef1234567890\n", stderr="", returncode=0)
            return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

        def fake_build(remote_https):
            token_present = bool(os.environ.get("GIT_TOKEN"))
            self.stdout.write(f"[fake_build_push_url] remote={remote_https} token_present={token_present}")
            return "https://SIMULATED_PUSH_URL"

        exporter._git = fake_git
        exporter._build_push_url = fake_build

        # Run exporter (with fake git) so we can see exact code path
        try:
            self.stdout.write("[debug_export] Running exporter.export_post (git calls simulated)")
            exporter.export_post(p)
            # Refresh from DB
            p2 = Post.objects.get(pk=p.pk)
            self.stdout.write(
                f"After export: exported_hash={p2.exported_hash} last_export_path={p2.last_export_path} last_exported_at={p2.last_exported_at}"
            )
        except Exception as e:
            self.stderr.write(f"[debug_export] export_post raised: {e}")
        finally:
            # restore
            if orig_git is not None:
                exporter._git = orig_git
            if orig_build is not None:
                exporter._build_push_url = orig_build

        self.stdout.write("[debug_export] Done")
