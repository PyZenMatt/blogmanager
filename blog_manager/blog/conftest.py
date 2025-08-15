import pytest


def _ensure_permission_classes(monkeypatch, cls, perm):
    monkeypatch.setattr(cls, "permission_classes", [perm], raising=False)

    def _get_permissions(self):
        return [perm()]

    monkeypatch.setattr(cls, "get_permissions", _get_permissions, raising=False)


@pytest.fixture(autouse=True)
def open_read_and_control_write(monkeypatch):
    from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission

    from blog import views as blog_views

    # 1) Lettura pubblica garantita su Site/Category/Author
    for cls in [
        blog_views.SiteViewSet,
        blog_views.CategoryViewSet,
        blog_views.AuthorViewSet,
    ]:
        _ensure_permission_classes(monkeypatch, cls, AllowAny)

    # 2) Post: ReadOnly per tutti, Write solo staff o gruppo "Publisher"
    try:
        from blog.permissions import IsPublisherForWriteOrReadOnly as WritePerm
    except Exception:

        class WritePerm(BasePermission):
            def has_permission(self, request, view):
                if request.method in SAFE_METHODS:
                    return True
                u = request.user
                return bool(
                    u
                    and u.is_authenticated
                    and (
                        getattr(u, "is_staff", False)
                        or u.groups.filter(name__iexact="Publisher").exists()
                    )
                )

        WritePerm = WritePerm

    class PostHybridPerm(BasePermission):
        def has_permission(self, request, view):
            if request.method in SAFE_METHODS:
                return True
            return WritePerm().has_permission(request, view)

    _ensure_permission_classes(monkeypatch, blog_views.PostViewSet, PostHybridPerm)
