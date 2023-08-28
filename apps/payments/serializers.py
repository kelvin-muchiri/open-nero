"""serializers"""
from rest_framework import serializers

from apps.paypal.models import Paypal
from apps.twocheckout.models import Twocheckout

from .models import Payment, PaymentMethod


class PaymentSerializer(serializers.ModelSerializer):
    """Payment model serializer"""

    order = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()

    def get_order(self, obj):
        """Override order value"""
        return obj.order.id

    def get_amount_paid(self, obj):
        """Override amount_paid value"""
        return f"${obj.amount_paid}"

    class Meta:
        model = Payment
        fields = (
            "order",
            "amount_paid",
            "date_paid",
        )
        read_only_fields = (
            "order",
            "amount_paid",
            "date_paid",
        )


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = (
            "title",
            "code",
            "is_active",
            "instructions",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["meta"] = None

        if instance.code == PaymentMethod.Code.PAYPAL:
            paypal = Paypal.objects.filter(is_active=True).first()

            if paypal:
                data["meta"] = {"client_id": paypal.client_id}

        if instance.code == PaymentMethod.Code.TWOCHECKOUT:
            twocheckout = Twocheckout.objects.filter(is_active=True).first()

            if twocheckout:
                data["meta"] = {"seller_id": twocheckout.seller_id}

        return data
