"""query param filters"""
import django_filters

from apps.catalog.models import Deadline, Level, Paper, Service


class LevelFilter(django_filters.FilterSet):
    """filters for model Level"""

    paper = django_filters.CharFilter(method="paper_filter")

    def paper_filter(self, queryset, _, value):
        """Return academic levels where paper query param matches value"""
        level_ids = (
            Service.objects.filter(paper__id=value)
            .values_list("level__id", flat=True)
            .distinct()
        )

        return queryset.filter(id__in=level_ids)

    class Meta:
        model = Level
        fields = ("paper",)


class DeadlineFilter(django_filters.FilterSet):
    """Filters for model Deadline"""

    paper = django_filters.CharFilter(method="paper_filter")
    level = django_filters.CharFilter(method="level_filter")

    def paper_filter(self, queryset, _, value):
        """Return distinct deadlines where paper query param matches value"""
        deadline_ids = (
            Service.objects.filter(paper__id=value)
            .values_list("deadline__id", flat=True)
            .distinct()
        )

        return queryset.filter(id__in=deadline_ids)

    def level_filter(self, queryset, _, value):
        """Return distinct deadlines where level query param matches value"""
        deadline_ids = (
            Service.objects.filter(level__id=value)
            .values_list("deadline__id", flat=True)
            .distinct()
        )

        return queryset.filter(id__in=deadline_ids)

    class Meta:
        model = Deadline
        fields = ("paper", "level")


class PaperFilter(django_filters.FilterSet):
    """Filters for model Paper"""

    service_only = django_filters.BooleanFilter(method="service_only_filter")

    def service_only_filter(self, queryset, _, value):
        if value:
            paper_ids = (
                Service.objects.all().values_list("paper__id", flat=True).distinct()
            )

            return queryset.filter(id__in=paper_ids)

        return queryset

    class Meta:
        model = Paper
        fields = ("name",)


class ServiceFilter(django_filters.FilterSet):
    class Meta:
        model = Service
        fields = ("paper",)
