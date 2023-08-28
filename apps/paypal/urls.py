"""Routing"""

from django.urls import path

from .views import PaypalWebhookAPIView

urlpatterns = [
    path("webhook/", PaypalWebhookAPIView.as_view(), name="paypal_webhook"),
]
