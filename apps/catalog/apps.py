from django.apps import AppConfig

# flake8: noqa
# pylint: skip-file


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
