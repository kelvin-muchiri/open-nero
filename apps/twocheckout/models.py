from django.db import models

from apps.common.models import AbstractBase


class Twocheckout(AbstractBase):
    seller_id = models.CharField(max_length=255)
    secret = models.CharField(max_length=255)

    def __str__(self):
        return self.seller_id
