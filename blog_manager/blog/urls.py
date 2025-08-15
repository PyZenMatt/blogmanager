from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views
from .views import AuthorViewSet, CategoryViewSet, PostViewSet, TagViewSet

router = DefaultRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"posts", PostViewSet, basename="post")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"authors", AuthorViewSet, basename="author")

urlpatterns = [
    # Posts
    # Comments (opzionale)
    path("comments/", views.CommentListView.as_view(), name="comment-list"),
    path("comments/new/", views.CommentCreateView.as_view(), name="comment-create"),
    # Upload immagini (PostImage)
    path("postimages/", views.PostImageCreateView.as_view(), name="postimage-create"),
]

urlpatterns += router.urls
