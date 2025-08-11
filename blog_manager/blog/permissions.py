from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsPublisherForWriteOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # Lettura per tutti
        if request.method in SAFE_METHODS:
            return True
        # Scrittura solo a staff o gruppo "Publisher"
        u = request.user
        return bool(
            u and u.is_authenticated and (
                getattr(u, "is_staff", False)
                or u.groups.filter(name__iexact="Publisher").exists()
            )
        )
from rest_framework.permissions import BasePermission

class CanPublish(BasePermission):
    """
    Custom permission: Only users in 'Publisher' group can set is_published=True.
    Authors can edit but not publish.
    """
    message = "You do not have permission to publish posts."

    def has_permission(self, request, view):
        # Allow all authenticated users for safe methods
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ['PATCH', 'PUT', 'POST']:
            is_published = request.data.get('is_published')
            if is_published in [True, 'true', 'True', 1, '1']:
                return request.user.groups.filter(name='Publisher').exists()
        return True

    def has_object_permission(self, request, view, obj):
        # Only restrict if trying to publish
        if request.method in ['PATCH', 'PUT', 'POST']:
            is_published = request.data.get('is_published')
            if is_published in [True, 'true', 'True', 1, '1']:
                return request.user.groups.filter(name='Publisher').exists()
        return True
