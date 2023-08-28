from django.urls import path

from .views import PublicConfigsAPIView

urlpatterns = [
    path("public-configs/", PublicConfigsAPIView.as_view(), name="public_configs"),
]
