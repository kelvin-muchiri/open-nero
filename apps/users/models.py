"""
User app models
"""
import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def now():
    """timezone.now wrapper to enable mocks during tests

    Models are loaded before mock has patched the timezone module,
    so at the time the expression default=timezone.now is evaluated,
    it sets the default kwarg to the real timezone.now function.
    """
    return timezone.now()


class UserManager(BaseUserManager):
    """Custom user manager"""

    def create_user(self, username, password=None, **extra_fields):
        """
        Creates and saves a User
        """

        if not username:
            raise ValueError("Users must have a username")

        user = self.model(
            email=self.normalize_email(extra_fields.pop("email", None)),
            username=username,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        """
        Creates and saves a superuser
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model

    Table contains keycloak & django-users.

    PermissionsMixin leverage built-in django model permissions system
    (which allows to limit information for staff users via Groups).
    """

    class Meta(AbstractBaseUser.Meta):
        ordering = ("-date_joined",)
        unique_together = ("profile_type", "email")

    class ProfileType(models.TextChoices):
        """profile_type field choices"""

        STAFF = "STAFF", _("Store staff")
        CUSTOMER = "CUSTOMER", _("Customer")

    # password is inherited from AbstractBaseUser

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(null=True, blank=True)  # allow non-unique emails
    first_name = models.CharField(max_length=35, null=True, blank=True)
    last_name = models.CharField(max_length=35, null=True, blank=True)
    other_names = models.CharField(max_length=255, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    is_store_owner = models.BooleanField(default=False)
    profile_type = models.CharField(
        max_length=32,
        choices=ProfileType.choices,
        default=ProfileType.CUSTOMER,
    )
    date_joined = models.DateTimeField(default=now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"

    # REQUIRED_FIELDS used only on createsuperuser. Must include any field
    # for which blank is False except the USERNAME_FIELD
    # or password as these fields will always be prompted for
    REQUIRED_FIELDS = ["first_name"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self) -> str:
        """A users full name

        Return the first_name plus the last_name plus other_names,
        with a space in between
        """
        if not self.first_name and not self.last_name and not self.other_names:
            return None

        full_name = (
            f'{self.first_name or ""} {self.last_name or ""} {self.other_names or ""}'
        )
        # Remove any multiple whitespace
        return " ".join(full_name.split())

    def get_full_name(self) -> str:
        """
        A longer formal identifier for the user

        Appears alongside the username in an object history in django.contrib.admin.
        """
        return self.full_name

    def save(self, *args, **kwargs):
        if hasattr(self, "first_name") and self.first_name:
            self.first_name = self.first_name.title()

        if hasattr(self, "last_name") and self.last_name:
            self.last_name = self.last_name.title()

        if hasattr(self, "other_names") and self.other_names:
            self.other_names = " ".join(
                [name.title() for name in self.other_names.split(" ")]
            )

        if hasattr(self, "email") and not self.email:
            # Make sure we do not save blank strings since they'll be treated
            # as unique
            self.email = None

        super().save(*args, **kwargs)


class StaffManager(UserManager):
    """Manager for Staff proxy model"""

    def get_queryset(self, *args, **kwargs):
        """Modify initial queryset"""
        return (
            super()
            .get_queryset(*args, **kwargs)
            .filter(
                profile_type=User.ProfileType.STAFF,
                is_staff=False,  # exclude django admin staff
                is_superuser=False,
            )
        )


class CustomerManager(UserManager):
    """Manager for Customer proxy model"""

    def get_queryset(self, *args, **kwargs):
        """Modify initial queryset"""
        return (
            super()
            .get_queryset(*args, **kwargs)
            .filter(
                profile_type=User.ProfileType.CUSTOMER,
                is_staff=False,  # exclude django admin staff
                is_superuser=False,
            )
        )


class Staff(User):
    """Proxy model for users of profile_type STAFF"""

    objects = StaffManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.profile_type = User.ProfileType.STAFF

        return super().save(*args, **kwargs)


class Customer(User):
    """Proxt model for users of profile_type CUSTOMER"""

    objects = CustomerManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.profile_type = User.ProfileType.CUSTOMER

        return super().save(*args, **kwargs)
