"""Celery tasks"""

import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_tenants.utils import schema_context

from apps.common.mail import send_mail
from apps.common.utils import get_absolute_web_url
from apps.tenants.models import Tenant

from .tokens import EmailChangeTokenGenerator, VerifyEmailTokenGenerator

User = get_user_model()


@shared_task
def send_email_change_verification(schema_name, user_id, new_email):
    """Send verification for change in email"""
    with schema_context(schema_name):
        try:
            user = User.objects.get(pk=user_id)

        except User.DoesNotExist:
            return

        webapp_relative_url = settings.WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL

        if user.profile_type == User.ProfileType.STAFF:
            webapp_relative_url = settings.WEBAPP_ADMIN_EMAIL_CHANGE_CONFIRM_URL

        if not webapp_relative_url:
            logging.error(
                "setting WEBAPP_CUSTOMER_EMAIL_CHANGE_CONFIRM_URL\
                WEBAPP_ADMIN_EMAIL_CHANGE_CONFIRM_URL or not set"
            )
            return

        tenant = Tenant.objects.get(schema_name=schema_name)
        absolute_url = get_absolute_web_url(tenant, webapp_relative_url)

        if not absolute_url:
            return

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        emailb64 = urlsafe_base64_encode(force_bytes(new_email))
        token = EmailChangeTokenGenerator().make_token(user)
        encoded_url = f"{absolute_url}/{uidb64}/{emailb64}/{token}"
        message = render_to_string(
            "users/verify_email_change.html",
            {
                "user": user,
                "url": encoded_url,
                "website": tenant.name,
                "contact_email": tenant.contact_email,
            },
        )
        if settings.MAIL_SENDER_EMAIL:
            send_mail(
                subject="Verify your email",
                message=message,
                recipient=new_email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error("Change email verification failed: MAIL_SENDER_EMAIL is null")


@shared_task
def send_signup_email_verification(schema_name, user_id):
    """Send email verification"""
    webapp_relative_url = settings.WEBAPP_VERIFY_EMAIL_URL

    if not webapp_relative_url:
        logging.error("setting WEBAPP_VERIFY_EMAIL_URL not set")
        return

    with schema_context(schema_name):
        try:
            user = User.objects.get(pk=user_id)

        except User.DoesNotExist:
            return

        tenant = Tenant.objects.get(schema_name=schema_name)
        absolute_url = get_absolute_web_url(tenant, webapp_relative_url)

        if absolute_url and settings.MAIL_SENDER_EMAIL:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = VerifyEmailTokenGenerator().make_token(user)
            encoded_url = f"{absolute_url}/{uidb64}/{token}"
            message = render_to_string(
                "users/verify_email_signup.html",
                {
                    "user": user,
                    "url": encoded_url,
                    "website": tenant.name,
                    "contact_email": tenant.contact_email,
                },
            )
            send_mail(
                subject="Verify your email",
                message=message,
                recipient=user.email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error(
                "Sign verify email failed: MAIL_SENDER_EMAIL or absolute_url is null"
            )


@shared_task
def send_password_reset_email_verification(schema_name, user_id):
    """Send email verification."""
    with schema_context(schema_name):
        try:
            user = User.objects.get(pk=user_id)

        except User.DoesNotExist:
            return

        webapp_relative_url = settings.WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL

        if user.profile_type == User.ProfileType.STAFF:
            webapp_relative_url = settings.WEBAPP_ADMIN_PASSWORD_RESET_CONFIRM_URL

        if not webapp_relative_url:
            logging.error(
                "setting WEBAPP_CUSTOMER_PASSWORD_RESET_CONFIRM_URL\
                WEBAPP_ADMIN_PASSWORD_RESET_CONFIRM_URL or not set"
            )
            return

        tenant = Tenant.objects.get(schema_name=schema_name)
        absolute_url = get_absolute_web_url(tenant, webapp_relative_url)

        if not absolute_url:
            return

        mail_subject = "Password Reset"
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)
        encoded_url = f"{absolute_url}/{uidb64}/{token}"
        message = render_to_string(
            "users/password_reset.html",
            {
                "user": user,
                "url": encoded_url,
                "website": tenant.name,
                "contact_email": tenant.contact_email,
            },
        )
        if settings.MAIL_SENDER_EMAIL:
            send_mail(
                subject=mail_subject,
                message=message,
                recipient=user.email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error("Password reset email failed: MAIL_SENDER_EMAIL is null")


@shared_task
def send_welcome_email(schema_name, user_id):
    """Send welcome email to a new user"""
    with schema_context(schema_name):
        try:
            user = User.objects.get(pk=user_id)

        except User.DoesNotExist:
            return

        tenant = Tenant.objects.get(schema_name=schema_name)
        mail_subject = f"Welcome to {tenant.name}"
        message = render_to_string(
            "users/welcome.html",
            {
                "user": user,
                "contact_email": tenant.contact_email,
                "website": tenant.name,
            },
        )
        if settings.MAIL_SENDER_EMAIL:
            send_mail(
                subject=mail_subject,
                message=message,
                recipient=user.email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error("Welcome email failed: MAIL_SENDER_EMAIL is null")
