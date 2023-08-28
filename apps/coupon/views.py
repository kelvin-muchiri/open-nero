"""Views"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.cart.models import Cart
from apps.common.permissions import IsStoreStaff, IsSubscriptionActive

from .models import Coupon
from .serializers import (
    CodeUniqueSerializer,
    CouponApplicationSerializer,
    CouponSerializer,
)
from .utils import calculate_discount


class CouponApplicationAPIView(APIView):
    """Apply coupon code"""

    serializer_class = CouponApplicationSerializer

    def post(self, request, *args, **kwargs):
        """Method POST"""
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        coupon = Coupon.objects.get(code=serializer.data["coupon_code"])
        cart = Cart.objects.get(pk=serializer.data["cart_id"])
        discount = calculate_discount(coupon, cart.subtotal)
        cart.coupon = coupon
        cart.save()
        response = {
            "discount": f"{discount}",
        }
        return Response(response, status=status.HTTP_200_OK)


class CouponViewSet(ModelViewSet):
    """Level model viewset"""

    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = (
        IsSubscriptionActive,
        IsAuthenticated,
        IsStoreStaff,
    )

    @action(
        detail=False, url_name="code-unique", url_path="code-unique", methods=["post"]
    )
    def slug_unique_create(self, request, *args, **kwargs):
        """Check if code is unique when creating page"""
        serializer = CodeUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        code = serializer.data.get("code")
        response = {"is_unique": True}

        if Coupon.objects.filter(code=code).exists():
            response.update({"is_unique": False})

        return Response(response)

    @action(
        detail=True, url_name="code-unique", url_path="code-unique", methods=["post"]
    )
    def slug_unique_update(self, request, *args, **kwargs):
        """Check if code is unique when updating page"""
        current = self.get_object()
        serializer = CodeUniqueSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        code = serializer.data.get("code")
        response = {"is_unique": True}

        if Coupon.objects.filter(code=code).exclude(pk=current.pk).exists():
            response.update({"is_unique": False})

        return Response(response)
