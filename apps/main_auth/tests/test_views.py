"""Tests for views module"""

import json
from unittest.mock import patch

import dateutil.parser
import responses
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.main_auth.views import PayPalSubscriptionWebhookAPIView
from apps.subscription.models import Payment, Paypal, Subscription
from apps.tenants.models import Domain, Tenant

from ..models import EmailVerification

User = get_user_model()


class CreateSiteTestCase(FastTenantTestCase):
    """Test cases for create site endpoint"""

    @staticmethod
    def get_test_tenant_domain():
        return "tenant.createsite.com"

    @staticmethod
    def get_test_schema_name():
        return "public"

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        EmailVerification.objects.create(
            email="bob@example.com", code="1234", is_verified=True
        )
        self.valid_payload = {
            "owner": {
                "full_name": "Bob Austin",
                "password": "passwordXmen",
                "confirm_password": "passwordXmen",
                "email": "bob@example.com",
            },
            "name": "essay masters",
        }

    def post(self, payload=None):
        """Method POST"""

        if payload is None:
            payload = {}

        return self.client.post(
            reverse(
                "create_site",
                urlconf=settings.PUBLIC_SCHEMA_URLCONF,
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    @override_settings(TENANT_DEFAULT_DOMAIN_SUFFIX=".example.com")
    @override_settings(TENANT_DEFAULT_DOMAIN_PREFIX="api.")
    def test_valid_payload(self):
        """Store is created with valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, {"host": "api.essay-masters.example.com"})
        site = Tenant.objects.get(schema_name="essay_masters")
        self.assertEqual(
            site.domains.filter(is_primary=True).first().domain,
            "api.essay-masters.example.com",
        )
        self.assertEqual(site.name, "essay masters")

        with schema_context("essay_masters"):
            owner = User.objects.get(username="bob@example.com.STAFF")
            self.assertEqual(owner.first_name, "Bob")
            self.assertEqual(owner.last_name, "Austin")
            self.assertEqual(owner.email, "bob@example.com")
            self.assertEqual(owner.profile_type, User.ProfileType.STAFF)
            self.assertTrue(owner.is_store_owner)
            self.assertTrue(owner.is_email_verified)
            self.assertTrue(owner.check_password("passwordXmen"))

    def test_owner_required(self):
        """owner is required"""
        response = self.post({"name": "quick essay"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post({"owner": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_site_name_required(self):
        """name is required"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                }
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(TENANT_DEFAULT_DOMAIN_SUFFIX=".example.com")
    @override_settings(TENANT_DEFAULT_DOMAIN_PREFIX="api.")
    def test_site_unique(self):
        """A site with a duplicate domain name should not be registered"""
        tenant = Tenant.objects.create(
            schema_name="essay_shark",
            name="Essay shark",
        )
        domain = Domain()
        domain.domain = "api.essay-shark.example.com"
        domain.tenant = tenant
        domain.is_primary = True
        domain.save()
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "essay-shark",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "essay shark",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "Essay Shark",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "ESSAY SHARK",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "$$$$@@#essay$$$shark$$###",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "essayshark",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_passwords_match(self):
        """password and confirm_password must match"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "hello",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "peponi",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_email_verification(self):
        """Site owner's email must be verified"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "unverified@example.com",
                },
                "name": "peponi",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_minimum_password_length(self):
        """Ensure the minimum password length of 6 chars is enforced"""
        # Test 5 chars
        password = "12345"
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": password,
                    "confirm_password": password,
                    "email": "bob@example.com",
                },
                "name": "test_password_min",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Test exact 6 chars
        password = password[:] + "6"
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": password,
                    "confirm_password": password,
                    "email": "bob@example.com",
                },
                "name": "test_password_min",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_maximum_password_length(self):
        """Ensure the maximum password length of 255 chars is enforced"""
        # Test 256 chars
        password = "Lorem ipsum dolor sit amet, consectetur adipiscing \
            elit, sed do eiusmod tempor incididunt ut labore et dolore magna \
                aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco \
                    laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure doloruit"
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": password,
                    "confirm_password": password,
                    "email": "bob@example.com",
                },
                "name": "test_password_max",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Test exact 255 chars
        password = password[:255]
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": password,
                    "confirm_password": password,
                    "email": "bob@example.com",
                },
                "name": "test_password_max",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_full_name_length(self):
        """Max length of 70 chars is not exceeded"""
        # 72 chars fails
        full_name = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmodo"
        )
        response = self.post(
            {
                "owner": {
                    "full_name": full_name,
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_max_full_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # 71 chars
        full_name = full_name[:71]
        response = self.post(
            {
                "owner": {
                    "full_name": full_name,
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_max_full_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_site_name_length(self):
        """Max length is 60 chars"""
        # test 61 chars
        name = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sedi"
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": name,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # test 60 chars
        name = name[:60]
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": name,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_name_required(self):
        """Owner full_name is required"""
        response = self.post(
            {
                "owner": {
                    "full_name": "",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_owner_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_owner_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_email_required(self):
        """Owner email is required"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "",
                },
                "name": "test_owner_email",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                },
                "name": "test_owner_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_password_required(self):
        """Owner password is required"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_owner_password",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "test_owner_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_full_name_variations(self):
        """Different variations of full name are saved correctly"""
        response = self.post(
            {
                "owner": {
                    "full_name": "Bob",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "owner_one_name",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        with schema_context("owner_one_name"):
            one_name = User.objects.get(email="bob@example.com")
            self.assertEqual(one_name.first_name, "Bob")
            self.assertIsNone(one_name.last_name)
            self.assertIsNone(one_name.other_names)

        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "owner_two_names",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        with schema_context("owner_two_names"):
            two_names = User.objects.get(email="bob@example.com")
            self.assertEqual(two_names.first_name, "Bob")
            self.assertEqual(two_names.last_name, "Austin")
            self.assertIsNone(two_names.other_names)

        response = self.post(
            {
                "owner": {
                    "full_name": "Bob Austin Bush",
                    "password": "passwordXmen",
                    "confirm_password": "passwordXmen",
                    "email": "bob@example.com",
                },
                "name": "owner_multiple_names",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        with schema_context("owner_multiple_names"):
            multiple_names = User.objects.get(email="bob@example.com")
            self.assertEqual(multiple_names.first_name, "Bob")
            self.assertEqual(multiple_names.last_name, "Austin")
            self.assertIsNone(multiple_names.other_names)


@patch("apps.paypal.utils.WebhookEvent.verify")
class PaypalSubscriptionWebookTestCase(FastTenantTestCase):
    """Test cases paypal subscription webhook endpoint"""

    @staticmethod
    def get_test_tenant_domain():
        return "tenant.test_subscription.com"

    @classmethod
    def setUpClass(cls):
        """Copied from FastTenantTestCase.setUpClass"""
        cls.add_allowed_test_domain()
        tenant_model = get_tenant_model()

        test_schema_name = cls.get_test_schema_name()
        if tenant_model.objects.filter(schema_name=test_schema_name).exists():
            cls.tenant = tenant_model.objects.filter(
                schema_name=test_schema_name
            ).first()
            cls.use_existing_tenant()
        else:
            cls.setup_test_tenant_and_domain()

        connection.set_tenant(cls.tenant)

        # create our test subscription tenant
        tenant = Tenant.objects.create(
            schema_name="test_subscription", name="Test subscription"
        )
        tenant.domains.create(domain="test.subscription.com")

    @staticmethod
    def get_test_schema_name():
        return "public"

    def post(self, payload):
        """Method POST"""
        factory = APIRequestFactory()
        request = factory.post("/api/v1/auth/paypal-webhook/subscription/", payload)
        request.META["HTTP_PAYPAL_TRANSMISSION_ID"] = "transmission_id"
        request.META["HTTP_PAYPAL_TRANSMISSION_TIME"] = "transmission_time"
        request.META["HTTP_PAYPAL_TRANSMISSION_SIG"] = "transmission_sig"
        request.META["HTTP_PAYPAL_CERT_URL"] = "cert_url"
        request.META["HTTP_PAYPAL_AUTH_ALGO"] = "auth_algo"
        view = PayPalSubscriptionWebhookAPIView.as_view()
        return view(request)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID=None)
    def test_paypal_webhook_id_required(self, mock_sdk_verify):
        """Config PAYPAL_SUBSCRIPTION_WEBHOOK_ID is required"""
        mock_sdk_verify.return_value = True
        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_invalid_signature(self, mock_sdk_verify):
        """Invalid signature is handled"""
        mock_sdk_verify.return_value = False
        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_event_no_handler(self, mock_sdk_verify):
        """Event is submitted that does not have a handler"""
        mock_sdk_verify.return_value = True
        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_on_trial_activated(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.ACTIVATED for a subscription on trial"""
        # trial not completed
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-77687562XN25889J8-8Y6T55435R66168T6",
            "create_time": "2018-19-12T22:20:32.000Z",
            "resource_type": "subscription",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "summary": "A billing agreement was activated.",
            "resource": {
                "custom_id": "test_subscription",
                "quantity": "20",
                "subscriber": {
                    "name": {"given_name": "John", "surname": "Doe"},
                    "email_address": "customer@example.com",
                    "shipping_address": {
                        "name": {"full_name": "John Doe"},
                        "address": {
                            "address_line_1": "2211 N First Street",
                            "address_line_2": "Building 17",
                            "admin_area_2": "San Jose",
                            "admin_area_1": "CA",
                            "postal_code": "95131",
                            "country_code": "US",
                        },
                    },
                },
                "create_time": "2018-12-10T21:20:49Z",
                "shipping_amount": {"currency_code": "USD", "value": "10.00"},
                "start_time": "2018-11-01T00:00:00Z",
                "update_time": "2018-12-10T21:20:49Z",
                "billing_info": {
                    "outstanding_balance": {"currency_code": "USD", "value": "10.00"},
                    "cycle_executions": [
                        {
                            "tenure_type": "TRIAL",
                            "sequence": 1,
                            "cycles_completed": 1,
                            "cycles_remaining": 1,
                            "current_pricing_scheme_version": 1,
                        },
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 2,
                            "cycles_completed": 0,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 2,
                        },
                    ],
                    "last_payment": {
                        "amount": {"currency_code": "USD", "value": "15.00"},
                        "time": "2018-12-01T01:20:49Z",
                    },
                    "next_billing_time": "2019-01-01T00:20:49Z",
                    "final_payment_time": "2020-01-01T00:20:49Z",
                    "failed_payments_count": 2,
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "edit",
                        "method": "PATCH",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                        "rel": "suspend",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                        "rel": "cancel",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
                "id": "I-BW452GLLEP1G",
                "plan_id": "P-5ML4271244454362WXNWU5NQ",
                "auto_renewal": True,
                "status": "ACTIVE",
                "status_update_time": "2018-12-10T21:20:49Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6/resend",
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

        with schema_context("test_subscription"):
            self.assertEqual(Subscription.objects.all().count(), 1)
            subscription = Subscription.objects.first()
            self.assertTrue(subscription.is_on_trial)
            self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
            self.assertEqual(
                subscription.next_billing_time,
                dateutil.parser.parse(
                    payload["resource"]["billing_info"]["next_billing_time"]
                ),
            )
            self.assertEqual(
                subscription.paypal.paypal_subscription_id, payload["resource"]["id"]
            )
            self.assertEqual(
                subscription.paypal.paypal_plan_id, payload["resource"]["plan_id"]
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_with_trial_complete_activated(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.ACTIVATED for a subscription whose trial is complete"""
        # trial not completed
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-77687562XN25889J8-8Y6T55435R66168T6",
            "create_time": "2018-19-12T22:20:32.000Z",
            "resource_type": "subscription",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "summary": "A billing agreement was activated.",
            "resource": {
                "custom_id": "test_subscription",
                "quantity": "20",
                "subscriber": {
                    "name": {"given_name": "John", "surname": "Doe"},
                    "email_address": "customer@example.com",
                    "shipping_address": {
                        "name": {"full_name": "John Doe"},
                        "address": {
                            "address_line_1": "2211 N First Street",
                            "address_line_2": "Building 17",
                            "admin_area_2": "San Jose",
                            "admin_area_1": "CA",
                            "postal_code": "95131",
                            "country_code": "US",
                        },
                    },
                },
                "create_time": "2018-12-10T21:20:49Z",
                "shipping_amount": {"currency_code": "USD", "value": "10.00"},
                "start_time": "2018-11-01T00:00:00Z",
                "update_time": "2018-12-10T21:20:49Z",
                "billing_info": {
                    "outstanding_balance": {"currency_code": "USD", "value": "10.00"},
                    "cycle_executions": [
                        {
                            "tenure_type": "TRIAL",
                            "sequence": 1,
                            "cycles_completed": 1,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 1,
                        },
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 2,
                            "cycles_completed": 0,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 2,
                        },
                    ],
                    "last_payment": {
                        "amount": {"currency_code": "USD", "value": "15.00"},
                        "time": "2018-12-01T01:20:49Z",
                    },
                    "next_billing_time": "2019-01-01T00:20:49Z",
                    "final_payment_time": "2020-01-01T00:20:49Z",
                    "failed_payments_count": 2,
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "edit",
                        "method": "PATCH",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                        "rel": "suspend",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                        "rel": "cancel",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
                "id": "I-BW452GLLEP1G",
                "plan_id": "P-5ML4271244454362WXNWU5NQ",
                "auto_renewal": True,
                "status": "ACTIVE",
                "status_update_time": "2018-12-10T21:20:49Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6/resend",
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

        with schema_context("test_subscription"):
            self.assertEqual(Subscription.objects.all().count(), 1)
            subscription = Subscription.objects.first()
            self.assertFalse(subscription.is_on_trial)
            self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
            self.assertEqual(
                subscription.next_billing_time,
                dateutil.parser.parse(
                    payload["resource"]["billing_info"]["next_billing_time"]
                ),
            )
            self.assertEqual(
                subscription.paypal.paypal_subscription_id, payload["resource"]["id"]
            )
            self.assertEqual(
                subscription.paypal.paypal_plan_id, payload["resource"]["plan_id"]
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_not_on_trial_activated(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.ACTIVATED for a subscription not on trial"""
        # subscription on trial period
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-77687562XN25889J8-8Y6T55435R66168T6",
            "create_time": "2018-19-12T22:20:32.000Z",
            "resource_type": "subscription",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "summary": "A billing agreement was activated.",
            "resource": {
                "custom_id": "test_subscription",
                "quantity": "20",
                "subscriber": {
                    "name": {"given_name": "John", "surname": "Doe"},
                    "email_address": "customer@example.com",
                    "shipping_address": {
                        "name": {"full_name": "John Doe"},
                        "address": {
                            "address_line_1": "2211 N First Street",
                            "address_line_2": "Building 17",
                            "admin_area_2": "San Jose",
                            "admin_area_1": "CA",
                            "postal_code": "95131",
                            "country_code": "US",
                        },
                    },
                },
                "create_time": "2018-12-10T21:20:49Z",
                "shipping_amount": {"currency_code": "USD", "value": "10.00"},
                "start_time": "2018-11-01T00:00:00Z",
                "update_time": "2018-12-10T21:20:49Z",
                "billing_info": {
                    "outstanding_balance": {"currency_code": "USD", "value": "10.00"},
                    "cycle_executions": [
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 1,
                            "cycles_completed": 1,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 2,
                        },
                    ],
                    "last_payment": {
                        "amount": {"currency_code": "USD", "value": "15.00"},
                        "time": "2018-12-01T01:20:49Z",
                    },
                    "next_billing_time": "2019-01-01T00:20:49Z",
                    "final_payment_time": "2020-01-01T00:20:49Z",
                    "failed_payments_count": 2,
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "edit",
                        "method": "PATCH",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                        "rel": "suspend",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                        "rel": "cancel",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
                "id": "I-BW452GLLEP1G",
                "plan_id": "P-5ML4271244454362WXNWU5NQ",
                "auto_renewal": True,
                "status": "ACTIVE",
                "status_update_time": "2018-12-10T21:20:49Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6/resend",
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

        with schema_context("test_subscription"):
            self.assertEqual(Subscription.objects.all().count(), 1)
            subscription = Subscription.objects.first()
            self.assertFalse(subscription.is_on_trial)
            self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
            self.assertEqual(
                subscription.next_billing_time,
                dateutil.parser.parse(
                    payload["resource"]["billing_info"]["next_billing_time"]
                ),
            )
            self.assertEqual(
                subscription.paypal.paypal_subscription_id, payload["resource"]["id"]
            )
            self.assertEqual(
                subscription.paypal.paypal_plan_id, payload["resource"]["plan_id"]
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_suspended_subscription_activated(self, mock_sdk_verify):
        """BILLING.SUBSCRIPTION.ACTIVATED for a an already existing subscription"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-77687562XN25889J8-8Y6T55435R66168T6",
            "create_time": "2018-19-12T22:20:32.000Z",
            "resource_type": "subscription",
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "summary": "A billing agreement was activated.",
            "resource": {
                "custom_id": "test_subscription",
                "quantity": "20",
                "subscriber": {
                    "name": {"given_name": "John", "surname": "Doe"},
                    "email_address": "customer@example.com",
                    "shipping_address": {
                        "name": {"full_name": "John Doe"},
                        "address": {
                            "address_line_1": "2211 N First Street",
                            "address_line_2": "Building 17",
                            "admin_area_2": "San Jose",
                            "admin_area_1": "CA",
                            "postal_code": "95131",
                            "country_code": "US",
                        },
                    },
                },
                "create_time": "2018-12-10T21:20:49Z",
                "shipping_amount": {"currency_code": "USD", "value": "10.00"},
                "start_time": "2018-11-01T00:00:00Z",
                "update_time": "2018-12-10T21:20:49Z",
                "billing_info": {
                    "outstanding_balance": {"currency_code": "USD", "value": "10.00"},
                    "cycle_executions": [
                        {
                            "tenure_type": "TRIAL",
                            "sequence": 1,
                            "cycles_completed": 1,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 1,
                        },
                        {
                            "tenure_type": "REGULAR",
                            "sequence": 2,
                            "cycles_completed": 0,
                            "cycles_remaining": 0,
                            "current_pricing_scheme_version": 2,
                        },
                    ],
                    "last_payment": {
                        "amount": {"currency_code": "USD", "value": "15.00"},
                        "time": "2018-12-01T01:20:49Z",
                    },
                    "next_billing_time": "2019-02-01T00:20:49Z",
                    "final_payment_time": "2020-01-01T00:20:49Z",
                    "failed_payments_count": 2,
                },
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                        "rel": "edit",
                        "method": "PATCH",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                        "rel": "suspend",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                        "rel": "cancel",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                        "rel": "capture",
                        "method": "POST",
                    },
                ],
                "id": "I-BW452GLLEP1G",
                "plan_id": "P-5ML4271244454362WXNWU5NQ",
                "auto_renewal": True,
                "status": "ACTIVE",
                "status_update_time": "2018-12-10T21:20:49Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-77687562XN25889J8-8Y6T55435R66168T6/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
            "resource_version": "2.0",
        }
        with schema_context("test_subscription"):
            subscription = Subscription.objects.create(
                is_on_trial=False,
                status=Subscription.Status.SUSPENDED,
                start_time=dateutil.parser.parse(
                    payload["resource"]["start_time"],
                ),
                next_billing_time=dateutil.parser.parse(
                    "2019-01-01T00:20:49Z",
                ),
            )
            Paypal.objects.create(
                subscription=subscription,
                paypal_subscription_id=payload["resource"]["id"],
            )

        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with schema_context("test_subscription"):
            subscription.refresh_from_db()
            self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
            self.assertEqual(
                subscription.next_billing_time,
                dateutil.parser.parse(
                    payload["resource"]["billing_info"]["next_billing_time"]
                ),
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_sale_completed(self, mock_sdk_verify):
        """Event PAYMENT.SALE.COMPLETED"""
        mock_sdk_verify.return_value = True

        with schema_context("test_subscription"):
            subscription = Subscription.objects.create(
                is_on_trial=False,
                status=Subscription.Status.ACTIVE,
                start_time=dateutil.parser.parse(
                    "2018-10-01T00:20:49Z",
                ),
                next_billing_time=dateutil.parser.parse(
                    "2019-01-01T00:20:49Z",
                ),
            )
            paypal_subscription = Paypal.objects.create(
                subscription=subscription,
                paypal_subscription_id="paypal_subscription_id",
            )

        payload = {
            "id": "WH-2WR32451HC0233532-67976317FL4543714",
            "create_time": "2014-10-23T17:23:52Z",
            "resource_type": "sale",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "summary": "A successful sale payment was made for $ 0.48 USD",
            "resource": {
                "billing_agreement_id": "paypal_subscription_id",
                "custom_id": "test_subscription",
                "parent_payment": "PAY-1PA12106FU478450MKRETS4A",
                "update_time": "2014-10-23T17:23:04Z",
                "amount": {"total": "0.48", "currency": "USD"},
                "payment_mode": "ECHECK",
                "create_time": "2014-10-23T17:22:56Z",
                "clearing_time": "2014-10-30T07:00:00Z",
                "protection_eligibility_type": "ITEM_NOT_RECEIVED_ELIGIBLE,UNAUTHORIZED_PAYMENT_ELIGIBLE",
                "protection_eligibility": "ELIGIBLE",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/payment/PAY-1PA12106FU478450MKRETS4A",
                        "rel": "parent_payment",
                        "method": "GET",
                    },
                ],
                "id": "80021663DE681814L",
                "state": "completed",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with schema_context("test_subscription"):
            self.assertEqual(Payment.objects.all().count(), 1)
            payment = Payment.objects.first()
            self.assertEqual(payment.content_object, paypal_subscription)
            self.assertEqual(
                str(payment.amount_paid), payload["resource"]["amount"]["total"]
            )
            self.assertEqual(
                payment.date_paid,
                dateutil.parser.parse(payload["resource"]["create_time"]),
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_sale_completed_subscription_does_not_exist(self, mock_sdk_verify):
        """Event PAYMENT.SALE.COMPLETE if subscription not found

        Should return HTTP status code 400 so that Paypal can retry after
        some time as we wait for BILLING.SUBSCRIPTION.ACTIVATED webhook
        to be received
        """
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-2WR32451HC0233532-67976317FL4543714",
            "create_time": "2014-10-23T17:23:52Z",
            "resource_type": "sale",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "summary": "A successful sale payment was made for $ 0.48 USD",
            "resource": {
                "billing_agreement_id": "paypal_subscription_id",
                "custom_id": "test_subscription",
                "parent_payment": "PAY-1PA12106FU478450MKRETS4A",
                "update_time": "2014-10-23T17:23:04Z",
                "amount": {"total": "0.48", "currency": "USD"},
                "payment_mode": "ECHECK",
                "create_time": "2014-10-23T17:22:56Z",
                "clearing_time": "2014-10-30T07:00:00Z",
                "protection_eligibility_type": "ITEM_NOT_RECEIVED_ELIGIBLE,UNAUTHORIZED_PAYMENT_ELIGIBLE",
                "protection_eligibility": "ELIGIBLE",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/payment/PAY-1PA12106FU478450MKRETS4A",
                        "rel": "parent_payment",
                        "method": "GET",
                    },
                ],
                "id": "80021663DE681814L",
                "state": "completed",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with schema_context("test_subscription"):
            self.assertEqual(Payment.objects.all().count(), 0)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_sale_completed_billing_agreement_id_missing(self, mock_sdk_verify):
        """Event PAYMENT.SALE.COMPLETE with billing_agreement_id missing

        Should return HTTP status code 400 so that Paypal can retry after
        some time as we wait for BILLING.SUBSCRIPTION.ACTIVATED webhook
        to be received
        """
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-2WR32451HC0233532-67976317FL4543714",
            "create_time": "2014-10-23T17:23:52Z",
            "resource_type": "sale",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "summary": "A successful sale payment was made for $ 0.48 USD",
            "resource": {
                "custom_id": "test_subscription",
                "parent_payment": "PAY-1PA12106FU478450MKRETS4A",
                "update_time": "2014-10-23T17:23:04Z",
                "amount": {"total": "0.48", "currency": "USD"},
                "payment_mode": "ECHECK",
                "create_time": "2014-10-23T17:22:56Z",
                "clearing_time": "2014-10-30T07:00:00Z",
                "protection_eligibility_type": "ITEM_NOT_RECEIVED_ELIGIBLE,UNAUTHORIZED_PAYMENT_ELIGIBLE",
                "protection_eligibility": "ELIGIBLE",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L",
                        "rel": "self",
                        "method": "GET",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/sale/80021663DE681814L/refund",
                        "rel": "refund",
                        "method": "POST",
                    },
                    {
                        "href": "https://api.paypal.com/v1/payments/payment/PAY-1PA12106FU478450MKRETS4A",
                        "rel": "parent_payment",
                        "method": "GET",
                    },
                ],
                "id": "80021663DE681814L",
                "state": "completed",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-2WR32451HC0233532-67976317FL4543714/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with schema_context("test_subscription"):
            self.assertEqual(Payment.objects.all().count(), 0)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_suspended(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.SUSPENDED is handled"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-0RD44774E41721427-487281337V896051W",
            "create_time": "2016-04-28T11:37:14Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "summary": "A billing subscription was suspended",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-PE7JWXKGVN0R",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-0RD44774E41721427-487281337V896051W",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-0RD44774E41721427-487281337V896051W/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        with schema_context("test_subscription"):
            subscription = Subscription.objects.create(
                is_on_trial=False,
                status=Subscription.Status.ACTIVE,
                start_time=dateutil.parser.parse(
                    "2016-01-01T00:20:49Z",
                ),
                next_billing_time=dateutil.parser.parse(
                    "2016-03-01T00:20:49Z",
                ),
            )
            Paypal.objects.create(
                subscription=subscription,
                paypal_subscription_id=payload["resource"]["id"],
            )
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with schema_context("test_subscription"):
            subscription.refresh_from_db()
            self.assertEqual(subscription.status, Subscription.Status.SUSPENDED)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_suspended_subscription_nonexistent(self, mock_sdk_verify):
        "Event BILLING.SUBSCRIPTION.SUSPENDED and subscription is nonexistent is handled"
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-0RD44774E41721427-487281337V896051W",
            "create_time": "2016-04-28T11:37:14Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.SUSPENDED",
            "summary": "A billing subscription was suspended",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-PE7JWXKGVN0R",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-0RD44774E41721427-487281337V896051W",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-0RD44774E41721427-487281337V896051W/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_cancelled(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.CANCELLED is handled"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-6TD369808N914414D-1YJ376786E892292F",
            "create_time": "2016-04-28T11:53:10Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "summary": "A billing subscription was cancelled",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "2017-11-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-PE7JWXKGVN0R",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Cancelled",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-6TD369808N914414D-1YJ376786E892292F",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-6TD369808N914414D-1YJ376786E892292F/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        with schema_context("test_subscription"):
            subscription = Subscription.objects.create(
                is_on_trial=False,
                status=Subscription.Status.ACTIVE,
                start_time=dateutil.parser.parse(
                    "2016-01-01T00:20:49Z",
                ),
                next_billing_time=dateutil.parser.parse(
                    "2016-05-01T00:20:49Z",
                ),
            )
            Paypal.objects.create(
                subscription=subscription,
                paypal_subscription_id=payload["resource"]["id"],
            )

        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with schema_context("test_subscription"):
            subscription.refresh_from_db()
            self.assertEqual(subscription.status, Subscription.Status.CANCELLED)
            self.assertEqual(
                subscription.cancelled_at,
                dateutil.parser.parse(
                    payload["create_time"],
                ),
            )

    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    def test_subscription_cancelled_subscription_nonexistent(self, mock_sdk_verify):
        "Event BILLING.SUBSCRIPTION.CANCELLED and subscription nonexistent is handled"
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-6TD369808N914414D-1YJ376786E892292F",
            "create_time": "2016-04-28T11:53:10Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "summary": "A billing subscription was cancelled",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "2017-11-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-PE7JWXKGVN0R",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Cancelled",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-6TD369808N914414D-1YJ376786E892292F",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-6TD369808N914414D-1YJ376786E892292F/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }

        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(PAYPAL_CLIENT_ID="paypal_client_id")
    @override_settings(PAYPAL_SECRET="PAYPAL_SECRET")
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    @responses.activate
    def test_subscription_updated(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.UPDATED is handled"""
        mock_sdk_verify.return_value = True
        sample_subscription = {
            "id": "I-BW452GLLEP1G",
            "custom_id": "test_subscription",
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": {"currency_code": "USD", "value": "10.0"},
            "subscriber": {
                "shipping_address": {
                    "name": {"full_name": "John Doe"},
                    "address": {
                        "address_line_1": "2211 N First Street",
                        "address_line_2": "Building 17",
                        "admin_area_2": "San Jose",
                        "admin_area_1": "CA",
                        "postal_code": "95131",
                        "country_code": "US",
                    },
                },
                "name": {"given_name": "John", "surname": "Doe"},
                "email_address": "customer@example.com",
                "payer_id": "2J6QB8YJQSJRJ",
            },
            "billing_info": {
                "outstanding_balance": {"currency_code": "USD", "value": "1.0"},
                "cycle_executions": [
                    {
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "cycles_completed": 2,
                        "cycles_remaining": 0,
                        "current_pricing_scheme_version": 1,
                    },
                    {
                        "tenure_type": "REGULAR",
                        "sequence": 2,
                        "cycles_completed": 0,
                        "cycles_remaining": 0,
                        "total_cycles": 0,
                    },
                ],
                "last_payment": {
                    "amount": {"currency_code": "USD", "value": "1.15"},
                    "time": "2019-04-09T10:27:20Z",
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0,
            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": [
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                    "rel": "cancel",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "edit",
                    "method": "PATCH",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                    "rel": "suspend",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST",
                },
            ],
            "status": "ACTIVE",
            "status_update_time": "2019-04-09T10:27:27Z",
        }
        paypal_subscription_id = sample_subscription["id"]
        # mock get paypal token
        responses.post(
            "https://api-m.sandbox.paypal.com/oauth2/token",
            json={
                "scope": "https://uri.paypal.com/scope-example",
                "access_token": "mocked_paypal_access_token",
                "token_type": "Bearer",
                "app_id": "APP-80W284485P519543T",
                "expires_in": 32400,
                "nonce": "2022-09-26T08:19:15ZE581R5bLeWmTuO4JAwzqUvO9tdKzDQTQ2ExPpJ2o-As",
            },
        )
        # mock get subscription details
        responses.get(
            f"https://api-m.sandbox.paypal.com/billing/subscriptions/{paypal_subscription_id}",
            json=sample_subscription,
        )
        with schema_context("test_subscription"):
            subscription = Subscription.objects.create(
                is_on_trial=True,
                status=Subscription.Status.ACTIVE,
                start_time=dateutil.parser.parse(
                    "2016-01-01T00:20:49Z",
                ),
                next_billing_time=dateutil.parser.parse(
                    "2016-05-01T00:20:49Z",
                ),
            )
            Paypal.objects.create(
                subscription=subscription, paypal_subscription_id=paypal_subscription_id
            )
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": paypal_subscription_id,
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with schema_context("test_subscription"):
            subscription.refresh_from_db()
            self.assertEqual(
                subscription.next_billing_time,
                dateutil.parser.parse(
                    sample_subscription["billing_info"]["next_billing_time"]
                ),
            )
            self.assertFalse(subscription.is_on_trial)

    @override_settings(PAYPAL_CLIENT_ID=None)
    @override_settings(PAYPAL_SECRET="PAYPAL_SECRET")
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    @responses.activate
    def test_subscription_updated_paypal_client_id_nonexistent(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.UPDATED and PAYPAL_CLIENT_ID env is null"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-BW452GLLEP1G",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(PAYPAL_CLIENT_ID="PAYPAL_CLIENT_ID")
    @override_settings(PAYPAL_SECRET=None)
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    @responses.activate
    def test_subscription_updated_paypal_secret_nonexistent(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.UPDATED and PAYPAL_SECRET env is null"""
        mock_sdk_verify.return_value = True
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": "I-BW452GLLEP1G",
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(PAYPAL_CLIENT_ID="PAYPAL_CLIENT_ID")
    @override_settings(PAYPAL_SECRET="PAYPAL_SECRET")
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @responses.activate
    def test_subscription_updated_paypal_token_failure(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.UPDATED token failure"""
        mock_sdk_verify.return_value = True
        sample_subscription = {
            "id": "I-BW452GLLEP1G",
            "custom_id": "test_subscription",
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": {"currency_code": "USD", "value": "10.0"},
            "subscriber": {
                "shipping_address": {
                    "name": {"full_name": "John Doe"},
                    "address": {
                        "address_line_1": "2211 N First Street",
                        "address_line_2": "Building 17",
                        "admin_area_2": "San Jose",
                        "admin_area_1": "CA",
                        "postal_code": "95131",
                        "country_code": "US",
                    },
                },
                "name": {"given_name": "John", "surname": "Doe"},
                "email_address": "customer@example.com",
                "payer_id": "2J6QB8YJQSJRJ",
            },
            "billing_info": {
                "outstanding_balance": {"currency_code": "USD", "value": "1.0"},
                "cycle_executions": [
                    {
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "cycles_completed": 2,
                        "cycles_remaining": 0,
                        "current_pricing_scheme_version": 1,
                    },
                    {
                        "tenure_type": "REGULAR",
                        "sequence": 2,
                        "cycles_completed": 0,
                        "cycles_remaining": 0,
                        "total_cycles": 0,
                    },
                ],
                "last_payment": {
                    "amount": {"currency_code": "USD", "value": "1.15"},
                    "time": "2019-04-09T10:27:20Z",
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0,
            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": [
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                    "rel": "cancel",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "edit",
                    "method": "PATCH",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                    "rel": "suspend",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST",
                },
            ],
            "status": "ACTIVE",
            "status_update_time": "2019-04-09T10:27:27Z",
        }
        paypal_subscription_id = sample_subscription["id"]
        # mock get paypal token
        responses.post("https://api-m.sandbox.paypal.com/oauth2/token", status=400)
        # mock get subscription details
        responses.get(
            f"https://api-m.sandbox.paypal.com/billing/subscriptions/{paypal_subscription_id}",
            json=sample_subscription,
        )
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": paypal_subscription_id,
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(PAYPAL_CLIENT_ID="PAYPAL_CLIENT_ID")
    @override_settings(PAYPAL_SECRET="PAYPAL_SECRET")
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @responses.activate
    def test_subscription_updated_paypal_get_subscription_failure(
        self, mock_sdk_verify
    ):
        """Event BILLING.SUBSCRIPTION.UPDATED get subscription failure"""
        mock_sdk_verify.return_value = True
        sample_subscription = {
            "id": "I-BW452GLLEP1G",
            "custom_id": "test_subscription",
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": {"currency_code": "USD", "value": "10.0"},
            "subscriber": {
                "shipping_address": {
                    "name": {"full_name": "John Doe"},
                    "address": {
                        "address_line_1": "2211 N First Street",
                        "address_line_2": "Building 17",
                        "admin_area_2": "San Jose",
                        "admin_area_1": "CA",
                        "postal_code": "95131",
                        "country_code": "US",
                    },
                },
                "name": {"given_name": "John", "surname": "Doe"},
                "email_address": "customer@example.com",
                "payer_id": "2J6QB8YJQSJRJ",
            },
            "billing_info": {
                "outstanding_balance": {"currency_code": "USD", "value": "1.0"},
                "cycle_executions": [
                    {
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "cycles_completed": 2,
                        "cycles_remaining": 0,
                        "current_pricing_scheme_version": 1,
                    },
                    {
                        "tenure_type": "REGULAR",
                        "sequence": 2,
                        "cycles_completed": 0,
                        "cycles_remaining": 0,
                        "total_cycles": 0,
                    },
                ],
                "last_payment": {
                    "amount": {"currency_code": "USD", "value": "1.15"},
                    "time": "2019-04-09T10:27:20Z",
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0,
            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": [
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                    "rel": "cancel",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "edit",
                    "method": "PATCH",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                    "rel": "suspend",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST",
                },
            ],
            "status": "ACTIVE",
            "status_update_time": "2019-04-09T10:27:27Z",
        }
        paypal_subscription_id = sample_subscription["id"]
        # mock get paypal token
        responses.post(
            "https://api-m.sandbox.paypal.com/oauth2/token",
            json={
                "scope": "https://uri.paypal.com/scope-example",
                "access_token": "mocked_paypal_access_token",
                "token_type": "Bearer",
                "app_id": "APP-80W284485P519543T",
                "expires_in": 32400,
                "nonce": "2022-09-26T08:19:15ZE581R5bLeWmTuO4JAwzqUvO9tdKzDQTQ2ExPpJ2o-As",
            },
        )
        # mock get subscription details
        responses.get(
            f"https://api-m.sandbox.paypal.com/billing/subscriptions/{paypal_subscription_id}",
            status=500,
        )
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": paypal_subscription_id,
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(PAYPAL_CLIENT_ID="paypal_client_id")
    @override_settings(PAYPAL_SECRET="PAYPAL_SECRET")
    @override_settings(PAYPAL_API_BASE_URL="https://api-m.sandbox.paypal.com")
    @override_settings(PAYPAL_SUBSCRIPTION_WEBHOOK_ID="paypal_webhook_id")
    @responses.activate
    def test_subscription_updated_subscription_nonexistent(self, mock_sdk_verify):
        """Event BILLING.SUBSCRIPTION.UPDATED and subscription nonexistent"""
        mock_sdk_verify.return_value = True
        sample_subscription = {
            "id": "I-BW452GLLEP1G",
            "custom_id": "test_subscription",
            "plan_id": "P-5ML4271244454362WXNWU5NQ",
            "start_time": "2019-04-10T07:00:00Z",
            "quantity": "20",
            "shipping_amount": {"currency_code": "USD", "value": "10.0"},
            "subscriber": {
                "shipping_address": {
                    "name": {"full_name": "John Doe"},
                    "address": {
                        "address_line_1": "2211 N First Street",
                        "address_line_2": "Building 17",
                        "admin_area_2": "San Jose",
                        "admin_area_1": "CA",
                        "postal_code": "95131",
                        "country_code": "US",
                    },
                },
                "name": {"given_name": "John", "surname": "Doe"},
                "email_address": "customer@example.com",
                "payer_id": "2J6QB8YJQSJRJ",
            },
            "billing_info": {
                "outstanding_balance": {"currency_code": "USD", "value": "1.0"},
                "cycle_executions": [
                    {
                        "tenure_type": "TRIAL",
                        "sequence": 1,
                        "cycles_completed": 2,
                        "cycles_remaining": 0,
                        "current_pricing_scheme_version": 1,
                    },
                    {
                        "tenure_type": "REGULAR",
                        "sequence": 2,
                        "cycles_completed": 0,
                        "cycles_remaining": 0,
                        "total_cycles": 0,
                    },
                ],
                "last_payment": {
                    "amount": {"currency_code": "USD", "value": "1.15"},
                    "time": "2019-04-09T10:27:20Z",
                },
                "next_billing_time": "2019-04-10T10:00:00Z",
                "failed_payments_count": 0,
            },
            "create_time": "2019-04-09T10:26:04Z",
            "update_time": "2019-04-09T10:27:27Z",
            "links": [
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/cancel",
                    "rel": "cancel",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "edit",
                    "method": "PATCH",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/suspend",
                    "rel": "suspend",
                    "method": "POST",
                },
                {
                    "href": "https://api-m.paypal.com/v1/billing/subscriptions/I-BW452GLLEP1G/capture",
                    "rel": "capture",
                    "method": "POST",
                },
            ],
            "status": "ACTIVE",
            "status_update_time": "2019-04-09T10:27:27Z",
        }
        paypal_subscription_id = sample_subscription["id"]
        # mock get paypal token
        responses.post(
            "https://api-m.sandbox.paypal.com/oauth2/token",
            json={
                "scope": "https://uri.paypal.com/scope-example",
                "access_token": "mocked_paypal_access_token",
                "token_type": "Bearer",
                "app_id": "APP-80W284485P519543T",
                "expires_in": 32400,
                "nonce": "2022-09-26T08:19:15ZE581R5bLeWmTuO4JAwzqUvO9tdKzDQTQ2ExPpJ2o-As",
            },
        )
        # mock get subscription details
        responses.get(
            f"https://api-m.sandbox.paypal.com/billing/subscriptions/{paypal_subscription_id}",
            json=sample_subscription,
        )
        payload = {
            "id": "WH-7BW55401AV391063H-02P24463AR970092S",
            "create_time": "2016-04-28T11:43:08Z",
            "resource_type": "Agreement",
            "event_type": "BILLING.SUBSCRIPTION.UPDATED",
            "summary": "A billing subscription was updated",
            "resource": {
                "custom_id": "test_subscription",
                "agreement_details": {
                    "outstanding_balance": {"value": "0.00"},
                    "num_cycles_remaining": "5",
                    "num_cycles_completed": "0",
                    "last_payment_date": "2016-04-28T11:29:54Z",
                    "last_payment_amount": {"value": "1.00"},
                    "final_payment_due_date": "1971-07-30T10:00:00Z",
                    "failed_payment_count": "0",
                },
                "description": "update desc",
                "links": [
                    {
                        "href": "https://api.paypal.com/v1/payments/billing-agreements/I-PE7JWXKGVN0R",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
                "id": paypal_subscription_id,
                "shipping_address": {
                    "recipient_name": "Cool Buyer",
                    "line1": "3rd st",
                    "line2": "cool",
                    "city": "San Jose",
                    "state": "CA",
                    "postal_code": "95112",
                    "country_code": "US",
                },
                "state": "Suspended",
                "plan": {
                    "curr_code": "USD",
                    "links": [],
                    "payment_definitions": [
                        {
                            "type": "TRIAL",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "5.00"},
                            "cycles": "5",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "1.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                        {
                            "type": "REGULAR",
                            "frequency": "Month",
                            "frequency_interval": "1",
                            "amount": {"value": "10.00"},
                            "cycles": "15",
                            "charge_models": [
                                {"type": "TAX", "amount": {"value": "2.00"}},
                                {"type": "SHIPPING", "amount": {"value": "1.00"}},
                            ],
                        },
                    ],
                    "merchant_preferences": {
                        "setup_fee": {"value": "0.00"},
                        "auto_bill_amount": "YES",
                        "max_fail_attempts": "21",
                    },
                },
                "payer": {
                    "payment_method": "paypal",
                    "status": "verified",
                    "payer_info": {
                        "email": "coolbuyer@example.com",
                        "first_name": "Cool",
                        "last_name": "Buyer",
                        "payer_id": "XLHKRXRA4H7QY",
                        "shipping_address": {
                            "recipient_name": "Cool Buyer",
                            "line1": "3rd st",
                            "line2": "cool",
                            "city": "San Jose",
                            "state": "CA",
                            "postal_code": "95112",
                            "country_code": "US",
                        },
                    },
                },
                "start_date": "2016-04-30T07:00:00Z",
            },
            "links": [
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S",
                    "rel": "self",
                    "method": "GET",
                    "encType": "application/json",
                },
                {
                    "href": "https://api.paypal.com/v1/notifications/webhooks-events/WH-7BW55401AV391063H-02P24463AR970092S/resend",
                    "rel": "resend",
                    "method": "POST",
                    "encType": "application/json",
                },
            ],
            "event_version": "1.0",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
