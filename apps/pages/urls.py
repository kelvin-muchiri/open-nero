from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    FooterGroupViewSet,
    FooterLinkViewSet,
    ImageViewSet,
    NavbarLinkViewSet,
    PageViewSet,
)

router = SimpleRouter()
router.register(r"images", ImageViewSet, basename="image")
router.register(r"navbar-links", NavbarLinkViewSet, basename="navbar_link")
router.register(r"footer-links", FooterLinkViewSet, basename="footer_link")
router.register(r"footer-groups", FooterGroupViewSet, basename="footer_group")
router.register(r"", PageViewSet, basename="page")

urlpatterns = [path(r"", include(router.urls))]
