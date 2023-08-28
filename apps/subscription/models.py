from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.common.models import AbstractBase


class Subscription(AbstractBase):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"
        RETIRED = "RETIRED", "Retired"

    is_on_trial = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.ACTIVE
    )
    start_time = models.DateTimeField()
    next_billing_time = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateField(null=True, blank=True)

    def __str__(self):
        start_time = timezone.localtime(self.start_time).strftime("%d %b %Y %I:%M %p")
        next_billing_time = timezone.localtime(self.next_billing_time).strftime(
            "%d %b %Y %I:%M %p"
        )

        return f"{start_time} - {next_billing_time}"

    def save(self, *args, **kwargs):
        # ensure we can only have one active subscription
        if self.status == self.Status.ACTIVE:
            for subscription in Subscription.objects.filter(status=self.Status.ACTIVE):
                subscription.status = self.Status.RETIRED
                subscription.retired_at = timezone.now()
                subscription.save()

        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """
        Returns true if subscription is expired, false otherwise
        """
        return timezone.now() > self.next_billing_time


class Paypal(AbstractBase):
    subscription = models.OneToOneField(
        Subscription, on_delete=models.CASCADE, related_name="paypal"
    )
    paypal_subscription_id = models.CharField(max_length=255, unique=True)
    paypal_plan_id = models.CharField(max_length=255)
    paypal_plan_name = models.CharField(max_length=255, null=True, blank=True)
    paypal_plan_description = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.subscription}"


class Payment(AbstractBase):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        related_name="subscription_payments",
    )
    object_id = models.UUIDField(null=True)
    content_object = GenericForeignKey()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(null=True, blank=True)
