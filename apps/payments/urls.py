"""Routing"""
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.payments import views

router = SimpleRouter()
router.register(r"", views.PaymentViewSet)
router.register(r"methods", views.PaymentMethodViewSet, basename="payment_method")

urlpatterns = [
    path(r"", include(router.urls)),
]
