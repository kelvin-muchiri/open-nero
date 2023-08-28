import datetime
from unittest.mock import Mock, patch

import dateutil.parser
import pytz
from django.contrib.auth import get_user_model
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.orders.models import Order, OrderItem
from apps.paypal.models import Paypal
from apps.paypal.views import PaypalWebhookAPIView

User = get_user_model()

# mock date so that auto_now_add returns mocked date
now_mock = datetime.datetime(2019, 2, 13, 0, 0, 0, tzinfo=pytz.utc)


@patch("apps.paypal.utils.WebhookEvent.verify")
class PaypalWebhookTestCase(FastTenantTestCase):
    """Tests for paypal webhook view"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        with patch("django.utils.timezone.now", Mock(return_value=now_mock)):
            # Unpaid order
            self.order_unpaid = Order.objects.create(
                owner=self.owner, status=Order.Status.UNPAID
            )
            self.order_item = OrderItem.objects.create(
                order=self.order_unpaid,
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
                page_price=2.51,
                due_date=datetime.datetime(2019, 2, 20, 0, 0, 0, tzinfo=pytz.utc),
                status=OrderItem.Status.PENDING,
            )
            self.paypal = Paypal.objects.create(webhook_id="webhook_id")

    def post(self, payload):
        """Method POST"""
        factory = APIRequestFactory()
        request = factory.post("/api/v1/paypal/webhook/", payload)
        request.META["HTTP_PAYPAL_TRANSMISSION_ID"] = "transmission_id"
        request.META["HTTP_PAYPAL_TRANSMISSION_TIME"] = "transmission_time"
        request.META["HTTP_PAYPAL_TRANSMISSION_SIG"] = "transmission_sig"
        request.META["HTTP_PAYPAL_CERT_URL"] = "cert_url"
        request.META["HTTP_PAYPAL_AUTH_ALGO"] = "auth_algo"
        request.tenant = self.tenant
        view = PaypalWebhookAPIView.as_view()
        return view(request)

    @patch("apps.paypal.views.add_payment")
    def test_capture_completed(self, mock_add_payment, mock_sdk_verify):
        """Event PAYMENT.CAPTURE.COMPLETED is handled"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-58D329510W468432D-8HN650336L201105X",
            "create_time": "2019-02-14T21:50:07.940Z",
            "resource_type": "capture",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "summary": "Payment completed for $ 2.51 USD",
            "resource": {
                "custom_id": str(self.order_unpaid.id),
                "amount": {"currency_code": "USD", "value": "2.51"},
                "seller_protection": {
                    "status": "ELIGIBLE",
                    "dispute_categories": [
                        "ITEM_NOT_RECEIVED",
                        "UNAUTHORIZED_TRANSACTION",
                    ],
                },
                "update_time": "2019-02-14T21:49:58Z",
                "create_time": "2019-02-14T21:49:58Z",
                "final_capture": True,
                "seller_receivable_breakdown": {
                    "gross_amount": {"currency_code": "USD", "value": "2.51"},
                    "paypal_fee": {"currency_code": "USD", "value": "0.37"},
                    "net_amount": {"currency_code": "USD", "value": "2.14"},
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/authorizations/7W5147081L658180V",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "27M47624FP291604U",
                "status": "COMPLETED",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_add_payment.assert_called_once_with(
            schema_name=FastTenantTestCase.get_test_schema_name(),
            order=self.order_unpaid,
            amount_paid=payload["resource"]["amount"]["value"],
            trx_ref_number=payload["resource"]["id"],
            date_paid=dateutil.parser.parse(payload["resource"]["create_time"]),
            gateway=self.paypal,
        )

    @patch("apps.paypal.views.refund_payment")
    def test_capture_refunded(self, mock_refund_payment, mock_sdk_verify):
        """Event PAYMENT.CAPTURE.REFUNDED is handled"""
        mock_sdk_verify.return_value = True
        order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        payload = {
            "id": "WH-1GE84257G0350133W-6RW800890C634293G",
            "create_time": "2018-08-15T19:14:04.543Z",
            "resource_type": "refund",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "summary": "A $ 0.99 USD capture payment was refunded",
            "resource": {
                "custom_id": str(order.id),
                "seller_payable_breakdown": {
                    "gross_amount": {"currency_code": "USD", "value": "0.99"},
                    "paypal_fee": {"currency_code": "USD", "value": "0.02"},
                    "net_amount": {"currency_code": "USD", "value": "0.97"},
                    "total_refunded_amount": {
                        "currency_code": "USD",
                        "value": "1.98",
                    },
                },
                "amount": {"currency_code": "USD", "value": "0.99"},
                "update_time": "2018-08-15T12:13:29-07:00",
                "create_time": "2018-08-15T12:13:29-07:00",
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/refunds/1Y107995YT783435V",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/0JF852973C016714D",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "1Y107995YT783435V",
                "status": "COMPLETED",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-1GE84257G0350133W-6RW800890C634293G",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-1GE84257G0350133W-6RW800890C634293G/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        response = self.post(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_refund_payment.assert_called_once_with(
            order=order,
            refunded_amount=payload["resource"]["seller_payable_breakdown"][
                "total_refunded_amount"
            ]["value"],
            trx_ref_number=payload["resource"]["id"],
            date_paid=dateutil.parser.parse(payload["resource"]["create_time"]),
            gateway=self.paypal,
        )

    @patch("apps.paypal.views.decline_payment")
    def test_capture_denied(self, mock_decline_payment, mock_sdk_verify):
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-4SW78779LY2325805-07E03580SX1414828",
            "create_time": "2019-02-14T22:20:08.370Z",
            "resource_type": "capture",
            "event_type": "PAYMENT.CAPTURE.DENIED",
            "summary": "A AUD 2.51 AUD capture payment was denied",
            "resource": {
                "custom_id": str(self.order_unpaid),
                "amount": {"currency_code": "AUD", "value": "2.51"},
                "seller_protection": {
                    "status": "ELIGIBLE",
                    "dispute_categories": [
                        "ITEM_NOT_RECEIVED",
                        "UNAUTHORIZED_TRANSACTION",
                    ],
                },
                "update_time": "2019-02-14T22:20:01Z",
                "create_time": "2019-02-14T22:18:14Z",
                "final_capture": True,
                "seller_receivable_breakdown": {
                    "gross_amount": {"currency_code": "AUD", "value": "2.51"},
                    "net_amount": {"currency_code": "AUD", "value": "2.51"},
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/7NW873794T343360M",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/7NW873794T343360M/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/authorizations/2W543679LP5841156",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "7NW873794T343360M",
                "status": "DECLINED",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-4SW78779LY2325805-07E03580SX1414828",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-4SW78779LY2325805-07E03580SX1414828/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_decline_payment.assert_called_once_with(
            order=self.order_unpaid,
            amount=payload["resource"]["amount"]["value"],
            trx_ref_number=payload["resource"]["id"],
            date_paid=dateutil.parser.parse(payload["resource"]["create_time"]),
            gateway=self.paypal,
        )

    def test_verification_failed(self, mock_sdk_verify):
        """Returns 400 if verification failed"""
        mock_sdk_verify.return_value = False
        payload = {
            "id": "WH-58D329510W468432D-8HN650336L201105X",
            "create_time": "2019-02-14T21:50:07.940Z",
            "resource_type": "capture",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "summary": "Payment completed for $ 2.51 USD",
            "resource": {
                "custom_id": str(self.order_unpaid.id),
                "amount": {"currency_code": "USD", "value": "2.51"},
                "seller_protection": {
                    "status": "ELIGIBLE",
                    "dispute_categories": [
                        "ITEM_NOT_RECEIVED",
                        "UNAUTHORIZED_TRANSACTION",
                    ],
                },
                "update_time": "2019-02-14T21:49:58Z",
                "create_time": "2019-02-14T21:49:58Z",
                "final_capture": True,
                "seller_receivable_breakdown": {
                    "gross_amount": {"currency_code": "USD", "value": "2.51"},
                    "paypal_fee": {"currency_code": "USD", "value": "0.37"},
                    "net_amount": {"currency_code": "USD", "value": "2.14"},
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/authorizations/7W5147081L658180V",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "27M47624FP291604U",
                "status": "COMPLETED",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def default_paypal_config_is_set(self, mock_sdk_verify):
        """Throws 500 if paypal config is missing"""
        mock_sdk_verify.return_value = False
        # no paypal entry
        Paypal.objects.delete()
        payload = {
            "id": "WH-58D329510W468432D-8HN650336L201105X",
            "create_time": "2019-02-14T21:50:07.940Z",
            "resource_type": "capture",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "summary": "Payment completed for $ 2.51 USD",
            "resource": {
                "custom_id": str(self.order_unpaid.id),
                "amount": {"currency_code": "USD", "value": "2.51"},
                "seller_protection": {
                    "status": "ELIGIBLE",
                    "dispute_categories": [
                        "ITEM_NOT_RECEIVED",
                        "UNAUTHORIZED_TRANSACTION",
                    ],
                },
                "update_time": "2019-02-14T21:49:58Z",
                "create_time": "2019-02-14T21:49:58Z",
                "final_capture": True,
                "seller_receivable_breakdown": {
                    "gross_amount": {"currency_code": "USD", "value": "2.51"},
                    "paypal_fee": {"currency_code": "USD", "value": "0.37"},
                    "net_amount": {"currency_code": "USD", "value": "2.14"},
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/27M47624FP291604U/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/authorizations/7W5147081L658180V",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "27M47624FP291604U",
                "status": "COMPLETED",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-58D329510W468432D-8HN650336L201105X/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # paypal entry present but webhook_id null
        Paypal.objects.create(client_id="client_id_no_webhook")
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_unsupported_event(self, mock_sdk_verify):
        """Unsupported event returns 200 status"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-9Y180613C5171350R-3A568107UP261041K",
            "create_time": "2018-08-15T20:03:06.086Z",
            "resource_type": "capture",
            "event_type": "PAYMENT.CAPTURE.PENDING",
            "summary": "Payment pending for $ 2.51 USD",
            "resource": {
                "amount": {"currency_code": "USD", "value": "2.51"},
                "seller_protection": {"status": "NOT_ELIGIBLE"},
                "update_time": "2018-08-15T20:02:40Z",
                "create_time": "2018-08-15T20:02:40Z",
                "final_capture": True,
                "links": [
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/02T21492PP3782704",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v2/payments/captures/02T21492PP3782704/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v2/checkout/orders/8PR65097T8571330M",
                        "rel": "up",
                        "method": "GET",
                    },
                ],
                "id": "02T21492PP3782704",
                "status_details": {"reason": "UNILATERAL"},
                "status": "PENDING",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-9Y180613C5171350R-3A568107UP261041K",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-9Y180613C5171350R-3A568107UP261041K/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }

        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
