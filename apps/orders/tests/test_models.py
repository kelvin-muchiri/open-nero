""""models"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DataError, transaction
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from apps.orders.models import (
    Order,
    OrderCoupon,
    OrderItem,
    OrderItemAttachment,
    OrderItemPaper,
    Rating,
)

# pylint: disable=too-many-locals

USER = get_user_model()


class OrderTestCase(FastTenantTestCase):
    """Tests for model `Order`"""

    def setUp(self):
        super().setUp()

        self.owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        self.order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        OrderItem.objects.create(
            order=self.order,
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )

    def test_creation(self):
        """Ensure we can create an `OrderItem` object"""
        self.assertTrue(isinstance(self.order, Order))
        self.assertEqual(f"{self.order}", str(self.order.id))
        self.assertEqual(self.order.owner, self.owner)
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_owner_can_be_null(self):
        """Ensure `owner` can be null"""
        order = Order.objects.create()
        self.assertEqual(order.owner, None)

    def test_status_default(self):
        """Ensure the default status is correct"""
        order = Order.objects.create(owner=self.owner)
        self.assertEqual(order.status, Order.Status.UNPAID)

    def test_original_amount_payable(self):
        """Ensure amount payable before discount is correct"""
        self.assertEqual(self.order.original_amount_payable, 250.00)

    def test_order_amount_payable(self):
        """Ensure the amount payable after discount is correct"""
        # Before discount
        self.assertEqual(self.order.amount_payable, 250.00)
        OrderCoupon.objects.create(order=self.order, code="MCER", discount=20.00)
        # After discount
        self.assertEqual(self.order.amount_payable, 230.00)
        self.assertEqual(self.order.original_amount_payable, 250.00)

    def test_discount(self):
        """Ensure property discount is correct"""
        # Before discount
        self.assertEqual(self.order.discount, 0.00)
        OrderCoupon.objects.create(order=self.order, code="MCER", discount=20.00)
        # After discount
        self.assertEqual(self.order.discount, 20.00)

    def test_total_amount_paid(self):
        """Ensure property total amount paid is correct"""
        # Before payment
        self.assertEqual(self.order.total_amount_paid, 0.00)
        # After payment
        self.order.payments.create(
            trx_ref_number="POPAPLL",
            paid_by=self.owner,
            amount_paid=250.00,
            status="COMPLETED",
        )
        self.assertEqual(self.order.total_amount_paid, 250.00)

        # If multiple payments were made separately
        self.order.payments.all().delete()
        self.order.payments.create(
            trx_ref_number="POPAPLL",
            paid_by=self.owner,
            amount_paid=100.00,
            status="COMPLETED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL2",
            paid_by=self.owner,
            amount_paid=100.00,
            status="COMPLETED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL3",
            paid_by=self.owner,
            amount_paid=50.00,
            status="COMPLETED",
        )
        self.assertEqual(self.order.total_amount_paid, 250.00)

        # only completed payments count
        self.order.payments.all().delete()
        self.order.payments.create(
            trx_ref_number="POPAPL4",
            paid_by=self.owner,
            amount_paid=250.00,
            status="REFUNDED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL5",
            paid_by=self.owner,
            amount_paid=250.00,
            status="PARTIALLY_REFUNDED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL5",
            paid_by=self.owner,
            amount_paid=250.00,
            status="FAILED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL5",
            paid_by=self.owner,
            amount_paid=250.00,
            status="PENDING",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL5",
            paid_by=self.owner,
            amount_paid=250.00,
            status="DECLINED",
        )
        self.assertEqual(self.order.total_amount_paid, 0.00)

        # a refund is subtracted from total amount paid
        self.order.payments.all().delete()
        self.order.payments.create(
            trx_ref_number="POPAPL6",
            paid_by=self.owner,
            amount_paid=250.00,
            status="COMPLETED",
        )
        self.order.payments.create(
            trx_ref_number="POPAPL7",
            paid_by=self.owner,
            amount_paid=10.00,
            status="REFUNDED",
        )
        self.assertEqual(self.order.total_amount_paid, 240.00)
        # Excess refund
        self.order.payments.create(
            trx_ref_number="POPAP10",
            paid_by=self.owner,
            amount_paid=300.00,
            status="REFUNDED",
        )
        self.assertEqual(self.order.total_amount_paid, 0.00)

    def test_balance(self):
        """Ensure property balance returns the correct value"""
        # Before payment
        self.assertEqual(self.order.balance, 250.00)
        self.order.payments.create(
            trx_ref_number="POPAPLL",
            paid_by=self.owner,
            amount_paid=250.00,
            status="COMPLETED",
        )
        # After full payment
        self.assertEqual(self.order.balance, 0.00)

        # After partial payment
        self.order.payments.all().delete()
        self.order.payments.create(
            trx_ref_number="POPAPLL",
            paid_by=self.owner,
            amount_paid=100.00,
            status="COMPLETED",
        )
        self.assertEqual(self.order.balance, 150.00)

        # After excess payment
        self.order.payments.all().delete()
        self.order.payments.create(
            trx_ref_number="POPAPLL",
            paid_by=self.owner,
            amount_paid=300.00,
            status="COMPLETED",
        )
        self.assertEqual(self.order.balance, 0.00)

    def test_earliest_due(self):
        """Ensure the value for property `earliest_due` is correct"""
        order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)

        due_date_1 = timezone.now() + timedelta(days=1)
        due_date_2 = timezone.now() + timedelta(days=2)

        # Item with earliest due date is in progress
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, due_date_1)

        # Item with earliest due date is complete
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, due_date_2)

        # Item with earliest due date is pending
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.PENDING,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, due_date_1)

        # Item with earliest due date is void
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.VOID,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, due_date_2)

        # All items complete
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, None)

        # All items either complete or void
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.VOID,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=due_date_2,
        )
        order.refresh_from_db()
        self.assertEqual(order.earliest_due, None)

        # An unpaid order returns None
        unpaid_order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        OrderItem.objects.create(
            order=unpaid_order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_1,
        )
        OrderItem.objects.create(
            order=unpaid_order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=due_date_2,
        )
        unpaid_order.refresh_from_db()
        self.assertEqual(order.earliest_due, None)

    def test_is_complete(self):
        """Ensure property `is_complete` returns the correct value"""
        order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        # Returns true if all items are complete
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        order.refresh_from_db()
        self.assertTrue(order.is_complete)

        # Returns true if all items are either complete or void
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() + timedelta(days=1),
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        order.refresh_from_db()
        self.assertTrue(order.is_complete)

        # Returns false if at least one item is pending
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        order.refresh_from_db()
        self.assertFalse(order.is_complete)

        # Returns false if at least one item is in progress
        order.items.all().delete()
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(days=1),
        )
        OrderItem.objects.create(
            order=order,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        order.refresh_from_db()
        self.assertFalse(order.is_complete)


class OrderItemTestCase(FastTenantTestCase):
    """Tests for model `OrderItem`"""

    def setUp(self):
        self.owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        self.order = Order.objects.create(owner=self.owner)
        self.due_date = timezone.now() + timedelta(days=1)
        self.topic = "This is a topic"
        self.item = OrderItem.objects.create(
            order=self.order,
            topic="This is a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=self.due_date,
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
            comment="Hello world",
        )

    def test_creation(self):
        """Ensure we can create an `OrderIterm` object"""
        self.assertTrue(isinstance(self.item, OrderItem))
        self.assertEqual(
            f"{self.item}",
            f"{self.order.id} - {self.item.paper} - {self.item.topic}",
        )
        self.assertEqual(self.item.topic, "This is a topic")
        self.assertEqual(self.item.level, "TestLevel")
        self.assertEqual(self.item.course, "TestCourse")
        self.assertEqual(self.item.paper, "TestPaper")
        self.assertEqual(self.item.paper_format, "TestFormat")
        self.assertEqual(self.item.deadline, "1 Day")
        self.assertEqual(self.item.language, "English UK")
        self.assertEqual(self.item.pages, 5)
        self.assertEqual(self.item.references, 3)
        self.assertEqual(self.item.quantity, 2)
        self.assertEqual(self.item.page_price, 20)
        self.assertEqual(self.item.due_date, self.due_date)
        self.assertEqual(self.item.writer_type, "Premium")
        self.assertEqual(self.item.writer_type_price, 5)
        self.assertEqual(self.item.status, OrderItem.Status.IN_PROGRESS)
        self.assertEqual(self.item.comment, "Hello world")

    def test_unit_price(self):
        """Ensure the unit price is correct"""
        self.assertEqual(self.item.price, 125.00)

    def test_total_price(self):
        """Ensure the total price is correct."""
        self.assertEqual(self.item.total_price, 250.00)

    def test_is_overdue(self):
        """Ensure correct return value if property `is_overdue`"""
        order_paid = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        order_unpaid = Order.objects.create(
            owner=self.owner, status=Order.Status.UNPAID
        )

        # A paid order item whose status is `In Progress` should
        # return false if due date is > current date/time
        order_paid_item_1 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due  date
        )
        self.assertFalse(order_paid_item_1.is_overdue)

        # A paid order item whose status is `In Progress` should
        # return true if due date < current date/time
        order_paid_item_2 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertTrue(order_paid_item_2.is_overdue)

        # A paid order item whose status is `Pending` should
        # return false if due date > current date/time
        order_paid_item_3 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due  date
        )
        self.assertFalse(order_paid_item_3.is_overdue)

        # A paid order item whose status is `Pending` should
        # return true if due date < current date/time
        order_paid_item_4 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertTrue(order_paid_item_4.is_overdue)

        # An unpaid order item whose status is `In Progress` should
        # return false if due date > current date/time
        order_unpaid_item_1 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due  date
        )
        self.assertFalse(order_unpaid_item_1.is_overdue)

        # An unpaid order item whose status is `In Progress` should
        # return false if due date < current date/time
        order_unpaid_item_2 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_unpaid_item_2.is_overdue)

        # An unpaid order item whose status is `Pending` should
        # return false if due date > current date/time
        order_unpaid_item_3 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due  date
        )
        self.assertFalse(order_unpaid_item_3.is_overdue)

        # An unpaid order item whose status is `Pending` should
        # return false if due date < current date/time
        order_unpaid_item_4 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_unpaid_item_4.is_overdue)

        # A paid order item whose status is `Complete` should return
        # false if due date > current date/time
        order_paid_item_5 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due date
        )
        self.assertFalse(order_paid_item_5.is_overdue)

        # A paid order item whose status is `Complete` should return
        # false if due date < current date/time
        order_paid_item_6 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_paid_item_6.is_overdue)

        # An unpaid order item whose status is `Complete` should return
        # false if due date > current date/time
        order_unpaid_item_5 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due date
        )
        self.assertFalse(order_unpaid_item_5.is_overdue)

        # An upaid order item whose status is `Complete` should return
        # false if due date < current date/time
        order_unpaid_item_6 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_unpaid_item_6.is_overdue)

        # A paid order item whose status is `Void` should return
        # false if due date > current date/time
        order_paid_item_7 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due date
        )
        self.assertFalse(order_paid_item_7.is_overdue)

        # A paid order item whose status is `Void` should return
        # false if due date < current date/time
        order_paid_item_8 = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_paid_item_8.is_overdue)

        # An unpaid order item whose status is `Void` should return
        # false if due date > current date/time
        order_unpaid_item_7 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due date
        )
        self.assertFalse(order_unpaid_item_7.is_overdue)

        # An upaid order item whose status is `Void` should return
        # false if due date < current date/time
        order_unpaid_item_8 = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertFalse(order_unpaid_item_8.is_overdue)

    def test_days_left(self):
        """Ensure property `days_left` returns the correct value"""
        order_paid = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        order_unpaid = Order.objects.create(
            owner=self.owner, status=Order.Status.UNPAID
        )

        # A paid order item whose status is `In Progress` and not overdue
        order_paid_not_overdue = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(days=1),  # Simulate future due  date
        )
        self.assertEqual(order_paid_not_overdue.days_left, 0)

        # A paid order item whose status is `In Progress` and due date is in hours
        order_paid_hours = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(hours=12),  # Simulate future due  date
        )
        self.assertEqual(order_paid_hours.days_left, 0)

        # A paid order item whose status is `In Progress` and overdue
        order_paid_overdue = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() - timedelta(days=1),  # Simulate past due date
        )
        self.assertEqual(order_paid_overdue.days_left, -2)

        # A paid order item whose status is `Pending`
        order_paid_pending = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_paid_pending.days_left, 0)

        # A paid order item whose status is `Complete`
        order_paid_complete = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_paid_complete.days_left, None)

        # A paid order item whose status is `Void`
        order_paid_void = OrderItem.objects.create(
            order=order_paid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_paid_void.days_left, None)

        # UnPaid orders start here

        # A unpaid order item whose status is `In Progress`
        order_unpaid_in_progress = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.IN_PROGRESS,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_unpaid_in_progress.days_left, None)

        # A unpaid order item whose status is `Pending`
        order_unpaid_pending = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_unpaid_pending.days_left, None)

        # A unpaid order item whose status is `Complete`
        order_unpaid_complete = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.COMPLETE,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_unpaid_complete.days_left, None)

        # A unpaid order item whose status is `Void`
        order_unpaid_void = OrderItem.objects.create(
            order=order_unpaid,
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
            status=OrderItem.Status.VOID,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(order_unpaid_void.days_left, None)

    def test_defaults(self):
        """Ensure the defaults are correct"""

        order = Order.objects.create(owner=self.owner)
        item = OrderItem.objects.create(
            order=order,
            topic="This a topic",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            page_price=20,
            due_date=self.due_date,
        )
        self.assertEqual(item.status, OrderItem.Status.PENDING)
        self.assertEqual(item.writer_type, None)
        self.assertEqual(item.writer_type_price, None)
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.pages, 1)
        self.assertEqual(item.references, None)
        self.assertEqual(item.comment, None)
        self.assertEqual(item.level, None)


class OrderCouponTestCase(FastTenantTestCase):
    """Tests for model `OrderCoupon`"""

    def setUp(self):
        self.owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        self.order = Order.objects.create(owner=self.owner)
        self.item = OrderItem.objects.create(
            order=self.order,
            topic="This is a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
            comment="Hello world",
        )
        self.order_coupon = OrderCoupon.objects.create(
            order=self.order, code="test", discount=20.00
        )

    def test_creation(self):
        """Ensure we can create an `OrderItemPaper` object"""
        self.assertTrue(isinstance(self.order_coupon, OrderCoupon))
        self.assertEqual(self.order_coupon.order, self.order)
        self.assertEqual(self.order_coupon.code, "test")
        self.assertEqual(self.order_coupon.discount, 20.000)
        self.assertEqual(
            f"{self.order_coupon}",
            f"{self.order} - {self.order_coupon.code} - {self.order_coupon.discount}",
        )


# Mock storage backends to prevent a file from being saved on
# disk (https://cscheng.info/2018/08/21/mocking-a-file-storage-backend-in-django-tests.html)
@mock.patch("django.core.files.storage.FileSystemStorage.save")
@mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
class RatingTestCase(FastTenantTestCase):
    """Tests for model `Rating`"""

    def setUp(self):
        owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        order = Order.objects.create(owner=owner)
        self.order_item = OrderItem.objects.create(
            order=order,
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )
        self.file_name = "best_file_eva.txt"
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )

    def test_creation(self, mock_s3_save, mock_file_storage_save):
        """Ensure we can create a `Rating`"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        paper = OrderItemPaper.objects.create(
            order_item=self.order_item, paper=self.file_field
        )
        rating = Rating.objects.create(paper=paper, rating=5, comment="Great work")
        self.assertTrue(isinstance(rating, Rating))
        self.assertEqual(f"{rating}", f"{paper}")
        self.assertEqual(rating.rating, 5)
        self.assertEqual(rating.comment, "Great work")

    def test_comment_length(self, mock_s3_save, mock_file_storage_save):
        """Ensure the comment length is correct"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        paper = OrderItemPaper.objects.create(
            order_item=self.order_item, paper=self.file_field
        )
        # Comment should not exceed 255
        with transaction.atomic(), self.assertRaises(DataError):
            # 256 chars
            Rating.objects.create(
                paper=paper,
                rating=5,
                comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in",
            )

        # Does not raise error if comment is 255 chars
        Rating.objects.create(
            paper=paper,
            rating=5,
            comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor i",
        )

    def test_comment_can_be_null(self, mock_s3_save, mock_file_storage_save):
        """Ensure `comment` field can be null"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        paper = OrderItemPaper.objects.create(
            order_item=self.order_item, paper=self.file_field
        )
        rating = Rating.objects.create(paper=paper, rating=5)
        self.assertEqual(rating.comment, None)


