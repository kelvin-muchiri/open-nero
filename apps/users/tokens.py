"""Activation tokens"""
import six
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    """Token generator for change in email link"""

    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk)
            + six.text_type(timestamp)
            + six.text_type(user.email)
        )


class VerifyEmailTokenGenerator(PasswordResetTokenGenerator):
    """Token generator for verify email link"""

    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk)
            + six.text_type(timestamp)
            + six.text_type(user.is_email_verified)
        )
