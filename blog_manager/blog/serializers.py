from rest_framework import serializers
from .models import Site, Category, Author, Post, Comment, PostImage, Tag
from django.contrib.auth import get_user_model


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
        fields = ["id", "name", "domain"]


class CategorySerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        site = attrs.get("site")
        slug = attrs.get("slug")
        if site and slug:
            qs = Category.objects.filter(site=site, slug=slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"slug": "Slug must be unique per site."})
        return attrs

    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ["id", "site", "name", "slug", "meta_title", "meta_description"]


class AuthorSerializer(serializers.ModelSerializer):
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Author
        fields = ["id", "site", "name", "bio", "slug", "meta_title", "meta_description"]


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "post", "author_name", "author_email", "text", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = [
            "id",
            "site",
            "title",
            "slug",
            "author",
            "categories",
            "body",
            "published_at",
            "is_published",
            "updated_at",
            "images",
            "comments",
            "cover_image_url",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "canonical_url",
            "repo_path",
            "og_title",
            "og_description",
            "og_image_url",
            "noindex",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        ]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Post.objects.all(), fields=["site", "slug"], message="Slug must be unique per site."
            )
        ]

    def validate_slug(self, value):
        site = None
        # Try to get site from initial_data (creation) or from instance (update)
        if hasattr(self, "initial_data") and isinstance(self.initial_data, dict):
            site = self.initial_data.get("site")
        if not site and self.instance:
            site = getattr(self.instance, "site", None)
        if not site:
            raise serializers.ValidationError("Site is required for slug uniqueness check.")
        qs = Post.objects.filter(site=site, slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Slug must be unique per site.")
        return value

    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all())
    author = serializers.PrimaryKeyRelatedField(queryset=Author.objects.all())
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True)
    body = serializers.CharField(source="content", required=True)
    # For GET, still provide nested serializers
    comments = CommentSerializer(many=True, read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)
    meta_keywords = serializers.CharField(required=False, allow_blank=True)
    canonical_url = serializers.URLField(required=False, allow_blank=True)
    repo_path = serializers.SerializerMethodField(read_only=True)
    og_title = serializers.CharField(required=False, allow_blank=True)
    og_description = serializers.CharField(required=False, allow_blank=True)
    og_image_url = serializers.URLField(required=False, allow_blank=True)
    noindex = serializers.BooleanField(required=False)
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