# Mock storage backends to prevent a file from being saved on
# disk (https://cscheng.info/2018/08/21/mocking-a-file-storage-backend-in-django-tests.html)
@mock.patch("django.core.files.storage.FileSystemStorage.save")
@mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
class OrderItemPaperTestCase(FastTenantTestCase):
    """Add tests for model `OrderItemPaper`"""

    def setUp(self):
        owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        order = Order.objects.create(owner=owner)
        self.order_item = OrderItem.objects.create(
            order=order,
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestPaper",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )
        self.file_name = "best_file_eva.txt"
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )

    def test_creation(self, mock_s3_save, mock_file_storage_save):
        """Ensure we can create a `OrderItemPaper`"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        paper = OrderItemPaper.objects.create(
            order_item=self.order_item,
            paper=self.file_field,
            comment="Do not forget to rate",
        )
        self.assertEqual(f"{paper}", f"{self.order_item}")
        self.assertEqual(paper.paper.name, self.file_name)
        self.assertEqual(paper.comment, "Do not forget to rate")

    def test_comment_length(self, mock_s3_save, mock_file_storage_save):
        """Ensure the comment length is correct"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        # Comment should not exceed 255
        with transaction.atomic(), self.assertRaises(DataError):
            # 256 chars
            OrderItemPaper.objects.create(
                order_item=self.order_item,
                paper=self.file_field,
                comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in",
            )

        # Does not raise error if comment is 255 chars
        OrderItemPaper.objects.create(
            order_item=self.order_item,
            paper=self.file_field,
            comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor i",
        )

    def test_comment_can_be_null(self, mock_s3_save, mock_file_storage_save):
        """Ensure `comment` field can be null"""
        mock_s3_save.return_value = self.file_name
        mock_file_storage_save.return_value = self.file_name
        paper = OrderItemPaper.objects.create(
            order_item=self.order_item,
            paper=self.file_field,
        )
        self.assertEqual(paper.comment, None)


