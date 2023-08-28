"""
Django REST custom authentication classes
"""

from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import HTTP_HEADER_ENCODING, exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication


class KeycloakTokenAuthentication(BaseAuthentication):
    """
    Custom Django REST authentication class
    """

    def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if a valid signature has been
        supplied .Otherwise returns `None`.
        """
        if "HTTP_AUTHORIZATION" not in request.META:
            return None

        if not settings.KEYCLOAK_SERVER_URL:
            raise Exception("KEYCLOAK_SERVER_URL not found")

        auth_header = request.META.get("HTTP_AUTHORIZATION").split()
        token = auth_header[1] if len(auth_header) == 2 else auth_header[0]
        user = authenticate(
            request,
            token=token,
            server_url=settings.KEYCLOAK_SERVER_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            realm_name=settings.KEYCLOAK_REALM,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
        )

        if user is None:
            raise exceptions.AuthenticationFailed

        return (user, token)


class CookieJWTAuthentication(JWTAuthentication):
    def get_no_credentials_header(self, request):
        """
        Extracts the header requesting to ignore the auth cookie if present

        This is a workaround to ignore credentials even if the auth cookie
        is in request header
        """
        header = request.META.get("HTTP_X_IGNORE_CREDENTIALS")

        if isinstance(header, str):
            # Work around django test client oddness
            header = header.encode(HTTP_HEADER_ENCODING)

        return header

    def authenticate(self, request):
        header = self.get_header(request)

        if header is None:

            if self.get_no_credentials_header(request):
                return None

            raw_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE"]) or None
        else:
            raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
