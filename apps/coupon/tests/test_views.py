import json
from datetime import timedelta

import dateutil
from django.core.serializers.json import DjangoJSONEncoder
from django.http import SimpleCookie
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.cart.models import Cart, Item
from apps.catalog.models import Course, Deadline, Format, Level, Paper
from apps.coupon.models import Coupon
from apps.orders.models import Order, OrderItem
from apps.subscription.models import Subscription
from apps.users.models import User


class ApplyCouponTestCase(FastTenantTestCase):
    """Tests for coupon calculation"""

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
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        self.coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        self.owner = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="testuser@testdomain.com",
            password="12345",
            is_email_verified=True,
        )
        self.level = Level.objects.create(name="TestLevel")
        self.course = Course.objects.create(name="TestCourse")
        self.paper = Paper.objects.create(name="TestPaper")
        self.paper_format = Format.objects.create(name="TestFormat")
        self.deadline = Deadline.objects.create(
            value=1, deadline_type=Deadline.DeadlineType.DAY
        )
        self.cart = Cart.objects.create(owner=self.owner)
        Item.objects.create(
            cart=self.cart,
            topic="First topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=1,
            page_price=15,
        )
        self.valid_payload = {"coupon_code": self.coupon.code, "cart_id": self.cart.pk}
        self.invalid_payload = {"coupon_code": "INVALID_COUPON_CODE", "cart_id": ""}

    def post(self, payload, user=None):
        """Method POST"""
        if user is None:
            user = self.owner

        self.client.cookies = SimpleCookie(
            {"access_token": RefreshToken.for_user(user).access_token}
        )
        return self.client.post(
            reverse("apply_coupon"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

    def test_authentication(self):
        """Authentication is required"""
        response = self.client.put(
            reverse("apply_coupon"),
            data=json.dumps({}, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_payload(self):
        """Ensure application of coupon for valid payload is correct"""
        response = self.post(self.valid_payload)
        self.assertEqual(
            response.data,
            {"discount": "9.00"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_coupon_code_required(self):
        """coupon_code is required"""
        response = self.post({"coupon_code": "", "cart_id": self.cart.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post({"cart_id": self.cart.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cart_id_required(self):
        """cart_id is required"""
        response = self.post({"coupon_code": self.coupon.code, "cart_id": ""})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.post({"coupon_code": self.coupon.code})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_coupon_applied_only_once(self):
        """Coupon should not be applied twice"""
        owner = User.objects.create_user(
            username="coupon_applied",
            first_name="Test",
            email="coupon_applied@example.com",
            password="12345",
            is_email_verified=True,
        )
        cart = Cart.objects.create(owner=owner, coupon=self.coupon)
        Item.objects.create(
            cart=cart,
            topic="First topic",
            level=self.level,
            course=self.course,
            paper=self.paper,
            paper_format=self.paper_format,
            deadline=self.deadline,
            language=Item.Language.ENGLISH_UK,
            pages=3,
            references=1,
            quantity=1,
            page_price=15,
        )
        payload = {"coupon_code": self.coupon.code, "cart_id": cart.pk}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_coupon(self):
        """Ensure expired coupon is not applied"""
        start_date = timezone.now() - timedelta(days=3)
        end_date = start_date + timedelta(days=1)
        expired_coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        payload = {"coupon_code": expired_coupon.code, "cart_id": self.cart.pk}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_amount_less(self):
        """Coupon is not applied if amount is less than coupon minimum"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        minimum_coupon = Coupon.objects.create(
            percent_off=20, minimum=150.00, start_date=start_date, end_date=end_date
        )
        payload = {"coupon_code": minimum_coupon.code, "cart_id": self.cart.pk}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_amount_more(self):
        """Coupon applied if amount is more than coupon minimum"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        minimum_coupon = Coupon.objects.create(
            percent_off=20, minimum=30.00, start_date=start_date, end_date=end_date
        )
        payload = {"coupon_code": minimum_coupon.code, "cart_id": self.cart.pk}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_minimum_amount_equal(self):
        """Coupon is applied if amoun is equal to minimum"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        minimum_coupon = Coupon.objects.create(
            percent_off=20, minimum=45.00, start_date=start_date, end_date=end_date
        )
        payload = {"coupon_code": minimum_coupon.code, "cart_id": self.cart.pk}
        response = self.post(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_first_timer_coupon(self):
        """First timer coupon should only be applied to first timers"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        coupon_first_timer = Coupon.objects.create(
            coupon_type=Coupon.CouponType.FIRST_TIMER,
            percent_off=20,
            start_date=start_date,
            end_date=end_date,
        )
        # first timer is successful
        response = self.post(
            {"coupon_code": coupon_first_timer.code, "cart_id": self.cart.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # non first timer fails (a user with at least 1 paid order)
        paid_order = Order.objects.create(owner=self.owner, status=Order.Status.PAID)
        OrderItem.objects.create(
            order=paid_order,
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
        response = self.post(
            {"coupon_code": coupon_first_timer.code, "cart_id": self.cart.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
