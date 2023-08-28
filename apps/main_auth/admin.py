# pylint: skip-file

from django.contrib import admin

from .models import EmailVerification


class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "is_verified", "created_at")
    search_fields = ("email",)


admin.site.register(EmailVerification, EmailVerificationAdmin)
