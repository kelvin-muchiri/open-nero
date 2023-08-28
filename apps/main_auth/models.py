"""Models"""
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils import timezone

from apps.common.models import AbstractBase


class EmailVerification(AbstractBase):
    """Email verification code model"""

    email = models.CharField(max_length=255)
    code = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    created_by = None

    def __str__(self):
        return f"{self.email}-{self.created_at}-{self.is_verified}"

    @property
    def is_expired(self):
        """Check if code is expired"""
        return timezone.now() > (self.created_at + timedelta(minutes=2))

    def save(self, *args, **kwargs):

        if self._state.adding:
            self.code = make_password(self.code)

        super().save(*args, **kwargs)
