"""Custom permissions"""
from django_tenants.utils import schema_context
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.subscription.utils import get_active_subscription


class IsEmailVerified(permissions.BasePermission):
    """Allow access only to users whose email is verified"""

    message = "Email not verified"

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_email_verified)


class IsStoreOwner(permissions.BasePermission):
    """Allow access only to the store owner"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_store_owner)


class IsCustomer(permissions.BasePermission):
    """Allow access only to a user of profile_type CUSTOMER"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.profile_type == "CUSTOMER")


class IsStoreStaff(permissions.BasePermission):
    """Allow access only to user of profile_type STAFF"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.profile_type == "STAFF")


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):

        return bool(request.user and obj.owner == request.user)


class IsStoreStaffOrReadOnly(permissions.BasePermission):
    """Allow edit access only to user of profile_type STAFF"""

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        return bool(request.user and request.user.profile_type == "STAFF")


class IsSubscriptionActive(permissions.BasePermission):
    """Allow access only to a tenant whose subscription is active"""

    message = "Inactive subscription"

    def has_permission(self, request, view):
        with schema_context(request.tenant.schema_name):
            current_subscription = get_active_subscription()

            if current_subscription:
                return True
            # We force a 403 response. This is because if the request was not
            # successfully authenticated, and the highest priority authentication
            # class does use WWW-Authenticate headers. — An HTTP 401 Unauthorized response,
            # with an appropriate WWW-Authenticate header will be returned.
            # (https://www.django-rest-framework.org/api-guide/permissions/#how-permissions-are-determined)
            raise PermissionDenied({"detail": self.message})
