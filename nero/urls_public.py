"""URL routing for the public schema"""

from django.conf.urls import include
from django.urls import path

apipatterns = [
    path("auth/", include("apps.main_auth.urls")),
]

urlpatterns = [
    path("api/v1/", include(apipatterns)),
]
