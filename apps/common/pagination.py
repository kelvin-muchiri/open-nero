"""
Custom Django REST pagination classes
"""

from collections import OrderedDict

from rest_framework import pagination
from rest_framework.response import Response


class CustomPagination(pagination.PageNumberPagination):
    """
    Custom pagination REST API pagination class
    """

    page_size_query_param = "page_size"
    max_page_size = 15000

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.page.paginator.per_page),
                    ("current_page", self.page.number),
                    ("total_pages", self.page.paginator.num_pages),
                    ("start_index", self.page.start_index()),
                    ("end_index", self.page.end_index()),
                    ("results", data),
                ]
            )
        )


class LargeResultsSetPagination(CustomPagination):
    """Large results pagination class"""

    page_size = 100


class SmallResultsSetPagination(CustomPagination):
    """Small results pagination class"""

    page_size = 5
