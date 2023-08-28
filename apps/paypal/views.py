"""Views"""
import logging

import dateutil.parser
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.utils import add_payment, decline_payment, refund_payment

from .models import Paypal
from .utils import verify_webhook_signature


class PaypalWebhookAPIView(APIView):
    """Paypal webhook"""

    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        """Method POST"""
        paypal = Paypal.objects.filter(is_active=True).first()

        if not paypal or not paypal.webhook_id:
            logging.error("Missing Paypal webhook id")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not verify_webhook_signature(request, paypal.webhook_id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if request.data.get("event_type") in [
            "PAYMENT.CAPTURE.COMPLETED",
            "PAYMENT.CAPTURE.REFUNDED",
            "PAYMENT.CAPTURE.DENIED",
        ]:

            order_id = request.data["resource"].get("custom_id")

            if not order_id:
                logging.error("Paypal: Webhook data does not contain custom_id")
                return Response(status=status.HTTP_400_BAD_REQUEST)

            try:
                order = Order.objects.get(id=order_id)

            except Order.DoesNotExist:
                logging.error("Paypal: Order %s does not exists", order_id)
                return Response(status=status.HTTP_400_BAD_REQUEST)

            transaction_id = request.data["resource"]["id"]
            utc_payment_date = dateutil.parser.parse(
                request.data["resource"]["create_time"]
            )

            if request.data.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
                amount_paid = request.data["resource"]["amount"]["value"]
                add_payment(
                    schema_name=request.tenant.schema_name,
                    order=order,
                    amount_paid=amount_paid,
                    trx_ref_number=transaction_id,
                    date_paid=utc_payment_date,
                    gateway=paypal,
                )

            if request.data.get("event_type") == "PAYMENT.CAPTURE.REFUNDED":
                refunded_amount = request.data["resource"]["seller_payable_breakdown"][
                    "total_refunded_amount"
                ]["value"]
                refund_payment(
                    order=order,
                    refunded_amount=refunded_amount,
                    trx_ref_number=transaction_id,
                    date_paid=utc_payment_date,
                    gateway=paypal,
                )

            if request.data.get("event_type") == "PAYMENT.CAPTURE.DENIED":
                amount = request.data["resource"]["amount"]["value"]
                decline_payment(
                    order=order,
                    amount=amount,
                    trx_ref_number=transaction_id,
                    date_paid=utc_payment_date,
                    gateway=paypal,
                )

        return Response(status=status.HTTP_200_OK)
