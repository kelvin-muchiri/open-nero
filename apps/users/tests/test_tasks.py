"""Tests for users.tasks"""

from unittest.mock import patch

from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from apps.tenants.models import Tenant

from ..models import User
from ..tasks import (
    EmailChangeTokenGenerator,
    PasswordResetTokenGenerator,
    VerifyEmailTokenGenerator,
    send_email_change_verification,
    send_password_reset_email_verification,
    send_signup_email_verification,
    send_welcome_email,
)

# pylint: disable=unused-argument


def mock_make_token(self, user):
    """
    Mock for users.tasks.VerifyEmailTokenGenerator.make_token
    """

    return "mocked_token"


class TasksTenantCase(TenantTestCase):
    """Base classes for test cases"""

    @staticmethod
    def get_test_tenant_domain():
        return "api.test.com"

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.contact_email = "info@test.com"
        tenant.primary_color = "#000"
        tenant.secondary_color = "#fff"
        tenant.name = "Test"
        return tenant


@patch.object(VerifyEmailTokenGenerator, "make_token", mock_make_token)
@patch("apps.users.tasks.render_to_string")
@patch("apps.users.tasks.send_mail")
class SendSignupVerificationTestCase(TasksTenantCase):
    """Tests for send email verification on signup"""

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_user(
            username="signup_send", email="signupsend@example.com"
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_VERIFY_EMAIL_URL="/verify")
    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send(self, send_mock, render_mock):
        """Email is sent"""
        render_mock.return_value = "mocked_render"
        send_signup_email_verification(self.tenant.schema_name, str(self.user.pk))
        send_mock.assert_called_once_with(
            subject="Verify your email",
            message="mocked_render",
            recipient=self.user.email,
            sender_email="no-reply@test.com",
            sender_name="Test",
        )
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        render_mock.assert_called_once_with(
            "users/verify_email_signup.html",
            {
                "user": self.user,
                "url": f"https://test.com/verify/{uidb64}/mocked_token",
                "website": self.tenant.name,
                "contact_email": "info@test.com",
            },
        )

    @override_settings(WEBAPP_VERIFY_EMAIL_URL=None)
    def test_relative_url_null(self, send_mock, render_mock):
        """Email not sent if relative url not set"""
        render_mock.return_value = "mocked_render"
        send_signup_email_verification(self.tenant.schema_name, str(self.user.pk))
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_VERIFY_EMAIL_URL="/verify")
    def test_user_not_found(self, send_mock, render_mock):
        """Email not sent if user not found"""
        render_mock.return_value = "mocked_render"
        send_signup_email_verification(
            self.tenant.schema_name, "1ba8feaf-f33d-437b-b6e9-0db0c01f66b9"
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_VERIFY_EMAIL_URL="/verify")
    def test_no_domain(self, send_mock, render_mock):
        """Email not sent if no domain found"""
        render_mock.return_value = "mocked_render"

        with schema_context("public"):
            tenant = Tenant.objects.create(schema_name="nice", name="Nice")
            tenant.save()

        with schema_context(tenant.schema_name):
            user = User.objects.create_user(username="megan", email="megan@example.com")
            send_signup_email_verification(tenant.schema_name, str(user.pk))

        send_mock.assert_not_called()
        render_mock.assert_not_called()


@patch.object(EmailChangeTokenGenerator, "make_token", mock_make_token)
@patch("apps.users.tasks.render_to_string")
@patch("apps.users.tasks.send_mail")
class SendEmailChangeVerificationTestCase(TasksTenantCase):
    """Tests for send email verification on signup"""

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_user(
            username="email_change_send",
            email="emailchange@example.com",
            is_email_verified=True,
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL="/verify")
    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send(self, send_mock, render_mock):
        """Email is sent"""
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name, str(self.user.pk), "newemail@example.com"
        )
        send_mock.assert_called_once_with(
            subject="Verify your email",
            message="mocked_render",
            recipient="newemail@example.com",
            sender_email="no-reply@test.com",
            sender_name=self.tenant.name,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        emailb64 = urlsafe_base64_encode(force_bytes("newemail@example.com"))
        render_mock.assert_called_once_with(
            "users/verify_email_change.html",
            {
                "user": self.user,
                "url": f"https://test.com/verify/{uidb64}/{emailb64}/mocked_token",
                "website": "Test",
                "contact_email": "info@test.com",
            },
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_ADMIN_EMAIL_CHANGE_CONFIRM_URL="/verify-admin")
    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send_staff(self, send_mock, render_mock):
        """Email is sent correcty for store staff"""
        staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name, str(staff.pk), "newemail@example.com"
        )
        send_mock.assert_called_once_with(
            subject="Verify your email",
            message="mocked_render",
            recipient="newemail@example.com",
            sender_email="no-reply@test.com",
            sender_name=self.tenant.name,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(staff.pk))
        emailb64 = urlsafe_base64_encode(force_bytes("newemail@example.com"))
        render_mock.assert_called_once_with(
            "users/verify_email_change.html",
            {
                "user": staff,
                "url": f"https://test.com/verify-admin/{uidb64}/{emailb64}/mocked_token",
                "website": "Test",
                "contact_email": "info@test.com",
            },
        )

    @override_settings(WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL=None)
    def test_relative_url_null(self, send_mock, render_mock):
        """Email not sent if relative url null"""
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name, str(self.user.pk), "newemail@example.com"
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_ADMIN_EMAIL_CHANGE_CONFIRM_URL=None)
    def test_staff_relative_url_null(self, send_mock, render_mock):
        """Email is sent not sent for staff if relative url null"""
        staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name, str(staff.pk), "newemail@example.com"
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL="/verify")
    def test_user_not_found(self, send_mock, render_mock):
        """Email not sent if user not found"""
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name,
            "1ba8feaf-f33d-437b-b6e9-0db0c01f66b9",
            "newemail@example.com",
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL="/verify")
    def test_no_domain(self, send_mock, render_mock):
        """Email not sent if no domain found"""
        render_mock.return_value = "mocked_render"

        with schema_context("public"):
            tenant = Tenant.objects.create(schema_name="nice", name="Nice")
            tenant.save()

        with schema_context(tenant.schema_name):
            user = User.objects.create_user(username="megan", email="megan@example.com")
            send_email_change_verification(
                tenant.schema_name, str(user.pk), "newemail@example.com"
            )

        send_mock.assert_not_called()
        render_mock.assert_not_called()


