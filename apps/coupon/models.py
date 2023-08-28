"""models"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import AbstractBase

from .utils import generate_coupon_code


class Coupon(AbstractBase):
    """Information for a coupon object"""

    class CouponType(models.IntegerChoices):
        """coupon_type field choices"""

        REGULAR = 1, _("Regular")
        FIRST_TIMER = 2, _("First Timer")

    code = models.CharField(max_length=8, unique=True, db_index=True)
    coupon_type = models.PositiveSmallIntegerField(
        choices=CouponType.choices, default=CouponType.REGULAR
    )
    percent_off = models.PositiveSmallIntegerField(
        help_text=_("The discount in percentage this coupon will give")
    )
    minimum = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Minimum purchase amount required"),
    )
    start_date = models.DateTimeField(
        default=timezone.now,
        help_text=_("The date and time this coupon will start to take effect"),
    )
    end_date = models.DateTimeField(
        help_text=_("The date and time this coupon will stop to take effect")
    )

    def __str__(self):
        return self.code

    @property
    def is_expired(self):
        """Return if coupon is expired or not"""
        if timezone.now() > self.end_date:
            return True

        return False

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_coupon_code()

        super().save(*args, **kwargs)
