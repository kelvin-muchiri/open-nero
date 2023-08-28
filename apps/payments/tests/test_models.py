"""tests for models"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from apps.orders.models import Order
from apps.payments.models import Payment

USER = get_user_model()


class PaymentTestCase(FastTenantTestCase):
    """
    Tests for model Payment
    """

    def setUp(self):
        self.owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        self.order = Order.objects.create(owner=self.owner)
        self.order.items.create(
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=1,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            trx_ref_number="ASSSFD",
            paid_by=self.owner,
            amount_paid=100,
            status="COMPLETED",
        )

    def test_payment_creation(self):
        """Ensure we can create a payment object"""
        self.assertEqual(
            str(self.payment),
            f"Order {self.payment.order.id} - {self.payment.amount_paid}",
        )
        self.assertEqual(self.payment.order, self.order)
        self.assertEqual(self.payment.trx_ref_number, "ASSSFD")
        self.assertEqual(self.payment.paid_by, self.owner)
        self.assertEqual(self.payment.amount_paid, 100)
        self.assertEqual(self.payment.status, "COMPLETED")

    def test_default_status(self):
        """Default status is PENDING"""
        payment = Payment.objects.create(
            order=self.order, trx_ref_number="ASSSFD", amount_paid=100
        )
        self.assertEqual(payment.status, "PENDING")
