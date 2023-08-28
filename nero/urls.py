"""nero URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import include
from django.contrib import admin
from django.urls import path

from apps.users.views import (
    CookieThrottledTokenObtainPairView,
    CookieTokenRefreshView,
    GoogleRecaptchaAPIView,
    LogoutAPIView,
)

apipatterns = [
    path(
        "auth/token/",
        CookieThrottledTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "auth/token/refresh/",
        CookieTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("auth/logout/", LogoutAPIView.as_view(), name="auth_logout"),
    path(
        "auth/google-recaptcha/",
        GoogleRecaptchaAPIView.as_view(),
        name="google_recaptcha",
    ),
    path("mail/", include("apps.mail.urls")),
    path("users/", include("apps.users.urls")),
    path("cart/", include("apps.cart.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("coupons/", include("apps.coupon.urls")),
    path("orders/", include("apps.orders.urls")),
    path("blog/", include("apps.blog.urls")),
    path("paypal/", include("apps.paypal.urls")),
    path("payments/", include("apps.payments.urls")),
    path("pages/", include("apps.pages.urls")),
    path("site-configs/", include("apps.tenants.urls")),
    path("subscription/", include("apps.subscription.urls")),
    path("twocheckout/", include("apps.twocheckout.urls")),
]

urlpatterns = [
    path("api/v1/", include(apipatterns)),
    path("api/woza/", admin.site.urls),
]
