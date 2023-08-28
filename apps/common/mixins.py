from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.utils.decorators import method_decorator
from django.views.decorators.cache import (  # type: ignore
    cache_page,
    patch_cache_control,
)
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated

from .permissions import IsStoreStaff, IsSubscriptionActive

CACHE_TTL = getattr(settings, "CACHE_TTL", DEFAULT_TIMEOUT)

# pylint: disable=too-few-public-methods


class PublicCacheListModelMixin(ListModelMixin):
    @method_decorator([cache_page(CACHE_TTL), vary_on_headers("Host")])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        if self.action == "list":
            patch_cache_control(response, public=True, no_cache=True)

        return super().finalize_response(request, response, *args, **kwargs)


class PublicCacheRetrieveModelMixin(RetrieveModelMixin):
    @method_decorator([cache_page(CACHE_TTL), vary_on_headers("Host")])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        if self.action == "retrieve":
            patch_cache_control(response, public=True, no_cache=True)

        return super().finalize_response(request, response, *args, **kwargs)


class UncachedListActionMixin:
    """Un-cached list

    Used by store admin. This is a work-around to resolve admin changes not reflecting
    immediately after adding new record(s) or updating existing records(s) due to caching.
    This work-around should be removed when a nice solution to invalidate cache per tenant
    is implemented
    """

    @action(
        detail=False,
        methods=["get"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
        url_name="no-cache",
        url_path="no-cache",
    )
    def uncached_list(self, request, *args, **kwargs):
        return ListModelMixin.list(self, request, *args, **kwargs)


class UncachedRetrieveActionMixin:
    """Un-cached detail

    Used by store admin. This is a work-around to resolve admin changes not reflecting
    immediately after adding new record(s) or updating existing records(s) due to caching.
    This work-around should be removed when a nice solution to invalidate cache per tenant
    is implemented
    """

    @action(
        detail=True,
        methods=["get"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
        url_name="no-cache",
        url_path="no-cache",
    )
    def uncached_retrieve(self, request, *args, **kwargs):
        return RetrieveModelMixin.retrieve(self, request, *args, **kwargs)
