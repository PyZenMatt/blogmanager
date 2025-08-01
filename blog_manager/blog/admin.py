
from django.contrib import admin

from .models import Site, Category, Author, Post, Comment, PostImage


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "domain")
    search_fields = ("name", "domain")

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
    list_display = ("title", "site", "author", "published_at", "is_published", "updated_at")
    search_fields = ("title", "slug", "content")
    list_filter = ("site", "author", "is_published")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("categories",)

    fieldsets = (
        (None, {
            'fields': ("site", "title", "slug", "author", "categories", "content", "published_at", "is_published")
        }),
        ("SEO e Social", {
            'fields': (
                "seo_title", "background", "tags", "description", "keywords", "canonical_url", "alt", "og_type", "og_title", "og_description"
            ),
            'classes': ('collapse',),
        }),
    )


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