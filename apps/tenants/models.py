"""Tenant related models"""
# pylint: disable=unnecessary-pass

from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    """Tenant model"""

    name = models.CharField(max_length=100)
    contact_email = models.CharField(max_length=255, null=True, blank=True)
    attachment_email = models.CharField(max_length=255, null=True, blank=True)
    notification_email = models.CharField(max_length=255, null=True, blank=True)
    facebook_profile = models.URLField(null=True, blank=True)
    twitter_profile = models.URLField(null=True, blank=True)
    instagram_profile = models.URLField(null=True, blank=True)
    primary_color = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text=("Primary color for the site e.g #ff0000"),
    )
    secondary_color = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text=("Secondary color for the site e.g #000000"),
    )
    theme = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    tawkto_property_id = models.CharField(max_length=255, null=True, blank=True)
    tawkto_widget_id = models.CharField(max_length=255, null=True, blank=True)
    ga_measurement_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Google Analytics Measurement ID",
    )
    order_sms_recipients = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="""Phone number of recipients who will receive
        SMS notifications for new orders separated by commas and starting with 254
        . e.g 254700000000,254711111111""",
    )
    created_at = models.DateField(auto_now_add=True)

    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    def __str__(self):
        return f"{self.name}"


class Domain(DomainMixin):
    """Tenant domain model"""

    pass
