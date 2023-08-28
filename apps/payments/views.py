"""views"""
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.common.pagination import SmallResultsSetPagination

from .filters import PaymentMethodFiter
from .models import Payment, PaymentMethod
from .serializers import PaymentMethodSerializer, PaymentSerializer


class PaymentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Payment model viewset"""

    serializer_class = PaymentSerializer
    queryset = Payment.objects.none()
    pagination_class = SmallResultsSetPagination

    def get_queryset(self):
        """Return only payments belonging to user"""
        return Payment.objects.filter(order__owner=self.request.user)


class PaymentMethodViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PaymentMethodSerializer
    queryset = PaymentMethod.objects.all()
    pagination_class = None
    filterset_class = PaymentMethodFiter
    permission_classes = (AllowAny,)
