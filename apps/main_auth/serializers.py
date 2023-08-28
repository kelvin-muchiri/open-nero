"""Serializers"""

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django_tenants.utils import schema_context
from rest_framework import serializers

from apps.tenants.models import Domain, Tenant
from apps.users.serializers import CreateUserSerializer

from .models import EmailVerification
from .utils import get_full_domain, normalize_domain, normalize_schema_name

User = get_user_model()

# pylint: disable=W0223


class EmailVerificationCodeSendSerializer(serializers.Serializer):
    """Initiate email verification"""

    email = serializers.EmailField()


class EmailVerificationCodeConfirmSerializer(serializers.Serializer):
    """Final step for email verification"""

    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        verification = (
            EmailVerification.objects.filter(email=attrs["email"])
            .order_by("-created_at")
            .first()
        )

        if (
            not verification
            or not check_password(attrs["code"], verification.code)
            or verification.is_expired
        ):
            raise serializers.ValidationError(
                _("Invalid/Expired code"), code="invalid_code"
            )

        return super().validate(attrs)


class StoreOwnerSerializer(CreateUserSerializer, serializers.Serializer):
    """Store owner"""

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(_("Passwords do not match"))

        verification = (
            EmailVerification.objects.filter(email=attrs.get("email"))
            .order_by("-created_at")
            .first()
        )

        if not verification or not verification.is_verified:
            raise serializers.ValidationError(_("Email is not verified"))

        return super().validate(attrs)


class CreateSiteSerializer(serializers.Serializer):
    """Create new tenant site"""

    owner = StoreOwnerSerializer()
    name = serializers.CharField(max_length=60)

    def validate_name(self, value):
        """Validate name"""
        if Domain.objects.filter(
            domain=get_full_domain(normalize_domain(value))
        ).exists():
            raise serializers.ValidationError(_("Site with that name already exists"))

        return value

    @transaction.atomic
    def create(self, validated_data):
        name = validated_data["name"]
        tenant = Tenant.objects.create(
            schema_name=normalize_schema_name(name),
            name=name,
        )
        domain = Domain()
        domain.domain = get_full_domain(normalize_domain(name))
        domain.tenant = tenant
        domain.is_primary = True
        domain.save()

        with schema_context(tenant.schema_name):
            owner_data = validated_data.pop("owner")
            model_user_fields = [f.name for f in User._meta.get_fields()]
            valid_user_data = {
                key: owner_data[key] for key in model_user_fields if key in owner_data
            }
            names = owner_data.pop("full_name").split()
            first_name = names[0]
            last_name = None

            if len(names) > 1:
                last_name = names[1]

            User.objects.create_user(
                username=f"{owner_data.get('email')}.{User.ProfileType.STAFF}",
                first_name=first_name,
                last_name=last_name,
                is_store_owner=True,
                profile_type=User.ProfileType.STAFF,
                is_email_verified=True,
                **valid_user_data,
            )
        return tenant
