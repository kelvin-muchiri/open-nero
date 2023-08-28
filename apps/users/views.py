"""
Views for the users app
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import Throttled
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.permissions import IsCustomer, IsStoreStaff, IsSubscriptionActive
from apps.common.utils import validate_google_captcha

from .models import Customer
from .serializers import (
    CaptchaVerificationSerializer,
    ChangePasswordSerializer,
    ConfirmEmailChangeSerializer,
    CookieTokenRefreshSerializer,
    CustomerDeleteSerializer,
    CustomerSerializer,
    EmailVerificationEndSerializer,
    LogoutSerializer,
    ProfileTypeTokenObtainPairSerializer,
    ResetPasswordEndSerializer,
    ResetPasswordStartSerializer,
    UserEmailExistsSerializer,
    UserSerializer,
)
from .tasks import send_signup_email_verification
from .utils import delete_auth_cookie, set_auth_cookies

User = get_user_model()


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """
    Takes a set of user credentials and returns an access and refresh JSON web
    token pair to prove the authentication of those credentials with login
    attempts limited to avoid users from abusing the view
    """

    throttle_scope = "login"
    serializer_class = ProfileTypeTokenObtainPairSerializer

    def throttled(self, request, wait):
        raise Throttled(
            detail={"message": _("Too many recent attempts. Try again later")}
        )


class CookieThrottledTokenObtainPairView(ThrottledTokenObtainPairView):
    """Takes a set of user credentials and sets a http only cookie
    for refresh token.

    Login attempts limited to void abuse
    """

    def finalize_response(self, request, response, *args, **kwargs):
        set_auth_cookies(response, True)

        return super().finalize_response(request, response, *args, **kwargs)


class CookieTokenRefreshView(TokenRefreshView):
    """Takes an access token in the request body. Reads refresh token from the
    cookies header and if valid returns a new access token and resets the refresh token cookie
    """

    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        set_auth_cookies(response, True)

        return super().finalize_response(request, response, *args, **kwargs)


class LogoutAPIView(APIView):
    """Logs out user

    Adds the the refresh token to black list
    """

    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)

    def finalize_response(self, request, response, *args, **kwargs):
        delete_auth_cookie(response)

        return super().finalize_response(request, response, *args, **kwargs)


class ProfileAPIView(generics.RetrieveUpdateAPIView):
    """Logged in user detail view"""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = self.serializer_class(request.user, context={"request": request})
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateCustomerAPIView(generics.CreateAPIView):
    """Create customer"""

    queryset = User.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = (AllowAny,)


class UserEmailExistsPIView(APIView):
    """Check if an email exists"""

    permission_classes = (AllowAny,)
    serializer_class = UserEmailExistsSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        email = serializer.data.get("email")
        response = {"exists": False}

        if request.user.is_authenticated:
            user = User.objects.filter(
                email=email, profile_type=request.user.profile_type
            ).first()

            if (
                user
                and request.user != user
                and request.user.profile_type == user.profile_type
            ):
                response.update({"exists": True})

        else:
            user = User.objects.filter(
                email=email, profile_type=serializer.data["profile_type"]
            ).first()
            if user:
                response.update({"exists": True})

        return Response(response, status=status.HTTP_200_OK)


class ResetPasswordStartAPIView(APIView):
    """Rest password start"""

    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordStartSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)


class ResetPasswordEndAPIView(APIView):
    """Password reset end"""

    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordEndSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_200_OK)


class EmailVerificationEndAPIView(APIView):
    """Email verification confirmation"""

    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationEndSerializer

    def post(self, request, *args, **kwargs):
        """Method method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_200_OK)


class ChangePasswordAPIView(APIView):
    """Change password view"""

    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)


class ResendEmailVerificationAPIView(APIView):
    """Re-send email verification for new users"""

    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticated,
        IsCustomer,
    )

    def get(self, request, *args, **kwargs):
        """Method GET"""
        if not request.user.is_email_verified:
            send_signup_email_verification.delay(
                request.tenant.schema_name, str(request.user.pk)
            )

        return Response(status=status.HTTP_200_OK)


class ConfirmEmailChangeAPIView(APIView):
    """Confirm email change"""

    permission_classes = (AllowAny,)
    serializer_class = ConfirmEmailChangeSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_200_OK)


class CustomerDeleteAccountAPIView(APIView):
    """Delete user account view"""

    queryset = User.objects.none()
    serializer_class = CustomerDeleteSerializer
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsCustomer)

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)


class GoogleRecaptchaAPIView(APIView):
    """Gooogle captch verification view"""

    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = CaptchaVerificationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        if not validate_google_captcha(request.tenant, serializer.data["token"]):
            response = {
                "success": False,
                "message": "Invalid reCAPTCHA. Pease try again",
            }
            return Response(response, status=status.HTTP_200_OK)

        response = {"success": True, "message": "reCAPTCHA Verified"}

        return Response(response, status=status.HTTP_200_OK)
