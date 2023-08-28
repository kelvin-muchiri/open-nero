import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import Course, Deadline, Format, Level, Paper, WriterType
from apps.common.models import AbstractBase
from apps.common.utils import FileValidator
from apps.coupon.models import Coupon
from apps.coupon.utils import calculate_discount

from .paths import path_cart_item_attachment

USER = get_user_model()

VALIDATE_ATTACHMENT = FileValidator(
    content_types=(
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sh",
        "application/zip",
        "image/jpeg",
        "image/png",
        "text/plain",
    ),
    max_size=settings.ORDER_ATTACHMENT_MAX_SIZE,
)


class Cart(AbstractBase):
    owner = models.OneToOneField(
        USER,
        on_delete=models.CASCADE,
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.owner}"

    @property
    def subtotal(self) -> float:
        """Raw total before discount"""
        total = sum([item.total_price for item in self.items.all()])
        return round(total, 2)

    @property
    def discount(self) -> float:
        """Discount applied by coupon"""
        discount = 0

        if self.coupon:
            discount = calculate_discount(self.coupon, self.subtotal)

        return round(discount, 2)

    @property
    def total(self) -> float:
        """Total after discount"""
        total = self.subtotal

        if self.coupon and not self.coupon.is_expired:
            total = total - self.discount

        return round(total, 2)


class Item(AbstractBase):
    class Language(models.IntegerChoices):
        """language field choices"""

        ENGLISH_UK = 1, "English UK"
        ENGLISH_US = 2, "English US"

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    topic = models.CharField(max_length=255)
    level = models.ForeignKey(
        Level, null=True, blank=True, on_delete=models.PROTECT, related_name="cart"
    )
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="cart")
    paper = models.ForeignKey(Paper, on_delete=models.PROTECT, related_name="cart")
    paper_format = models.ForeignKey(
        Format, on_delete=models.PROTECT, related_name="cart"
    )
    deadline = models.ForeignKey(
        Deadline, on_delete=models.PROTECT, related_name="cart"
    )
    language = models.PositiveSmallIntegerField(
        choices=Language.choices, default=Language.ENGLISH_UK
    )
    pages = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    references = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    page_price = models.DecimalField(max_digits=15, decimal_places=2)
    writer_type = models.ForeignKey(
        WriterType, on_delete=models.PROTECT, null=True, blank=True
    )
    writer_type_price = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.paper} - {self.topic}"

    @property
    def price(self):
        """Get the unit price"""
        unit_price = self.pages * self.page_price

        if self.writer_type_price:
            unit_price += self.pages * self.writer_type_price

        return round(Decimal(unit_price), 2)

    @property
    def total_price(self):
        """Get the total price based on quantity"""
        return self.price * self.quantity


class Attachment(AbstractBase):
    cart_item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="attachments"
    )
    attachment = models.FileField(
        max_length=10000,
        upload_to=path_cart_item_attachment,
        validators=[VALIDATE_ATTACHMENT],
    )
    comment = models.CharField(max_length=255, null=True, blank=True)

    @property
    def filename(self):
        return os.path.basename(self.attachment.name)

    def __str__(self):
        return f"{self.cart_item} - {self.attachment.name}"
