import unittest
from unittest.mock import patch

from rest_framework.test import APIRequestFactory

from apps.paypal.utils import verify_webhook_signature


@patch("apps.paypal.utils.WebhookEvent.verify")
class VerifyWebhookSignatureTestCase(unittest.TestCase):
    """Test for Paypal verify webhook signature"""

    def setUp(self) -> None:
        super().setUp()

        self.factory = APIRequestFactory()

    def test_verify(self, mock_sdk_verify):
        """Test verification works"""
        mock_sdk_verify.return_value = "verified"
        request = self.factory.post(
            "/api/v1/paypal/webhook/", {"event_type": "PAYMENT.CAPTURE.COMPLETED"}
        )
        request.META["HTTP_PAYPAL_TRANSMISSION_ID"] = "transmission_id"
        request.META["HTTP_PAYPAL_TRANSMISSION_TIME"] = "transmission_time"
        request.META["HTTP_PAYPAL_TRANSMISSION_SIG"] = "transmission_sig"
        request.META["HTTP_PAYPAL_CERT_URL"] = "cert_url"
        request.META["HTTP_PAYPAL_AUTH_ALGO"] = "auth_algo"

        res = verify_webhook_signature(request, "webhook_id")

        self.assertEqual(res, "verified")
        mock_sdk_verify.assert_called_once_with(
            "transmission_id",
            "transmission_time",
            "webhook_id",
            request.body.decode("utf-8"),
            "cert_url",
            "transmission_sig",
            "auth_algo",
        )
