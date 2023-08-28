import os

from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.common.backends.storage import PublicMediaStorage
from apps.common.models import AbstractBase
from apps.common.utils import FileValidator

from .utils import image_path

IMAGE_VALIDATORS = FileValidator(
    content_types=(
        "image/webp",
        "image/png",
        "image/jpeg",
    )
)


class Tag(AbstractBase):
    name = models.CharField(max_length=32)
    slug = models.SlugField(
        max_length=60,
        db_index=True,
        help_text=_(
            """URL-friendly version of the name. All lowercase and contains only
        letters, numbers and hyphens. If not provided, the name will be used as URL"""
        ),
    )
    description = models.CharField(max_length=160, null=True, blank=True)

    def __str__(self):
        return self.name


class Category(AbstractBase):
    class Meta(AbstractBase.Meta):
        ordering = ("name",)
        verbose_name_plural = "Categories"

    name = models.CharField(max_length=32)
    slug = models.SlugField(
        max_length=60,
        db_index=True,
        help_text=_(
            """URL-friendly version of the name. All lowercase and contains only
        letters, numbers and hyphens. If not provided, the name will be used as URL"""
        ),
        unique=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        help_text=_(
            """Categories, unlike tags can have a hierarchy. You might have a Essay Sample
            category, and under that have categories for Medicine, Business
            """
        ),
    )
    description = models.CharField(max_length=160, null=True, blank=True)

    def __str__(self):
        return self.name


class Image(AbstractBase):
    image = models.FileField(
        max_length=500,
        upload_to=image_path,
        storage=PublicMediaStorage,
        validators=[IMAGE_VALIDATORS],
    )

    @property
    def file_name(self):
        return os.path.basename(self.image.name)

    def __str__(self):
        return self.file_name


class Post(AbstractBase):
    title = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=60,
        db_index=True,
        help_text=_(
            """URL-friendly version of the title. All lowercase and contains only
        letters, numbers and hyphens. If not provided, the title will be used as URL"""
        ),
        unique=True,
    )
    seo_title = models.CharField(
        max_length=60,
        help_text=_("An SEO friendly title with a max length of 60"),
        null=True,
        blank=True,
    )
    seo_description = models.CharField(
        max_length=160,
        help_text=_("An SEO friendly with a max length of 160"),
        null=True,
        blank=True,
    )
    categories = models.ManyToManyField(Category, related_name="blogs", blank=True)
    tags = models.ManyToManyField(Tag, related_name="blogs", blank=True)
    featured_image = models.ForeignKey(
        Image,
        on_delete=models.SET_NULL,
        related_name="posts",
        null=True,
        blank=True,
    )
    is_published = models.BooleanField(default=False)
    is_pinned = models.BooleanField(
        default=False,
        help_text=_(
            """Set true if you want this post to be pinned at the top of the blog page.
            Only one post can be pinned at a time"""
        ),
    )
    is_featured = models.BooleanField(
        default=False,
        help_text=_(
            """Set true if post should be displayed in the featured section. More than
            post can be featured
            """
        ),
    )
    content = models.JSONField(default=list, blank=True)
    draft = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.title

    def publish(self):
        """Publish a post to make it public"""
        self.content = self.draft
        self.is_published = True
        self.save()

    @cached_property
    def previous_post(self):
        """Get the previous post"""
        return (
            Post.objects.filter(is_published=True, created_at__lt=self.created_at)
            .order_by("-created_at")
            .first()
        )

    @cached_property
    def next_post(self):
        """Get the next post"""
        return (
            Post.objects.filter(is_published=True, created_at__gt=self.created_at)
            .order_by("created_at")
            .first()
        )
