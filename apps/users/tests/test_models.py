"""Tests for user app models"""
import datetime
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django_tenants.test.cases import FastTenantTestCase

from ..models import Customer, Staff, User, timezone

date_mock = datetime.datetime(2010, 1, 1, tzinfo=timezone.utc)

# pylint: disable=no-value-for-parameter


class UserTestCase(FastTenantTestCase):
    """Tests for model `User`"""

    @patch("apps.users.models.timezone")
    def test_create_user(self, mock_timezone):
        """Ensure we can create a user object"""
        mock_timezone.now.return_value = date_mock
        user = User.objects.create_user(
            username="janedoe@example.com",
            first_name="Jane",
            email="janedoe@example.com",
            password="12345",
            last_name="Doe",
            other_names="Test",
            date_joined=date_mock,
            profile_type=User.ProfileType.CUSTOMER,
        )
        self.assertEqual(str(user), "Jane Doe Test")
        self.assertEqual(user.full_name, "Jane Doe Test")
        self.assertEqual(user.get_full_name(), "Jane Doe Test")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.other_names, "Test")
        self.assertEqual(user.email, "janedoe@example.com")
        self.assertEqual(user.username, "janedoe@example.com")
        self.assertTrue(user.check_password("12345"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_store_owner)
        self.assertEqual(user.profile_type, User.ProfileType.CUSTOMER)
        self.assertEqual(user.date_joined, date_mock)

        # username is required
        with self.assertRaises(TypeError):
            User.objects.create_user(
                first_name="John",
                email="johndoe@example.com",
                password="12345",
                last_name="Doe",
                other_names="Test",
                date_joined=date_mock,
            )
        with self.assertRaises(ValueError):
            User.objects.create_user(
                username=None,
                first_name="John",
                email="johndoe@example.com",
                password="12345",
                last_name="Doe",
                other_names="Test",
                date_joined=date_mock,
            )
        with self.assertRaises(ValueError):
            User.objects.create_user(
                username="",
                first_name="John",
                email="johndoe@example.com",
                password="12345",
                last_name="Doe",
                other_names="Test",
                date_joined=date_mock,
            )

        # username is unique
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user(username="janedoe@example.com")

        # optional fields
        user2 = User.objects.create_user(
            username="alice",
        )
        self.assertEqual(str(user2), "alice")
        self.assertEqual(user2.full_name, None)
        self.assertEqual(user2.get_full_name(), None)
        self.assertIsNone(user2.first_name)
        self.assertIsNone(user2.last_name)
        self.assertIsNone(user2.other_names)
        self.assertIsNone(user2.email)
        self.assertFalse(user2.has_usable_password())
        self.assertEqual(user2.date_joined, date_mock)
        self.assertEqual(user2.profile_type, User.ProfileType.CUSTOMER)

    @patch("apps.users.models.timezone")
    def test_create_superuser(self, mock_timezone):
        """Ensure we can create a super user"""
        mock_timezone.now.return_value = date_mock
        user = User.objects.create_superuser(
            username="super",
            first_name="Super",
            email="super@example.com",
            password="12345",
            last_name="User",
            other_names="Test",
            date_joined=date_mock,
        )
        self.assertEqual(str(user), "Super User Test")
        self.assertEqual(user.full_name, "Super User Test")
        self.assertEqual(user.get_full_name(), "Super User Test")
        self.assertEqual(user.first_name, "Super")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(user.other_names, "Test")
        self.assertEqual(user.email, "super@example.com")
        self.assertEqual(user.username, "super")
        self.assertTrue(user.check_password("12345"))
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_store_owner)
        self.assertEqual(user.profile_type, User.ProfileType.CUSTOMER)
        self.assertEqual(user.date_joined, date_mock)

        # username is required
        with self.assertRaises(TypeError):
            User.objects.create_superuser(
                first_name="Super",
                email="super@example.com",
                password="12345",
                last_name="User",
                other_names="Test",
                date_joined=date_mock,
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                username=None,
                first_name="Super",
                email="super@example.com",
                password="12345",
                last_name="User",
                other_names="Test",
                date_joined=date_mock,
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                username="",
                first_name="Super",
                email="super@example.com",
                password="12345",
                last_name="User",
                other_names="Test",
                date_joined=date_mock,
            )

        # is_staff should be True
        with self.assertRaises(ValueError):
            User.objects.create_superuser(username="supernova", is_staff=False)

        # is_superuser shoule be True
        with self.assertRaises(ValueError):
            User.objects.create_superuser(username="supernova", is_superuser=False)

        # optional fields
        user2 = User.objects.create_superuser(
            username="super2",
        )
        self.assertEqual(str(user2), "super2")
        self.assertEqual(user2.full_name, None)
        self.assertEqual(user2.get_full_name(), None)
        self.assertIsNone(user2.first_name)
        self.assertIsNone(user2.last_name)
        self.assertIsNone(user2.other_names)
        self.assertIsNone(user2.email)
        self.assertFalse(user2.has_usable_password())
        self.assertEqual(user2.date_joined, date_mock)

    def test_user_full_name(self):
        """Ensure the full name of user object is correct"""
        # All names provided
        user = User.objects.create_user(
            username="janedoetest@example.com",
            first_name="Jane",
            email="janedoetest@example.com",
            password="12345",
            last_name="Doe",
            other_names="Test",
        )
        self.assertEqual((str(user)), "Jane Doe Test")
        self.assertEqual(user.full_name, "Jane Doe Test")

        # Only first_name provided
        user = User.objects.create_user(
            username="jane@example.com",
            first_name="Jane",
            email="jane@example.com",
            password="12345",
        )
        self.assertEqual((str(user)), "Jane")
        self.assertEqual(user.full_name, "Jane")

        # first_name and last_name
        user = User.objects.create_user(
            username="janedoe@example.com",
            first_name="Jane",
            email="janedoe@example.com",
            password="12345",
            last_name="Doe",
        )
        self.assertEqual((str(user)), "Jane Doe")
        self.assertEqual(user.full_name, "Jane Doe")

        # first_name and other_names
        user = User.objects.create_user(
            username="janetest@example.com",
            first_name="Jane",
            email="janetest@example.com",
            password="12345",
            other_names="Test",
        )
        self.assertEqual((str(user)), "Jane Test")
        self.assertEqual(user.full_name, "Jane Test")

    def test_names_auto_format(self):
        """Ensure names are formatted to title case"""
        user = User.objects.create_user(
            username="username",
            email="johndoe@example.com",
            first_name="johN",
            last_name="DOE",
            other_names="iron Fist",
            password="12345",
        )
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.other_names, "Iron Fist")

    def test_unique_togther_email_and_profile_type(self):
        """Test that profile type and email must be unique"""
        email = "bobmarley@example.com"
        User.objects.create_user(
            username="bobmarley_staff",
            email=email,
            password="pas$***())",
            profile_type=User.ProfileType.STAFF,
        )

        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user(
                username="bobmarley_staff_email_duplicate",
                email=email,
                password="pas$***())",
                profile_type=User.ProfileType.STAFF,
            )

        # we can create a new user if same email exists
        # but different profile
        User.objects.create_user(
            username="bobmarley_customer",
            email=email,
            password="pas$***())",
            profile_type=User.ProfileType.CUSTOMER,
        )

    def test_email_not_empty_string(self):
        """Email passed as sting should be saved as null

        An empty string and profile type will be treated as unique
        """
        user = User.objects.create_user(
            username="empty_email_string",
            email="",
            password="pas$***())",
            profile_type=User.ProfileType.STAFF,
        )
        self.assertIsNone(user.email)
        # we should create another user without
        # an email if need be
        User.objects.create_user(
            username="empty_email_string_2",
            email="",
            password="pas$***())",
            profile_type=User.ProfileType.STAFF,
        )


