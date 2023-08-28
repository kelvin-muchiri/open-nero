"""Endpoint query param filters"""
import django_filters

from apps.blog.models import Post


class PostFilter(django_filters.FilterSet):
    """Filters for post list"""

    title = django_filters.CharFilter(lookup_expr="icontains")
    tag_slug = django_filters.CharFilter(field_name="tags__slug", lookup_expr="exact")
    category_slug = django_filters.CharFilter(
        field_name="categories__slug",
        lookup_expr="exact",
    )

    class Meta:
        model = Post
        fields = (
            "is_published",
            "is_pinned",
            "is_featured",
        )


class TagFilter(django_filters.FilterSet):
    """Filters for tag list"""

    name = django_filters.CharFilter(lookup_expr="icontains")


class CategoryFilter(django_filters.FilterSet):
    """Filters for category list"""

    name = django_filters.CharFilter(lookup_expr="icontains")
