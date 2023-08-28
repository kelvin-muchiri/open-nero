"""Routing"""
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    ChangePasswordAPIView,
    ConfirmEmailChangeAPIView,
    CreateCustomerAPIView,
    CustomerDeleteAccountAPIView,
    CustomerViewSet,
    EmailVerificationEndAPIView,
    ProfileAPIView,
    ResendEmailVerificationAPIView,
    ResetPasswordEndAPIView,
    ResetPasswordStartAPIView,
    UserEmailExistsPIView,
)

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    path("profile/", ProfileAPIView.as_view(), name="user_profile"),
    path("check-exists/email/", UserEmailExistsPIView.as_view(), name="check_email"),
    path(
        "reset-password/start/",
        ResetPasswordStartAPIView.as_view(),
        name="reset_password_start",
    ),
    path(
        "reset-password/end/",
        ResetPasswordEndAPIView.as_view(),
        name="reset_password_end",
    ),
    path(
        "verify/email/resend/",
        ResendEmailVerificationAPIView.as_view(),
        name="resend_email_verification",
    ),
    path(
        "verify/email/",
        EmailVerificationEndAPIView.as_view(),
        name="email_verification_end",
    ),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change_password"),
    path(
        "change-email/confirm/",
        ConfirmEmailChangeAPIView.as_view(),
        name="confirm_email_change",
    ),
    path("customers/create/", CreateCustomerAPIView.as_view(), name="create_customer"),
    path(
        "customers/delete-account/",
        CustomerDeleteAccountAPIView.as_view(),
        name="customer_delete_account",
    ),
    path(r"", include(router.urls)),
]
