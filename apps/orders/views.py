from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import (  # type: ignore
    cache_page,
    patch_cache_control,
)
from django.views.decorators.vary import vary_on_headers
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.pagination import SmallResultsSetPagination
from apps.common.permissions import IsCustomer, IsStoreStaff, IsSubscriptionActive
from apps.common.utils import create_presigned_url
from apps.users.models import User

from .filters import OrderItemFilter
from .models import Order, OrderItem, OrderItemAttachment, OrderItemPaper, Rating
from .serializers import (
    CustomerOrderSerializer,
    DownloadAttachmentSerializer,
    OrderDetailSerializer,
    OrderItemPaperSerializer,
    OrderItemSerializer,
    OrderSerializer,
    RatingSerializer,
    SelfOrderListSerializer,
)


class SelfOrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CustomerOrderSerializer
    queryset = Order.objects.none()
    pagination_class = SmallResultsSetPagination
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticated,
        IsCustomer,
    )

    def get_queryset(self):
        return Order.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return SelfOrderListSerializer

        if self.action == "retrieve":
            return OrderDetailSerializer

        if self.action == "download_attachment":
            return DownloadAttachmentSerializer

        return super().get_serializer_class()

    @action(
        methods=[
            "post",
        ],
        detail=True,
        url_name="download-attachment",
        url_path="download-attachment",
    )
    def download_attachment(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attachment = OrderItemAttachment.objects.get(pk=serializer.data["attachment"])
        url = create_presigned_url(
            settings.AWS_STORAGE_BUCKET_NAME,
            f"media/{request.tenant.schema_name}/{attachment.attachment.name}",
        )

        if url:
            return Response({"url": url}, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    queryset = Order.objects.all()
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticated,
        IsStoreStaff,
    )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrderDetailSerializer

        return super().get_serializer_class()


class RatingViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = RatingSerializer
    queryset = Rating.objects.all()


class OrderItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderItemSerializer
    queryset = OrderItem.objects.all()
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)
    filterset_class = OrderItemFilter

    @method_decorator([cache_page(60 * 5), vary_on_headers("Host")])
    @action(
        methods=[
            "get",
        ],
        detail=False,
    )
    def statistics(self, request, *args, **kwargs):
        response = {
            "all": OrderItem.objects.all().count(),
            "new": OrderItem.objects.filter(
                status=OrderItem.Status.IN_PROGRESS
            ).count(),
            "overdue": OrderItem.objects.filter(
                Q(status=OrderItem.Status.PENDING)
                | Q(status=OrderItem.Status.IN_PROGRESS),
                order__status=Order.Status.PAID,
                due_date__lt=timezone.now(),
            ).count(),
            "complete": OrderItem.objects.filter(
                status=OrderItem.Status.COMPLETE
            ).count(),
        }

        return Response(response, status=status.HTTP_200_OK)

    def finalize_response(self, request, response, *args, **kwargs):
        if self.action == "statistics":
            patch_cache_control(response, public=True, no_cache=True)

        return super().finalize_response(request, response, *args, **kwargs)


class OrderItemPaperViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderItemPaperSerializer
    queryset = OrderItemPaper.objects.all()
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)

    @action(
        methods=[
            "get",
        ],
        detail=True,
        url_name="download",
        url_path="download",
        permission_classes=[
            IsSubscriptionActive,
            IsAuthenticated,
        ],
    )
    def download(self, request, *args, **kwargs):
        paper = self.get_object()

        if (
            request.user.profile_type == User.ProfileType.CUSTOMER
            and paper.order_item.order.owner != request.user
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        url = create_presigned_url(
            settings.AWS_STORAGE_BUCKET_NAME,
            f"media/{request.tenant.schema_name}/{paper.paper.name}",
        )

        if url:
            return Response({"url": url}, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
