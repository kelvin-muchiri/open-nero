from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.mixins import (
    PublicCacheListModelMixin,
    UncachedListActionMixin,
    UncachedRetrieveActionMixin,
)
from apps.common.pagination import LargeResultsSetPagination
from apps.common.permissions import (
    IsStoreStaff,
    IsStoreStaffOrReadOnly,
    IsSubscriptionActive,
)
from apps.users.models import User

from .filters import PageFilter
from .models import FooterGroup, FooterLink, Image, NavbarLink, Page
from .serializers import (
    DraftPageSerializer,
    FooterGroupDetailSerializer,
    FooterGroupSerializer,
    FooterLinkDetailSerializer,
    FooterLinkSerializer,
    ImageSerializer,
    NavbarLinkDetailSerializer,
    NavbarLinkSerializer,
    PageSerializer,
    SlugUniqueSerializer,
)


class PageViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None
    filterset_class = PageFilter

    def get_serializer_class(self):
        if (
            self.request.user.is_authenticated
            and self.request.user.profile_type == User.ProfileType.STAFF
        ):
            return DraftPageSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        if (
            not self.request.user.is_authenticated
            or self.request.user.profile_type != User.ProfileType.STAFF
        ):
            return super().get_queryset().filter(is_active=True, is_public=True)

        return super().get_queryset()

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
        """Check if slug is unique when updating page"""
        current = self.get_object()
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Page.objects.filter(slug=slug).exclude(pk=current.pk).exists():
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
        """Check if slug is unique when creating page"""
        serializer = SlugUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        slug = serializer.data.get("slug")
        response = {"is_unique": True}

        if Page.objects.filter(slug=slug).exists():
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


class NavbarLinkViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    UncachedRetrieveActionMixin,
    viewsets.GenericViewSet,
):
    queryset = NavbarLink.objects.all()
    serializer_class = NavbarLinkSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()

        if self.action in ["list", "uncached_list"]:
            # we do not return children links since they will be nested in parent links
            return qs.filter(parent=None)

        return qs

    def get_serializer_class(self):
        if self.action in ["list", "uncached_list", "uncached_retrieve"]:
            return NavbarLinkDetailSerializer

        return super().get_serializer_class()


class FooterLinkViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    queryset = FooterLink.objects.all()
    serializer_class = FooterLinkSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ["list", "uncached_list"]:
            return FooterLinkDetailSerializer

        return super().get_serializer_class()


class FooterGroupViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    queryset = FooterGroup.objects.all()
    serializer_class = FooterGroupSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ["list", "uncached_list"]:
            return FooterGroupDetailSerializer

        return super().get_serializer_class()
