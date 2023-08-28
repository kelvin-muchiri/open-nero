"""query param filters"""
import django_filters

from .models import PaymentMethod


class PaymentMethodFiter(django_filters.FilterSet):
    """Filters for model PaymentMethod"""

    class Meta:
        model = PaymentMethod
        fields = (
            "is_active",
            "code",
        )
