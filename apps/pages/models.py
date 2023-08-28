import os

from django.db import models

from apps.common.backends.storage import PublicMediaStorage
from apps.common.models import AbstractBase
from apps.common.utils import FileValidator

IMAGE_VALIDATORS = FileValidator(
    content_types=(
        "image/webp",
        "image/png",
        "image/jpeg",
    )
)


def default_empty_json():
    """Callable that returns default empty dict for JSONField"""
    return {}


class Page(AbstractBase):
    title = models.CharField(max_length=255)
    slug = slug = models.SlugField(
        max_length=60,
        db_index=True,
        help_text="""URL-friendly version of the name. All lowercase and contains only
        letters, numbers and hyphens. If not provided, the name will be used as URL""",
        unique=True,
    )
    seo_title = models.CharField(max_length=60, null=True, blank=True)
    seo_description = models.CharField(max_length=160, null=True, blank=True)
    is_public = models.BooleanField(default=True)
    blocks = models.JSONField(default=list)
    draft = models.JSONField(default=list)
    metadata = models.JSONField(default=default_empty_json)

    def __str__(self) -> str:
        return self.title

    def publish(self):
        self.blocks = self.draft
        self.is_public = True
        self.save()


class Image(AbstractBase):
    image = models.FileField(
        max_length=500,
        upload_to="pages/images/",
        storage=PublicMediaStorage,
        validators=[IMAGE_VALIDATORS],
    )

    @property
    def file_name(self):
        return os.path.basename(self.image.name)

    def __str__(self):
        return self.file_name


class NavbarLink(AbstractBase):
    class Meta(AbstractBase.Meta):
        ordering = ("created_at",)

    title = models.CharField(max_length=50)
    link_to = models.ForeignKey(
        Page,
        on_delete=models.SET_NULL,
        related_name="navbar_links",
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return self.title


class FooterGroup(AbstractBase):
    class Meta(AbstractBase.Meta):
        ordering = ("sort_order", "title")  # type: ignore

    title = models.CharField(max_length=20)
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=("The position of display when ordering is done by this field"),
    )


class FooterLink(AbstractBase):
    class Meta(AbstractBase.Meta):
        ordering = ("sort_order",)

    title = models.CharField(max_length=20)
    link_to = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="footer_links",
    )
    group = models.ForeignKey(
        FooterGroup,
        on_delete=models.SET_NULL,
        related_name="links",
        null=True,
        blank=True,
    )
    sort_order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text=("The position of display when ordering is done by this field"),
    )
