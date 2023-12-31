# Generated by Django 4.0 on 2022-02-02 12:31

import apps.cart.paths
import apps.common.utils
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Attachment",
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
                    "attachment",
                    models.FileField(
                        max_length=10000,
                        upload_to=apps.cart.paths.path_cart_item_attachment,
                        validators=[
                            apps.common.utils.FileValidator(
                                content_types=(
                                    "application/pdf",
                                    "application/msword",
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    "application/vnd.ms-powerpoint",
                                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                    "application/vnd.ms-excel",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sh",
                                    "application/zip",
                                    "image/jpeg",
                                    "image/png",
                                    "text/plain",
                                ),
                                max_size=5242880,
                            )
                        ],
                    ),
                ),
                ("comment", models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                "ordering": ("-updated_at", "-created_at"),
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Cart",
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
            ],
            options={
                "ordering": ("-updated_at", "-created_at"),
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Item",
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
                ("topic", models.CharField(max_length=255)),
                (
                    "language",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "English UK"), (2, "English US")], default=1
                    ),
                ),
                (
                    "pages",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(1000),
                        ],
                    ),
                ),
                ("references", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("comment", models.TextField(blank=True, null=True)),
                (
                    "quantity",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(3),
                        ],
                    ),
                ),
                ("page_price", models.DecimalField(decimal_places=2, max_digits=15)),
                (
                    "writer_type_price",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=15, null=True
                    ),
                ),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="cart.cart",
                    ),
                ),
            ],
            options={
                "ordering": ("-updated_at", "-created_at"),
                "abstract": False,
            },
        ),
    ]