@patch.object(PasswordResetTokenGenerator, "make_token", mock_make_token)
@patch("apps.users.tasks.render_to_string")
@patch("apps.users.tasks.send_mail")
class SendPasswordResetVerificationTestCase(TasksTenantCase):
    """Tests for send email verification on signup"""

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_user(
            username="reset_password",
            email="resetpassword@example.com",
            is_email_verified=True,
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL="/change-password")
    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send(self, send_mock, render_mock):
        """Email is sent"""
        render_mock.return_value = "mocked_render"
        send_password_reset_email_verification(
            self.tenant.schema_name, str(self.user.pk)
        )
        send_mock.assert_called_once_with(
            subject="Password Reset",
            message="mocked_render",
            recipient=self.user.email,
            sender_email="no-reply@test.com",
            sender_name=self.tenant.name,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        render_mock.assert_called_once_with(
            "users/password_reset.html",
            {
                "user": self.user,
                "url": f"https://test.com/change-password/{uidb64}/mocked_token",
                "website": "Test",
                "contact_email": "info@test.com",
            },
        )

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_ADMIN_PASSWORD_RESET_CONFIRM_URL="/admin/change-password")
    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send_staff(self, send_mock, render_mock):
        """Email is sent correcty for store staff"""
        staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        render_mock.return_value = "mocked_render"
        send_password_reset_email_verification(self.tenant.schema_name, str(staff.pk))
        send_mock.assert_called_once_with(
            subject="Password Reset",
            message="mocked_render",
            recipient=staff.email,
            sender_email="no-reply@test.com",
            sender_name=self.tenant.name,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(staff.pk))
        render_mock.assert_called_once_with(
            "users/password_reset.html",
            {
                "user": staff,
                "url": f"https://test.com/admin/change-password/{uidb64}/mocked_token",
                "website": "Test",
                "contact_email": "info@test.com",
            },
        )

    @override_settings(WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL=None)
    def test_relative_url_null(self, send_mock, render_mock):
        """Email not sent if relative url null"""
        render_mock.return_value = "mocked_render"
        send_password_reset_email_verification(
            self.tenant.schema_name, str(self.user.pk)
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_ADMIN_PASSWORD_RESET_CONFIRM_URL=None)
    def test_staff_relative_url_null(self, send_mock, render_mock):
        """Email is sent not sent for staff if relative url null"""
        staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            is_email_verified=True,
            profile_type=User.ProfileType.STAFF,
        )
        render_mock.return_value = "mocked_render"
        send_password_reset_email_verification(self.tenant.schema_name, str(staff.pk))
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL="/change-password")
    def test_user_not_found(self, send_mock, render_mock):
        """Email not sent if user not found"""
        render_mock.return_value = "mocked_render"
        send_email_change_verification(
            self.tenant.schema_name,
            "1ba8feaf-f33d-437b-b6e9-0db0c01f66b9",
            "newemail@example.com",
        )
        send_mock.assert_not_called()
        render_mock.assert_not_called()

    @override_settings(WEBAPP_PROTOCOL="https")
    @override_settings(WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL="/change-password")
    def test_no_domain(self, send_mock, render_mock):
        """Email not sent if no domain found"""
        render_mock.return_value = "mocked_render"

        with schema_context("public"):
            tenant = Tenant.objects.create(schema_name="nice", name="Nice")
            tenant.save()

        with schema_context(tenant.schema_name):
            user = User.objects.create_user(username="megan", email="megan@example.com")
            send_password_reset_email_verification(tenant.schema_name, str(user.pk))

        send_mock.assert_not_called()
        render_mock.assert_not_called()


@patch("apps.users.tasks.render_to_string")
@patch("apps.users.tasks.send_mail")
class SendWelcomeEmailTestCase(TasksTenantCase):
    """Tests for sending welcome email"""

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            is_email_verified=True,
        )

    @override_settings(MAIL_SENDER_EMAIL="no-reply@test.com")
    def test_send(self, send_mock, render_mock):
        """Weclome email is sent"""
        render_mock.return_value = "mocked_render"
        send_welcome_email(self.tenant.schema_name, str(self.user.pk))
        send_mock.assert_called_once_with(
            subject="Welcome to Test",
            message="mocked_render",
            recipient=self.user.email,
            sender_email="no-reply@test.com",
            sender_name=self.tenant.name,
        )
        render_mock.assert_called_once_with(
            "users/welcome.html",
            {
                "user": self.user,
                "contact_email": "info@test.com",
                "website": "Test",
            },
        )

    def test_user_not_found(self, send_mock, render_mock):
        """Email not sent if user not found"""
        render_mock.return_value = "mocked_render"
        send_welcome_email(
            self.tenant.schema_name,
            "1ba8feaf-f33d-437b-b6e9-0db0c01f66b9",
        )
        send_mock.assert_not_called()
