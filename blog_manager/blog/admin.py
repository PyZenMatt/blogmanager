
from django.contrib import admin

from .models import Site, Category, Author, Post, Comment, PostImage


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "repo_owner", "repo_name", "default_branch", "posts_dir", "media_dir", "base_url")
    search_fields = ("name", "domain", "repo_owner", "repo_name")
    fieldsets = (
        (None, {
            'fields': ("name", "domain")
        }),
        ("Repository", {
            'fields': ("repo_owner", "repo_name", "default_branch", "posts_dir", "media_dir", "base_url"),
            'classes': ('collapse',),
        }),
    )

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "slug")
    search_fields = ("name", "slug")
    list_filter = ("site",)

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "slug")
    search_fields = ("name", "slug")
    list_filter = ("site",)

from django.utils.html import format_html

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "site", "author", "status", "published_at", "is_published", "updated_at", "reviewed_by")
    search_fields = ("title", "slug", "content")
    list_filter = ("site", "author", "is_published", "status")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("categories",)

    fieldsets = (
        (None, {
            'fields': ("site", "title", "slug", "author", "categories", "content", "status", "published_at", "is_published", "reviewed_by", "reviewed_at", "review_notes")
        }),
        ("SEO e Social", {
            'fields': (
                "seo_title", "background", "tags", "description", "keywords", "canonical_url", "og_title", "og_description"
            ),
            'classes': ('collapse',),
        }),
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        obj = self.instance if hasattr(self, 'instance') else None
        if obj:
            # Only staff can publish
            if obj.status == "published" and not obj.published_at:
                raise ValidationError("published_at is required when status is published.")
            if obj.status == "published" and not obj.is_published:
                raise ValidationError("is_published must be True when status is published.")
            if obj.status == "review" and not obj.reviewed_by:
                raise ValidationError("reviewed_by is required when status is review.")


# Inline dichiarato DOPO la classe PostAdmin
class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ("image", "caption",)

PostAdmin.inlines = [PostImageInline]

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author_name", "author_email", "created_at")
    search_fields = ("author_name", "author_email", "text")
    list_filter = ("post",)

@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ("post", "image_thumb", "caption", "image_url")
    search_fields = ("post__title", "caption")
    list_filter = ("post",)

    def image_thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 60px; max-width: 100px;" />', obj.image.url)
        return ""
    image_thumb.short_description = "Anteprima"

    def image_url(self, obj):
        if obj.image:
            return obj.image.url
        return ""
    image_url.short_description = "URL Immagine"