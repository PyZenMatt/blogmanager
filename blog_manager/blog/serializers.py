from rest_framework import serializers
from .models import Site, Category, Author, Post, Comment, PostImage, Tag
from django.contrib.auth import get_user_model

class PostImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PostImage
        fields = ['id', 'image_url', 'caption']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['id', 'name', 'domain']

class CategorySerializer(serializers.ModelSerializer):
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ['id', 'site', 'name', 'slug', 'meta_title', 'meta_description']


class AuthorSerializer(serializers.ModelSerializer):
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Author
        fields = ['id', 'site', 'name', 'bio', 'slug', 'meta_title', 'meta_description']

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'post', 'author_name', 'author_email', 'text', 'created_at']

class PostSerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all())
    author = serializers.PrimaryKeyRelatedField(queryset=Author.objects.all())
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True)
    body = serializers.CharField(source='content', required=True)
    # For GET, still provide nested serializers
    comments = CommentSerializer(many=True, read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)
    meta_keywords = serializers.CharField(required=False, allow_blank=True)
    canonical_url = serializers.URLField(required=False, allow_blank=True)
    og_title = serializers.CharField(required=False, allow_blank=True)
    og_description = serializers.CharField(required=False, allow_blank=True)
    og_image_url = serializers.URLField(required=False, allow_blank=True)
    noindex = serializers.BooleanField(required=False)
    status = serializers.CharField(required=False)
    reviewed_by = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), required=False, allow_null=True)
    reviewed_at = serializers.DateTimeField(required=False, allow_null=True)
    review_notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Post
        fields = [
            'id', 'site', 'title', 'slug', 'author', 'categories',
            'body', 'published_at', 'is_published', 'updated_at',
            'images', 'comments', 'cover_image_url',
            'meta_title', 'meta_description', 'meta_keywords',
            'canonical_url', 'og_title', 'og_description', 'og_image_url', 'noindex',
            'status', 'reviewed_by', 'reviewed_at', 'review_notes'
        ]

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']
