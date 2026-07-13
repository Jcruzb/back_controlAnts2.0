from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsFamilyAdminOrReadOnly(BasePermission):
    """Allow family members to read, but reserve configuration mutations for admins."""

    message = "Only family administrators can modify this resource."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) in getattr(view, "family_member_actions", ()):
            return True
        profile = getattr(request.user, "profile", None)
        return bool(profile and profile.role == "admin")
