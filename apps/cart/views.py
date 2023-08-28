"""serializers"""

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.utils import create_presigned_url
from apps.coupon.utils import is_coupon_valid

from .models import Attachment, Cart, Item
from .serializers import (
    AttachmentSerializer,
    CartItemRemoveSerializer,
    CartItemSerializer,
    CartSerializer,
    DownloadAttachmentSerializer,
)

# pylint: disable=too-many-ancestors


class BaseGenericViewSet(viewsets.GenericViewSet):
    """Base genric viewset for the module"""

    def perform_create(self, serializer):
        """Override perform_create"""
        serializer.save(created_by=self.request.user)


class CartViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, BaseGenericViewSet):
    """Cart model viewset"""

    serializer_class = CartSerializer
    queryset = Cart.objects.none()

    def list(self, request, *args, **kwargs):
        cart = self.get_queryset().first()

        if not cart:
            return Response({"cart": None})

        serializer = CartSerializer(self.get_queryset().first())
        return Response({"cart": serializer.data})

    def get_queryset(self):
        """Override queryset to return only cart object owned by user"""
        return Cart.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        """Get serializer class that matches current action"""
        if self.action == "remove":
            return CartItemRemoveSerializer

        return super().get_serializer_class()

    @action(
        methods=[
            "post",
        ],
        detail=True,
    )
    def remove(self, request, *args, **kwargs):
        """Remove cart item action"""
        cart = self.get_object()
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        item = cart.items.get(pk=serializer.data["item"])
        item.delete()

        # re-evaluate coupon validity. If valid keep coupon, else
        # remove coupon. Coupon can e.g become valid if cart subtotal
        # does not meet the minimum amount required for coupon
        if cart.coupon and not is_coupon_valid(cart.coupon, cart.owner):
            cart.coupon = None
            cart.save()

        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(
        methods=[
            "get",
        ],
        detail=True,
    )
    def clear(self, request, *args, **kwargs):
        """Clear cart action"""
        cart = self.get_object()
        cart.items.all().delete()
        cart.coupon = None
        cart.save()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


class CartItemViewset(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, BaseGenericViewSet
):
    """Item model viewset"""

    serializer_class = CartItemSerializer
    queryset = Item.objects.none()

    def get_queryset(self):
        """Override queryset to return only cart object owned by user"""
        return Item.objects.filter(cart__owner=self.request.user)

    def get_serializer_class(self):
        """Get serializer class that matches current action"""
        if self.action == "download_attachment":
            return DownloadAttachmentSerializer

        return super().get_serializer_class()

    @action(
        methods=[
            "post",
        ],
        detail=True,
        url_name="download-attachment",
    )
    def download_attachment(self, request, *args, **kwargs):
        """Download cart item attachment"""
        item = self.get_object()
        serializer_class = self.get_serializer_class()
        request.data.update({"item": item.id})
        serializer = serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        attachment = Attachment.objects.get(pk=serializer.data["attachment"])
        url = create_presigned_url(
            settings.AWS_STORAGE_BUCKET_NAME,
            f"media/{request.tenant.schema_name}/{attachment.attachment.name}",
        )

        if url:
            return Response({"url": url}, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AttachmentViewset(
    mixins.CreateModelMixin, mixins.DestroyModelMixin, BaseGenericViewSet
):
    """Attachment model view set"""

    serializer_class = AttachmentSerializer
    queryset = Attachment.objects.none()

    def get_queryset(self):
        """Return only attachments owned by user"""
        return Attachment.objects.filter(cart_item__cart__owner=self.request.user)
