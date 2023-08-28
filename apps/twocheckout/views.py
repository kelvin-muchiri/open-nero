import datetime
import logging

import pytz
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.utils import add_payment

from .ins import Notification
from .models import Twocheckout


class TwocheckoutWebhookAPIView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        gateway = Twocheckout.objects.filter(is_active=True).first()

        if gateway and gateway.secret:
            data = request.data.copy()
            data["secret"] = gateway.secret
            result = Notification.check(data)

            if result.response_code != "SUCCESS":
                logging.error(
                    "Twocheckout failed: Validation failed with code %s",
                    result.response_code,
                )

                return Response(status=status.HTTP_400_BAD_REQUEST)

            message_type = data.get("message_type")

            if message_type == "ORDER_CREATED":
                if not data.get("vendor_order_id"):
                    logging.error("Param vendor_order_id is not set")
                    return Response(status=status.HTTP_400_BAD_REQUEST)

                order_id = data["vendor_order_id"]
                order = None

                try:
                    order = Order.objects.get(id=order_id)

                except Order.DoesNotExist:
                    logging.error(
                        "Twocheckout failed: Order %s does not exists", order_id
                    )
                    return Response(status=status.HTTP_400_BAD_REQUEST)

                except Exception as err:  # pylint: disable=broad-except
                    logging.exception(err)
                    return Response(status=status.HTTP_400_BAD_REQUEST)

                time_zone = pytz.timezone("Europe/Athens")
                sale_date_placed = time_zone.localize(
                    datetime.datetime.strptime(
                        data["sale_date_placed"], "%Y-%m-%d %H:%M:%S"
                    )
                )
                utc_sale_date_placed = sale_date_placed.astimezone(pytz.utc)
                add_payment(
                    schema_name=request.tenant.schema_name,
                    order=order,
                    amount_paid=data.get("invoice_list_amount"),
                    trx_ref_number=data.get("sale_id"),
                    date_paid=utc_sale_date_placed,
                    gateway=gateway,
                )

            return Response(status=status.HTTP_200_OK)

        logging.error("Twocheckout failed: Missing secret")
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