class StaffTestCase(FastTenantTestCase):
    """Tests for proxy model Staff"""

    def setUp(self) -> None:
        super().setUp()

        self.staff = Staff.objects.create_user(
            username="staff@example.com",
        )

    def test_create_staff(self):
        """Ensure we can create user with profile_type Staff"""
        self.assertEqual(self.staff.profile_type, User.ProfileType.STAFF)

    def test_queryset(self):
        """Queryset results should be correct"""
        User.objects.create_user(
            username="customer", profile_type=User.ProfileType.CUSTOMER
        )
        User.objects.create_user(
            username="django_staff", is_staff=True, profile_type=User.ProfileType.STAFF
        )
        User.objects.create_user(
            username="superuser", is_superuser=True, profile_type=User.ProfileType.STAFF
        )

        self.assertEqual(Staff.objects.all().count(), 1)
        self.assertEqual(Staff.objects.all().first().username, "staff@example.com")
        self.assertEqual(User.objects.all().count(), 4)


class CustomerTestCase(FastTenantTestCase):
    """Tests for proxy model Customer"""

    def setUp(self) -> None:
        super().setUp()

        self.customer = Customer.objects.create_user(
            username="customer@example.com",
        )

    def test_create_customer(self):
        """Ensure we can create user with profile_type Customer"""
        self.assertEqual(self.customer.profile_type, User.ProfileType.CUSTOMER)

    def test_queryset(self):
        """Queryset results should be correct"""
        User.objects.create_user(username="staff", profile_type=User.ProfileType.STAFF)
        User.objects.create_user(
            username="django_staff",
            is_staff=True,
            profile_type=User.ProfileType.CUSTOMER,
        )
        User.objects.create_user(
            username="superuser",
            is_superuser=True,
            profile_type=User.ProfileType.CUSTOMER,
        )

        self.assertEqual(Customer.objects.all().count(), 1)
        self.assertEqual(
            Customer.objects.all().first().username, "customer@example.com"
        )
        self.assertEqual(User.objects.all().count(), 4)
