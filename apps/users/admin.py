from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


class UserAdmin(BaseUserAdmin):
    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = (
        "full_name",
        "email",
        "profile_type",
        "is_store_owner",
        "is_staff",
        "is_superuser",
        "is_active",
        "is_email_verified",
        "date_joined",
        "last_login",
    )
    list_filter = (
        "is_store_owner",
        "is_staff",
        "is_superuser",
        "is_active",
        "is_email_verified",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "is_active",
                    "password",
                )
            },
        ),
        (
            "Personal Info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "other_names",
                    "email",
                    "profile_type",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                    "is_store_owner",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Other", {"fields": ("is_email_verified",)}),
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    filter_horizontal = (
        "groups",
        "user_permissions",
    )


admin.site.register(User, UserAdmin)
