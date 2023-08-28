import datetime

from django.contrib import admin
from django.db.models import Sum

from apps.payments.models import Payment, PaymentMethod


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "trx_ref_number",
        "amount_paid",
        "date_paid",
    )
    search_fields = ("trx_ref_number", "amount_paid")

    def get_current_week(self):
        date = datetime.date.today()
        start_week = date - datetime.timedelta(date.weekday())
        end_week = start_week + datetime.timedelta(7)
        return [start_week, end_week]

    def get_overall_total(self):
        """Get all total payments."""
        return Payment.objects.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0.00

    def get_total_this_week(self):
        """Get total payments for currrent week.

        Week starts from Monday."""

        return (
            Payment.objects.filter(
                date_paid__date__range=self.get_current_week()
            ).aggregate(Sum("amount_paid"))["amount_paid__sum"]
            or 0.00
        )

    def get_total_this_month(self):
        """Get total payments for current month."""
        today = datetime.date.today()
        return (
            Payment.objects.filter(
                date_paid__year=today.year, date_paid__month=today.month
            ).aggregate(Sum("amount_paid"))["amount_paid__sum"]
            or 0.00
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["overall_total"] = self.get_overall_total()
        extra_context["week_total"] = self.get_total_this_week()
        extra_context["month_total"] = self.get_total_this_month()
        return super(PaymentAdmin, self).changelist_view(
            request, extra_context=extra_context
        )


class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "is_active",
    )


admin.site.register(Payment, PaymentAdmin)
admin.site.register(PaymentMethod, PaymentMethodAdmin)
