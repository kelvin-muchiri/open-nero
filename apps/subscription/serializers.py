from rest_framework import serializers

from .models import Payment, Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "is_on_trial",
            "status",
            "start_time",
            "next_billing_time",
            "is_expired",
        )


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "date_paid",
            "amount_paid",
        )
