"""Utility methods"""

import random
from decimal import Decimal

from django.apps import apps

from apps.orders.models import Order

# pylint: disable=invalid-name


def generate_coupon_code(num_chars=8):
    """Generate coupon code from a length of chars."""
    code_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""

    for _ in range(0, num_chars):
        slice_start = random.randint(0, len(code_chars) - 1)
        code += code_chars[slice_start : slice_start + 1]

    Coupon = apps.get_model("coupon.Coupon")

    if Coupon.objects.filter(code=code).exists():
        return generate_coupon_code(num_chars)

    return code


def calculate_discount(coupon, amount_payable):
    """Calculate the discount given by a coupon"""
    discount = Decimal((coupon.percent_off / 100)) * amount_payable

    return round(discount, 2)


def is_coupon_valid(coupon, amount_payable, user=None):
    """Return true if user is eligible for coupon, false otherwise"""
    Coupon = apps.get_model("coupon.Coupon")

    if (
        user
        and coupon.coupon_type == Coupon.CouponType.FIRST_TIMER
        and Order.objects.filter(owner=user, status=Order.Status.PAID).exists()
    ):
        return False

    if coupon.minimum and amount_payable < coupon.minimum:
        return False

    if coupon.is_expired:
        return False

    return True


def get_best_match_coupon(total_price, user=None):
    """
    Get most appropriate coupon that can be applied
    """
    Coupon = apps.get_model("coupon.Coupon")

    first_timer_coupon = Coupon.objects.filter(
        coupon_type=Coupon.CouponType.FIRST_TIMER
    ).first()

    if first_timer_coupon and is_coupon_valid(
        first_timer_coupon, total_price, user=user
    ):
        return first_timer_coupon

    min_price_coupon = (
        Coupon.objects.filter(minimum__lte=total_price).order_by("-minimum").first()
    )

    if min_price_coupon and is_coupon_valid(min_price_coupon, total_price, user=user):
        return min_price_coupon

    return None
