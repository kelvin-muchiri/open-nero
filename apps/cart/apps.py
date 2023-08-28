from django.apps import AppConfig

# flake8: noqa
# pylint: skip-file


class CartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cart"

    def ready(self):
        import apps.cart.signals
