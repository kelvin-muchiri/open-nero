"""Custom authentication backends"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.db.models import Q
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakAuthenticationError, KeycloakInvalidTokenError

User = get_user_model()


class KeycloakBackend(BaseBackend):
    """Custom backend to authenticate user against a Keycloak server"""

    def authenticate(self, request, **kwargs):
        server_url = kwargs.get("server_url")
        realm_name = kwargs.get("realm_name")
        client_id = kwargs.get("client_id")
        client_secret_key = kwargs.get("client_secret_key")
        token = kwargs.get("token")

        if not server_url or not realm_name or not client_id or not token:
            return None

        keycloak = KeycloakOpenID(
            server_url=server_url,
            realm_name=realm_name,
            client_id=client_id,
            client_secret_key=client_secret_key,
        )
        user_info = None

        try:
            user_info = keycloak.userinfo(token)
        except (KeycloakInvalidTokenError, KeycloakAuthenticationError):
            return None

        if user_info.get("sub"):
            try:
                user = User.objects.get(username=user_info["sub"])

            except User.DoesNotExist:
                # Create a new  user
                user = User.objects.create(username=user_info["sub"])

            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class UsernameorEmailModelBackend(ModelBackend):
    """
    Custom backend to authenticate user by username or email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            return None
        else:
            if user.check_password(password):
                return user
        return None


class ProfileTypeUsernameorEmail(ModelBackend):
    """
    Custom backend to authenticate user by username or email and profile type
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not kwargs.get("profile_type"):
            return None

        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username),
                profile_type=kwargs.get("profile_type"),
            )
        except User.DoesNotExist:
            return None
        else:
            if user.check_password(password):
                return user
        return None
