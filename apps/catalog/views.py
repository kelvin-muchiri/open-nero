"""views"""
from django.conf import settings
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterTypeService,
)
from apps.common.mixins import PublicCacheListModelMixin, UncachedListActionMixin
from apps.common.permissions import (
    IsStoreStaff,
    IsStoreStaffOrReadOnly,
    IsSubscriptionActive,
)
from apps.coupon.utils import calculate_discount, get_best_match_coupon

from .filters import DeadlineFilter, LevelFilter, PaperFilter, ServiceFilter
from .serializers import (
    CalculatorSerializer,
    CourseSerializer,
    CreatePricesSerializer,
    DeadlineExistsSerializer,
    DeadlineSerializer,
    DeletePricesSerializer,
    FormatSerializer,
    LevelSerializer,
    PaperSerializer,
    ServiceSerializer,
    WriterTypeServiceListSerializer,
    WriterTypeServiceSerializer,
)
from .utils import get_service, get_writer_type_service

CACHE_TTL = getattr(settings, "CACHE_TTL", DEFAULT_TIMEOUT)


class LevelViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Level model viewset"""

    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)
    filterset_class = LevelFilter
    pagination_class = None


class CourseViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    """Course model viewset"""

    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None


class FormatViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    """Format model viewset"""

    queryset = Format.objects.all()
    serializer_class = FormatSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None


class DeadlineViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Deadline model viewset"""

    queryset = Deadline.objects.all()
    serializer_class = DeadlineSerializer
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)
    filterset_class = DeadlineFilter
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "exists":
            return DeadlineExistsSerializer

        return super().get_serializer_class()

    @action(detail=False, methods=["post"])
    def exists(self, request):
        serializer = self.get_serializer_class()(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        value = serializer.data.get("value")
        deadline_type = serializer.data.get("deadline_type")
        response = {"exists": False}

        if (Deadline.objects.filter(value=value, deadline_type=deadline_type)).exists():
            response.update({"exists": True})

        return Response(response, status=status.HTTP_200_OK)


class PaperViewSet(
    PublicCacheListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UncachedListActionMixin,
    viewsets.GenericViewSet,
):
    """Paper model viewset"""

    queryset = Paper.objects.all()
    serializer_class = PaperSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticatedOrReadOnly,
        IsStoreStaffOrReadOnly,
    )
    pagination_class = None
    filterset_class = PaperFilter


class CalculatorAPIView(APIView):
    """Calculator view"""

    permission_classes = (
        IsSubscriptionActive,
        AllowAny,
    )
    serializer_class = CalculatorSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        service = get_service(
            serializer.data["paper"],
            serializer.data["deadline"],
            serializer.data.get("level"),
        )
        subtotal = round(service.amount * serializer.data["pages"], 2)
        user = None

        if request.user.is_authenticated:
            user = request.user

        # If writer_type was specified, add total writer price to
        # total price
        if serializer.data.get("writer_type"):
            writer_type_service = get_writer_type_service(
                serializer.data["paper"],
                serializer.data["deadline"],
                serializer.data["writer_type"],
                serializer.data.get("level"),
            )

            if writer_type_service:
                subtotal += round(
                    writer_type_service.amount * serializer.data["pages"], 2
                )

        total = subtotal
        coupon_code = None
        coupon = get_best_match_coupon(subtotal, user=user)

        if coupon:
            total = round(subtotal - calculate_discount(coupon, subtotal), 2)
            coupon_code = coupon.code

        response = {
            "subtotal": str(subtotal),
            "total": str(total),
            "coupon_code": coupon_code,
        }

        return Response(response, status=status.HTTP_200_OK)


class WriterTypeServiceAPIView(APIView):
    """Get writer types by service"""

    permission_classes = (
        IsSubscriptionActive,
        AllowAny,
    )
    serializer_class = WriterTypeServiceSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        service = get_service(
            serializer.data["paper"],
            serializer.data["deadline"],
            serializer.data.get("level"),
        )
        if not service:
            return Response([], status=status.HTTP_200_OK)

        qs = WriterTypeService.objects.filter(service=service).order_by(
            "writer_type__sort_order"
        )

        return Response(
            WriterTypeServiceListSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )


class ServiceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = (IsSubscriptionActive, IsAuthenticated, IsStoreStaff)
    filterset_class = ServiceFilter
    pagination_class = None

    def get_serializer_class(self):
        if self.action == "create_bulk":
            return CreatePricesSerializer

        if self.action == "delete_bulk":
            return DeletePricesSerializer

        return super().get_serializer_class()

    @action(
        detail=False, methods=["post"], url_path="create-bulk", url_name="create-bulk"
    )
    def create_bulk(self, request):
        serializer = self.get_serializer_class()(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)

    @action(
        detail=False, methods=["post"], url_path="delete-bulk", url_name="delete-bulk"
    )
    def delete_bulk(self, request):
        serializer = self.get_serializer_class()(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)
