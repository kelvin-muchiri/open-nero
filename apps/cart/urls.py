"""Routing"""
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.cart import views

router = SimpleRouter()
router.register(r"", views.CartViewSet, basename="cart")
router.register(
    r"items/attachments", views.AttachmentViewset, basename="cart_attachment"
)
router.register(r"items", views.CartItemViewset, basename="cart_item")


urlpatterns = [path(r"", include(router.urls))]
