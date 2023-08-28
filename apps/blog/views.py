"""Views"""

from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.views.decorators.cache import patch_cache_control  # type: ignore
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.blog.models import Category, Image, Post, Tag
from apps.common.mixins import (
    PublicCacheListModelMixin,
    PublicCacheRetrieveModelMixin,
    UncachedListActionMixin,
    UncachedRetrieveActionMixin,
)
from apps.common.pagination import LargeResultsSetPagination
from apps.common.permissions import (
    IsStoreStaff,
    IsStoreStaffOrReadOnly,
    IsSubscriptionActive,
)

from .filters import CategoryFilter, PostFilter, TagFilter
from .serializers import (
    CategoryDetailSerializer,
    CategoryListSerializer,
    CategorySerializer,
    ImageSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PostSerializer,
    SlugUniqueSerializer,
    TagListSerializer,
    TagSerializer,
)

CACHE_TTL = getattr(settings, "CACHE_TTL", DEFAULT_TIMEOUT)


class PostViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    PublicCacheRetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    UncachedRetrieveActionMixin,
    viewsets.GenericViewSet,
):
    queryset = Post.objects.all()
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    serializer_class = PostSerializer
    filterset_class = PostFilter
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action in ["retrieve", "uncached_retrieve"]:
            return PostDetailSerializer

        if self.action in ["list", "uncached_list"]:
            return PostListSerializer

        return super().get_serializer_class()

    @action(
        detail=True,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_update(self, request, *args, **kwargs):
        """Check if slug is unique when updating"""
        current = self.get_object()
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Post.objects.filter(slug=slug).exclude(pk=current.pk).exists():
            response.update({"is_unique": False})

        return Response(response)

    @action(
        detail=False,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_create(self, request, *args, **kwargs):
        """Check if slug is unique when creating"""
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Post.objects.filter(slug=slug).exists():
            response.update({"is_unique": False})

        return Response(response)

    def finalize_response(self, request, response, *args, **kwargs):
        if self.action in ["featured", "pinned", "latest"]:
            patch_cache_control(response, public=True, no_cache=True)

        return super().finalize_response(request, response, *args, **kwargs)


class TagViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):

    queryset = Tag.objects.all()
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    serializer_class = TagSerializer
    pagination_class = None
    filterset_class = TagFilter

    def get_serializer_class(self):
        if self.action in ["list", "uncached_list"]:
            return TagListSerializer

        return super().get_serializer_class()

    @action(
        detail=True,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_update(self, request, *args, **kwargs):
        """Check if slug is unique when updating"""
        current = self.get_object()
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Tag.objects.filter(slug=slug).exclude(pk=current.pk).exists():
            response.update({"is_unique": False})

        return Response(response)

    @action(
        detail=False,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_create(self, request, *args, **kwargs):
        """Check if slug is unique when creating"""
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Tag.objects.filter(slug=slug).exists():
            response.update({"is_unique": False})

        return Response(response)


class CategoryViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    UncachedRetrieveActionMixin,
    viewsets.GenericViewSet,
):

    queryset = Category.objects.all()
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    serializer_class = CategorySerializer
    pagination_class = None
    filterset_class = CategoryFilter

    def get_queryset(self):
        qs = super().get_queryset()

        if self.action in ["list", "uncached_list"]:
            # we do not return children links since they will be nested in parent links
            return qs.filter(parent=None)

        return qs

    def get_serializer_class(self):
        if self.action in ["list", "uncached_list"]:
            return CategoryListSerializer

        if self.action == "uncached_retrieve":
            return CategoryDetailSerializer

        return super().get_serializer_class()

    @action(
        detail=True,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_update(self, request, *args, **kwargs):
        """Check if slug is unique when updating"""
        current = self.get_object()
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Category.objects.filter(slug=slug).exclude(pk=current.pk).exists():
            response.update({"is_unique": False})

        return Response(response)

    @action(
        detail=False,
        url_name="slug-unique",
        url_path="slug-unique",
        methods=["post"],
        permission_classes=(
            IsSubscriptionActive,
            IsAuthenticated,
            IsStoreStaff,
        ),
    )
    def slug_unique_create(self, request, *args, **kwargs):
        """Check if slug is unique when creating"""
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Category.objects.filter(slug=slug).exists():
            response.update({"is_unique": False})

        return Response(response)


class ImageViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticated,
        IsStoreStaff,
    )
    pagination_class = LargeResultsSetPagination
