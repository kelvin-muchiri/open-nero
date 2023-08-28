"""query param filters"""
import django_filters
from django.db.models import Q

from .models import Order, OrderItem


class OrderItemFilter(django_filters.FilterSet):
    topic = django_filters.CharFilter(lookup_expr="icontains")
    is_overdue = django_filters.BooleanFilter(method="is_overdue_filter")
    order_id = django_filters.NumberFilter(field_name="order__id", lookup_expr="exact")
    new = django_filters.BooleanFilter(method="new_filter")

    def is_overdue_filter(self, queryset, _, value):
        if value:
            overdue_ids = []

            for order_item in queryset:
                if order_item.is_overdue:
                    overdue_ids.append(order_item.id)

            return queryset.filter(id__in=overdue_ids)

        return queryset

    def new_filter(self, queryset, _, value):
        if value:
            return queryset.filter(
                Q(status=OrderItem.Status.PENDING)
                | Q(status=OrderItem.Status.IN_PROGRESS),
                order__status=Order.Status.PAID,
            )

        return queryset

    class Meta:
        model = OrderItem
        fields = ("status",)
