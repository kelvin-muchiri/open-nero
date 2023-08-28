import datetime
from datetime import timedelta
from typing import Optional
from unittest import mock

import dateutil.parser
import pytest
import pytz
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.payments.utils import add_payment, decline_payment, refund_payment
from apps.paypal.models import Paypal

# mock date so that auto_now_add returns mocked date
now_mock = datetime.datetime(2019, 2, 13, 0, 0, 0, tzinfo=pytz.utc)


@pytest.fixture
def gateway(customer):
    return Paypal.objects.create(webhook_id="webhook_id")


@pytest.mark.django_db
@mock.patch("apps.payments.utils.send_admin_email_new_order.delay")
@mock.patch("apps.payments.utils.send_admin_sms_new_order.delay")
def test_add_payment(
    send_sms_mock, send_email_mock, use_tenant_connection, customer, gateway
):
    """Order payment is updated after successful payment"""
    with mock.patch("django.utils.timezone.now", mock.Mock(return_value=now_mock)):
        # Unpaid order
        order = Order.objects.create(owner=customer, status=Order.Status.UNPAID)
        order_item = OrderItem.objects.create(
            order=order,
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=1,
            references=3,
            quantity=1,
            page_price=2.51,
            due_date=datetime.datetime(2019, 2, 20, 0, 0, 0, tzinfo=pytz.utc),
            status=OrderItem.Status.PENDING,
        )

    date_paid = dateutil.parser.parse("2019-02-14T21:50:07.940Z")
    trx_ref_number = "WH-58D329510W468432D-8HN650336L201105X"
    amount_paid = "2.51"

    add_payment(
        schema_name=FastTenantTestCase.get_test_schema_name(),
        order=order,
        amount_paid=amount_paid,
        trx_ref_number=trx_ref_number,
        date_paid=date_paid,
        gateway=gateway,
    )

    order.refresh_from_db()
    order_item.refresh_from_db()
    payment = order.payments.first()

    assert order.status == Order.Status.PAID
    assert order_item.status == OrderItem.Status.IN_PROGRESS
    assert payment.trx_ref_number == trx_ref_number
    assert str(payment.amount_paid) == amount_paid
    assert payment.status == Payment.Status.COMPLETED
    assert payment.date_paid == date_paid
    send_sms_mock.assert_called_once_with(
        FastTenantTestCase.get_test_schema_name(), order.id
    )
    send_email_mock.assert_called_once_with(
        FastTenantTestCase.get_test_schema_name(), order.id
    )

    content_type = ContentType.objects.get_for_model(gateway)

    assert payment.content_type == content_type

    date_order_created = datetime.datetime(2019, 2, 13, 0, 0, 0, tzinfo=pytz.utc)
    item_due_date = datetime.datetime(2019, 2, 20, 0, 0, 0, tzinfo=pytz.utc)
    # elapsed time since order creation is added to item due date
    elapsed_time = date_paid - date_order_created

    assert order_item.due_date == item_due_date + elapsed_time

    # duplicate transaction reference number for same order are now allowed
    add_payment(
        schema_name=FastTenantTestCase.get_test_schema_name(),
        order=order,
        amount_paid=amount_paid,
        trx_ref_number=trx_ref_number,
        date_paid=date_paid,
        gateway=gateway,
    )

    assert Payment.objects.all().count() == 1


@pytest.mark.django_db
def test_refund_payment(use_tenant_connection, customer, gateway):
    """Order payment status is updated after refund"""
    order = Order.objects.create(owner=customer, status=Order.Status.PAID)
    order_item = OrderItem.objects.create(
        order=order,
        topic="This a topic",
        level="TestLevel",
        course="TestCourse",
        paper="TestPaper",
        paper_format="TestFormat",
        deadline="1 Day",
        language="English UK",
        pages=1,
        references=3,
        quantity=1,
        page_price=2.51,
        due_date=timezone.now() + timedelta(days=1),
        status=OrderItem.Status.IN_PROGRESS,
    )
    trx_ref_number = "WH-1GE84257G0350133W-6RW800890C634293G"
    amount_refunded = "1.98"
    date_refunded = dateutil.parser.parse("2018-08-15T19:14:04.543Z")

    refund_payment(
        order=order,
        refunded_amount=amount_refunded,
        trx_ref_number=trx_ref_number,
        date_paid=date_refunded,
        gateway=gateway,
    )

    order.refresh_from_db()
    order_item.refresh_from_db()

    assert order.status == Order.Status.REFUNDED
    assert order_item.status == OrderItem.Status.VOID

    payment: Optional["Payment"] = order.payments.all().order_by("-created_at").first()

    assert payment.trx_ref_number == trx_ref_number
    assert str(payment.amount_paid) == amount_refunded
    assert payment.status == Payment.Status.REFUNDED

    content_type = ContentType.objects.get_for_model(gateway)

    assert payment.content_type == content_type


@pytest.mark.django_db
def test_decline_payment(use_tenant_connection, customer, gateway):
    """Declined payment is recorded"""
    order = Order.objects.create(owner=customer, status=Order.Status.UNPAID)

    decline_payment(
        order=order,
        amount="2.51",
        trx_ref_number="123",
        date_paid=dateutil.parser.parse("2018-08-15T19:14:04.543Z"),
        gateway=gateway,
    )

    payment = order.payments.first()

    assert payment.trx_ref_number == "123"
    assert str(payment.amount_paid) == "2.51"
    assert payment.status == Payment.Status.DECLINED
