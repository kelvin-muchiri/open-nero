"""query param filters"""
import json

import django_filters

from .models import Page


class PageFilter(django_filters.FilterSet):
    metadata = django_filters.CharFilter(method="metadata_filter")

    class Meta:
        model = Page
        fields = (
            "is_public",
            "slug",
        )

    def metadata_filter(self, queryset, _, value):
        query = json.loads(value)

        if isinstance(query, dict):
            return queryset.filter(metadata__contains=query)

        return queryset
