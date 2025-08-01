from rest_framework import serializers
from .models import Site, Category, Author, Post, Comment, PostImage
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
    class Meta:
        model = Category
        fields = ['id', 'site', 'name', 'slug']

class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['id', 'site', 'name', 'bio', 'slug']


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'post', 'author_name', 'author_email', 'text', 'created_at']


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    site = SiteSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    images = PostImageSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'site', 'title', 'slug', 'author', 'categories',
            'content', 'published_at', 'is_published', 'updated_at',
            'images', 'comments'
        ]

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'post', 'author_name', 'author_email', 'text', 'created_at']
