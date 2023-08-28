"""Asynchronous tasks"""

import logging
from typing import Optional

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from django_tenants.utils import schema_context

from apps.common.mail import send_mail
from apps.common.sms import send_sms
from apps.orders.models import Order, OrderItem
from apps.tenants.models import Tenant


@shared_task
def send_email_order_received(schema_name: str, order_id: int) -> None:
    """Send order received email."""
    with schema_context(schema_name):
        order = Order.objects.get(pk=order_id)
        tenant = Tenant.objects.get(schema_name=schema_name)

        if order.owner and settings.MAIL_SENDER_EMAIL:
            mail_subject = "Order Received"
            message = render_to_string(
                "orders/order_received.html",
                {
                    "order": order,
                    "website": tenant.name,
                    "contact_email": tenant.contact_email,
                },
            )
            send_mail(
                subject=mail_subject,
                message=message,
                recipient=order.owner.email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error(
                "Order received email failed: MAIL_SENDER_EMAIL or owner is null"
            )


@shared_task
def send_email_order_item_status(schema_name, order_item_id):
    """Send email when the status of order item changes."""
    with schema_context(schema_name):
        item = OrderItem.objects.get(pk=order_item_id)

        if item.order.owner and settings.MAIL_SENDER_EMAIL:
            tenant = Tenant.objects.get(schema_name=schema_name)
            subject = "Order Item Status"
            message = render_to_string(
                "orders/order_item_status.html",
                {
                    "item": item,
                    "website": tenant.name,
                },
            )
            send_mail(
                subject=subject,
                message=message,
                recipient=item.order.owner.email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error(
                "Item status changed email failed: MAIL_SENDER_EMAIL or owner is null"
            )


@shared_task
def send_admin_email_new_order(schema_name: str, order_id: int) -> None:
    """Send email to admin that a new order has been placed"""
    with schema_context(schema_name):
        tenant = Tenant.objects.get(schema_name=schema_name)

        if not tenant.notification_email:
            return

        if settings.MAIL_SENDER_EMAIL:
            order = Order.objects.get(pk=order_id)
            earliest_due_item: Optional["OrderItem"] = (
                order.items.filter(
                    Q(status=OrderItem.Status.IN_PROGRESS)
                    | Q(status=OrderItem.Status.PENDING)
                )
                .order_by("due_date")
                .first()
            )
            customer_name: str = ""
            earliest_due_date: str = ""

            if order.owner:
                customer_name = order.owner.full_name

            if earliest_due_item:
                earliest_due_date = earliest_due_item.due_date.strftime("%d, %b %Y")

            message = render_to_string(
                "orders/order_new.html",
                {
                    "customer_name": customer_name,
                    "tenant_name": tenant.name,
                    "earliest_due_date": earliest_due_date,
                },
            )
            send_mail(
                subject="New Order",
                message=message,
                recipient=tenant.notification_email,
                sender_email=settings.MAIL_SENDER_EMAIL,
                sender_name=tenant.name,
            )
        else:
            logging.error("Admin new order email failed: MAIL_SENDER_EMAIL is null")


@shared_task
def send_admin_sms_new_order(schema_name: str, order_id: int):
    """Send SMS to admin that a new order has been placed"""
    with schema_context(schema_name):
        tenant = Tenant.objects.get(schema_name=schema_name)

        if not tenant.order_sms_recipients:
            return

        if settings.AFRICAS_TALKING_USERNAME and settings.AFRICAS_TALKING_API_KEY:
            order = Order.objects.get(pk=order_id)
            earliest_due_date: str = ""

            if order.earliest_due:
                earliest_due_date = order.earliest_due.strftime("%d, %b %Y")

            # pylint: disable=line-too-long
            msg = f"{tenant.name}. New order by {order.owner}. First item is due on {earliest_due_date}"
            recipients = [
                phone_number.strip()
                for phone_number in tenant.order_sms_recipients.split(",")
            ]
            send_sms(
                username=settings.AFRICAS_TALKING_USERNAME,
                api_key=settings.AFRICAS_TALKING_API_KEY,
                message=msg,
                recipients=recipients,
                sender_id=settings.AFRICAS_TALKING_SENDER_ID,
            )
        else:
            logging.error(
                "Admin new order SMS failed: AFRICAS_TALKING_USERNAME or AFRICAS_TALKING_API_KEY is null"
            )
