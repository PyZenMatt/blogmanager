
from rest_framework.exceptions import APIException
from http import HTTPStatus
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone

class Conflict(APIException):
    # Usa HTTPStatus per non dipendere dall'ordine degli import
    status_code = HTTPStatus.CONFLICT
    default_detail = "Conflitto: slug già in uso per questo sito."
from django_filters.rest_framework import DjangoFilterBackend
import re
import yaml
from rest_framework import filters, generics, decorators, permissions, response, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
import logging

logger = logging.getLogger(__name__)

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
from api.filters import SafeOrderingFilter
from .github_client import GitHubClient


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


class TaxonomyView(generics.GenericAPIView):
    """Return a grouped taxonomy (category -> subclusters -> examples) for a site.

    Query params:
      - site: site id (optional). If provided, taxonomy is built for that site only.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        site = request.query_params.get('site')
        from collections import defaultdict

        fm_re = re.compile(r'^\s*---\s*\n([\s\S]*?)\n---\s*\n', re.M)
        categories_map = defaultdict(lambda: defaultdict(set))

        posts_qs = Post.objects.all()
        if site:
            try:
                site_id = int(site)
                posts_qs = posts_qs.filter(site_id=site_id)
            except Exception:
                pass

        for p in posts_qs:
            raw = p.content or getattr(p, 'body', '') or ''
            m = fm_re.search(raw)
            fm = None
            if m:
                txt = m.group(1)
                try:
                    fm = yaml.safe_load(txt) or {}
                except Exception:
                    fm = None

            category_vals = []
            sub_vals = []
            # parse fm if present: prefer `categories` as primary key
            if fm and isinstance(fm, dict):
                c = fm.get('categories') or fm.get('category')
                if c:
                    if isinstance(c, list):
                        category_vals.extend([str(x).strip() for x in c if x])
                    else:
                        category_vals.append(str(c).strip())
                s = fm.get('subcluster') or fm.get('subclusters')
                if s:
                    if isinstance(s, list):
                        sub_vals.extend([str(x).strip() for x in s if x])
                    else:
                        sub_vals.append(str(s).strip())

            # fallback: inspect post.categories M2M
            if not category_vals:
                try:
                    for cat in p.categories.all():
                        name = cat.name or ''
                        if '/' in name:
                            category_vals.append(name.split('/')[0].strip())
                        else:
                            category_vals.append(name.strip())
                except Exception:
                    pass

            if not category_vals and not sub_vals:
                continue

            if not category_vals:
                category_vals = ['(no-category)']
            if not sub_vals:
                sub_vals = ['(no-subcluster)']

            for cat_name in category_vals:
                for su in sub_vals:
                    categories_map[cat_name][su].add(p.title or f'post-{p.pk}')

        # also include categories from Category model if no posts-derived categories
        if not categories_map:
            qs = Category.objects.all()
            if site:
                try:
                    qs = qs.filter(site_id=int(site))
                except Exception:
                    pass
            for c in qs:
                parts = (c.name or '').split('/')
                if not parts:
                    continue
                catn = parts[0].strip()
                sub = '/'.join(parts[1:]).strip() if len(parts) > 1 else '(no-subcluster)'
                categories_map[catn][sub].add(c.name)

        # format response
        resp = []
        for catn, subs in sorted(categories_map.items(), key=lambda x: x[0]):
            subs_out = []
            for su, items in sorted(subs.items(), key=lambda x: x[0]):
                subs_out.append({'name': su, 'count': len(items), 'examples': list(items)[:5]})
            resp.append({'category': catn, 'subclusters': subs_out})

        # include available sites so the client can present site choices
        try:
            sites_qs = Site.objects.all()
            sites_ser = SiteSerializer(sites_qs, many=True, context={'request': request}).data
        except Exception:
            sites_ser = []

        return response.Response({'site': site or None, 'categories': resp, 'sites': sites_ser})


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
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["site", "is_published", "categories__slug"]
    search_fields = ["title", "slug", "content"]
    ordering_fields = ["published_at", "updated_at"]
    ordering = ["-published_at"]
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Post.objects.all()
        site = self.request.query_params.get("site")

        def perform_create(self, serializer):
            obj = serializer.save()
            if obj.status == "published" and not obj.published_at:
                obj.published_at = timezone.now()
                obj.save(update_fields=["published_at"])

        def perform_update(self, serializer):
            prev = self.get_object()
            obj = serializer.save()
            if obj.status == "published" and not obj.published_at:
                obj.published_at = timezone.now()
                obj.save(update_fields=["published_at"])
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

    # Allow filtering by site via ?site=<id>
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["site"]

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
            from .serializers import PostWriteSerializer
            return PostWriteSerializer
        from .serializers import PostSerializer
        return PostSerializer

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            # If this is a DRF API exception (e.g. ValidationError), re-raise so
            # DRF can render the appropriate 4xx response.
            from rest_framework.exceptions import APIException as DRFAPIException
            if isinstance(exc, DRFAPIException):
                raise
            logger.exception('Unhandled exception during PostViewSet.create')
            return response.Response({'detail': 'Internal server error', 'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _unique_slug_for_site(self, *, site_id: int, base_slug: str) -> str:
        slug = base_slug
        i = 2
        from .models import Post
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

        from .models import Post
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
        # Only adjust slug if client explicitly provided a slug in the payload.
        data = serializer.validated_data
        if "slug" in data:
            site_obj_or_id = data.get("site", prev.site_id)
            site_id = getattr(site_obj_or_id, "id", site_obj_or_id)
            title = data.get("title", prev.title)
            desired_slug = data.get("slug") or slugify(title)
            auto_slug = (desired_slug == slugify(title))

            from .models import Post
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
    from api.filters import SafeOrderingFilter
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
    
    @decorators.action(detail=True, methods=["post", "delete"], url_path="preview", permission_classes=[permissions.IsAuthenticated])
    def preview(self, request, pk=None):
        """
        Manage post preview in site's own Jekyll repository.
        
        POST /api/posts/{id}/preview/ - Create/update preview
        DELETE /api/posts/{id}/preview/ - Delete preview
        
        POST Returns:
        {
            "preview_url": "https://<owner>.github.io/<repo_name>/preview/<post_id>/",
            "preview_path": "preview/<post_id>/index.md",
            "commit_sha": "abc123...",
            "content_sha": "def456..."
        }
        
        DELETE Returns:
        {
            "status": "deleted" | "already_absent",
            "preview_path": "preview/<post_id>/index.md",
            "commit_sha": "abc123..." (if deleted)
        }
        """
        from .preview import export_post_to_preview, delete_post_from_preview
        from .exporter import FrontMatterValidationError
        
        post = self.get_object()
        
        logger.info(
            "[preview] Request received: method=%s, post_id=%s, user=%s",
            request.method, post.id, request.user
        )
        
        # Check if preview is enabled
        if not getattr(settings, 'PREVIEW_ENABLED', True):
            return response.Response(
                {'detail': 'Preview functionality is disabled'},
                status=status.HTTP_409_CONFLICT
            )
        
        # Handle DELETE request
        if request.method == 'DELETE':
            try:
                result = delete_post_from_preview(post)
                
                logger.info(
                    "[preview] Deleted preview for post_id=%s: status=%s",
                    post.id, result.get('status')
                )
                
                return response.Response(result, status=status.HTTP_200_OK)
                
            except ValueError as e:
                logger.warning(
                    "[preview] Configuration error for post_id=%s: %s",
                    post.id, str(e)
                )
                return response.Response(
                    {'detail': str(e)},
                    status=status.HTTP_409_CONFLICT
                )
            except Exception as e:
                logger.exception(
                    "[preview] Failed to delete preview for post_id=%s",
                    post.id
                )
                return response.Response(
                    {'detail': f'Preview deletion failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Handle POST request (create/update)
        try:
            result = export_post_to_preview(post)
            
            # Save preview URL permanently on the post
            preview_url = result.get('preview_url')
            if preview_url and post.preview_url != preview_url:
                post.preview_url = preview_url
                post.save(update_fields=['preview_url'])
            
            logger.info(
                "[preview] Created preview for post_id=%s: %s",
                post.id, preview_url
            )
            
            return response.Response(result, status=status.HTTP_201_CREATED)
            
        except FrontMatterValidationError as e:
            logger.warning(
                "[preview] Validation failed for post_id=%s: %s",
                post.id, str(e)
            )
            return response.Response(
                {'detail': f'Front-matter validation failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            logger.warning(
                "[preview] Configuration error for post_id=%s: %s",
                post.id, str(e)
            )
            return response.Response(
                {'detail': str(e)},
                status=status.HTTP_409_CONFLICT
            )
        except Exception as e:
            logger.exception(
                "[preview] Failed to create preview for post_id=%s",
                post.id
            )
            return response.Response(
                {'detail': f'Preview creation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_permissions(self):
        # lettura per tutti, scrittura con permission custom
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsPublisherForWriteOrReadOnly()]

    def partial_update(self, request, *args, **kwargs):
        try:
            post = self.get_object()
            self.check_object_permissions(request, post)
            serializer = self.get_serializer(post, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            # Export handled automatically by post_save signal in blog.signals
            # Return the updated post data
            return response.Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:  # pragma: no cover - defensive
            from rest_framework.exceptions import APIException as DRFAPIException
            if isinstance(exc, DRFAPIException):
                raise
            logger.exception('Unhandled exception during partial_update for post id=%s', kwargs.get('pk'))
            # Prefer structured JSON error for client parsing
            return response.Response({'detail': 'Internal server error', 'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from django.views import View
from django.http import JsonResponse
import threading
import os


class SiteSyncAPIView(generics.GenericAPIView):
    """Start a background sync_repos run for a given site.

    POST body: { "mode": "dry-run"|"apply" }
    Returns: { run_id, log_path, message }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        try:
            site = Site.objects.get(pk=pk)
        except Site.DoesNotExist:
            return response.Response({'detail': 'Site not found'}, status=status.HTTP_404_NOT_FOUND)

        mode = request.data.get('mode') or request.POST.get('mode') or 'dry-run'
        mode = 'apply' if str(mode).lower() == 'apply' else 'dry-run'

        # prepare log file
        logs_dir = os.path.join('reports', 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        run_id = timezone.now().strftime('%Y%m%d%H%M%S')
        log_path = os.path.join(logs_dir, f'sync-{site.slug}-{run_id}.log')

        # Start background thread to run management command
        def _runner(m=mode, lp=log_path, s=site):
            old_env = dict(os.environ)
            os.environ['SYNC_LOG_PATH'] = lp
            try:
                from django.core.management import call_command
                if m == 'apply':
                    call_command('sync_repos', '--apply', '--sites', s.slug)
                else:
                    call_command('sync_repos', '--dry-run', '--sites', s.slug)
            except Exception:
                logger.exception('Background sync run failed for site %s', s.slug)
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()

        # try to return initial tail if any
        initial = None
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as lf:
                    initial = lf.read()[-32768:]
        except Exception:
            initial = None

        return response.Response({'run_id': run_id, 'log_path': log_path, 'message': 'Background sync started', 'initial_log': initial})


class SiteSyncTailAPIView(generics.GenericAPIView):
    """Return tail of log for a given site run. Query param `run_id` or `path` may be used.

    GET /api/blog/sites/<pk>/sync/tail/?run_id=... or &path=...
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        try:
            site = Site.objects.get(pk=pk)
        except Site.DoesNotExist:
            return response.Response({'detail': 'Site not found'}, status=status.HTTP_404_NOT_FOUND)

        run_id = request.query_params.get('run_id')
        path = request.query_params.get('path')
        if not path and run_id:
            logs_dir = os.path.join('reports', 'logs')
            path = os.path.join(logs_dir, f'sync-{site.slug}-{run_id}.log')

        if not path or not os.path.exists(path):
            return response.Response({'status': 'missing', 'log': ''})

        try:
            with open(path, 'r', encoding='utf-8') as lf:
                data = lf.read()
            tail = data[-32768:]
            return response.Response({'status': 'ok', 'log': tail})
        except Exception:
            return response.Response({'status': 'error', 'log': ''}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



