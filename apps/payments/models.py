"""models"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import AbstractBase
from apps.orders.models import Order
from apps.users.models import User


class PaymentMethod(AbstractBase):
    class Code(models.TextChoices):
        PAYPAL = "PAYPAL", "Paypal"
        BRAINTREE = "BRAINTREE", "Braintree"
        INSTRUCTIONS = "INSTRUCTIONS", "Instructions"
        TWOCHECKOUT = "TWOCHECKOUT", "2Checkout"

    title = models.CharField(max_length=50)
    code = models.CharField(max_length=20, choices=Code.choices)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )
    instructions = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.code

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order",)


class Payment(AbstractBase):
    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"
        REFUNDED = "REFUNDED", "Refunded"
        PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially Refunded"
        FAILED = "FAILED", "Failed"
        PENDING = "PENDING", "Pending"
        DECLINED = "DECLINED", "Declined"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    trx_ref_number = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Transaction reference number from payment gateway"),
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text=_("Person who paid the order"),
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.UUIDField(null=True)
    content_object = GenericForeignKey()

    def __str__(self):
        return f"Order {self.order.id} - {self.amount_paid}"
