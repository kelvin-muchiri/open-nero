"""Utility methods"""


from apps.orders.models import Order, OrderItem
from apps.orders.tasks import send_admin_email_new_order, send_admin_sms_new_order

from .models import Payment


def add_payment(schema_name, order, amount_paid, date_paid, **kwargs):
    """Add order payment and update items status"""
    # Check if payment exists
    trx_ref_number = kwargs.get("trx_ref_number")

    if (
        trx_ref_number
        and Payment.objects.filter(order=order, trx_ref_number=trx_ref_number).exists()
    ):
        return

    # Update order items due date
    for item in order.items.all():
        payment_elapsed_time = date_paid - order.created_at
        item.due_date = item.due_date + payment_elapsed_time

        if item.status == OrderItem.Status.PENDING:
            item.status = OrderItem.Status.IN_PROGRESS

        item.save()

    # Add payment
    Payment.objects.create(
        order=order,
        trx_ref_number=trx_ref_number,
        amount_paid=amount_paid,
        content_object=kwargs.get("gateway"),
        date_paid=date_paid,
        status=Payment.Status.COMPLETED,
    )

    # Update order status to paid if full amount is paid
    if not order.balance:
        order.status = Order.Status.PAID
        order.save()
        send_admin_email_new_order.delay(schema_name, order.id)
        send_admin_sms_new_order.delay(schema_name, order.id)


def refund_payment(order: Order, refunded_amount: float, **kwargs) -> None:
    """Refund payment"""
    trx_ref_number = kwargs.get("trx_ref_number")
    date_paid = kwargs.get("date_paid")

    Payment.objects.create(
        order=order,
        trx_ref_number=trx_ref_number,
        amount_paid=refunded_amount,
        content_object=kwargs.get("gateway"),
        date_paid=date_paid,
        status=Payment.Status.REFUNDED,
    )

    order.status = Order.Status.REFUNDED
    order.save()

    for item in order.items.all():
        item.status = OrderItem.Status.VOID
        item.save()


def decline_payment(order: "Order", amount: str, **kwargs) -> None:
    """Decline payment"""
    trx_ref_number = kwargs.get("trx_ref_number")
    date_paid = kwargs.get("date_paid")

    Payment.objects.create(
        order=order,
        trx_ref_number=trx_ref_number,
        amount_paid=amount,
        content_object=kwargs.get("gateway"),
        date_paid=date_paid,
        status=Payment.Status.DECLINED,
    )