class OrderItemAttachmentTestCase(FastTenantTestCase):
    """Add tests for model `OrderItemAttachment`"""

    def setUp(self):
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name

        owner = USER.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
        )
        order = Order.objects.create(owner=owner)
        self.order_item = OrderItem.objects.create(
            order=order,
            topic="This a topic",
            level="TestLevel",
            course="TestCourse",
            paper="TestAttachment",
            paper_format="TestFormat",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )
        self.file_field = SimpleUploadedFile(
            self.file_name, b"these are the file contents!"
        )

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def test_creation(self):
        """Ensure we can create a `OrderItemAttachment`"""
        attachment = OrderItemAttachment.objects.create(
            order_item=self.order_item,
            attachment=self.file_field,
            comment="Do not forget to rate",
        )
        self.assertEqual(
            f"{attachment}", f"{self.order_item} - {attachment.attachment.name}"
        )
        self.assertEqual(attachment.attachment.name, self.file_name)
        self.assertEqual(attachment.comment, "Do not forget to rate")
        self.assertEqual(attachment.file_path, self.file_name)

    def test_comment_length(self):
        """Ensure the comment length is correct"""
        # Comment should not exceed 255
        with transaction.atomic(), self.assertRaises(DataError):
            # 256 chars
            OrderItemAttachment.objects.create(
                order_item=self.order_item,
                attachment=self.file_field,
                comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in",
            )

        # Does not raise error if comment is 255 chars
        OrderItemAttachment.objects.create(
            order_item=self.order_item,
            attachment=self.file_field,
            comment="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor i",
        )

    def test_comment_can_be_null(self):
        """Ensure `comment` field can be null"""
        attachment = OrderItemAttachment.objects.create(
            order_item=self.order_item,
            attachment=self.file_field,
        )
        self.assertEqual(attachment.comment, None)
