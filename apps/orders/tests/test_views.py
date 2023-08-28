import json
from datetime import timedelta
from unittest import mock

import dateutil
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Attachment, Cart, Item
from apps.catalog.models import Course, Deadline, Format, Level, Paper
from apps.common.utils import reverse_querystring
from apps.coupon.models import Coupon
from apps.orders.models import (
    Order,
    OrderCoupon,
    OrderItem,
    OrderItemAttachment,
    OrderItemPaper,
    Rating,
)
from apps.subscription.models import Subscription
from apps.users.models import User


class GetAllSelfOrdersTestCase(FastTenantTestCase):
    """Tests for GET all orders by self"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        # Paid order
        self.order_paid = Order.objects.create(
            owner=self.owner, status=Order.Status.PAID
        )
        self.order_paid_item_1 = OrderItem.objects.create(
            order=self.order_paid,
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
        # Unpaid order
        self.order_unpaid = Order.objects.create(
            owner=self.owner, status=Order.Status.UNPAID
        )
        self.order_unpaid_item_1 = OrderItem.objects.create(
            order=self.order_unpaid,
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
        # Complete order
        self.order_complete = Order.objects.create(
            owner=self.owner, status=Order.Status.PAID
        )
        self.order_complete_item_1 = OrderItem.objects.create(
            order=self.order_complete,
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
            status=OrderItem.Status.COMPLETE,
        )
        self.order_complete_item_2 = OrderItem.objects.create(
            order=self.order_complete,
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
            status=OrderItem.Status.VOID,
        )

    def get(self, user=None):
        """Method GET"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.get(reverse("self_order-list"))

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.get(reverse("self_order-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_orders(self):
        """Ensure the response no orders are available is correct"""
        user = User.objects.create_user(
            username="janedoe",
            first_name="Jane",
            email="janedoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        response = self.get(user)
        self.assertEqual(response.data["results"], [])

    def test_orders_available(self):
        """Ensure the response when orders are available is correct"""
        response = self.get()
        self.maxDiff = None
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = json.dumps(
            [
                {
                    "id": self.order_complete.id,
                    "status": self.order_complete.status,
                    "is_complete": True,
                    "created_at": self.order_complete.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "earliest_due": None,
                },
                {
                    "id": self.order_unpaid.id,
                    "status": self.order_unpaid.status,
                    "is_complete": False,
                    "created_at": self.order_unpaid.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "earliest_due": None,
                },
                {
                    "id": self.order_paid.id,
                    "status": self.order_paid.status,
                    "is_complete": False,
                    "created_at": self.order_paid.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "earliest_due": self.order_paid.earliest_due.isoformat().replace(
                        "+00:00", "Z"
                    ),
                },
            ],
            cls=DjangoJSONEncoder,
        )
        self.assertEqual(
            json.dumps(response.data["results"], cls=DjangoJSONEncoder), expected
        )

    def test_owner(self):
        """Ensure orders returned belong to logged in user"""
        user_1 = User.objects.create_user(
            username="janedoe",
            first_name="Jane",
            email="janedoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        user_2 = User.objects.create_user(
            username="johndoe",
            first_name="John",
            email="johndoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        user_1_order = Order.objects.create(owner=user_1, status=Order.Status.PAID)
        Order.objects.create(owner=user_2, status=Order.Status.PAID)
        response = self.get(user_1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0].get("id"), user_1_order.id)


@pytest.mark.django_db
class TestGetSingleSelfOrder:
    """Tests for GET single order"""

    @pytest.fixture()
    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def set_up(self, mock_system_save, mock_s3_save, customer):
        # Mock storage backends to prevent a file from being saved on disk
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name
        file_field = SimpleUploadedFile(file_name, b"these are the file contents!")

        order = Order.objects.create(owner=customer, status=Order.Status.PAID)
        item_1 = OrderItem.objects.create(
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
        paper_1 = OrderItemPaper.objects.create(
            order_item=item_1, paper=file_field, comment="We added an extra page"
        )
        paper_1_attachment = OrderItemAttachment.objects.create(
            order_item=item_1, attachment=file_field, comment="Hello"
        )
        paper_1_rating = Rating.objects.create(
            paper=paper_1, rating=5, comment="Great work"
        )
        order_coupon = OrderCoupon.objects.create(order=order, code="test", discount=20)

        return locals()

    def test_auth_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        set_up,
        create_active_subscription,
    ):
        """Authentication is required"""
        order = set_up["order"]
        response = fast_tenant_client.get(
            reverse("self_order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_single_order(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        set_up,
        create_active_subscription,
    ):
        """Returns a single order"""
        order = set_up["order"]
        order_coupon = set_up["order_coupon"]
        item_1 = set_up["item_1"]
        paper_1 = set_up["paper_1"]
        paper_1_rating = set_up["paper_1_rating"]
        paper_1_attachment = set_up["paper_1_attachment"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(
            reverse("self_order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": order.id,
                "owner": {
                    "id": str(order.owner.id),
                    "full_name": order.owner.full_name,
                    "email": order.owner.email,
                },
                "status": order.status,
                "is_complete": False,
                "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
                "earliest_due": order.earliest_due.isoformat().replace("+00:00", "Z"),
                "coupon": {"code": order_coupon.code, "discount": "20.00"},
                "balance": order.balance,
                "amount_payable": order.amount_payable,
                "original_amount_payable": order.original_amount_payable,
                "items": [
                    {
                        "id": item_1.id,
                        "order": {
                            "id": order.id,
                            "owner": {
                                "id": str(order.owner.id),
                                "full_name": order.owner.full_name,
                                "email": order.owner.email,
                            },
                            "status": order.status,
                        },
                        "topic": item_1.topic,
                        "level": item_1.level,
                        "course": item_1.course,
                        "paper": item_1.paper,
                        "paper_format": item_1.paper_format,
                        "deadline": item_1.deadline,
                        "language": item_1.language,
                        "pages": item_1.pages,
                        "references": item_1.references,
                        "quantity": item_1.quantity,
                        "comment": item_1.comment,
                        "due_date": item_1.due_date.isoformat().replace("+00:00", "Z"),
                        "status": item_1.status,
                        "days_left": item_1.days_left,
                        "price": item_1.price,
                        "total_price": item_1.total_price,
                        "writer_type": item_1.writer_type,
                        "writer_type_price": "5.00",
                        "is_overdue": item_1.is_overdue,
                        "created_at": item_1.created_at.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "attachments": [
                            {
                                "id": str(paper_1_attachment.pk),
                                "file_path": paper_1_attachment.file_path,
                                "comment": paper_1_attachment.comment,
                            }
                        ],
                        "papers": [
                            {
                                "id": str(paper_1.pk),
                                "file_name": "test.doc",
                                "comment": paper_1.comment,
                                "rating": {
                                    "rating": paper_1_rating.rating,
                                    "comment": paper_1_rating.comment,
                                },
                            }
                        ],
                    }
                ],
            },
            cls=DjangoJSONEncoder,
        )

    def test_get_invalid_order(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Ensure get invalid single order is correct."""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(
            reverse(
                "self_order-detail",
                kwargs={"pk": "3351cacd-13e4-412d-bb44-636bab7e0ea7"},
            ),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_earlist_due(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        set_up,
        create_active_subscription,
    ):
        """Ensure the earliest_due response is correct"""
        order = set_up["order"]
        item_1 = set_up["item_1"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        # Unpaid order
        unpaid_order = Order.objects.create(owner=customer, status=Order.Status.UNPAID)
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
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )
        response = fast_tenant_client.get(
            reverse("self_order-detail", kwargs={"pk": unpaid_order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] is None
        assert response.data["items"][0]["due_date"] is None

        # Complete order
        order_complete = Order.objects.create(owner=customer, status=Order.Status.PAID)
        OrderItem.objects.create(
            order=order_complete,
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
            status=OrderItem.Status.COMPLETE,
        )
        OrderItem.objects.create(
            order=order_complete,
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
            status=OrderItem.Status.VOID,
        )
        response = fast_tenant_client.get(
            reverse("self_order-detail", kwargs={"pk": order_complete.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] is None

        # In Progress order
        response = fast_tenant_client.get(
            reverse("self_order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] == item_1.due_date.isoformat().replace(
            "+00:00", "Z"
        )


@mock.patch("apps.orders.serializers.send_admin_email_new_order.delay")
@mock.patch("apps.orders.serializers.send_email_order_received.delay")
class CreateSelfOrderTestCase(FastTenantTestCase):
    """Tests for CREATE single self order"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = self.file_name
        file_field = SimpleUploadedFile(self.file_name, b"these are the file contents!")

        self.patcher_3 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.delete")
        self.mock_s3_delete = self.patcher_3.start()

        self.patcher_4 = mock.patch(
            "django.core.files.storage.FileSystemStorage.delete"
        )
        self.mock_file_storage_delete = self.patcher_4.start()
        # End mock

        level = Level.objects.create(name="TestLevel")
        course = Course.objects.create(name="TestCourse")
        paper = Paper.objects.create(name="TestPaper")
        paper_format = Format.objects.create(name="TestFormat")
        deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.cart = Cart.objects.create(owner=self.owner)
        item = Item.objects.create(
            cart=self.cart,
            topic="This is a topic",
            level=level,
            course=course,
            paper=paper,
            paper_format=paper_format,
            deadline=deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=2,
            page_price=15,
        )
        Attachment.objects.create(
            cart_item=item, attachment=file_field, comment="Hello"
        )
        self.valid_payload = {"cart": self.cart.id}

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()
        self.patcher_3.stop()
        self.patcher_4.stop()

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.post(
            reverse("self_order-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(
        self, send_email_received_mock, send_admin_email_new_order_mock
    ):
        """Ensure correct authentication for create order"""
        response = self.client.post(reverse("self_order-list"), data={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(
        self, send_email_received_mock, send_admin_email_new_order_mock
    ):
        """Ensure valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrderItemAttachment.objects.count(), 1)
        self.assertEqual(Cart.objects.count(), 0)
        order = Order.objects.filter(owner=self.owner).first()
        item = order.items.first()
        attachment = item.attachments.first()
        self.maxDiff = None
        self.assertEqual(
            json.dumps(response.data, cls=DjangoJSONEncoder),
            json.dumps(
                {
                    "id": order.id,
                    "status": order.status,
                    "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
                    "items": [
                        {
                            "id": item.id,
                            "order": {
                                "id": order.id,
                                "owner": {
                                    "id": str(order.owner.id),
                                    "full_name": order.owner.full_name,
                                    "email": order.owner.email,
                                },
                                "status": order.status,
                            },
                            "topic": "This is a topic",
                            "level": item.level,
                            "course": item.course,
                            "paper": item.paper,
                            "paper_format": item.paper_format,
                            "deadline": item.deadline,
                            "language": item.language,
                            "pages": item.pages,
                            "references": item.references,
                            "quantity": item.quantity,
                            "comment": item.comment,
                            "due_date": None,
                            "status": item.status,
                            "days_left": item.days_left,
                            "price": item.price,
                            "total_price": item.total_price,
                            "writer_type": None,
                            "writer_type_price": None,
                            "is_overdue": item.is_overdue,
                            "created_at": item.created_at.isoformat().replace(
                                "+00:00", "Z"
                            ),
                            "attachments": [
                                {
                                    "id": str(attachment.pk),
                                    "file_path": attachment.file_path,
                                    "comment": attachment.comment,
                                }
                            ],
                            "papers": [],
                        }
                    ],
                },
                cls=DjangoJSONEncoder,
            ),
        )

    def test_coupon_save(
        self, send_email_received_mock, send_admin_email_new_order_mock
    ):
        """Coupon applied in cart is saved"""
        coupon = Coupon.objects.create(
            code="SAVE",
            percent_off=20,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=1),
        )
        self.cart.coupon = coupon
        self.cart.save()
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.filter(owner=self.owner).first()
        self.assertEqual(order.coupon.code, "SAVE")
        self.assertEqual(order.coupon.discount, 18.00)

        # expired coupon is not applied
        OrderCoupon.objects.all().delete()
        coupon = Coupon.objects.create(
            code="EXPIRED",
            percent_off=20,
            start_date=timezone.now() - timedelta(days=10),
            end_date=timezone.now() - timedelta(days=2),
        )
        self.cart.coupon = coupon
        self.cart.save()
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.filter(owner=self.owner).first()
        self.assertFalse(hasattr(order, "coupon"))

    def test_cart_required(
        self, send_email_received_mock, send_admin_email_new_order_mock
    ):
        """Ensure field `cart` is required"""
        response = self.post({**self.valid_payload, "cart": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cart_valid(
        self, send_email_received_mock, send_admin_email_new_order_mock
    ):
        """Ensure field `cart` is valid"""
        response = self.post({**self.valid_payload, "cart": "81919"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
class TestGetAllOrders:
    """Tests for GET all orders"""

    @pytest.fixture()
    def set_up(self, customer):
        order_1 = Order.objects.create(owner=customer, status=Order.Status.PAID)
        order_item = OrderItem.objects.create(
            order=order_1,
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
            status=OrderItem.Status.IN_PROGRESS,
        )

        return locals()

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("order-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("order-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_orders(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Returns empty results when no orders are available"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("order-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_get_all(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Returns all orders"""
        order_1 = set_up["order_1"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("order-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(
            response.data["results"], cls=DjangoJSONEncoder
        ) == json.dumps(
            [
                {
                    "id": order_1.id,
                    "owner": {
                        "id": str(order_1.owner.id),
                        "full_name": order_1.owner.full_name,
                        "email": order_1.owner.email,
                    },
                    "status": order_1.status,
                    "is_complete": False,
                    "created_at": order_1.created_at.isoformat().replace("+00:00", "Z"),
                    "earliest_due": order_1.earliest_due.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "amount_payable": "100.00",
                    "no_of_items": 1,
                }
            ],
            cls=DjangoJSONEncoder,
        )


@pytest.mark.django_db
class TestGetSingleOrder:
    """Tests for GET single order"""

    @pytest.fixture()
    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def set_up(
        self, mock_system_save, mock_s3_save, customer, create_active_subscription
    ):
        # Mock storage backends to prevent a file from being saved on disk
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name
        file_field = SimpleUploadedFile(file_name, b"these are the file contents!")

        order = Order.objects.create(owner=customer, status=Order.Status.PAID)
        item_1 = OrderItem.objects.create(
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
        paper_1 = OrderItemPaper.objects.create(
            order_item=item_1, paper=file_field, comment="We added an extra page"
        )
        paper_1_attachment = OrderItemAttachment.objects.create(
            order_item=item_1, attachment=file_field, comment="Hello"
        )
        paper_1_rating = Rating.objects.create(
            paper=paper_1, rating=5, comment="Great work"
        )
        order_coupon = OrderCoupon.objects.create(order=order, code="test", discount=20)

        return locals()

    def test_auth_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        set_up,
        create_active_subscription,
    ):
        """Authentication is required"""
        order = set_up["order"]
        response = fast_tenant_client.get(
            reverse("order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_single_order(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Returns a single order"""
        order = set_up["order"]
        order_coupon = set_up["order_coupon"]
        item_1 = set_up["item_1"]
        paper_1 = set_up["paper_1"]
        paper_1_rating = set_up["paper_1_rating"]
        paper_1_attachment = set_up["paper_1_attachment"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(
            reverse("order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "id": order.id,
                "owner": {
                    "id": str(order.owner.id),
                    "full_name": order.owner.full_name,
                    "email": order.owner.email,
                },
                "status": order.status,
                "is_complete": False,
                "created_at": order.created_at.isoformat().replace("+00:00", "Z"),
                "earliest_due": order.earliest_due.isoformat().replace("+00:00", "Z"),
                "coupon": {"code": order_coupon.code, "discount": "20.00"},
                "balance": order.balance,
                "amount_payable": order.amount_payable,
                "original_amount_payable": order.original_amount_payable,
                "items": [
                    {
                        "id": item_1.id,
                        "order": {
                            "id": order.id,
                            "owner": {
                                "id": str(order.owner.id),
                                "full_name": order.owner.full_name,
                                "email": order.owner.email,
                            },
                            "status": order.status,
                        },
                        "topic": item_1.topic,
                        "level": item_1.level,
                        "course": item_1.course,
                        "paper": item_1.paper,
                        "paper_format": item_1.paper_format,
                        "deadline": item_1.deadline,
                        "language": item_1.language,
                        "pages": item_1.pages,
                        "references": item_1.references,
                        "quantity": item_1.quantity,
                        "comment": item_1.comment,
                        "due_date": item_1.due_date.isoformat().replace("+00:00", "Z"),
                        "status": item_1.status,
                        "days_left": item_1.days_left,
                        "price": item_1.price,
                        "total_price": item_1.total_price,
                        "writer_type": item_1.writer_type,
                        "writer_type_price": "5.00",
                        "is_overdue": item_1.is_overdue,
                        "created_at": item_1.created_at.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "attachments": [
                            {
                                "id": str(paper_1_attachment.pk),
                                "file_path": paper_1_attachment.file_path,
                                "comment": paper_1_attachment.comment,
                            }
                        ],
                        "papers": [
                            {
                                "id": str(paper_1.pk),
                                "file_name": "test.doc",
                                "comment": paper_1.comment,
                                "rating": {
                                    "rating": paper_1_rating.rating,
                                    "comment": paper_1_rating.comment,
                                },
                            }
                        ],
                    }
                ],
            },
            cls=DjangoJSONEncoder,
        )

    def test_get_invalid_order(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Ensure get invalid single order is correct."""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(
            reverse(
                "order-detail",
                kwargs={"pk": "3351cacd-13e4-412d-bb44-636bab7e0ea7"},
            ),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_earlist_due(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Ensure the earliest_due response is correct"""
        order = set_up["order"]
        item_1 = set_up["item_1"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # Unpaid order
        unpaid_order = Order.objects.create(
            owner=store_staff, status=Order.Status.UNPAID
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
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            writer_type="Premium",
            writer_type_price=5,
            status=OrderItem.Status.IN_PROGRESS,
        )
        response = fast_tenant_client.get(
            reverse("order-detail", kwargs={"pk": unpaid_order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] is None
        assert response.data["items"][0]["due_date"] is None

        # Complete order
        order_complete = Order.objects.create(
            owner=store_staff, status=Order.Status.PAID
        )
        OrderItem.objects.create(
            order=order_complete,
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
            status=OrderItem.Status.COMPLETE,
        )
        OrderItem.objects.create(
            order=order_complete,
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
            status=OrderItem.Status.VOID,
        )
        response = fast_tenant_client.get(
            reverse("order-detail", kwargs={"pk": order_complete.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] is None

        # In Progress order
        response = fast_tenant_client.get(
            reverse("order-detail", kwargs={"pk": order.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["earliest_due"] == item_1.due_date.isoformat().replace(
            "+00:00", "Z"
        )


@pytest.mark.django_db
class TestUpdateSingleOrder:
    """Tests for updating a single order"""

    @pytest.fixture()
    def set_up(self, customer):
        order = Order.objects.create(owner=customer)
        order_item = OrderItem.objects.create(
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
            due_date=timezone.now() + timedelta(days=1),
            status=OrderItem.Status.PENDING,
        )

        return locals()

    def test_auth_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        set_up,
        create_active_subscription,
    ):
        """Authentication is required"""
        order = set_up["order"]
        response = fast_tenant_client.patch(
            reverse("order-detail", kwargs={"pk": order.pk}),
            data={},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        set_up,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        order = set_up["order"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.patch(
            reverse("order-detail", kwargs={"pk": order.pk}),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_status(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Updates order status"""
        order = set_up["order"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.patch(
            reverse("order-detail", kwargs={"pk": order.pk}),
            data=json.dumps({"status": Order.Status.PAID}),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == Order.Status.PAID


class CreateRatingTestCase(FastTenantTestCase):
    """Tests for `POST` single rating"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        # Mock storage backends to prevent a file from being saved
        self.patcher_1 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_1.start()
        self.mock_file_storage_save.return_value = "test.doc"
        self.patcher_2 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_2.start()
        self.mock_s3_save.return_value = "test.doc"
        # Endmock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        order = Order.objects.create(owner=self.owner)
        order_item = OrderItem.objects.create(
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
            due_date=timezone.now() + timedelta(days=1),
        )
        self.file_name = "best_file_eva.txt"
        file_field = SimpleUploadedFile(self.file_name, b"these are the file contents!")
        self.paper = OrderItemPaper.objects.create(
            order_item=order_item, paper=file_field
        )
        self.valid_payload = {
            "paper": self.paper.id,
            "rating": 4,
            "comment": "Nice work",
        }

    def tearDown(self):
        self.patcher_1.stop()
        self.patcher_2.stop()

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        response = self.client.post(
            reverse("rating-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        return response

    def test_authentication(self):
        """Ensure correct authentication"""
        response = self.client.post(reverse("rating-list"), data={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self):
        """Ensure rating is created for valid payload"""
        response = self.post(self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.paper.rating.rating, 4)

    def test_paper_required(self):
        """Ensure `paper` field is required"""
        response = self.post({**self.valid_payload, "paper": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_required(self):
        """Ensure `rating` field is required"""
        response = self.post({**self.valid_payload, "rating": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_optional(self):
        response = self.post({**self.valid_payload, "comment": ""})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_comment_length(self):
        # Comment should not exceed 255
        response = self.post(
            {
                **self.valid_payload,
                # 256 chars
                "comment": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Does not raise error if comment is 255 chars
        response = self.post(
            {
                **self.valid_payload,
                "comment": "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor i",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


@mock.patch("apps.orders.views.create_presigned_url")
class DownloadAttachmentTestCase(FastTenantTestCase):
    """Tests for downloading an attachment"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_2 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_2.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_3 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_3.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.order = Order.objects.create(owner=self.owner)
        order_item = OrderItem.objects.create(
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
            quantity=1,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.file_field = SimpleUploadedFile(
            "test.doc", b"these are the file contents!"
        )
        attachment = OrderItemAttachment.objects.create(
            order_item=order_item, attachment=self.file_field, comment="Hello"
        )
        self.payload = {"attachment": attachment.id}

    def tearDown(self):
        self.patcher_2.stop()
        self.patcher_3.stop()

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.post(
            reverse("self_order-download-attachment", kwargs={"pk": self.order.pk}),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self, mock_create_signed_url):
        """Ensure correct authentication"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.client.post(
            reverse("self_order-download-attachment", kwargs={"pk": self.order.pk}),
            data={},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self, mock_create_signed_url):
        """Ensure we can download an attachment for valid payload"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post(self.payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"url": "https://s3.amazaon.com/signed-url/"})

    def test_failure(self, mock_create_signed_url):
        """Returns 500 status code if download fails"""
        mock_create_signed_url.return_value = None
        response = self.post(self.payload)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_attachment_required(self, mock_create_signed_url):
        """Ensure `attachment` field is required"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post({**self.payload, "attachment": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_attachment_id(self, mock_create_signed_url):
        """Ensure `attachment` should be a valid id"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.post({**self.payload, "attachment": "1223"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_permission(self, mock_create_signed_url):
        """Ensure a user can only donwload their attachment"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        owner = User.objects.create_user(
            username="johndoe",
            first_name="John",
            email="johndoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        order = Order.objects.create(owner=owner)
        order_item = OrderItem.objects.create(
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
            due_date=timezone.now() + timedelta(days=1),
        )
        attachment = OrderItemAttachment.objects.create(
            order_item=order_item, attachment=self.file_field, comment="Hello"
        )
        response = self.post({**self.payload, "attachment": attachment.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
class TestGetOrderItems:
    """Tests for get order items"""

    @pytest.fixture()
    def set_up(self):
        customer_1 = User.objects.create_user(
            username="customer_1",
            first_name="Customer 1",
            email="customer_1@example.com",
            password="12345",
            is_email_verified=True,
        )
        order_1 = Order.objects.create(owner=customer_1, status=Order.Status.PAID)
        order_item_1 = OrderItem.objects.create(
            order=order_1,
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
            status=OrderItem.Status.COMPLETE,
        )
        customer_2 = User.objects.create_user(
            username="customer_2",
            first_name="Customer 2",
            email="customer_2@example.com",
            password="12345",
            is_email_verified=True,
        )
        order_2 = Order.objects.create(owner=customer_2, status=Order.Status.PAID)
        order_item_2 = OrderItem.objects.create(
            order=order_2,
            topic="Evolution of man",
            level="High School",
            course="History",
            paper="Book Review",
            paper_format="MLA",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() - timedelta(days=1),
            status=OrderItem.Status.IN_PROGRESS,
        )
        customer_3 = User.objects.create_user(
            username="customer_3",
            first_name="Customer 3",
            email="customer_3@example.com",
            password="12345",
            is_email_verified=True,
        )
        order_3 = Order.objects.create(owner=customer_3, status=Order.Status.UNPAID)
        order_item_3 = OrderItem.objects.create(
            order=order_3,
            topic="Unpaid order",
            level="High School",
            course="History",
            paper="Book Review",
            paper_format="MLA",
            deadline="1 Day",
            language="English UK",
            pages=5,
            references=3,
            quantity=2,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
            status=OrderItem.Status.PENDING,
        )

        return locals()

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("order_item-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("order_item-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Staff can get order items"""
        order_item_1 = set_up["order_item_1"]
        order_1 = set_up["order_1"]
        customer_1 = set_up["customer_1"]
        order_item_2 = set_up["order_item_2"]
        order_2 = set_up["order_2"]
        customer_2 = set_up["customer_2"]
        order_item_3 = set_up["order_item_3"]
        order_3 = set_up["order_3"]
        customer_3 = set_up["customer_3"]

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("order_item-list"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(
            response.data["results"], cls=DjangoJSONEncoder
        ) == json.dumps(
            [
                {
                    "id": order_item_3.id,
                    "order": {
                        "id": order_3.id,
                        "owner": {
                            "id": str(customer_3.id),
                            "full_name": customer_3.full_name,
                            "email": customer_3.email,
                        },
                        "status": order_3.status,
                    },
                    "topic": order_item_3.topic,
                    "level": order_item_3.level,
                    "course": order_item_3.course,
                    "paper": order_item_3.paper,
                    "paper_format": order_item_3.paper_format,
                    "deadline": order_item_3.deadline,
                    "language": order_item_3.language,
                    "pages": order_item_3.pages,
                    "references": order_item_3.references,
                    "quantity": order_item_3.quantity,
                    "comment": order_item_3.comment,
                    "due_date": None,
                    "status": order_item_3.status,
                    "days_left": None,
                    "price": order_item_3.price,
                    "total_price": order_item_3.total_price,
                    "writer_type": None,
                    "writer_type_price": None,
                    "is_overdue": order_item_3.is_overdue,
                    "created_at": order_item_3.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "attachments": [],
                    "papers": [],
                },
                {
                    "id": order_item_2.id,
                    "order": {
                        "id": order_2.id,
                        "owner": {
                            "id": str(customer_2.id),
                            "full_name": customer_2.full_name,
                            "email": customer_2.email,
                        },
                        "status": order_2.status,
                    },
                    "topic": order_item_2.topic,
                    "level": order_item_2.level,
                    "course": order_item_2.course,
                    "paper": order_item_2.paper,
                    "paper_format": order_item_2.paper_format,
                    "deadline": order_item_2.deadline,
                    "language": order_item_2.language,
                    "pages": order_item_2.pages,
                    "references": order_item_2.references,
                    "quantity": order_item_2.quantity,
                    "comment": order_item_2.comment,
                    "due_date": order_item_2.due_date.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "status": order_item_2.status,
                    "days_left": order_item_2.days_left,
                    "price": order_item_2.price,
                    "total_price": order_item_2.total_price,
                    "writer_type": None,
                    "writer_type_price": None,
                    "is_overdue": order_item_2.is_overdue,
                    "created_at": order_item_2.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "attachments": [],
                    "papers": [],
                },
                {
                    "id": order_item_1.id,
                    "order": {
                        "id": order_1.id,
                        "owner": {
                            "id": str(customer_1.id),
                            "full_name": customer_1.full_name,
                            "email": customer_1.email,
                        },
                        "status": order_1.status,
                    },
                    "topic": order_item_1.topic,
                    "level": order_item_1.level,
                    "course": order_item_1.course,
                    "paper": order_item_1.paper,
                    "paper_format": order_item_1.paper_format,
                    "deadline": order_item_1.deadline,
                    "language": order_item_1.language,
                    "pages": order_item_1.pages,
                    "references": order_item_1.references,
                    "quantity": order_item_1.quantity,
                    "comment": order_item_1.comment,
                    "due_date": order_item_1.due_date.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "status": order_item_1.status,
                    "days_left": order_item_1.days_left,
                    "price": order_item_1.price,
                    "total_price": order_item_1.total_price,
                    "writer_type": order_item_1.writer_type,
                    "writer_type_price": "5.00",
                    "is_overdue": order_item_1.is_overdue,
                    "created_at": order_item_1.created_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "attachments": [],
                    "papers": [],
                },
            ],
            cls=DjangoJSONEncoder,
        )

    def test_filters_work(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        customer,
        create_active_subscription,
    ):
        """Query param filters work"""
        order_item_1 = set_up["order_item_1"]
        order_1 = set_up["order_1"]
        order_item_2 = set_up["order_item_2"]

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        # filter by topic works
        response = fast_tenant_client.get(
            reverse_querystring("order_item-list", query_kwargs={"topic": "MaN"})
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == order_item_2.id

        # filter by order_id works
        response = fast_tenant_client.get(
            reverse_querystring(
                "order_item-list", query_kwargs={"order_id": order_1.id}
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == order_item_1.id

        # filter by is_overdue works
        response = fast_tenant_client.get(
            reverse_querystring("order_item-list", query_kwargs={"is_overdue": True})
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == order_item_2.id

        # filter by status works
        response = fast_tenant_client.get(
            reverse_querystring(
                "order_item-list", query_kwargs={"status": OrderItem.Status.COMPLETE}
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == order_item_1.id

        # filter by new works
        order_4 = Order.objects.create(owner=customer, status=Order.Status.PAID)
        order_item_4 = OrderItem.objects.create(
            order=order_4,
            topic="Pending paid order",
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
            status=OrderItem.Status.PENDING,
        )
        response = fast_tenant_client.get(
            reverse_querystring("order_item-list", query_kwargs={"new": True})
        )
        assert response.status_code == status.HTTP_200_OK
        # should including pending & in progress paid order items
        assert len(response.data["results"]) == 2
        assert response.data["results"][0]["id"] == order_item_4.id
        assert response.data["results"][1]["id"] == order_item_2.id


@pytest.mark.django_db
class TestGetSingleOrderItem:
    """Tests for GET single order item"""

    @pytest.fixture()
    @mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    def set_up(self, mock_system_save, mock_s3_save):
        # Mock storage backends to prevent a file from being saved on disk
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name
        file_field = SimpleUploadedFile(file_name, b"these are the file contents!")

        customer_1 = User.objects.create_user(
            username="customer_1",
            first_name="Customer 1",
            email="customer_1@example.com",
            password="12345",
            is_email_verified=True,
        )
        order_1 = Order.objects.create(owner=customer_1, status=Order.Status.PAID)
        item_1 = OrderItem.objects.create(
            order=order_1,
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
        paper_1 = OrderItemPaper.objects.create(
            order_item=item_1, paper=file_field, comment="We added an extra page"
        )
        paper_1_attachment = OrderItemAttachment.objects.create(
            order_item=item_1, attachment=file_field, comment="Hello"
        )
        paper_1_rating = Rating.objects.create(
            paper=paper_1, rating=5, comment="Great work"
        )

        # confirm mock storage is working. we are currently using s3
        assert mock_s3_save.call_count == 2

        return locals()

    def test_auth_required(
        self,
        use_tenant_connection,
        fast_tenant_client,
        set_up,
        create_active_subscription,
    ):
        """Authentication is required"""
        item_1 = set_up["item_1"]

        response = fast_tenant_client.get(
            reverse("order_item-detail", kwargs={"pk": item_1.pk})
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        set_up,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        item_1 = set_up["item_1"]

        response = fast_tenant_client.get(
            reverse("order_item-detail", kwargs={"pk": item_1.pk})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_valid_order_item(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        item_1 = set_up["item_1"]
        order_1 = set_up["order_1"]
        paper_1 = set_up["paper_1"]
        paper_1_attachment = set_up["paper_1_attachment"]
        paper_1_rating = set_up["paper_1_rating"]

        response = fast_tenant_client.get(
            reverse("order_item-detail", kwargs={"pk": item_1.pk})
        )
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data) == json.dumps(
            {
                "id": item_1.id,
                "order": {
                    "id": order_1.id,
                    "owner": {
                        "id": str(order_1.owner.id),
                        "full_name": order_1.owner.full_name,
                        "email": order_1.owner.email,
                    },
                    "status": order_1.status,
                },
                "topic": item_1.topic,
                "level": item_1.level,
                "course": item_1.course,
                "paper": item_1.paper,
                "paper_format": item_1.paper_format,
                "deadline": item_1.deadline,
                "language": item_1.language,
                "pages": item_1.pages,
                "references": item_1.references,
                "quantity": item_1.quantity,
                "comment": item_1.comment,
                "due_date": item_1.due_date.isoformat().replace("+00:00", "Z"),
                "status": item_1.status,
                "days_left": item_1.days_left,
                "price": item_1.price,
                "total_price": item_1.total_price,
                "writer_type": item_1.writer_type,
                "writer_type_price": "5.00",
                "is_overdue": item_1.is_overdue,
                "created_at": item_1.created_at.isoformat().replace("+00:00", "Z"),
                "attachments": [
                    {
                        "id": str(paper_1_attachment.pk),
                        "file_path": paper_1_attachment.file_path,
                        "comment": paper_1_attachment.comment,
                    }
                ],
                "papers": [
                    {
                        "id": str(paper_1.pk),
                        "file_name": "test.doc",
                        "comment": paper_1.comment,
                        "rating": {
                            "rating": paper_1_rating.rating,
                            "comment": paper_1_rating.comment,
                        },
                    }
                ],
            },
            cls=DjangoJSONEncoder,
        )

    def test_get_invalid_order_item(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Invalid order item"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(
            reverse(
                "order_item-detail",
                kwargs={"pk": "3351cacd-13e4-412d-bb44-636bab7e0ea7"},
            )
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
@mock.patch("django.core.files.storage.FileSystemStorage.save")
class TestUploadPaper:
    """Tests for upload an order item's paper"""

    @pytest.fixture()
    def set_up(self, customer):
        order_1 = Order.objects.create(owner=customer, status=Order.Status.PAID)
        item_1 = OrderItem.objects.create(
            order=order_1,
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

        return locals()

    def test_auth_required(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        create_active_subscription,
    ):
        """Authentication is required"""
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_valid_payload(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """For valid payload, file is uploaded"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        item_1 = set_up["item_1"]
        file_name = "test.doc"
        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": dummy_file,
                "comment": "we added an extra page for free",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        # confirm mock storage is working. we are currently using s3
        assert mock_s3_save.call_count == 1
        assert OrderItemPaper.objects.all().count() == 1

    def test_order_item_required(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Ensure `order_item` field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name

        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": "",
                "paper": dummy_file,
                "comment": "we added an extra page for free",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "paper": dummy_file,
                "comment": "we added an extra page for free",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_paper_required(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Ensure `paper` field is required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        item_1 = set_up["item_1"]
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name

        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": "",
                "comment": "we added an extra page for free",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "comment": "we added an extra page for free",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_comment_optional(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Ensure comment is not required"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        item_1 = set_up["item_1"]
        file_name = "test.doc"
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name

        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": dummy_file,
                "comment": "",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": dummy_file,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_comment_length(
        self,
        mock_system_save,
        mock_s3_save,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """Max comment length is 255"""
        # 255 chars
        comment = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolorui"
        assert len(comment) == 255
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        item_1 = set_up["item_1"]
        file_name = "test.doc"
        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        mock_system_save.return_value = file_name
        mock_s3_save.return_value = file_name

        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": dummy_file,
                "comment": comment,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

        # 256 chars fails
        comment = comment + "k"
        assert len(comment) == 256

        dummy_file = SimpleUploadedFile(file_name, b"these are the file contents!")
        response = fast_tenant_client.post(
            reverse("order_item_paper-list"),
            data={
                "order_item": f"{item_1.id}",
                "paper": dummy_file,
                "comment": comment,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@mock.patch("apps.orders.views.create_presigned_url")
class DownloadPaperFileTestCase(FastTenantTestCase):
    """Tests for downloading upload paper file"""

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        # create active subscription
        Subscription.objects.create(
            is_on_trial=False,
            status=Subscription.Status.ACTIVE,
            start_time=dateutil.parser.parse(
                "2016-01-01T00:20:49Z",
            ),
            next_billing_time=dateutil.parser.parse(
                "2016-05-01T00:20:49Z",
            ),
        )
        # Mock storage backends to prevent a file from being saved on disk
        self.file_name = "test.doc"
        self.patcher_2 = mock.patch("django.core.files.storage.FileSystemStorage.save")
        self.mock_file_storage_save = self.patcher_2.start()
        self.mock_file_storage_save.return_value = self.file_name
        self.patcher_3 = mock.patch("storages.backends.s3boto3.S3Boto3Storage.save")
        self.mock_s3_save = self.patcher_3.start()
        self.mock_s3_save.return_value = self.file_name
        # End mock

        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.order = Order.objects.create(owner=self.owner)
        order_item = OrderItem.objects.create(
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
            quantity=1,
            page_price=20,
            due_date=timezone.now() + timedelta(days=1),
        )
        self.file_field = SimpleUploadedFile(
            "test.doc", b"these are the file contents!"
        )
        self.item_paper = OrderItemPaper.objects.create(
            order_item=order_item, paper=self.file_field, comment="Hello"
        )

    def tearDown(self):
        self.patcher_2.stop()
        self.patcher_3.stop()

    def get(self, user=None, item_paper_id=None):
        """Method GET"""
        if user is None:
            user = self.owner

        if item_paper_id is None:
            item_paper_id = self.item_paper.pk

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.get(
            reverse("order_item_paper-download", kwargs={"pk": item_paper_id}),
        )

    def test_authentication(self, mock_create_signed_url):
        """Ensure correct authentication"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.client.get(
            reverse("order_item_paper-download", kwargs={"pk": self.item_paper.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_download(self, mock_create_signed_url):
        """Ensure we can download file"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        response = self.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"url": "https://s3.amazaon.com/signed-url/"})

    def test_failure(self, mock_create_signed_url):
        """Returns 500 status code if download fails"""
        mock_create_signed_url.return_value = None
        response = self.get()
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_owner_permission(self, mock_create_signed_url):
        """Customer can only download file they own"""
        mock_create_signed_url.return_value = "https://s3.amazaon.com/signed-url/"
        owner = User.objects.create_user(
            username="johndoe",
            first_name="John",
            email="johndoe@example.com",
            password="12345",
            is_email_verified=True,
        )
        order = Order.objects.create(owner=owner)
        order_item = OrderItem.objects.create(
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
            due_date=timezone.now() + timedelta(days=1),
        )
        item_paper = OrderItemPaper.objects.create(
            order_item=order_item, paper=self.file_field, comment="Hello"
        )
        response = self.get(item_paper_id=item_paper.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # staff user can download any
        store_satff = User.objects.create(
            username="store_staff",
            profile_type=User.ProfileType.STAFF,
            is_email_verified=True,
            password="12345",
        )
        response = self.get(user=store_satff, item_paper_id=item_paper.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.django_db
@mock.patch("apps.orders.serializers.send_email_order_item_status.delay")
class TestUpdateOrderItem:
    """Tests for updating a single order item"""

    @pytest.fixture
    def set_up(self, customer):
        order = Order.objects.create(owner=customer)
        order_item = OrderItem.objects.create(
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
            due_date=timezone.now() + timedelta(days=1),
            status=OrderItem.Status.PENDING,
        )

        return locals()

    def test_auth_required(
        self,
        mock_send_status,
        use_tenant_connection,
        fast_tenant_client,
        set_up,
        create_active_subscription,
    ):
        """Authentication is required"""
        order_item = set_up["order_item"]
        response = fast_tenant_client.put(
            reverse("order_item-detail", kwargs={"pk": order_item.pk}),
            data={},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        mock_send_status,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        set_up,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        order_item = set_up["order_item"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.put(
            reverse("order_item-detail", kwargs={"pk": order_item.pk}),
            data={},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_status(
        self,
        mock_send_status,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        set_up,
        create_active_subscription,
    ):
        """PATCH status"""
        order_item = set_up["order_item"]
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.patch(
            reverse("order_item-detail", kwargs={"pk": order_item.pk}),
            data=json.dumps(
                {"status": OrderItem.Status.COMPLETE}, cls=DjangoJSONEncoder
            ),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        order_item.refresh_from_db()
        assert order_item.status == OrderItem.Status.COMPLETE
        mock_send_status.assert_called_once_with(
            FastTenantTestCase.get_test_schema_name(), str(order_item.pk)
        )


@pytest.mark.django_db
class TestGetOrderItemStatistics:
    """Tests for GET order item statistics"""

    def test_auth_required(
        self, use_tenant_connection, fast_tenant_client, create_active_subscription
    ):
        """Authentication is required"""
        response = fast_tenant_client.get(reverse("order_item-statistics"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_only_staff(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        create_active_subscription,
    ):
        """Non-staff is not allowed"""
        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(customer).access_token}
        )
        response = fast_tenant_client.get(reverse("order_item-statistics"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_gets_statistics(
        self,
        use_tenant_connection,
        fast_tenant_client,
        customer,
        store_staff,
        create_active_subscription,
    ):
        """Gets statistics"""

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        order_paid = Order.objects.create(owner=customer, status=Order.Status.PAID)
        order_unpaid = Order.objects.create(owner=customer, status=Order.Status.UNPAID)
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order_paid,
                    topic="Complete",
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
                    status=OrderItem.Status.COMPLETE,
                ),
                OrderItem(
                    order=order_paid,
                    topic="In progress",
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
                ),
                OrderItem(
                    order=order_paid,
                    topic="Overdue in progress",
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
                    due_date=timezone.now() - timedelta(days=1),
                    writer_type="Premium",
                    writer_type_price=5,
                    status=OrderItem.Status.IN_PROGRESS,
                ),
                OrderItem(
                    order=order_paid,
                    topic="Overdue pending",
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
                    due_date=timezone.now() - timedelta(days=1),
                    writer_type="Premium",
                    writer_type_price=5,
                    status=OrderItem.Status.PENDING,
                ),
                OrderItem(
                    order=order_unpaid,
                    topic="Unpaid overdue pending",
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
                    due_date=timezone.now() - timedelta(days=1),
                    writer_type="Premium",
                    writer_type_price=5,
                    status=OrderItem.Status.PENDING,
                ),
            ]
        )

        response = fast_tenant_client.get(reverse("order_item-statistics"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "all": 5,
                "new": 2,
                "overdue": 2,
                "complete": 1,
            },
            cls=DjangoJSONEncoder,
        )

    def test_no_data(
        self,
        use_tenant_connection,
        fast_tenant_client,
        store_staff,
        create_active_subscription,
    ):
        """Returns correctly if no data is available"""

        fast_tenant_client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(store_staff).access_token}
        )
        response = fast_tenant_client.get(reverse("order_item-statistics"))
        assert response.status_code == status.HTTP_200_OK
        assert json.dumps(response.data, cls=DjangoJSONEncoder) == json.dumps(
            {
                "all": 0,
                "new": 0,
                "overdue": 0,
                "complete": 0,
            },
            cls=DjangoJSONEncoder,
        )
