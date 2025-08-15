
from rest_framework.exceptions import APIException
from http import HTTPStatus
from django.utils.text import slugify
from django.utils import timezone

class Conflict(APIException):
    # Usa HTTPStatus per non dipendere dall'ordine degli import
    status_code = HTTPStatus.CONFLICT
    default_detail = "Conflitto: slug già in uso per questo sito."
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, decorators, permissions, response, status
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
)
from blog_manager.api.filters import SafeOrderingFilter


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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, SafeOrderingFilter]
    filterset_fields = ["site", "is_published", "categories__slug"]
    search_fields = ["title", "slug", "content"]
    ordering_fields = ["published_at", "updated_at"]
    ordering = ["-published_at", "-id"]
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
            queryset = queryset.filter(
                is_published=published.lower() in ["1", "true", "yes"]
            )
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
    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            from blog_manager.blog.serializers import PostWriteSerializer
            return PostWriteSerializer
        else:
            from blog_manager.blog.serializers import PostSerializer
            return PostSerializer

    def _unique_slug_for_site(self, *, site_id: int, base_slug: str) -> str:
        slug = base_slug
        i = 2
        from blog_manager.blog.models import Post
        while Post.objects.filter(site_id=site_id, slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1
        return slug

    def perform_create(self, serializer):
        # Normalizza slug e gestisci conflitti
        site_obj_or_id = serializer.validated_data.get("site")
        site_id = getattr(site_obj_or_id, "id", site_obj_or_id)
        title = serializer.validated_data.get("title") or ""
        desired_slug = serializer.validated_data.get("slug") or slugify(title)
        auto_slug = (desired_slug == slugify(title))

    from blog_manager.blog.models import Post
        if Post.objects.filter(site_id=site_id, slug=desired_slug).exists():
            if auto_slug:
                desired_slug = self._unique_slug_for_site(site_id=site_id, base_slug=desired_slug)
            else:
                # Slug esplicito occupato => 409
                raise Conflict()

        serializer.validated_data["slug"] = desired_slug
        obj = serializer.save()
        if obj.status == "published" and not obj.published_at:
            obj.published_at = timezone.now()
            obj.save(update_fields=["published_at"])

    def perform_update(self, serializer):
        prev = self.get_object()
        # Se l'update cambia slug/title, applica stessa logica di creazione
        data = serializer.validated_data
        site_obj_or_id = data.get("site", prev.site_id)
        site_id = getattr(site_obj_or_id, "id", site_obj_or_id)
        title = data.get("title", prev.title)
        desired_slug = data.get("slug", prev.slug) or slugify(title)
        auto_slug = (desired_slug == slugify(title))

    from blog_manager.blog.models import Post
        conflict = Post.objects.filter(site_id=site_id, slug=desired_slug).exclude(pk=prev.pk).exists()
        if conflict:
            if auto_slug:
                desired_slug = self._unique_slug_for_site(site_id=site_id, base_slug=desired_slug)
            else:
                raise Conflict()
        serializer.validated_data["slug"] = desired_slug

        obj = serializer.save()
        if obj.status == "published" and not obj.published_at:
            obj.published_at = timezone.now()
            obj.save(update_fields=["published_at"])
    # Usa l'implementazione base di ModelViewSet.create (nessun override personalizzato!)
    # Usa l'implementazione base di ModelViewSet.create (nessun override)

    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [IsPublisherForWriteOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        SafeOrderingFilter,
    ]
    filterset_fields = ["site", "status"]
    search_fields = ["title", "slug", "content"]
    ordering_fields = ["published_at", "title", "id"]
    ordering = ["-published_at", "-id"]
    
    @decorators.action(detail=True, methods=["post"], url_path="publish", permission_classes=[permissions.IsAuthenticated])
    def publish(self, request, pk=None):
        post = self.get_object()
        if post.status == "published":
            return response.Response({"detail": "Già pubblicato."}, status=status.HTTP_200_OK)
        post.status = "published"
        # `published_at` verrà impostato in pre_save
        post.save(update_fields=["status"])
        ser = PostSerializer(post, context={"request": request})
        return response.Response(ser.data, status=status.HTTP_200_OK)

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
        filename = (
            f"{new_date.strftime('%Y-%m-%d')}-{new_slug}.md"
            if new_date and new_slug
            else None
        )
        posts_dir = site.posts_dir if hasattr(site, "posts_dir") else "_posts"
        new_path = f"{posts_dir}/{filename}" if filename else None

        # Se path cambia, gestisci rename
        if old_path and new_path and old_path != new_path:
            from blog_manager.blog.exporter import render_markdown

            _ = render_markdown(post, site)
            post.last_export_path = new_path
            post.save(update_fields=["last_export_path"])
        elif new_path:
            from blog_manager.blog.exporter import render_markdown

            _ = render_markdown(post, site)
            post.last_export_path = new_path
            post.save(update_fields=["last_export_path"])

        return super().partial_update(request, *args, **kwargs)
