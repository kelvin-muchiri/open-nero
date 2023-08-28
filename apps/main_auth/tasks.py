"""Celery tasks"""
import logging

from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string
from django_tenants.utils import schema_context

from apps.common.mail import send_mail
from apps.tenants.models import Tenant

from .models import EmailVerification
from .utils import generate_email_verification_code


@shared_task
def send_email_verification_code(schema_name, recipient):
    """Celery async task to send email verification"""
    with schema_context(schema_name):
        tenant = Tenant.objects.get(schema_name=schema_name)
        code = generate_email_verification_code()
        EmailVerification.objects.create(code=code, email=recipient)
        subject = "Confirm your email address"
        message = render_to_string(
            "main_auth/verification_code.html",
            {
                "website": tenant.name,
                "code": code,
            },
        )

        if settings.MAIL_SENDER_EMAIL:
            send_mail(
                subject=subject,
                message=message,
                recipient=recipient,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )

        else:
            logging.error("Setting MAIL_SENDER_EMAIL is null")
