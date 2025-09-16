from django.contrib import admin, messages
from django.utils.html import format_html
import os
from django.conf import settings
from django.db import transaction
import logging
import threading

logger = logging.getLogger(__name__)

from .models import Author, Category, Comment, Post, PostImage, Site
from django import forms
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.safestring import mark_safe
from .services.github_ops import delete_post_from_repo


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    readonly_fields = ("repo_candidate",)
    search_fields = ("name",)
    fieldsets = (
        (None, {"fields": ("name", "domain")}),
        (
            "Repository",
            {
                "fields": (
                    "repo_owner",
                    "repo_name",
                    "repo_candidate",
                    "default_branch",
                    "posts_dir",
                    "media_dir",
                    "base_url",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def repo_candidate(self, obj: Site) -> str:
        """Return the full candidate repo path shown in admin (either repo_path or BLOG_REPO_BASE/<slug>)."""
        if obj.repo_path and str(obj.repo_path).strip():
            return str(obj.repo_path)
        base = getattr(settings, "BLOG_REPO_BASE", None)
        if base:
            return os.path.join(base, obj.slug or "")
        return ""

    repo_candidate.short_description = "Percorso repo candidato"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "site")
    search_fields = ("name", "slug")
    list_filter = ("site",)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "site")
    search_fields = ("name", "slug")
    list_filter = ("site",)


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ("image", "caption")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "slug", "status", "published_at", "site")
    list_filter = ("status", "site", "published_at", "categories", "tags")
    # Removed SEO/meta fields from search as they are no longer model fields
    search_fields = ("title", "slug", "body")
    autocomplete_fields = ("author", "categories")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("categories",)
    inlines = [PostImageInline]
    actions = ["admin_delete_posts"]
    # Add publish action
    actions += ["publish_posts"]

    class DeleteConfirmationForm(forms.Form):
        MODE_CHOICES = [("db", "DB-only (default)"), ("repo", "DB + Repo")]
        mode = forms.ChoiceField(choices=MODE_CHOICES, widget=forms.RadioSelect, initial="db")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("delete_selected_confirm/", self.admin_site.admin_view(self.delete_selected_confirm), name="blog_post_delete_confirm"),
        ]
        return custom + urls

    def admin_delete_posts(self, request, queryset):
        # Redirect to confirmation view with selected pks
        pks = ",".join(str(p.pk) for p in queryset)
        return redirect(f"./delete_selected_confirm/?pks={pks}")

    admin_delete_posts.short_description = "Delete selected posts (DB-only or DB+Repo)"

    def publish_posts(self, request, queryset):
        """Admin action to publish selected posts immediately via `publish_post`.

        For each post: ensure status/published_at, call `publish_post`, and record an ExportJob.
        """
        from django.utils import timezone
        from .services.publish import publish_post
        from .models import ExportJob

        successes = 0
        failures = []

        for p in queryset.select_related("site"):
            # Ensure published status
            changed = False
            if getattr(p, "status", "") != "published":
                p.status = "published"
                changed = True
            if not getattr(p, "published_at", None):
                p.published_at = timezone.now()
                changed = True
            if changed:
                p.save(update_fields=["status", "published_at"])

            try:
                res = publish_post(p)
                # If commit_sha is None => no changes
                if res.commit_sha is None:
                    ExportJob.objects.create(
                        post=p,
                        commit_sha=None,
                        repo_url=f"https://github.com/{p.site.repo_owner}/{p.site.repo_name}",
                        branch=getattr(p.site, "default_branch", "main"),
                        path=getattr(p, "repo_path", None),
                        export_status="success",
                        action="publish",
                        message="no_changes",
                    )
                else:
                    ExportJob.objects.create(
                        post=p,
                        commit_sha=res.commit_sha,
                        repo_url=f"https://github.com/{p.site.repo_owner}/{p.site.repo_name}",
                        branch=getattr(p.site, "default_branch", "main"),
                        path=getattr(p, "repo_path", None),
                        export_status="success",
                        action="publish",
                    )
                successes += 1
            except Exception as e:
                # Log failure and create failed ExportJob
                logger.exception("Admin publish failed for post pk=%s", p.pk)
                # Try to extract friendly message from exception (GithubException returns dict in args)
                emsg = None
                try:
                    arg0 = e.args[0]
                    if isinstance(arg0, dict) and "message" in arg0:
                        emsg = arg0["message"]
                except Exception:
                    emsg = str(e)
                if not emsg:
                    emsg = str(e)
                ExportJob.objects.create(
                    post=p,
                    commit_sha=None,
                    repo_url=f"https://github.com/{p.site.repo_owner}/{p.site.repo_name}",
                    branch=getattr(p.site, "default_branch", "main"),
                    path=getattr(p, "repo_path", None),
                    export_status="failed",
                    action="publish",
                    message=emsg,
                )
                failures.append((p.pk, emsg))

        if successes:
            self.message_user(request, f"Published {successes} posts.", level=messages.SUCCESS)
        if failures:
            for pk, err in failures:
                self.message_user(request, f"Post {pk} publish failed: {err}", level=messages.ERROR)

    publish_posts.short_description = "Publish selected posts"

    def refresh_posts(self, request, queryset):
        """Admin action to refresh selected posts: compare DB content with repo content and record drift or ok."""
        from .github_client import GitHubClient
        from .utils import content_hash
        from .models import ExportJob

        gh = None
        try:
            gh = GitHubClient()
        except Exception:
            self.message_user(request, "GitHub client initialization failed (missing token?)", level=messages.ERROR)
            return

        oks = 0
        drifts = 0
        for p in queryset.select_related("site"):
            logger.debug("refresh_posts: checking post pk=%s site=%s", getattr(p, 'pk', None), getattr(p, 'site', None))
            owner = getattr(p.site, "repo_owner", None)
            repo = getattr(p.site, "repo_name", None)
            branch = getattr(p.site, "default_branch", "main")
            path = getattr(p, "repo_path", None)
            try:
                file_obj = gh.get_file(owner, repo, path, branch=branch)
                logger.debug("refresh_posts: got file_obj=%s", bool(file_obj))
            except Exception as e:
                logger.exception("refresh_posts: get_file failed for post pk=%s: %s", p.pk, e)
                # Try to extract friendly message; if it's a 404-like error we'll treat as drift_absent
                emsg = None
                try:
                    arg0 = e.args[0]
                    if isinstance(arg0, dict) and "message" in arg0:
                        emsg = arg0["message"]
                except Exception:
                    emsg = str(e)
                if emsg and "404" in emsg:
                    msg_code = "drift_absent"
                elif emsg and ("Token mancante" in emsg or "permessi" in emsg):
                    msg_code = "permission_denied"
                elif emsg and ("Rate limit" in emsg or "rate limit" in emsg or "429" in emsg):
                    msg_code = "rate_limited"
                else:
                    msg_code = "drift_absent"

                ExportJob.objects.create(
                    post=p,
                    commit_sha=None,
                    repo_url=f"https://github.com/{owner}/{repo}",
                    branch=branch,
                    path=path,
                    export_status="failed",
                    action="refresh",
                    message=emsg or msg_code,
                )
                # Map to admin-visible message
                if msg_code == "permission_denied":
                    self.message_user(request, f"Post {p.pk} error: Token mancante o permessi insufficienti.", level=messages.ERROR)
                elif msg_code == "rate_limited":
                    self.message_user(request, f"Post {p.pk} rate-limited by GitHub: riprova più tardi.", level=messages.ERROR)
                else:
                    self.message_user(request, f"Post {p.pk} drift: file absent in repo.", level=messages.WARNING)
                drifts += 1
                continue

            repo_content = file_obj.get("content")
            local_hash = content_hash(p)
            # Compute hash of repo content in same way; create a temporary Post-like object? We'll reuse content_hash by patching p.content temporarily
            orig_content = p.content
            try:
                p.content = repo_content
                repo_hash = content_hash(p)
            finally:
                p.content = orig_content

            if repo_hash == local_hash:
                ExportJob.objects.create(
                    post=p,
                    commit_sha=file_obj.get("sha"),
                    repo_url=f"https://github.com/{owner}/{repo}",
                    branch=branch,
                    path=path,
                        export_status="success",
                        action="refresh",
                        message="ok",
                )
                self.message_user(request, f"Post {p.pk} ok (no drift).", level=messages.INFO)
                oks += 1
            else:
                ExportJob.objects.create(
                    post=p,
                    commit_sha=file_obj.get("sha"),
                    repo_url=f"https://github.com/{owner}/{repo}",
                    branch=branch,
                    path=path,
                        export_status="failed",
                        action="refresh",
                        message="drift_content",
                )
                self.message_user(request, f"Post {p.pk} drift: content differs.", level=messages.WARNING)
                drifts += 1

        self.message_user(request, f"Refresh complete: {oks} ok, {drifts} drifts.", level=messages.INFO)

    refresh_posts.short_description = "Refresh selected posts (check repo vs DB)"

    def delete_selected_confirm(self, request):
        pks = request.GET.get("pks", "")
        ids = [int(x) for x in pks.split(",") if x]
        posts = Post.objects.filter(pk__in=ids).select_related("site")

        allow_repo = getattr(settings, "ALLOW_REPO_DELETE", False)

        if request.method == "POST":
            form = self.DeleteConfirmationForm(request.POST)
            if form.is_valid():
                mode = form.cleaned_data["mode"]
                results = []
                for p in posts:
                    if mode == "repo" and allow_repo:
                        try:
                            res = delete_post_from_repo(p, message=f"admin: delete post #{p.pk}")
                            results.append((p.pk, "repo", res.get("status"), res.get("commit_sha"), res.get("html_url")))
                        except Exception as e:
                            results.append((p.pk, "repo", "error", str(e), None))
                    # Only delete DB after successful repo delete (if requested)
                    if mode == "db" or (mode == "repo" and allow_repo):
                        # If repo requested but delete failed, skip DB delete
                        if mode == "repo" and allow_repo:
                            last = results[-1]
                            if last[2] == "error":
                                continue
                        p.delete()
                        results.append((p.pk, "db", "deleted", None, None))

                # Build a simple summary message
                for r in results:
                    if r[2] == "deleted":
                        self.message_user(request, mark_safe(f"Post {r[0]} deleted from DB."), level=messages.SUCCESS)
                    elif r[2] in ("deleted", "already_absent"):
                        self.message_user(request, f"Post {r[0]} repo status: {r[2]}", level=messages.INFO)
                    else:
                        self.message_user(request, f"Post {r[0]} error: {r[2]}", level=messages.ERROR)

                return redirect("../")
        else:
            form = self.DeleteConfirmationForm()

        return render(request, "admin/blog/post/delete_confirm.html", {"posts": posts, "form": form, "allow_repo": allow_repo})

    def _schedule_export_async(self, post_pk: int):
        """Lancia l'export in un thread separato (non blocca la response admin)."""
        def _runner(pk=post_pk):
            try:
                from .models import Post
                from .exporter import export_post
                p = Post.objects.get(pk=pk)
                export_post(p)
            except Exception:
                logger.exception("Export/push async fallito per Post pk=%s", pk)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()

    def save_model(self, request, obj, form, change):
        # era già pubblicato?
        was_published = False
        if change:
            try:
                old = type(obj).objects.get(pk=obj.pk)
                was_published = bool(getattr(old, "is_published", False)) or (
                    getattr(old, "status", "") == "published"
                )
            except type(obj).DoesNotExist:
                was_published = False

        # salva subito sul DB (MySQL)
        super().save_model(request, obj, form, change)

        # ora è pubblicato?
        now_published = bool(getattr(obj, "is_published", False)) or (
            getattr(obj, "status", "") == "published"
        )

        # se è appena passato a pubblicato → programma export async DOPO il commit
        if now_published and not was_published:
            pk = obj.pk
            transaction.on_commit(lambda: self._schedule_export_async(pk))
            self.message_user(
                request,
                "✅ Export programmato: push tra pochi secondi.",
                level=messages.SUCCESS,
            )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author_name", "author_email", "created_at")
    list_filter = ("created_at",)
    search_fields = ("author_name", "author_email", "text")


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ("post", "image_thumb", "caption", "image_url")
    search_fields = ("post__title", "caption")
    list_filter = ("post",)

    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 100px;" />',
                obj.image.url,
            )
        return ""

    image_thumb.short_description = "Anteprima"  # noqa: A003 - admin attr

    def image_url(self, obj):
        if obj.image:
            return obj.image.url
        return ""

    image_url.short_description = "URL Immagine"  # noqa: A003 - admin attr
