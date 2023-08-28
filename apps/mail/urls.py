"""Routing"""

from django.urls import path

from .views import SendMailAPIView

urlpatterns = [
    path("send/", SendMailAPIView.as_view()),
]
