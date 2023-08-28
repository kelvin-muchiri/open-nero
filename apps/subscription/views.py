import logging

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.mixins import PublicCacheListModelMixin
from apps.common.permissions import IsEmailVerified
from apps.paypal.utils import get_paypal_access_token

from .models import Payment, Paypal, Subscription
from .serializers import PaymentSerializer, SubscriptionSerializer
from .utils import get_active_subscription


class CurrentSubscriptionAPIView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):
        """Method GET"""
        subscription = {"subscription": None}
        latest = Subscription.objects.all().order_by("-created_at").first()

        if latest:
            subscription.update({"subscription": SubscriptionSerializer(latest).data})

        return Response(subscription, status=status.HTTP_200_OK)


class BillingHistoryViewSet(PublicCacheListModelMixin, viewsets.GenericViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = (
        IsAuthenticated,
        IsEmailVerified,
    )


class CancelSubscriptionAPIView(APIView):
    """Cancel active subscription"""

    def post(self, request, *args, **kwargs):
        """Method POST"""
        subscription = get_active_subscription()

        if subscription:
            if Paypal.objects.filter(subscription=subscription).exists():
                if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET:
                    logging.error(
                        "Cancel subscription failed, missing Paypal client id or secret"
                    )

                    return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                try:
                    token = get_paypal_access_token(
                        settings.PAYPAL_API_BASE_URL,
                        settings.PAYPAL_CLIENT_ID,
                        settings.PAYPAL_SECRET,
                    )
                    # pylint: disable=broad-except
                except Exception as err:
                    logging.exception(err)

                    return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                subscription_id = subscription.paypal.paypal_subscription_id

                try:
                    response = requests.post(
                        f"{settings.PAYPAL_API_BASE_URL}/billing/subscriptions/{subscription_id}/cancel",
                        headers=headers,
                    )
                    response.raise_for_status()
                # pylint: disable=broad-except
                except Exception as err:
                    logging.exception(err)

                    return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            subscription.status = Subscription.Status.CANCELLED
            subscription.cancelled_at = timezone.now()
            subscription.save()

        return Response(status=status.HTTP_200_OK)
