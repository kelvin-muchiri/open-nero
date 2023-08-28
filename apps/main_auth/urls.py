"""Routing"""
from django.urls import path

from .views import (
    CreateSiteAPIView,
    EmailVerificationCodeConfirmAPIView,
    EmailVerificationCodeSendAPIView,
    PayPalSubscriptionWebhookAPIView,
)

urlpatterns = [
    path("verify/email/send/", EmailVerificationCodeSendAPIView.as_view()),
    path("verify/email/", EmailVerificationCodeConfirmAPIView.as_view()),
    path("create-site/", CreateSiteAPIView.as_view(), name="create_site"),
    path(
        "paypal-webhook/subscription/",
        PayPalSubscriptionWebhookAPIView.as_view(),
        name="paypal_webhook_subscription",
    ),
]
