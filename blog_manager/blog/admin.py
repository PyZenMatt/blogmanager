from django.contrib import admin, messages
from django.utils.html import format_html
import os
from django.conf import settings
from django.db import transaction
import logging
import threading

logger = logging.getLogger(__name__)

from .models import Author, Category, Comment, Post, PostImage, Site


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
    search_fields = ("title", "slug", "body", "meta_title", "meta_description")
    autocomplete_fields = ("author", "categories")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("categories",)
    inlines = [PostImageInline]

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
