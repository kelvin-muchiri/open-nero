"""serializers"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.cart.models import Cart
from apps.common.utils import check_model_or_throw_validation_error
from apps.coupon.models import Coupon
from apps.coupon.utils import is_coupon_valid


class CouponApplicationSerializer(serializers.Serializer):
    """Apply coupon"""

    coupon_code = serializers.CharField(max_length=8)
    cart_id = serializers.CharField()

    def validate_cart_id(self, cart_id):
        return check_model_or_throw_validation_error(Cart, cart_id, "id")

    def validate(self, attrs):
        if not Coupon.objects.filter(code=attrs["coupon_code"]).exists():
            raise serializers.ValidationError(_("Invalid coupon code"))

        coupon = Coupon.objects.get(code=attrs["coupon_code"])
        cart = Cart.objects.get(pk=attrs["cart_id"])

        if not is_coupon_valid(
            coupon,
            cart.subtotal,
            cart.owner,
        ):
            raise serializers.ValidationError(_("Invalid coupon code"))

        if cart.coupon:
            raise serializers.ValidationError(_("Coupon already applied"))

        return super().validate(attrs)


class CouponInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "is_expired",
        )


class CouponSerializer(serializers.ModelSerializer):
    """Default Coupon serializer"""

    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "coupon_type",
            "percent_off",
            "minimum",
            "start_date",
            "end_date",
            "is_expired",
        )


class CodeUniqueSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
