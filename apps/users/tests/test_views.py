"""Tests for users app views"""
import json
from datetime import timedelta
from unittest.mock import patch

import dateutil
import pytest
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.subscription.models import Subscription

from ..models import Customer, Staff
from ..serializers import ProfileTypeTokenObtainPairSerializer, TokenRefreshSerializer
from ..tokens import (
    EmailChangeTokenGenerator,
    PasswordResetTokenGenerator,
    VerifyEmailTokenGenerator,
)

User = get_user_model()


def mock_get_token(cls, user):
    """
    Mock for users.serializers.ProfileTypeTokenObtainPairSerializer.get_token
    """

    class FakeToken:
        """Mock for token class"""

        def __str__(self):
            return "secure_refresh_token"

        @property
        def access_token(self):
            """Return mocked access token string"""
            return "secure_access_token"

    return FakeToken()


def mock_refresh_token(self, attrs):
    return {"access": "refreshed_access_token"}


@patch("rest_framework.throttling.ScopedRateThrottle.get_rate")
@patch.object(ProfileTypeTokenObtainPairSerializer, "get_token", mock_get_token)
class GetTokenTestCase(FastTenantTestCase):
    """Tests for get access token"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(username="johndoe", password="1234")
        self.valid_payload = {
            "username": "johndoe",
            "password": "1234",
            "profile_type": "CUSTOMER",
        }

    def post(self, payload=None):
        """Method POST"""

        if payload is None:
            payload = {}

        response = self.client.post(
            reverse("token_obtain_pair"),
            payload,
            format="json",
        )
        return response

    def test_valid_payload(self, mocked_rate):
        """Token is returned for valid payload"""
        mocked_rate.return_value = "1000/day"

        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            json.dumps(response.data),
            json.dumps(
                {
                    "user": {
                        "id": str(self.user.id),
                        "first_name": self.user.first_name,
                        "last_name": self.user.last_name,
                        "full_name": self.user.full_name,
                        "email": self.user.email,
                        "is_email_verified": self.user.is_email_verified,
                        "profile_type": self.user.profile_type,
                    }
                }
            ),
        )
        self.assertEqual(
            response.client.cookies.get("access_token").value, "secure_access_token"
        )
        self.assertEqual(response.client.cookies.get("access_token")["httponly"], True)
        self.assertEqual(
            response.client.cookies.get("access_token")["max-age"],
            timedelta(hours=24).total_seconds(),
        )
        self.assertEqual(
            response.client.cookies.get("access_token")["expires"],
            timedelta(hours=24),
        )
        self.assertEqual(
            response.client.cookies.get("refresh_token").value,
            "secure_refresh_token",
        )
        self.assertEqual(response.client.cookies.get("refresh_token")["httponly"], True)
        self.assertEqual(
            response.client.cookies.get("refresh_token")["max-age"],
            timedelta(days=30).total_seconds(),
        )
        self.assertEqual(
            response.client.cookies.get("refresh_token")["expires"],
            timedelta(days=30),
        )

    def test_username_required(self, mocked_rate):
        """username field is required"""
        mocked_rate.return_value = "1000/day"

        response = self.post(
            {
                "password": "1234",
                "profile_type": "CUSTOMER",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post(
            {
                "username": "",
                "password": "1234",
                "profile_type": "CUSTOMER",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_required(self, mocked_rate):
        """password field is required"""
        mocked_rate.return_value = "1000/day"

        response = self.post(
            {
                "username": "johndoe",
                "profile_type": "CUSTOMER",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post(
            {
                "username": "johndoe",
                "password": "",
                "profile_type": "CUSTOMER",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_type_required(self, mocked_rate):
        """profile_type field is required"""
        mocked_rate.return_value = "1000/day"

        response = self.post(
            {
                "username": "johndoe",
                "password": "1234",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post(
            {
                "username": "johndoe",
                "password": "1234",
                "profile_type": "",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_throttling_implemented(self, mocked_rate):
        """Throttling is implemented to prevent abuse"""
        mocked_rate.return_value = "0/day"
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.django_db
@patch.object(TokenRefreshSerializer, "validate", mock_refresh_token)
class TestRefreshToken:
    """Tests for get refresh token"""

    def test_authentication(self, use_tenant_connection, fast_tenant_client):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("token_refresh"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_required(
        self, use_tenant_connection, fast_tenant_client, customer
    ):
        """Refresh token is required for a new access token to be granted"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("token_refresh"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert (
            response.data.get("detail")
            == "No valid token found in cookie refresh_token"
        )

    def test_refreshes_token(self, use_tenant_connection, fast_tenant_client, customer):
        """Token is refreshed"""
        refresh = RefreshToken.for_user(customer)
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": refresh.access_token, "refresh_token": str(refresh)}
        )
        response = fast_tenant_client.post(reverse("token_refresh"))
        assert response.status_code == status.HTTP_200_OK
        assert (
            response.client.cookies.get("access_token").value
            == "refreshed_access_token"
        )
        assert response.client.cookies.get("access_token")["httponly"] is True
        assert (
            response.client.cookies.get("access_token")["max-age"]
            == timedelta(hours=24).total_seconds()
        )
        assert response.client.cookies.get("access_token")["expires"] == timedelta(
            hours=24
        )


