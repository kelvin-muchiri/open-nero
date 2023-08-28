import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from rest_framework import status

from apps.common.utils import reverse_querystring
from apps.payments.models import PaymentMethod
from apps.paypal.models import Paypal
from apps.twocheckout.models import Twocheckout


@pytest.mark.django_db
class TestPaymentMethods:
    """Tests for get payment methods"""

    @pytest.fixture
    def create_methods(self):
        PaymentMethod.objects.create(title="Paypal", code="PAYPAL", sort_order=1)
        PaymentMethod.objects.create(title="Braintree", code="BRAINTREE", sort_order=2)

    def test_gets_all_payment_methods(
        self,
        use_tenant_connection,
        fast_tenant_client,
        create_methods,
    ):
        """All payment methods are returned"""
        response = fast_tenant_client.get(reverse("payment_method-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "title": "Paypal",
                    "code": "PAYPAL",
                    "is_active": True,
                    "instructions": None,
                    "meta": None,
                },
                {
                    "title": "Braintree",
                    "code": "BRAINTREE",
                    "is_active": True,
                    "instructions": None,
                    "meta": None,
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_filters_work(
        self,
        use_tenant_connection,
        fast_tenant_client,
    ):
        """Query params filter data"""
        PaymentMethod.objects.create(title="Paypal", code="PAYPAL", sort_order=1)
        PaymentMethod.objects.create(
            title="Braintree", code="BRAINTREE", sort_order=2, is_active=False
        )
        # is_active filter works
        response = fast_tenant_client.get(
            reverse_querystring("payment_method-list", query_kwargs={"is_active": True})
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "title": "Paypal",
                    "code": "PAYPAL",
                    "is_active": True,
                    "instructions": None,
                    "meta": None,
                },
            ],
            cls=DjangoJSONEncoder,
        )
        # code filter works
        response = fast_tenant_client.get(
            reverse_querystring(
                "payment_method-list", query_kwargs={"code": "BRAINTREE"}
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "title": "Braintree",
                    "code": "BRAINTREE",
                    "is_active": False,
                    "instructions": None,
                    "meta": None,
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_meta_data(self, use_tenant_connection, fast_tenant_client):
        """Payment meta data is returned correctly"""
        PaymentMethod.objects.create(title="Paypal", code="PAYPAL", sort_order=1)
        PaymentMethod.objects.create(
            title="2Checkout", code="TWOCHECKOUT", sort_order=2
        )
        Paypal.objects.create(client_id="paypal_client_id", webhook_id="webhook_id")
        Twocheckout.objects.create(seller_id="1238", secret="some_secret")

        response = fast_tenant_client.get(reverse("payment_method-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            [
                {
                    "title": "Paypal",
                    "code": "PAYPAL",
                    "is_active": True,
                    "instructions": None,
                    "meta": {"client_id": "paypal_client_id"},
                },
                {
                    "title": "2Checkout",
                    "code": "TWOCHECKOUT",
                    "is_active": True,
                    "instructions": None,
                    "meta": {"seller_id": "1238"},
                },
            ],
            cls=DjangoJSONEncoder,
        )
