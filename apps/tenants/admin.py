from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, Tenant


class DomainInline(admin.StackedInline):
    model = Domain
    extra = 0


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "created_at")
    inlines = (DomainInline,)
