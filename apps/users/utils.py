"""users helper methods"""


from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode
from django_tenants.utils import schema_context
from rest_framework.response import Response

from .tasks import send_welcome_email
from .tokens import EmailChangeTokenGenerator, VerifyEmailTokenGenerator

USER = get_user_model()


def get_user_from_encoded_uidb64(uidb64):
    """Return user from decoded uidb64."""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = USER.objects.get(pk=uid)

    # pylint: disable=broad-except
    except Exception:
        user = None

    return user


def confirm_signup_email(schema_name, uidb64, token):
    """Confirm email verification"""
    with schema_context(schema_name):
        user = get_user_from_encoded_uidb64(uidb64)

        if user and VerifyEmailTokenGenerator().check_token(user, token):
            user.is_email_verified = True
            user.save()

            # Send welcome email to new user
            send_welcome_email.delay(schema_name, user.id)

            return True

        return False


def confirm_password_reset(schema_name, uidb64, token, new_password):
    """Confirm password reset and reset user password"""
    with schema_context(schema_name):
        user = get_user_from_encoded_uidb64(uidb64)

        if user and PasswordResetTokenGenerator().check_token(user, token):
            user.set_password(new_password)
            user.save()

            return True

        return False


def confirm_email_change(schema_name, uidb64, emailb64, token):
    """Confirm email change and update user email"""
    with schema_context(schema_name):
        user = get_user_from_encoded_uidb64(uidb64)

        if user and EmailChangeTokenGenerator().check_token(user, token):
            try:
                email = urlsafe_base64_decode(emailb64).decode()
            # pylint: disable=broad-except
            except Exception:
                return False

            user.email = email
            user.save()

            return True

        return False


def set_auth_cookies(response: Response, set_access_token=False):
    """Set cookies for refresh token and optionally access token"""

    def set_cookie(key: str, value: str, expires):
        response.set_cookie(
            key=key,
            value=value,
            expires=expires,
            secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
            httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
            domain=settings.SIMPLE_JWT["AUTH_COOKIE_DOMAIN"],
            max_age=expires.total_seconds(),
        )

    if response.data.get("refresh"):
        set_cookie(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
            response.data["refresh"],
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
        )

        del response.data["refresh"]

    if response.data.get("access") and set_access_token:
        set_cookie(
            settings.SIMPLE_JWT["AUTH_COOKIE"],
            response.data["access"],
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
        )

        del response.data["access"]


def delete_auth_cookie(response: Response):
    def delete_cookie(key: str):
        response.delete_cookie(
            key=key,
            domain=settings.SIMPLE_JWT["AUTH_COOKIE_DOMAIN"],
        )

    delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
    delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE"])
