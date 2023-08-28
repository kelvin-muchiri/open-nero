import json
from datetime import datetime, timedelta
from unittest import mock

import pytz
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from apps.orders.models import Order, OrderItem
from apps.twocheckout.models import Twocheckout
from apps.users.models import User


class TwocheckoutWebhookTestCase(FastTenantTestCase):
    """Tests for TwoCheckout webhook"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.order = Order.objects.create(owner=owner)
        order_item = OrderItem(
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=1,
            references=3,
            quantity=1,
            page_price=22,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.order.items.add(order_item, bulk=False)

    def create_twochekout_configs(self):
        """Create TwoCheckout configurations"""
        Twocheckout.objects.create(
            seller_id="901336188",
            secret="MTE1OGI1ZmEtNGUyNS00YTdmLTlmMGYtMjAxZDFhYjcxNjk2",
        )

    def post(self, payload):
        """Make Http POST request"""
        return self.client.post(
            reverse("twocheckout_webhook"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_missing_two_checkout_secret(self):
        """Webhook event is not processed if twocheckout secret is missing"""
        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_unhandled_message_type(self):
        """Unhandled message type is handled correctly"""
        self.create_twochekout_configs()
        response = self.post(
            {
                "vendor_id": "901336188",
                "sale_id": "9093752140230",
                "invoice_id": "9093752140239",
                "message_type": "UNHANDLED_MESSAGE_TYPE",
                "md5_hash": "F632E4175201F649884E3AC2D67E86E1",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch("apps.twocheckout.views.add_payment")
    def test_order_created(self, mock_add_payment):
        """ORDER_CREATED event is handled"""
        self.create_twochekout_configs()
        payload = {
            "invoice_id": "9093752140239",
            "vendor_order_id": str(self.order.id),
            "message_type": "ORDER_CREATED",
            "sale_date_placed": "2019-11-19 12:36:37",
            "sale_id": "9093752140230",
            "invoice_list_amount": 22.00,
            "vendor_id": "901336188",
            "md5_hash": "F632E4175201F649884E3AC2D67E86E1",
        }
        response = self.post(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        time_zone = pytz.timezone("Europe/Athens")
        sale_date_placed = time_zone.localize(
            datetime.strptime(payload["sale_date_placed"], "%Y-%m-%d %H:%M:%S")
        )
        utc_sale_date_placed = sale_date_placed.astimezone(pytz.utc)
        mock_add_payment.assert_called_once_with(
            schema_name=FastTenantTestCase.get_test_schema_name(),
            order=self.order,
            amount_paid=22.00,
            trx_ref_number=payload["sale_id"],
            date_paid=utc_sale_date_placed,
            gateway=Twocheckout.objects.first(),
        )
        # reset mock_add_payment for the next tests
        mock_add_payment.reset_mock()
        # missing vendor_order_id in payload
        response = self.post(
            {
                "invoice_id": "9093752140239",
                "message_type": "ORDER_CREATED",
                "sale_date_placed": "2019-11-19 12:36:37",
                "sale_id": "9093752140230",
                "invoice_list_amount": 22.00,
                "vendor_id": "901336188",
                "md5_hash": "F632E4175201F649884E3AC2D67E86E1",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_add_payment.assert_not_called()

        # invalid vendor_order_id
        response = self.post(
            {
                "invoice_id": "9093752140239",
                "vendor_order_id": "HTYBNIDT",
                "message_type": "ORDER_CREATED",
                "sale_date_placed": "2019-11-20 12:36:37",
                "sale_id": "9093752140230",
                "invoice_list_amount": 22.00,
                "vendor_id": "901336188",
                "md5_hash": "F632E4175201F649884E3AC2D67E86E1",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_add_payment.assert_not_called()
