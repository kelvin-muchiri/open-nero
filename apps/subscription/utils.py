from django.db.models import Q
from django.utils import timezone

from .models import Subscription


def get_active_subscription():
    """Get the current active subscription"""
    return (
        Subscription.objects.filter(
            Q(status=Subscription.Status.ACTIVE)
            | Q(
                status=Subscription.Status.CANCELLED,
                next_billing_time__gt=timezone.now(),
            )
        )
        .order_by("-created_at")
        .first()
    )
