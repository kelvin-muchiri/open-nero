from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.orders import views

router = SimpleRouter()
router.register(r"rate-paper", views.RatingViewSet, basename="rating")
router.register(
    r"paper-files", views.OrderItemPaperViewSet, basename="order_item_paper"
)
router.register(r"items", views.OrderItemViewSet, basename="order_item")
router.register(r"self", views.SelfOrderViewSet, basename="self_order")
router.register(r"", views.OrderViewSet, basename="order")

urlpatterns = [
    path(r"", include(router.urls)),
]
