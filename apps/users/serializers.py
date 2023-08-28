"""Serializer classes for users app views"""

from contextlib import suppress

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import (
    TokenObtainSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .tasks import (
    send_email_change_verification,
    send_password_reset_email_verification,
    send_signup_email_verification,
)
from .utils import confirm_email_change, confirm_password_reset, confirm_signup_email

# pylint: disable=W0223


User = get_user_model()


class ProfileTypeTokenObtainSerializer(TokenObtainSerializer):
    """Serializer to authenticate user in order obtain token"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["profile_type"] = serializers.CharField()
        self.user = None

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
            "profile_type": attrs["profile_type"],
        }

        with suppress(KeyError):
            authenticate_kwargs["request"] = self.context["request"]

        self.user = authenticate(**authenticate_kwargs)

        if not api_settings.USER_AUTHENTICATION_RULE(self.user):
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"],
                "no_active_account",
            )

        return {}


class ProfileTypeTokenObtainPairSerializer(ProfileTypeTokenObtainSerializer):
    """
    Serializer to obtain token pair
    """

    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)

        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user"] = UserSerializer(self.user).data

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = None

    def validate(self, attrs):
        attrs["refresh"] = self.context["request"].COOKIES.get(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]
        )

        if not attrs["refresh"]:
            raise InvalidToken(
                f"No valid token found in cookie {settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH']}"
            )

        return super().validate(attrs)


class LogoutSerializer(serializers.Serializer):
    def validate(self, attrs):
        attrs["refresh"] = self.context["request"].COOKIES.get(
            settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]
        )

        if not attrs["refresh"]:
            raise InvalidToken(
                f"No valid token found in cookie {settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH']}"
            )

        return super().validate(attrs)

    def save(self, **kwargs):
        token = RefreshToken(
            self.context["request"].COOKIES.get(
                settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"]
            )
        )
        token.blacklist()


class UserSerializer(serializers.ModelSerializer):
    """User model serializer"""

    @transaction.atomic
    def update(self, instance, validated_data):
        send_email_change_verify = False
        send_signup_email_verify = False
        email = validated_data.pop("email", None)

        if email and email != instance.email:
            if User.objects.filter(
                email=email, profile_type=instance.profile_type
            ).exists():
                raise serializers.ValidationError(
                    _("A user with this email already exists"), code="email_exists"
                )
            # if email is already verified, preserve the old email,
            # send verification link to the new email to be updated after user verifies email
            # if email is NOT verified (new user), update email and send
            # a verification link
            if instance.is_email_verified:
                send_email_change_verify = True

            else:
                instance.email = email
                send_signup_email_verify = True

        for (key, value) in validated_data.items():
            setattr(instance, key, value)

        instance.save()

        if send_email_change_verify:
            send_email_change_verification.delay(
                self.context["request"].tenant.schema_name,
                str(instance.pk),
                email,
            )

        if send_signup_email_verify:
            send_signup_email_verification.delay(
                self.context["request"].tenant.schema_name,
                str(instance.pk),
            )

        return instance

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "is_email_verified",
            "profile_type",
        )
        read_only_fields = (
            "is_email_verified",
            "full_name",
            "profile_type",
        )
        extra_kwargs = {
            "email": {"allow_blank": False},
            "first_name": {"allow_blank": False},
        }


class UserInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
        )


class CreateUserSerializer(serializers.Serializer):
    """Create user serializer"""

    full_name = serializers.CharField(max_length=71)
    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=255,
        error_messages={
            "min_length": "Password is too short",
            "max_length": "Password is too long",
        },
    )
    email = serializers.EmailField()


class CustomerSerializer(serializers.ModelSerializer, CreateUserSerializer):
    """Customer serializer"""

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(_("Passwords do not match"))

        if User.objects.filter(
            email=attrs.get("email"), profile_type=User.ProfileType.CUSTOMER
        ).exists():
            raise ValidationError(_("A user with that email already exists"))

        return super().validate(attrs)

    @transaction.atomic
    def create(self, validated_data):
        email = validated_data.get("email")
        names = validated_data.pop("full_name").split()
        user_model_fields = [f.name for f in User._meta.get_fields()]
        valid_user_data = {
            key: validated_data[key]
            for key in user_model_fields
            if key in validated_data
        }
        first_name = names[0]
        last_name = None

        if len(names) > 1:
            last_name = names[1]

        user = User.objects.create_user(
            username=f"{email}.{User.ProfileType.CUSTOMER}",
            profile_type=User.ProfileType.CUSTOMER,
            first_name=first_name,
            last_name=last_name,
            **valid_user_data,
        )
        send_signup_email_verification.delay(
            self.context["request"].tenant.schema_name, str(user.pk)
        )

        return user

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
            "email",
            "is_email_verified",
            "date_joined",
            "last_login",
        )
        read_only_fields = (
            "first_name",
            "last_name",
            "is_email_verified",
            "date_joined",
            "last_login",
        )


class UserEmailExistsSerializer(serializers.Serializer):
    """User email exists check"""

    email = serializers.EmailField()
    profile_type = serializers.ChoiceField(choices=User.ProfileType, required=False)

    def validate(self, attrs):
        if not self.context["request"].user.is_authenticated and not attrs.get(
            "profile_type"
        ):
            raise serializers.ValidationError(_("profile_type is required"))
        return super().validate(attrs)


class ResetPasswordStartSerializer(serializers.Serializer):
    """Reset password start"""

    email = serializers.EmailField()
    profile_type = serializers.ChoiceField(choices=User.ProfileType)

    def save(self, **kwargs):
        email = self.validated_data["email"]
        profile_type = self.validated_data["profile_type"]

        try:
            user = User.objects.get(
                email=email,
                profile_type=profile_type,
            )
        except User.DoesNotExist:
            return

        send_password_reset_email_verification.delay(
            self.context["request"].tenant.schema_name, str(user.pk)
        )


class ResetPasswordEndSerializer(serializers.Serializer):
    """Reset password end"""

    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password1 = serializers.CharField(min_length=6)
    new_password2 = serializers.CharField()

    def validate_new_password2(self, new_password2):
        """Validate field new_password2"""
        new_password1 = self.get_initial().get("new_password1")
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise serializers.ValidationError(_("Passwords do not match"))

        return new_password2

    def validate(self, attrs):
        uidb64 = attrs.get("uidb64")
        token = attrs.get("token")
        new_password = attrs.get("new_password1")

        if not confirm_password_reset(
            self.context["request"].tenant.schema_name, uidb64, token, new_password
        ):
            raise serializers.ValidationError(
                _("Invalid activation credentials"), code="invalid_credentials"
            )

        return super().validate(attrs)


class EmailVerificationEndSerializer(serializers.Serializer):
    """Email verification start"""

    uidb64 = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        uidb64 = attrs.get("uidb64")
        token = attrs.get("token")

        if not confirm_signup_email(
            self.context["request"].tenant.schema_name, uidb64, token
        ):
            raise serializers.ValidationError(
                _("Invalid activation credentials"), code="invalid_credentials"
            )

        return super().validate(attrs)


class ChangePasswordSerializer(serializers.Serializer):
    """Change password"""

    password = serializers.CharField(
        min_length=6,
        max_length=255,
        error_messages={
            "min_length": "Password is too short",
            "max_length": "Password is too long",
        },
    )
    confirm_password = serializers.CharField()

    def validate_confirm_password(self, confirm_password):
        """Validate field confirm_password"""
        password = self.get_initial().get("password")

        if password and confirm_password and password != confirm_password:
            raise serializers.ValidationError(_("Passwords do not match"))

        return confirm_password

    def save(self, **kwargs):
        user = User.objects.get(pk=self.context["request"].user.id)
        user.password = make_password(self.validated_data["password"])
        user.save()


class ConfirmEmailChangeSerializer(serializers.Serializer):
    """Confirm email change"""

    uidb64 = serializers.CharField()
    token = serializers.CharField()
    emailb64 = serializers.CharField()

    def validate(self, attrs):
        uidb64 = attrs.get("uidb64")
        emailb64 = attrs.get("emailb64")
        token = attrs.get("token")

        if not confirm_email_change(
            self.context["request"].tenant.schema_name, uidb64, emailb64, token
        ):
            raise serializers.ValidationError(
                _("Invalid activation credentials"), code="invalid_credentials"
            )

        return super().validate(attrs)


class CustomerDeleteSerializer(serializers.Serializer):
    """Delete customer"""

    password = serializers.CharField()

    def validate(self, attrs):
        if not self.context["request"].user.check_password(attrs.get("password")):
            raise serializers.ValidationError(
                _("Invalid password"), code="invalid_password"
            )

        return super().validate(attrs)

    def save(self, **kwargs):
        user = User.objects.get(pk=self.context["request"].user.id)
        user.delete()


class CaptchaVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()
