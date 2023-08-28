"""Views for app endpoints"""

import logging

import dateutil.parser
import requests
from django.conf import settings
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.paypal.utils import get_paypal_access_token, verify_webhook_signature
from apps.subscription.models import Payment, Paypal, Subscription
from apps.tenants.models import Tenant

from .models import EmailVerification
from .serializers import (
    CreateSiteSerializer,
    EmailVerificationCodeConfirmSerializer,
    EmailVerificationCodeSendSerializer,
)
from .tasks import send_email_verification_code

SUBSCRIPTION_ACTIVATED = "BILLING.SUBSCRIPTION.ACTIVATED"
SUBSCRIPTION_CANCELLED = "BILLING.SUBSCRIPTION.CANCELLED"
SUBSCRIPTION_SUSPENDED = "BILLING.SUBSCRIPTION.SUSPENDED"
SUBSCRIPTION_SALE_COMPLETED = "PAYMENT.SALE.COMPLETED"
SUBSCRIPTION_UPDATED = "BILLING.SUBSCRIPTION.UPDATED"


class EmailVerificationCodeSendAPIView(APIView):
    """Send email verification code to user"""

    throttle_scope = "email_send_code"
    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationCodeSendSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        send_email_verification_code.delay(
            request.tenant.schema_name, serializer.data["email"]
        )
        return Response(status=status.HTTP_200_OK)


class EmailVerificationCodeConfirmAPIView(APIView):
    """Confirm email verification code"""

    throttle_scope = "email_confirm_code"
    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationCodeConfirmSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        verification = (
            EmailVerification.objects.filter(
                email=serializer.data["email"], is_verified=False
            )
            .order_by("-created_at")
            .first()
        )
        verification.is_verified = True
        verification.save()

        return Response(status=status.HTTP_200_OK)


class CreateSiteAPIView(APIView):
    """Create a new site"""

    permission_classes = (AllowAny,)
    serializer_class = CreateSiteSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        site = serializer.save()
        domain = site.domains.filter(is_primary=True).first()

        if domain:
            domain = domain.domain
        return Response(
            {"host": domain},
            status=status.HTTP_201_CREATED,
        )


