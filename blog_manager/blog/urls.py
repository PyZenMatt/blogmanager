from django.urls import path
from . import views

urlpatterns = [
    # Sites
    path('sites/', views.SiteListView.as_view(), name='site-list'),
    path('sites/<int:pk>/', views.SiteDetailView.as_view(), name='site-detail'),

    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category-list'),

    # Authors
    path('authors/', views.AuthorListView.as_view(), name='author-list'),

    # Posts
    path('posts/', views.PostListView.as_view(), name='post-list'),
    path('posts/<slug:slug>/', views.PostDetailView.as_view(), name='post-detail'),

    # Comments (opzionale)
    path('comments/', views.CommentListView.as_view(), name='comment-list'),
    path('comments/new/', views.CommentCreateView.as_view(), name='comment-create'),

    # Upload immagini (PostImage)
    path('postimages/', views.PostImageCreateView.as_view(), name='postimage-create'),
]
