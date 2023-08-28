"""Routing"""
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.blog import views

router = SimpleRouter()
router.register(r"posts", views.PostViewSet, basename="post")
router.register(r"tags", views.TagViewSet, basename="tag")
router.register(r"categories", views.CategoryViewSet, basename="category")
router.register(r"images", views.ImageViewSet, basename="image")

urlpatterns = [path(r"", include(router.urls))]