class PayPalSubscriptionWebhookAPIView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        # pylint: disable=too-many-return-statements
        if not settings.PAYPAL_SUBSCRIPTION_WEBHOOK_ID:
            logging.error("Missing Paypal subscription webhook id")

            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not verify_webhook_signature(
            request, settings.PAYPAL_SUBSCRIPTION_WEBHOOK_ID
        ):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if request.data.get("event_type") in [
            SUBSCRIPTION_ACTIVATED,
            SUBSCRIPTION_CANCELLED,
            SUBSCRIPTION_SUSPENDED,
            SUBSCRIPTION_SALE_COMPLETED,
            SUBSCRIPTION_UPDATED,
        ]:
            schema_name = request.data["resource"].get("custom_id")

            if not schema_name:
                logging.error(
                    "Paypal: Subscription webhook data does not contain custom_id"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)

            try:
                Tenant.objects.get(schema_name=schema_name)

            except Tenant.DoesNotExist:
                logging.error("Paypal: Tenant %s does not exists", schema_name)

                return Response(status=status.HTTP_400_BAD_REQUEST)

            with schema_context(schema_name):
                if request.data["event_type"] == SUBSCRIPTION_SALE_COMPLETED:
                    return self.handle_sale_completed(request)

                if request.data["event_type"] == SUBSCRIPTION_ACTIVATED:
                    return self.handle_subscription_activated(request)

                if request.data["event_type"] == SUBSCRIPTION_SUSPENDED:
                    return self.handle_subscription_suspended(request)

                if request.data["event_type"] == SUBSCRIPTION_CANCELLED:
                    return self.handle_subscription_cancelled(request)

                if request.data["event_type"] == SUBSCRIPTION_UPDATED:
                    return self.handle_subscription_updated(request)

        return Response(status=status.HTTP_200_OK)

    def is_subscription_on_trial(self, cycle_executions):
        """Returns true if subscription is on trial, false otherwise"""
        is_on_trial = False
        i = 0
        trial_cycle_found = False

        while i < len(cycle_executions) and not trial_cycle_found:
            cycle = cycle_executions[i]

            if cycle.get("tenure_type") == "TRIAL":
                trial_cycle_found = True

                if cycle.get("cycles_remaining") > 0:
                    is_on_trial = True

            i += 1

        return is_on_trial

    def handle_subscription_activated(self, request):
        """Handle BILLING.SUBSCRIPTION.ACTIVATED event"""
        is_on_trial = self.is_subscription_on_trial(
            request.data["resource"]["billing_info"]["cycle_executions"]
        )
        next_billing_time = dateutil.parser.parse(
            request.data["resource"]["billing_info"]["next_billing_time"]
        )
        subscription_id = request.data["resource"]["id"]
        plan_id = request.data["resource"]["plan_id"]
        paypal_subscription = Paypal.objects.filter(
            paypal_subscription_id=subscription_id
        ).first()

        if not paypal_subscription:
            # create subscription
            subscription = Subscription.objects.create(
                is_on_trial=is_on_trial,
                start_time=dateutil.parser.parse(
                    request.data["resource"]["start_time"]
                ),
                next_billing_time=next_billing_time,
                status=Subscription.Status.ACTIVE,
            )
            Paypal.objects.create(
                subscription=subscription,
                paypal_subscription_id=subscription_id,
                paypal_plan_id=plan_id,
            )
        else:
            paypal_subscription.subscription.next_billing_time = next_billing_time
            paypal_subscription.subscription.status = Subscription.Status.ACTIVE
            paypal_subscription.subscription.save()

        return Response(status=status.HTTP_200_OK)

    def handle_sale_completed(self, request):
        """Handle PAYMENT.SALE.COMPLETED event"""
        subscription_id = request.data["resource"].get("billing_agreement_id")

        if not subscription_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if subscription_id:
            paypal_subscription = Paypal.objects.filter(
                paypal_subscription_id=subscription_id
            ).first()

            # if record not found, then BILLING.SUBSCRIPTION.ACTIVATED has not
            # being received, we return failure so that Paypal can retry again
            # after some time when BILLING.SUBSCRIPTION.ACTIVATED is received
            if not paypal_subscription:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            Payment.objects.create(
                content_object=paypal_subscription,
                amount_paid=request.data["resource"]["amount"]["total"],
                date_paid=dateutil.parser.parse(
                    request.data["resource"]["create_time"]
                ),
            )

        return Response(status=status.HTTP_200_OK)

    def handle_subscription_suspended(self, request):
        """Handle BILLING.SUBSCRIPTION.SUSPENDED event"""
        subscription_id = request.data["resource"]["id"]
        paypal_subscription = Paypal.objects.filter(
            paypal_subscription_id=subscription_id
        ).first()

        if paypal_subscription:
            paypal_subscription.subscription.status = Subscription.Status.SUSPENDED
            paypal_subscription.subscription.save()

        return Response(status=status.HTTP_200_OK)

    def handle_subscription_cancelled(self, request):
        """Handle BILLING.SUBSCRIPTION.CANCELLED event"""
        subscription_id = request.data["resource"]["id"]
        paypal_subscription = Paypal.objects.filter(
            paypal_subscription_id=subscription_id
        ).first()

        if paypal_subscription:
            paypal_subscription.subscription.cancelled_at = dateutil.parser.parse(
                request.data["create_time"]
            )
            paypal_subscription.subscription.status = Subscription.Status.CANCELLED
            paypal_subscription.subscription.save()

        return Response(status=status.HTTP_200_OK)

    def handle_subscription_updated(self, request):
        """Handle "BILLING.SUBSCRIPTION.UPDATED event"""
        subscription_id = request.data["resource"]["id"]

        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET:
            logging.error("Missing Paypal client id or secret")

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

        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(
                f"{settings.PAYPAL_API_BASE_URL}/billing/subscriptions/{subscription_id}",
                headers=headers,
            )
            response.raise_for_status()
        # pylint: disable=broad-except
        except Exception as err:
            logging.exception(err)

            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response_data = response.json()
        paypal_subscription = Paypal.objects.filter(
            paypal_subscription_id=subscription_id
        ).first()

        if paypal_subscription:
            next_billing_time = dateutil.parser.parse(
                response_data["billing_info"]["next_billing_time"]
            )
            paypal_subscription.subscription.next_billing_time = next_billing_time
            paypal_subscription.subscription.is_on_trial = (
                self.is_subscription_on_trial(
                    response_data["billing_info"]["cycle_executions"]
                )
            )
            paypal_subscription.subscription.save()

        return Response(status=status.HTTP_200_OK)