@pytest.mark.django_db
class TestGetProfile:
    """Tests for getting a logged in user profile"""

    def test_authentication(self, use_tenant_connection, fast_tenant_client):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("user_profile"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_returns_profile_data(
        self, use_tenant_connection, fast_tenant_client, customer
    ):
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("user_profile"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data) == json.dumps(
            {
                "id": str(customer.pk),
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "full_name": customer.full_name,
                "email": customer.email,
                "is_email_verified": customer.is_email_verified,
                "profile_type": customer.profile_type,
            }
        )


@patch("apps.users.serializers.send_signup_email_verification.delay")
@patch("apps.users.serializers.send_email_change_verification.delay")
class UpdateProfileTestCase(FastTenantTestCase):
    """Tests for UPDATE existing user"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Jane",
            last_name="Doe",
            email="janedoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        self.valid_payload = {
            "first_name": "Test",
            "last_name": "User",
            "email": "newemail@example.com",
        }

    def put(self, payload, user=None):
        """Method `PUT`"""
        if user:
            self.client.cookies = SimpleCookie(
                {"access_token": RefreshToken.for_user(user).access_token}
            )
            return self.client.put(
                reverse("user_profile"),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )

        return self.client.put(
            reverse("user_profile"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def patch(self, payload=None, authorize=True):
        """Method `PATCH`"""
        if payload is None:
            payload = {}

        if authorize:
            self.client.cookies = SimpleCookie(
                {"access_token": RefreshToken.for_user(self.user).access_token}
            )
            return self.client.patch(
                reverse("user_profile"),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )

        return self.client.patch(
            reverse("user_profile"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self, email_change_mock, sign_up_mock):
        """Ensure correct authentication when updating profile"""
        response = self.put({})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_valid_payload(self, email_change_mock, sign_up_mock):
        """Ensure update of an user with valid payload is correct"""
        response = self.put(self.valid_payload, self.user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(self.user.email, "janedoe@example.com")
        self.assertTrue(self.user.is_email_verified)
        self.assertEqual(
            response.data,
            {
                "id": str(self.user.id),
                "first_name": "Test",
                "last_name": "User",
                "full_name": "Test User",
                "email": "janedoe@example.com",
                "is_email_verified": True,
                "profile_type": "CUSTOMER",
            },
        )

        email_change_mock.assert_called_once_with(
            self.tenant.schema_name, str(self.user.pk), "newemail@example.com"
        )
        sign_up_mock.assert_not_called()

    def test_unverified_user(self, email_change_mock, sign_up_mock):
        """Update of a user whose email is unverified is correct"""
        unverified = User.objects.create_user(
            username="update_user_unverified",
            first_name="Unverified",
            email="unverified@example.com",
            password="12345",
            is_email_verified=False,
        )
        payload = {
            "first_name": "Bob",
            "last_name": "Austen",
            "email": "newunveried@example.com",
        }
        response = self.put(payload, unverified)
        unverified.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(unverified.first_name, "Bob")
        self.assertEqual(unverified.last_name, "Austen")
        self.assertEqual(unverified.email, "newunveried@example.com")
        self.assertFalse(unverified.is_email_verified)
        self.assertEqual(
            response.data,
            {
                "id": str(unverified.id),
                "first_name": "Bob",
                "last_name": "Austen",
                "full_name": "Bob Austen",
                "email": "newunveried@example.com",
                "is_email_verified": False,
                "profile_type": "CUSTOMER",
            },
        )

        email_change_mock.assert_not_called()
        sign_up_mock.assert_called_once_with(
            self.tenant.schema_name, str(unverified.pk)
        )

    def test_patch_email(self, email_change_mock, sign_up_mock):
        """Patch email"""
        response = self.patch({"email": "updated@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "janedoe@example.com")

        email_change_mock.assert_called_once_with(
            self.tenant.schema_name, str(self.user.pk), "updated@example.com"
        )
        sign_up_mock.assert_not_called()

    def test_patch_first_name(self, email_change_mock, sign_up_mock):
        """Patch first_name"""
        response = self.patch({"first_name": "Bob"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Bob")
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_patch_last_name(self, email_change_mock, sign_up_mock):
        """Patch last_name"""
        response = self.patch({"last_name": "Marley"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Marley")
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_email_not_blank(self, email_change_mock, sign_up_mock):
        """email cannot be blank"""
        response = self.patch({"email": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_first_name_not_blank(self, email_change_mock, sign_up_mock):
        """first_name cannot be blank"""
        response = self.patch({"first_name": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_is_email_verified_is_read_only(self, email_change_mock, sign_up_mock):
        """Field `is_email_verified` is read only"""
        alice = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="12345",
            is_email_verified=True,
        )
        payload = {"is_email_verified": False}
        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(alice).access_token}
        )
        response = self.client.patch(
            reverse("user_profile"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(alice.is_email_verified)
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()

    def test_email_profile_unique(self, email_change_mock, sign_up_mock):
        """Email and profile are unique"""
        amy = User.objects.create_user(
            username="amy",
            email="amy@example.com",
            password="12345",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        mary = User.objects.create_user(
            username="mary",
            email="mary@example.com",
            password="12345",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        payload = {"email": amy.email}
        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(mary).access_token}
        )
        response = self.client.patch(
            reverse("user_profile"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        email_change_mock.assert_not_called()
        sign_up_mock.assert_not_called()


@patch("apps.users.serializers.send_signup_email_verification.delay")
class CreateCustomerTestCase(FastTenantTestCase):
    """Tests for create single user"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.valid_payload = {
            "full_name": "Bob Austin",
            "email": "createcustomer@example.com",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
        }

    def post(self, payload):
        """Method POST"""
        return self.client.post(
            reverse("create_customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_valid_payload(self, send_email_verification_mock):
        """Customer is created with valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="createcustomer@example.com.CUSTOMER")
        self.assertEqual(user.first_name, "Bob")
        self.assertEqual(user.last_name, "Austin")
        self.assertIsNone(user.other_names)
        self.assertEqual(user.email, "createcustomer@example.com")
        self.assertTrue(user.check_password("mushrooms"))
        self.assertEqual(user.profile_type, User.ProfileType.CUSTOMER)
        send_email_verification_mock.assert_called_once_with(
            self.tenant.schema_name, str(user.pk)
        )
        self.assertEqual(
            response.data,
            {
                "id": str(user.id),
                "full_name": "Bob Austin",
                "first_name": "Bob",
                "last_name": "Austin",
                "email": "createcustomer@example.com",
                "is_email_verified": False,
                "date_joined": user.date_joined.isoformat().replace("+00:00", "Z"),
                "last_login": None,
            },
        )

    def test_name_required(self, send_email_verification_mock):
        """full_name required"""
        payload = {
            "full_name": "",
            "email": "alice@example.com",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["full_name"]
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_required(self, send_email_verification_mock):
        """email is provided"""
        payload = {
            "full_name": "Alice",
            "email": "",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(first_name="Bob")

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["email"]
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(first_name="Bob")

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_required(self, send_email_verification_mock):
        """password is provided"""
        payload = {
            "full_name": "Alice",
            "email": "passwordrequired@example.com",
            "password": "",
            "confirm_password": "mushrooms",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["password"]
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_required(self, send_email_verification_mock):
        """confirm_password is provided"""
        payload = {
            "full_name": "Alice",
            "email": "confirmpasswordrequired@example.com",
            "password": "mushrooms",
            "confirm_password": "",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["confirm_password"]
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_match(self, send_email_verification_mock):
        """password and confirm_password match"""
        payload = {
            "full_name": "Alice",
            "email": "passwordmatch@example.com",
            "password": "mushrooms",
            "confirm_password": "jibberish",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_password_length(self, send_email_verification_mock):
        """Ensure the minimum password length of 6 chars is enforced"""
        # Test 5 chars
        password = "12345"
        payload = {
            "full_name": "Alice",
            "email": "minpasswordlength@example.com",
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            Customer.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Test exact 6 chars
        password = password[:] + "6"
        payload = {
            **payload,
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_valid_email(self, send_email_verification_mock):
        """email format provided is correct"""
        payload = {
            "full_name": "Alice",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
            "email": "invalidemail",
        }
        response = self.post(payload)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(email=payload["email"])

        send_email_verification_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_unique(self, send_email_verification_mock):
        """Ensure customer email unique"""
        # Simulate existing user
        customer = Customer.objects.create_user(
            username="existing_customer",
            first_name="Existing",
            last_name="Customer",
            email="existingcustomer@example.com",
            password="12345",
        )
        payload = {
            "full_name": "Alice",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
            "email": customer.email,
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Customer.objects.filter(email=customer.email).count(), 1)
        send_email_verification_mock.assert_not_called()
        # existing staff email has no effect
        staff = Staff.objects.create_user(
            username="existing_staff",
            first_name="Existing",
            last_name="Staff",
            email="existingstaff@example.com",
            password="12345",
        )
        payload = {**payload, "email": staff.email}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(email=staff.email)
        send_email_verification_mock.assert_called_once_with(
            self.tenant.schema_name, str(customer.pk)
        )

    def test_non_existing_fields(self, send_email_verification_mock):
        """Non existing fields do not cause a crash"""
        payload = {
            "full_name": "Alice",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
            "email": "nonexisting@example.com",
            "foo_bar": "One 57",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(email="nonexisting@example.com")
        send_email_verification_mock.assert_called_once_with(
            self.tenant.schema_name, str(customer.pk)
        )

    def test_full_name_variations(self, send_email_verification_mock):
        """Different variations of full name are saved correctly"""
        payload = {
            "full_name": "Alice",
            "password": "mushrooms",
            "confirm_password": "mushrooms",
            "email": "onename@example.com",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        one_name = User.objects.get(email="onename@example.com")
        self.assertEqual(one_name.first_name, "Alice")
        self.assertIsNone(one_name.last_name)
        self.assertIsNone(one_name.other_names)

        response = self.post(
            {**payload, "full_name": "Alice Keller", "email": "twonames@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        two_names = User.objects.get(email="twonames@example.com")
        self.assertEqual(two_names.first_name, "Alice")
        self.assertEqual(two_names.last_name, "Keller")
        self.assertIsNone(two_names.other_names)

        response = self.post(
            {
                **payload,
                "full_name": "Alice Keller Johnson",
                "email": "multiplenames@example.com",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        multiple_names = User.objects.get(email="multiplenames@example.com")
        self.assertEqual(multiple_names.first_name, "Alice")
        self.assertEqual(multiple_names.last_name, "Keller")
        self.assertIsNone(multiple_names.other_names)

    def test_full_name_length(self, send_email_verification_mock):
        """Max length is not exceeded"""
        # 72 chars fails
        full_name = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmodw"
        )
        payload = {
            "full_name": full_name,
            "password": "mushrooms",
            "confirm_password": "mushrooms",
            "email": "fullnamelength@example.com",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # 71 chars succeeds
        full_name = full_name[:71]
        payload = {**payload, "full_name": full_name}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class UserEmailExistsTestCase(FastTenantTestCase):
    """Tests for checking email existence"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.customer_1 = Customer.objects.create_user(
            username="customer_email_exists_1",
            first_name="Test",
            email="user@example.com",
            password="12345",
        )
        self.customer_2 = Customer.objects.create_user(
            username="customer_email_exists_2",
            first_name="Test2",
            email="user2@example.com",
            password="12345",
        )
        self.staff_1 = Staff.objects.create_user(
            username="customer_email_exists_3",
            first_name="Test2",
            email="staff@example.com",
            password="12345",
        )
        self.staff_2 = Staff.objects.create_user(
            username="customer_email_exists_4",
            first_name="Test2",
            email="staff2@example.com",
            password="12345",
        )

    def post(self, payload=None, user=None):
        """Method `POST`"""
        if payload is None:
            payload = {}

        url_name = "check_email"

        if user:
            self.client.cookies = SimpleCookie(
                {"access_token": RefreshToken.for_user(user).access_token}
            )
            return self.client.post(
                reverse(url_name),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )

        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_logged_in_user(self):
        """User is logged in"""
        # a check of their own email returns false
        own_email_response = self.post({"email": "user@example.com"}, self.customer_1)
        self.assertEqual(own_email_response.data, {"exists": False})
        self.assertEqual(own_email_response.status_code, status.HTTP_200_OK)
        # a check of another user's email returns true
        other_user_email_response = self.post(
            {"email": "user2@example.com"}, self.customer_1
        )
        self.assertEqual(other_user_email_response.data, {"exists": True})
        self.assertEqual(other_user_email_response.status_code, status.HTTP_200_OK)
        # a check of an email that does not exist returns false
        does_not_exist_response = self.post(
            {"email": "nouser@example.com"}, self.customer_1
        )
        self.assertEqual(does_not_exist_response.data, {"exists": False})
        self.assertEqual(does_not_exist_response.status_code, status.HTTP_200_OK)
        # a check of a staff email returns false
        response = self.post({"email": "staff@example.com"}, self.customer_1)
        self.assertEqual(response.data, {"exists": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_user(self):
        """Ensure email exists check is correct if user is NOT logged in"""
        # profile_type must be provided
        response = self.post({"email": "user@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post({"email": "user@example.com", "profile_type": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # a check of an existing email should return true
        exists_response = self.post(
            {"email": "user@example.com", "profile_type": "CUSTOMER"}
        )
        self.assertEqual(exists_response.data, {"exists": True})
        self.assertEqual(exists_response.status_code, status.HTTP_200_OK)
        # a check of an email that does exist should return false
        does_not_exist_response = self.post(
            {"email": "nouser@example.com", "profile_type": "CUSTOMER"}
        )
        self.assertEqual(does_not_exist_response.data, {"exists": False})
        self.assertEqual(does_not_exist_response.status_code, status.HTTP_200_OK)
        # a check of a staff email that exusts should return false
        response = self.post({"email": "staff@example.com", "profile_type": "CUSTOMER"})
        self.assertEqual(response.data, {"exists": False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_email_required(self):
        """Ensure `email` is required"""
        response = self.post({"email": "", "profile_type": "CUSTOMER"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.post({"profile_type": "CUSTOMER"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email(self):
        """Ensure `email` should be valid"""
        response = self.post({"email": "wagwan", "profile_type": "CUSTOMER"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_profile_type(self):
        "profile_type must be valid"
        response = self.post({"email": "user@example.com", "profile_type": "foo"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@patch("apps.users.serializers.send_password_reset_email_verification.delay")
class ResetPasswordStartTestCase(FastTenantTestCase):
    """Tests for reset password start"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="resetpasswordstart",
            first_name="Test",
            email="resetpasswordstart@example.com",
            password="12345",
        )
        self.valid_payload = {
            "email": "resetpasswordstart@example.com",
            "profile_type": "CUSTOMER",
        }

    def post(self, payload):
        """Method `POST`"""
        response = self.client.post(
            reverse("reset_password_start"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_valid_payload(self, send_email_password_reset_mock):
        """Email sent for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_email_password_reset_mock.assert_called_once_with(
            self.tenant.schema_name,
            str(self.user.pk),
        )

    def test_invalid_user(self, send_email_password_reset_mock):
        """No email sent for a user that does NOT exist"""
        response = self.post(
            {
                "email": "doesnotexist@example.com",
                "profile_type": "CUSTOMER",
            }
        )
        send_email_password_reset_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_email_required(self, send_email_password_reset_mock):
        """email is required"""
        response = self.post(
            {
                "email": "",
                "profile_type": "CUSTOMER",
            }
        )
        send_email_password_reset_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "profile_type": "CUSTOMER",
            }
        )
        send_email_password_reset_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_type_required(self, send_email_password_reset_mock):
        """profile_type is required"""
        response = self.post(
            {
                "email": "resetpasswordstart@example.com",
                "profile_type": "",
            }
        )
        send_email_password_reset_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post(
            {
                "email": "resetpasswordstart@example.com",
            }
        )
        send_email_password_reset_mock.assert_not_called()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ResetPasswordEndTestCase(FastTenantTestCase):
    """Tests for password reset end"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="password_reset_end",
            first_name="Test",
            email="passwordresetend@example.com",
            password="12345",
        )
        self.valid_payload = {
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": PasswordResetTokenGenerator().make_token(self.user),
            "new_password1": "new_pass_12345",
            "new_password2": "new_pass_12345",
        }

    def post(self, payload):
        """Method `POST`"""
        response = self.client.post(
            reverse("reset_password_end"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_valid_payload(self):
        """Ensure password reset is correct for valid payload."""
        response = self.post(self.valid_payload)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("12345"))
        self.assertTrue(self.user.check_password("new_pass_12345"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # token is invalidate once used
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_match(self):
        """Ensure password reset is unsuccessful if passwords do not match"""
        response = self.post(
            {
                **self.valid_payload,
                "new_password1": "new_pass_12345",
                "new_password2": "new_pass_12346",
            }
        )
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_password_length(self):
        """Ensure the minimum password length of 6 chars is enforced"""
        # Test 5 chars
        payload = {
            **self.valid_payload,
            "new_password1": "abcde",
            "new_password2": "abcde",
        }
        response = self.post(payload)

        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Test exact 6 chars
        payload = {
            **self.valid_payload,
            "new_password1": "abcdef",
            "new_password2": "abcdef",
        }
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_uidb64(self):
        """Ensure unsuccessful password reset for invalid `uidb64`"""
        response = self.post({**self.valid_payload, "uidb64": "something"})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token(self):
        """Ensure unsuccessful verification for invalid `token`"""
        response = self.post({**self.valid_payload, "token": "something"})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_uidb64_required(self):
        """Ensure `uidb64` is required"""
        response = self.post({**self.valid_payload, "uidb64": ""})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_required(self):
        """Ensure `token` is required"""
        response = self.post({**self.valid_payload, "token": ""})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_password1_required(self):
        """Ensure `new_password1` is required"""
        response = self.post({**self.valid_payload, "new_password1": ""})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_password2_required(self):
        """Ensure `new_password2` is required"""
        response = self.post({**self.valid_payload, "new_password2": ""})
        self.assertTrue(self.user.check_password("12345"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@patch("apps.users.utils.send_welcome_email.delay")
class EmailVerificationEndTestCase(FastTenantTestCase):
    """Tests for email confirmation"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="email_verification_end",
            first_name="Test",
            email="emailverificationend@example.com",
            password="12345",
        )
        self.valid_payload = {
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": VerifyEmailTokenGenerator().make_token(self.user),
        }

    def post(self, payload):
        """Method `POST`"""
        response = self.client.post(
            reverse("email_verification_end"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_valid_payload(self, send_email_welcome_mock):
        """Verification works for valid payload"""
        self.assertFalse(self.user.is_email_verified)
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_email_welcome_mock.assert_called_once_with(
            self.tenant.schema_name, self.user.id
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

        # token is invalidate once used
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_uidb64(self, send_email_welcome_mock):
        """Ensure unsuccessful verification for invalid `uidb64`"""
        response = self.post({**self.valid_payload, "uidb64": "something"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)

    def test_invalid_token(self, send_email_welcome_mock):
        """Ensure unsuccessful verification for invalid `token`"""
        response = self.post({**self.valid_payload, "token": "something"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)

    def test_uidb64_required(self, send_email_welcome_mock):
        """Ensure `uidb64` is required"""
        payload = {**self.valid_payload, "uidb64": ""}
        response = self.post(payload)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["uidb64"]
        response = self.post(payload)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_required(self, send_email_welcome_mock):
        """Ensure `token` is required"""
        payload = {**self.valid_payload, "token": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)

        del payload["token"]
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        send_email_welcome_mock.assert_not_called()
        self.assertFalse(self.user.is_email_verified)


class ChangePasswordTestCase(FastTenantTestCase):
    """Tests for change password"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        self.user = User.objects.create_user(
            username="change_password",
            first_name="Jane",
            email="change_password@example.com",
            password="12345",
            is_email_verified=True,
        )
        self.valid_payload = {"password": "vampire", "confirm_password": "vampire"}

    def post(self, payload=None, user=None):
        """Method `POST`"""
        if payload is None:
            payload = {}

        url_name = "change_password"

        if user:
            self.client.cookies = SimpleCookie(
                {"access_token": RefreshToken.for_user(user).access_token}
            )
            return self.client.post(
                reverse(url_name),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )

        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self):
        """Authentication is required"""
        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change(self):
        """Change password works"""
        response = self.post(self.valid_payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        # Old password is false
        self.assertFalse(self.user.check_password("12345"))
        # New password is true
        self.assertTrue(self.user.check_password("vampire"))

    def test_password_required(self):
        """password is required"""
        payload = {**self.valid_payload, "password": ""}
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["password"]
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_required(self):
        """confirm_password is required"""
        payload = {**self.valid_payload, "confirm_password": ""}
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["confirm_password"]
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passwords_match(self):
        """Passwords should match"""
        response = self.post(
            {**self.valid_payload, "confirm_password": "something"}, self.user
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_password_length(self):
        """Minimum password length of 6 chars is enforced"""
        # 5 chars fails
        password = "12345"
        payload = {
            **self.valid_payload,
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload, self.user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Test exact 6 chars
        password = password[:] + "6"
        payload = {
            **self.valid_payload,
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_maximum_password_length(self):
        """Maximum password length of 255 is enforced"""
        # 256 chars fails
        password = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, \
        sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. \
        Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris \
        nisi ut aliquip ex ea commodo consequat. Duis aute irure doloruit"
        payload = {
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload, self.user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # 255 chars succeeds
        password = password[:255]
        payload = {
            "password": password,
            "confirm_password": password,
        }
        response = self.post(payload, self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@patch("apps.users.views.send_signup_email_verification.delay")
class ResendEmailVerificationTestCase(FastTenantTestCase):
    """Tests for resending email confirmation"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        self.user = User.objects.create(
            username="resend_verification",
            email="resend@example.com",
            is_email_verified=False,
        )

    def get(self, user=None):
        """Method `GET`"""
        if user:
            self.client.cookies = SimpleCookie(
                {"access_token": RefreshToken.for_user(user).access_token}
            )
            return self.client.get(reverse("resend_email_verification"))

        return self.client.get(
            reverse("resend_email_verification"),
        )

    def test_authentication(self, send_mock):
        """User must be authenticated"""
        response = self.get()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        send_mock.assert_not_called()

    def test_is_customer(self, send_mock):
        """User must be a customer"""
        user = User.objects.create(
            username="staff_resend",
            email="resend@example.com",
            is_email_verified=False,
            profile_type="STAFF",
        )
        response = self.get(user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        send_mock.assert_not_called()

    def test_send(self, send_mock):
        """Email confirmation is sent"""
        response = self.get(self.user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_mock.assert_called_once_with(self.tenant.schema_name, str(self.user.pk))

    def test_send_verified_user(self, send_mock):
        """Email confirmation should not be sent for verified user"""
        user = User.objects.create(
            username="verified_user",
            email="verified@example.com",
            is_email_verified=True,
        )
        response = self.get(user)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_mock.assert_not_called()


class ConfirmEmailChangeTestCase(FastTenantTestCase):
    """Tests for email change confirmation"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        self.user = User.objects.create_user(
            username="confirm_email",
            first_name="Test",
            email="confirm@example.com",
            password="12345",
        )
        self.valid_payload = {
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": EmailChangeTokenGenerator().make_token(self.user),
            "emailb64": urlsafe_base64_encode(force_bytes("newconfirm@example.com")),
        }

    def post(self, payload):
        """Method `POST`"""
        response = self.client.post(
            reverse("confirm_email_change"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_valid_payload(self):
        """Verification works for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "newconfirm@example.com")

        # token is invalidate once used
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_uidb64(self):
        """Unsuccessful for invalid `uidb64`"""
        response = self.post({**self.valid_payload, "uidb64": "something"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token(self):
        """Unsuccessful for invalid `token`"""
        response = self.post({**self.valid_payload, "token": "something"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_emailb64(self):
        """Unsuccessful for invalid emailb64"""
        response = self.post({**self.valid_payload, "emailb64": "something"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_uidb64_required(self):
        """Ensure `uidb64` is required"""
        payload = {**self.valid_payload, "uidb64": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["uidb64"]
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_required(self):
        """Ensure `token` is required"""
        payload = {**self.valid_payload, "token": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["token"]
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_emailb64_required(self):
        """Ensure emailb64 is required"""
        payload = {**self.valid_payload, "emailb64": ""}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        del payload["emailb64"]
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomerDeleteAccountTestCase(FastTenantTestCase):
    """Tests for customer account deletion"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Jane",
            last_name="Doe",
            other_names="Test",
            email="janedoe@gmail.com",
            password="12345",
            is_email_verified=True,
        )

        self.valid_payload = {"password": "12345"}

    def post(self, payload, user=None):
        """Method `POST`"""

        if user is None:
            user = self.user

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        response = self.client.post(
            reverse("customer_delete_account"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_authentication(self):
        """Ensure authentication is required"""
        response = self.client.post(
            reverse("customer_delete_account"),
            data=json.dumps({}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_is_customer(self):
        """User is a customer"""
        user = User.objects.create_user(
            username="staff_delete",
            email="staffdelete@example.com",
            password="12345",
            is_email_verified=True,
            profile_type="STAFF",
        )
        response = self.post({}, user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_account_deletion(self):
        """Ensure account deletion is correct"""
        response = self.post(self.valid_payload)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username=self.user.username)

    def test_password(self):
        """Password is correct"""
        response = self.post({"password": "monalisa"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        User.objects.get(username=self.user.username)

        response = self.post({"password": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        User.objects.get(username=self.user.username)

        response = self.post({})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        User.objects.get(username=self.user.username)


@pytest.mark.django_db
class TestLogout:
    """Tests for logout view"""

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(reverse("auth_logout"), data={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_is_logout_out(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """User is logged out"""
        token = RefreshToken.for_user(customer)
        fast_tenant_client.cookies = SimpleCookie(
            {
                "access_token": str(token.access_token),
                "refresh_token": str(token),
            }
        )
        response = fast_tenant_client.post(reverse("auth_logout"), data={})

        assert response.status_code == status.HTTP_205_RESET_CONTENT
        assert BlacklistedToken.objects.count() == 1
        # auth cookies should be deleted
        assert response.client.cookies.get("access_token").value == ""
        assert response.client.cookies.get("refresh_token").value == ""

    def test_refresh_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Refresh token is required to be set in cookies"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(reverse("auth_logout"), data={})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGetCustomers:
    """Tests for get customers"""

    @pytest.fixture
    def create_users(self):
        customer_1 = User.objects.create_user(
            username="customer1",
            first_name="Jane",
            last_name="Doe",
            email="janedoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        customer_2 = User.objects.create_user(
            username="customer2",
            first_name="John",
            last_name="Doe",
            email="johndoe@example.com",
            password="12345",
            last_login=timezone.now() + timedelta(minutes=10),
        )
        store_staff_1 = User.objects.create_user(
            username="store_staff1",
            first_name="Jane",
            last_name="Staff",
            email="storestaff1@example.com",
            password="12345",
            profile_type=User.ProfileType.STAFF,
        )
        django_staff_1 = User.objects.create_user(
            username="django_staff1",
            first_name="Jane",
            last_name="Staff",
            email="djangostaff1@example.com",
            password="12345",
            profile_type=User.ProfileType.CUSTOMER,
            is_staff=True,
        )

        return locals()

    def test_authentication(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("customer-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("customer-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_all_customers(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_users,
        create_active_subscription,
    ):
        """Get all returns correct response

        Non customers are excluded from response
        """
        customer_1 = create_users["customer_1"]
        customer_2 = create_users["customer_2"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("customer-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(
            response.data["results"], cls=DjangoJSONEncoder
        ) == json.dumps(
            [
                {
                    "id": str(customer_2.pk),
                    "full_name": customer_2.full_name,
                    "first_name": customer_2.first_name,
                    "last_name": customer_2.last_name,
                    "email": customer_2.email,
                    "is_email_verified": customer_2.is_email_verified,
                    "date_joined": customer_2.date_joined.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "last_login": customer_2.last_login.isoformat().replace(
                        "+00:00", "Z"
                    ),
                },
                {
                    "id": str(customer_1.pk),
                    "full_name": customer_1.full_name,
                    "first_name": customer_1.first_name,
                    "last_name": customer_1.last_name,
                    "email": customer_1.email,
                    "is_email_verified": customer_1.is_email_verified,
                    "date_joined": customer_1.date_joined.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "last_login": None,
                },
            ],
            cls=DjangoJSONEncoder,
        )
