# Generated by Django 4.0 on 2022-02-03 09:45

import apps.blog.utils
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_active", models.BooleanField(default=True, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=32)),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL-friendly version of the name. All lowercase and contains only\n        letters, numbers and hyphens. If not provided, the name will be used as URL",
                        max_length=60,
                    ),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_related",
                        related_query_name="%(app_label)s_%(class)ss",
                        to="users.user",
                    ),
                ),
            ],
            options={
                "ordering": ("-updated_at", "-created_at"),
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_active", models.BooleanField(default=True, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "title",
                    models.CharField(
                        help_text="An SEO friendly title with a max length of 60",
                        max_length=60,
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        help_text="An SEO friendly with a max length of 160",
                        max_length=160,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL-friendly version of the title. All lowercase and contains only\n        letters, numbers and hyphens. If not provided, the title will be used as URL",
                        max_length=60,
                    ),
                ),
                (
                    "featured_image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=apps.blog.utils.image_path,
                    ),
                ),
                ("is_published", models.BooleanField(default=True)),
                (
                    "is_pinned",
                    models.BooleanField(
                        default=False,
                        help_text="Set true if you want this post to be pinned at the top of the blog page.\n            Only one post can be pinned at a time",
                    ),
                ),
                (
                    "is_featured",
                    models.BooleanField(
                        default=False,
                        help_text="Set true if post should be displayed in the featured section. More than\n            post can be featured\n            ",
                    ),
                ),
                ("content", models.TextField()),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(app_label)s_%(class)s_related",
                        related_query_name="%(app_label)s_%(class)ss",
                        to="users.user",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True, related_name="blogs", to="blog.Tag"
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
                "abstract": False,
            },
        ),
    ]
