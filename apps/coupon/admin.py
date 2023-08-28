from django.contrib import admin

from apps.coupon.models import Coupon


class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "percent_off",
        "coupon_type",
        "minimum",
        "start_date",
        "end_date",
        "is_expired",
    )
    search_fields = ("code",)

    def is_expired(self, obj):
        if obj.is_expired:
            return True

        return False

    is_expired.boolean = True


admin.site.register(Coupon, CouponAdmin)
