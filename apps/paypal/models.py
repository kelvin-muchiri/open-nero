"""Models"""

from django.db import models

from apps.common.models import AbstractBase


class Paypal(AbstractBase):
    client_id = models.TextField()
    webhook_id = models.TextField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.client_id
