"""
URL configuration for blog_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings
from rest_framework.routers import DefaultRouter

from django.http import JsonResponse

from blog.views import PostViewSet, SiteViewSet


def root_redirect(request):
    return redirect(
        "writer:post_new" if request.user.is_authenticated else "writer:login"
    )


router = DefaultRouter()
router.register(r"sites", SiteViewSet, basename="site")
router.register(r"posts", PostViewSet, basename="post")

urlpatterns = [
    path("", root_redirect),
    path("admin/", admin.site.urls),
    path("api/contact/", include("contact.urls")),
    path("api/blog/", include("blog.urls")),
    # Expose /api/sites/ (list/create) and /api/sites/<id>/ via DRF router
    path("api/", include((router.urls, "api"), namespace="api")),
    path("api/health/", lambda r: JsonResponse({"ok": True}, status=200)),
    path("writer/", include("writer.urls", namespace="writer")),
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=False)),
]
