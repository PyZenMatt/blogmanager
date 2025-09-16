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
