from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Post, Site, Author

class PostWriteSerializer(serializers.ModelSerializer):
    body = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # When writing via API, we prefer the front-matter title/slug; prevent clients from overriding
    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)

    class Meta:
        model = Post
        fields = "__all__"
        validators = []

    def to_internal_value(self, data):
        return super().to_internal_value(data)

    def validate(self, attrs):
        body = attrs.pop("body", None)
        if body is not None and not attrs.get("content"):
            attrs["content"] = body
        slug = attrs.get("slug")
        if isinstance(slug, str) and not slug.strip():
            attrs["slug"] = None

        # If title not provided via API, try to extract it from YAML front-matter in content
        content = attrs.get("content") or ""
        if not attrs.get("title") and content:
            try:
                import re
                import yaml

                m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if m:
                    fm = yaml.safe_load(m.group(1)) or {}
                    fm_title = fm.get("title") or fm.get("Title")
                    if isinstance(fm_title, str) and fm_title.strip():
                        attrs["title"] = fm_title.strip()
            except Exception:
                # best-effort extraction; ignore failures and proceed
                pass
        return attrs

        def to_internal_value(self, data):
            return super().to_internal_value(data)

        def validate(self, attrs):
            body = attrs.pop("body", None)
            if body is not None and not attrs.get("content"):
                attrs["content"] = body
            slug = attrs.get("slug")
            if isinstance(slug, str) and not slug.strip():
                attrs["slug"] = None
            return attrs

        def _unique_slug_for_site(self, site, base_slug: str) -> str:
            slug = base_slug or ""
            if not slug:
                slug = "post"
            candidate = slug
            idx = 2
            from .models import Post
            while Post.objects.filter(site=site, slug=candidate).exists():
                candidate = f"{slug}-{idx}"
                idx += 1
            return candidate

        from django.db import transaction

        @transaction.atomic
        def create(self, validated_data):
            title = validated_data.get("title") or ""
            site = validated_data.get("site")
            provided_slug = validated_data.get("slug")
            base_slug = self.slugify(provided_slug or title) if (provided_slug or title) else None
            if site:
                validated_data["slug"] = self._unique_slug_for_site(site, base_slug or "")
            else:
                validated_data["slug"] = base_slug or "post"
            return super().create(validated_data)

        @transaction.atomic
        def update(self, instance, validated_data):
            site = validated_data.get("site", getattr(instance, "site", None))
            new_slug = validated_data.get("slug", None)
            if new_slug is not None:
                base_slug = self.slugify(new_slug) if new_slug else self.slugify(validated_data.get("title") or instance.title or "")
                if site:
                    validated_data["slug"] = self._unique_slug_for_site(site, base_slug)
                else:
                    validated_data["slug"] = base_slug or instance.slug
            return super().update(instance, validated_data)
from .models import Category, Comment, Post, PostImage, Tag


class PostImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PostImage
        fields = ["id", "image_url", "caption"]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        # Expose additional editable fields so the UI can create a fully-configured Site
        fields = [
            "id",
            "name",
            "domain",
            "slug",
            "repo_path",
            "repo_owner",
            "repo_name",
            "default_branch",
            "posts_dir",
            "media_dir",
            "base_url",
            "media_strategy",
        ]


class CategorySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        site = attrs.get("site")
        slug = attrs.get("slug")
        if site and slug:
            qs = Category.objects.filter(site=site, slug=slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"slug": "Slug must be unique per site."}
                )
        return attrs

    class Meta:
        model = Category
        fields = ["id", "site", "name", "slug"]


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "site", "name", "bio", "slug"]
        extra_kwargs = {
            "site": {"allow_null": True, "required": False},
        }


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "post", "author_name", "author_email", "text", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    body = serializers.CharField(source="content", required=True)
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.all(), required=False, allow_empty=True)
    class Meta:
        model = Post
        fields = [
            "id",
            "site",
            "title",
            "slug",
            "author",
            "categories",
            "content",
            "body",
            "published_at",
            "is_published",
            "updated_at",
            "images",
            "comments",
            "cover_image_url",
            "canonical_url",
            "repo_path",
            # SEO/meta fields removed — front matter is derived from content only
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "exported_hash",
            "last_exported_at",
        ]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Post.objects.all(),
                fields=["site", "slug"],
                message="Slug must be unique per site.",
            )
        ]

    def validate_status(self, value):
        # Consenti bozza→pubblicato; evita published→draft salvo utenti staff
        request = self.context.get("request")
        instance = getattr(self, "instance", None)
        if instance and instance.status == "published" and value == "draft":
            if not request or not request.user or not request.user.is_staff:
                raise serializers.ValidationError("Transizione non consentita.")
        return value

    def validate_slug(self, value):
        import re
        import unicodedata
        v = value
        v = re.sub(r"[\x00\uD800-\uDFFF]", "", v or "")
        try:
            v = unicodedata.normalize("NFKD", v)
        except Exception:
            pass
        from django.utils.text import slugify as dj_slugify
        v = dj_slugify(v)[:200].strip("-") or "post"
        site = None
        if hasattr(self, "initial_data") and isinstance(self.initial_data, dict):
            site = self.initial_data.get("site")
        if not site and self.instance:
            site = getattr(self.instance, "site", None)
        if not site:
            raise serializers.ValidationError("Site is required for slug uniqueness check.")
        qs = Post.objects.filter(site=site, slug=v)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Slug must be unique per site.")
        return v
    def create(self, validated_data):
        # Autogenerazione server-side se slug mancante
        if not validated_data.get("slug"):
            post = Post(**validated_data)
            post.slug = Post.safe_slugify(site_id=post.site.pk, title=post.title)
            post.save()
            return post
            # fields = ("id", "site", "title", "slug", "body", "status", "categories", "tags", "author")

    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all())
    author = serializers.PrimaryKeyRelatedField(queryset=Author.objects.all())
    categories = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), many=True
    )
    body = serializers.CharField(source="content", required=True)
    # For GET, still provide nested serializers
    comments = CommentSerializer(many=True, read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    # meta/seo fields removed
    canonical_url = serializers.URLField(required=False, allow_blank=True)
    repo_path = serializers.SerializerMethodField(read_only=True)
    # og_* and noindex removed
    status = serializers.CharField(required=False)
    reviewed_by = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        required=False,
        allow_null=True,
    )
    reviewed_at = serializers.DateTimeField(required=False, allow_null=True)
    review_notes = serializers.CharField(required=False, allow_blank=True)

    cover_image_url = serializers.SerializerMethodField(read_only=True)

    def get_cover_image_url(self, obj):
        url = getattr(obj, "cover_image_url", None)
        if url:
            return url
        image = getattr(obj, "cover_image", None)
        try:
            return image.url if image else None
        except Exception:
            return None

    def get_repo_path(self, obj):
        # If repo_path is a model field, just return obj.repo_path
        # Otherwise, calculate or fetch from related ExportJob or metadata
        return getattr(obj, "repo_path", None)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
