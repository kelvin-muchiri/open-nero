import os
from decimal import Decimal

from django.apps import apps
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import AbstractBase
from apps.common.utils import FileValidator
from apps.users.models import User

from .paths import path_order_item_attachment, path_order_item_paper

VALIDATE_FILE = FileValidator(
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
    )
)


class Order(AbstractBase):
    class Status(models.IntegerChoices):
        """status field choices"""

        PAID = 1, _("Paid")
        UNPAID = 2, _("Awaiting Payment")
        REFUNDED = 3, _("Refunded")
        DECLINED = 4, _("Declined")
        PARTIALLY_REFUNDED = 5, _("Partially Refunded")

    id = models.BigAutoField(primary_key=True, editable=False)  # type: ignore
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        help_text=_("Person whom this order is for"),
        editable=False,
    )
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.UNPAID
    )

    def __str__(self):
        return str(self.id)

    @property
    def original_amount_payable(self):
        """Amount payble before discount"""
        amount = sum([item.total_price for item in self.items.all()])

        return round(amount, 2)

    @property
    def amount_payable(self):
        """Amount payable after discount."""
        amount = self.original_amount_payable

        if amount:
            amount = amount - self.discount

        return round(amount, 2)

    @property
    def discount(self):
        """Calculate discount from coupon."""
        amount = 0

        if hasattr(self, "coupon"):
            amount = self.coupon.discount

        return round(Decimal(amount), 2)

    @property
    def total_amount_paid(self):
        """Calculate the total amount paid"""
        # pylint: disable=invalid-name
        Payment = apps.get_model("payments.Payment")

        total_paid = (
            Payment.objects.filter(order=self, status=Payment.Status.COMPLETED)
            .aggregate(Sum("amount_paid"))
            .get("amount_paid__sum")
            or 0
        )
        total_refunded = (
            Payment.objects.filter(order=self, status=Payment.Status.REFUNDED)
            .aggregate(Sum("amount_paid"))
            .get("amount_paid__sum")
            or 0
        )
        actual_paid = total_paid - total_refunded

        if actual_paid < 1:
            return round(0, 2)

        return round(actual_paid, 2)

    @property
    def balance(self):
        """Calculate balance"""
        if self.total_amount_paid:
            if self.total_amount_paid >= self.amount_payable:
                return 0.00

            return self.amount_payable - self.total_amount_paid

        return self.amount_payable

    @property
    def earliest_due(self):
        """Return the earliest due date of order items"""
        if self.status != Order.Status.PAID:
            return None

        earliest_item = (
            self.items.filter(
                Q(status=OrderItem.Status.IN_PROGRESS)
                | Q(status=OrderItem.Status.PENDING)
            )
            .order_by("due_date")
            .first()
        )

        if earliest_item:
            return earliest_item.due_date

        return None

    @property
    def is_complete(self):
        """Return True if all items are complete, false otherwise"""
        return (
            self.items.filter(
                Q(status=OrderItem.Status.COMPLETE) | Q(status=OrderItem.Status.VOID)
            ).count()
            == self.items.all().count()
        )


class OrderItem(AbstractBase):
    class Status(models.IntegerChoices):
        """status field choices"""

        PENDING = 1, _("Pending")
        IN_PROGRESS = 2, _("In progress")
        COMPLETE = 3, _("Complete")
        VOID = 4, _("Void")

    id = models.BigAutoField(primary_key=True, editable=False)  # type: ignore
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    topic = models.CharField(max_length=255)
    level = models.CharField(max_length=255, null=True, blank=True)
    course = models.CharField(max_length=255)
    paper = models.CharField(max_length=255)
    paper_format = models.CharField(max_length=255)
    deadline = models.CharField(max_length=255)
    language = models.CharField(max_length=255)
    pages = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    references = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    page_price = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateTimeField()
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.PENDING
    )
    writer_type = models.CharField(max_length=255, null=True, blank=True)
    writer_type_price = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.order.id} - {self.paper} - {self.topic}"

    @property
    def price(self):
        """Return the price of all pages based on the unit price."""
        unit_price = self.pages * self.page_price

        if self.writer_type_price:
            unit_price += self.pages * self.writer_type_price

        return round(Decimal(unit_price), 2)

    @property
    def total_price(self):
        """Return the total price based on the quantity and the price."""
        return self.quantity * self.price

    @property
    def is_overdue(self):
        """Return True if an order item is overdue, False otherwise"""
        return (
            self.order.status == Order.Status.PAID
            and self.status in [self.Status.IN_PROGRESS, self.Status.PENDING]
            and timezone.now() > self.due_date
        )

    @property
    def days_left(self):
        """Return days left till due date"""
        if self.order.status == Order.Status.PAID and self.status in [
            self.Status.IN_PROGRESS,
            self.Status.PENDING,
        ]:
            return (self.due_date - timezone.now()).days

        return None


class OrderItemPaper(AbstractBase):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="papers"
    )
    paper = models.FileField(
        max_length=300, upload_to=path_order_item_paper, validators=[VALIDATE_FILE]
    )
    comment = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.order_item}"


class OrderCoupon(AbstractBase):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="coupon")
    code = models.CharField(max_length=8, help_text=_("Coupon code that was applied"))
    discount = models.DecimalField(
        max_digits=15, decimal_places=2, help_text=_("Discount given to this order")
    )

    def __str__(self):
        return f"{self.order} - {self.code} - {self.discount}"


class Rating(AbstractBase):
    paper = models.OneToOneField(
        OrderItemPaper, on_delete=models.CASCADE, related_name="rating"
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.paper}"


class OrderItemAttachment(AbstractBase):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="attachments"
    )
    attachment = models.FileField(
        max_length=10000, upload_to=path_order_item_attachment
    )
    comment = models.CharField(max_length=255, null=True, blank=True)

    @property
    def file_path(self):
        return os.path.basename(self.attachment.name)

    def __str__(self):
        return f"{self.order_item} - {self.attachment.name}"
