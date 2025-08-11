from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from .models import Author, Category, Comment, Post, PostImage, Site, Tag
from .permissions import IsPublisherForWriteOrReadOnly
from .serializers import (
    AuthorSerializer,
    CategorySerializer,
    CommentSerializer,
    PostImageSerializer,
    PostSerializer,
    SiteSerializer,
    TagSerializer,
))


# ENDPOINT API PER UPLOAD IMMAGINI (PostImage)
class PostImageCreateView(generics.CreateAPIView):
    queryset = PostImage.objects.all()
    serializer_class = PostImageSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]


# SITES
class SiteListView(generics.ListAPIView):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class SiteDetailView(generics.RetrieveAPIView):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    permission_classes = [AllowAny]


# CATEGORIES
class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["site"]
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Category.objects.all()


# AUTHORS
class AuthorListView(generics.ListAPIView):
    serializer_class = AuthorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["site"]
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Author.objects.all()


# POSTS
class PostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["site", "is_published", "categories__slug"]
    search_fields = ["title", "slug", "content"]
    ordering_fields = ["published_at", "updated_at"]
    ordering = ["-published_at"]
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Post.objects.all()
        site = self.request.query_params.get("site")
        if site:
            queryset = queryset.filter(site__domain=site)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(categories__slug=category)
        published = self.request.query_params.get("published")
        if published is not None:
            queryset = queryset.filter(is_published=published.lower() in ["1", "true", "yes"])
        return queryset.distinct()


class PostDetailView(generics.RetrieveUpdateAPIView):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    lookup_field = "slug"
    permission_classes = [IsPublisherForWriteOrReadOnly]


# COMMENTS (opzionale)
class CommentListView(generics.ListAPIView):
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["post"]
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Comment.objects.all()


class CommentCreateView(generics.CreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [AllowAny]


# TAGS
class TagViewSet(ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class SiteViewSet(ModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return super().get_permissions()


class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return super().get_permissions()


class AuthorViewSet(ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return super().get_permissions()


class PostViewSet(ModelViewSet):
    def create(self, request, *args, **kwargs):
        from django.db import IntegrityError, transaction
        from rest_framework import status
        from rest_framework.response import Response

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError:
            return Response(
                {"detail": "Integrity error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsPublisherForWriteOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["site", "status"]
    search_fields = ["title", "slug", "content"]
    ordering_fields = ["published_at", "updated_at"]
    ordering = ["-published_at"]

    def get_permissions(self):
        # lettura per tutti, scrittura con permission custom
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsPublisherForWriteOrReadOnly()]

    def partial_update(self, request, *args, **kwargs):
        post = self.get_object()
        self.check_object_permissions(request, post)
        old_path = post.last_export_path

        serializer = self.get_serializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        post.refresh_from_db()
        # Calcola nuovo path Jekyll
        new_slug = post.slug
        new_date = post.published_at
        site = post.site
        filename = f"{new_date.strftime('%Y-%m-%d')}-{new_slug}.md" if new_date and new_slug else None
        posts_dir = site.posts_dir if hasattr(site, "posts_dir") else "_posts"
        new_path = f"{posts_dir}/{filename}" if filename else None

        # Se path cambia, gestisci rename
        if old_path and new_path and old_path != new_path:
            from .exporter import render_markdown

            _ = render_markdown(post, site)
            post.last_export_path = new_path
            post.save(update_fields=["last_export_path"])
        elif new_path:
            from .exporter import render_markdown

            _ = render_markdown(post, site)
            post.last_export_path = new_path
            post.save(update_fields=["last_export_path"])

        return super().partial_update(request, *args, **kwargs)
