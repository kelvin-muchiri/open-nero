from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    BillingHistoryViewSet,
    CancelSubscriptionAPIView,
    CurrentSubscriptionAPIView,
)

router = SimpleRouter()
router.register(r"billing-history", BillingHistoryViewSet, basename="billing_history")

urlpatterns = [
    *router.urls,
    path("cancel/", CancelSubscriptionAPIView.as_view(), name="cancel_subscription"),
    path("", CurrentSubscriptionAPIView.as_view(), name="current_subscription"),
]
