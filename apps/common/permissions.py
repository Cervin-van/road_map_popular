from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrAdmin(BasePermission):
    """Object-level: read for everyone, write for the author or staff."""

    owner_field = "author_id"

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or getattr(obj, self.owner_field, None) == user.pk)
        )


class IsAnonymous(BasePermission):
    message = "Already authenticated."

    def has_permission(self, request, view):
        return not (request.user and request.user.is_authenticated)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
