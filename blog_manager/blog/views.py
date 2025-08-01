from rest_framework import generics, filters
from rest_framework.parsers import MultiPartParser, FormParser
from .models import PostImage, Site, Category, Author, Post, Comment
from .serializers import PostImageSerializer, SiteSerializer, CategorySerializer, AuthorSerializer, PostSerializer, CommentSerializer
from django_filters.rest_framework import DjangoFilterBackend

# ENDPOINT API PER UPLOAD IMMAGINI (PostImage)
class PostImageCreateView(generics.CreateAPIView):
    queryset = PostImage.objects.all()
    serializer_class = PostImageSerializer
    parser_classes = (MultiPartParser, FormParser)
from .models import Site, Category, Author, Post, Comment
from .serializers import SiteSerializer, CategorySerializer, AuthorSerializer, PostSerializer, CommentSerializer
from django_filters.rest_framework import DjangoFilterBackend

# SITES
class SiteListView(generics.ListAPIView):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer

class SiteDetailView(generics.RetrieveAPIView):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer

# CATEGORIES
class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['site']

    def get_queryset(self):
        return Category.objects.all()

# AUTHORS
class AuthorListView(generics.ListAPIView):
    serializer_class = AuthorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['site']

    def get_queryset(self):
        return Author.objects.all()

# POSTS
class PostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['site', 'is_published', 'categories__slug']
    search_fields = ['title', 'slug', 'content']
    ordering_fields = ['published_at', 'updated_at']
    ordering = ['-published_at']

    def get_queryset(self):
        queryset = Post.objects.all()
        site = self.request.query_params.get('site')
        if site:
            queryset = queryset.filter(site__domain=site)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(categories__slug=category)
        published = self.request.query_params.get('published')
        if published is not None:
            queryset = queryset.filter(is_published=published.lower() in ['1', 'true', 'yes'])
        return queryset.distinct()

class PostDetailView(generics.RetrieveAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    lookup_field = 'slug'

# COMMENTS (opzionale)
class CommentListView(generics.ListAPIView):
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['post']

    def get_queryset(self):
        return Comment.objects.all()

class CommentCreateView(generics.CreateAPIView):
    serializer_class = CommentSerializer
