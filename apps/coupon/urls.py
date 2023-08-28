"""Routing"""
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.coupon import views

router = SimpleRouter()
router.register(r"", views.CouponViewSet, basename="coupon")

urlpatterns = [
    path("apply/", views.CouponApplicationAPIView.as_view(), name="apply_coupon"),
    path(r"", include(router.urls)),
]
