"""tests for models"""
from datetime import timedelta

from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase

from apps.coupon.models import Coupon


class CouponTestCase(FastTenantTestCase):
    """Tests for model coupon."""

    def setUp(self):
        start_date = timezone.now()
        end_date = start_date + timedelta(days=1)
        self.coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )

    def test_coupon_creation(self):
        """Ensure we can create a coupon object."""
        self.assertTrue(isinstance(self.coupon, Coupon))
        self.assertEqual(self.coupon.__str__(), self.coupon.code)

    def test_coupon_expiry(self):
        """Ensure correct return value of expiry status."""
        self.assertFalse(self.coupon.is_expired)

        start_date = timezone.now() - timedelta(days=3)
        end_date = start_date + timedelta(days=1)
        expired_coupon = Coupon.objects.create(
            percent_off=20, start_date=start_date, end_date=end_date
        )
        self.assertTrue(expired_coupon)
