"""models"""
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import AbstractBase


class Level(AbstractBase):
    """level object information"""

    name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )

    def __str__(self):
        return self.name

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "name")  # type: ignore


class Course(AbstractBase):
    """course object information"""

    name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )

    def __str__(self):
        return self.name

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "name")  # type: ignore


class Deadline(AbstractBase):
    """deadline object information"""

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "value")  # type: ignore
        unique_together = ("value", "deadline_type")

    class DeadlineType(models.IntegerChoices):
        """deadline_type field choices"""

        HOUR = 1, _("Hour")
        DAY = 2, _("Day")

    value = models.PositiveSmallIntegerField(
        help_text=_("Number representing the value of the deadline")
    )
    deadline_type = models.PositiveSmallIntegerField(
        choices=DeadlineType.choices,
        default=DeadlineType.DAY,
        help_text=_("Duration of the deadline"),
    )
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Returns full name by combining the value and type"""
        suffix = ""

        if self.value > 1:
            suffix = "s"

        return f"{self.value} {self.get_deadline_type_display()}{suffix}"

    @property
    def duration(self):
        """Return the value as datetime duration"""
        if self.deadline_type == self.DeadlineType.HOUR:
            return timedelta(hours=self.value)

        return timedelta(days=self.value)

    def get_due_date(self, start=timezone.now):
        """Calculates the due date of the deadline"""

        return start + self.duration


class Paper(AbstractBase):
    """paper object information"""

    name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )

    def __str__(self):
        return self.name

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "name")  # type: ignore


class Format(AbstractBase):
    """format object information"""

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "name")  # type: ignore

    name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )

    def __str__(self):
        return self.name


class Service(AbstractBase):
    """service object information"""

    class Meta(AbstractBase.Meta):
        unique_together = ("level", "deadline", "paper")

    level = models.ForeignKey(
        Level,
        on_delete=models.CASCADE,
        related_name="services",
        null=True,
        blank=True,
        help_text=_(
            "If left none, this service will be given priority and used for all levels"
        ),
    )
    deadline = models.ForeignKey(
        Deadline,
        on_delete=models.CASCADE,
        related_name="services",
    )
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name="services",
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, help_text=_("Price per page")
    )

    def __str__(self):
        if self.level:
            return f"{self.paper} - {self.level} - {self.deadline}"

        return f"{self.paper} - {self.deadline}"


class WriterTypeTag(AbstractBase):
    title = models.CharField(max_length=20)


class WriterType(AbstractBase):
    """type of writer information"""

    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "name")  # type: ignore

    name = models.CharField(max_length=32)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=_("The position of display when ordering is done by this field"),
    )
    description = models.CharField(max_length=160, null=True, blank=True)
    tags = models.ManyToManyField(
        WriterTypeTag, related_name="writer_types", blank=True
    )

    def __str__(self):
        return self.name


class WriterTypeService(AbstractBase):
    """type of writer and service relationship information"""

    class Meta(AbstractBase.Meta):
        unique_together = ("writer_type", "service")

    writer_type = models.ForeignKey(
        WriterType,
        on_delete=models.CASCADE,
        related_name="writer_prices",
    )
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="writer_prices"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Price per page. Leave blank or fill 0.00 if free"),
    )

    def __str__(self):
        return f"{self.writer_type} - {self.service}"
