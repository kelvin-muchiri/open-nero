from django.urls import path

from .views import TwocheckoutWebhookAPIView

urlpatterns = [
    path("webhook/", TwocheckoutWebhookAPIView.as_view(), name="twocheckout_webhook"),
]
