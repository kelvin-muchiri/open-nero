"""Routing"""

from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.catalog import views

router = SimpleRouter()
router.register(r"levels", views.LevelViewSet, basename="level")
router.register(r"courses", views.CourseViewSet, basename="course")
router.register(r"formats", views.FormatViewSet, basename="format")
router.register(r"deadlines", views.DeadlineViewSet, basename="deadline")
router.register(r"papers", views.PaperViewSet, basename="paper")
router.register("services", views.ServiceViewSet, basename="service")

urlpatterns = [
    path("calculator/", views.CalculatorAPIView.as_view(), name="calculator"),
    path("writer_types/", views.WriterTypeServiceAPIView.as_view(), name="writer_type"),
    path(r"", include(router.urls)),
]
