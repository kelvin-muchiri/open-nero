from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils import timezone

from apps.common.utils import has_model_field_changed
from apps.orders.models import (
    Order,
    OrderCoupon,
    OrderItem,
    OrderItemAttachment,
    OrderItemPaper,
    Rating,
)

from .tasks import send_email_order_item_status


class OverdueFilter(SimpleListFilter):
    title = "overdue"
    parameter_name = "overdue"

    def lookups(self, request, model_admin):
        return [("Yes", "Yes")]

    def queryset(self, request, queryset):
        if self.value() == "Yes":
            return OrderItem.objects.filter(
                status=OrderItem.Status.IN_PROGRESS, due_date__lt=timezone.now()
            )


class OrderItemPaperInline(admin.StackedInline):
    model = OrderItemPaper
    extra = 1


class OrderItemAttachmentInline(admin.StackedInline):
    model = OrderItemAttachment
    extra = 0


class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "topic",
        "owner",
        "order",
        "paper",
        "due_date",
        "days_left",
        "quantity",
        "status",
        "is_paid",
        "created_at",
    )
    list_filter = ("status", OverdueFilter)
    search_fields = (
        "topic",
        "order__id",
        "paper",
        "order__owner__first_name",
        "order__owner__last_name",
    )
    inlines = (
        OrderItemAttachmentInline,
        OrderItemPaperInline,
    )
    ordering = ("-created_at",)

    def is_paid(self, obj):
        if obj.order.status == Order.Status.PAID:
            return True

        return False

    def days_left(self, obj):
        return obj.days_left

    def owner(self, obj):
        if not obj.order.owner:
            return None

        return obj.order.owner.full_name

    is_paid.boolean = True

    def save_model(self, request, obj, form, change):
        instance = form.save(commit=False)
        status_change = False

        if has_model_field_changed(instance, "status"):
            status_change = True

        super(OrderItemAdmin, self).save_model(request, obj, form, change)

        if status_change:
            send_email_order_item_status(request.tenant.schema_name, instance.pk)


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "amount_payable",
        "item_count",
        "next_due",
        "is_paid",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "id",
        "owner__first_name",
        "owner__last_name",
    )
    inlines = (OrderItemInline,)

    def is_paid(self, obj):
        if obj.status == Order.Status.PAID:
            return True

        return False

    def amount_payable(self, obj):
        return obj.amount_payable

    def next_due(self, obj):
        return obj.earliest_due

    def item_count(self, obj):
        return obj.items.count()

    is_paid.boolean = True
    amount_payable.short_description = "Amount"
    item_count.short_description = "Items"


class OrderCouponAdmin(admin.ModelAdmin):
    list_display = ("order", "code", "discount")
    search_fields = ("code", "order__id")


class RatingAdmin(admin.ModelAdmin):
    list_display = ("paper", "rating", "comment")
    search_fields = (
        "paper__order_item__topic",
        "paper__order_item__order__id",
    )


admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(OrderCoupon, OrderCouponAdmin)
admin.site.register(Rating, RatingAdmin)
