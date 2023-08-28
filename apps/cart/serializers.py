from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.catalog.serializers import (
    CourseInlineSerializer,
    DeadlineInlineSerializer,
    FormatInlineSerializer,
    LevelInlineSerializer,
    PaperInlineSerializer,
    WriterTypeInlineSerializer,
)
from apps.catalog.utils import get_service, get_writer_type_service
from apps.common.utils import check_model_or_throw_validation_error
from apps.coupon.serializers import CouponInlineSerializer
from apps.coupon.utils import calculate_discount, get_best_match_coupon

from .models import Attachment, Cart, Item


class AttachmentInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ("id", "filename", "comment")


class CartItemSerializer(serializers.ModelSerializer):
    update_quantity = serializers.BooleanField(default=True, write_only=True)
    attachments = AttachmentInlineSerializer(many=True, read_only=True)

    def to_internal_value(self, data):
        if "language" in data and data["language"] == "":
            del data["language"]

        if "pages" in data and data["pages"] == "":
            del data["pages"]

        if "references" in data and data["references"] == "":
            del data["references"]

        if "quantity" in data and data["quantity"] == "":
            del data["quantity"]

        return super().to_internal_value(data)

    def validate(self, attrs):
        level_id = None

        if attrs.get("level"):
            level_id = attrs.get("level").id

        if attrs.get("paper") and attrs.get("deadline"):
            if not get_service(
                attrs.get("paper").id, attrs.get("deadline").id, level_id
            ):
                raise serializers.ValidationError(
                    _("Apologies, this service is currently unavailable")
                )

            if attrs.get("writer_type") and not get_writer_type_service(
                attrs["paper"].id,
                attrs["deadline"].id,
                attrs["writer_type"].id,
                level_id,
            ):

                raise serializers.ValidationError(
                    _("Type of writer service is currently unavailable")
                )

        return super().validate(attrs)

    @transaction.atomic
    def update(self, instance, validated_data):
        quantity = validated_data.pop("quantity", None)
        update_quantity = validated_data.pop("update_quantity", True)
        level = validated_data.get("level", instance.level)
        deadline = validated_data.get("deadline", instance.deadline)
        paper = validated_data.get("paper", instance.paper)
        writer_type = validated_data.get("writer_type", instance.writer_type)

        level_id = None

        if level:
            level_id = level.id

        service = get_service(paper.id, deadline.id, level_id)

        if not service:
            raise serializers.ValidationError(
                _("Apologies, this service is currently unavailable")
            )

        instance.page_price = service.amount

        if quantity:
            if update_quantity:
                instance.quantity = quantity

            else:
                instance.quantity += quantity

        if writer_type:
            writer_type_service = get_writer_type_service(
                paper.id, deadline.id, writer_type.id, level_id
            )

            if not writer_type_service:
                raise serializers.ValidationError(
                    _("Type of writer service is currently unavailable")
                )

            instance.writer_type_price = writer_type_service.amount

        else:
            instance.writer_type_price = None

        for (key, value) in validated_data.items():
            setattr(instance, key, value)

        instance.save()

        return instance

    class Meta:
        model = Item
        fields = (
            "id",
            "topic",
            "level",
            "course",
            "paper",
            "paper_format",
            "deadline",
            "language",
            "pages",
            "references",
            "comment",
            "quantity",
            "price",
            "total_price",
            "update_quantity",
            "writer_type",
            "attachments",
        )
        read_only_fields = (
            "price",
            "total_price",
        )


class CartItemInlineSerializer(serializers.ModelSerializer):
    level = LevelInlineSerializer(read_only=True)
    course = CourseInlineSerializer(read_only=True)
    paper = PaperInlineSerializer(read_only=True)
    paper_format = FormatInlineSerializer(read_only=True)
    deadline = DeadlineInlineSerializer(read_only=True)
    language = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    writer_type = WriterTypeInlineSerializer(read_only=True)
    attachments = AttachmentInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Item
        fields = (
            "id",
            "topic",
            "level",
            "course",
            "paper",
            "paper_format",
            "deadline",
            "language",
            "pages",
            "references",
            "comment",
            "quantity",
            "price",
            "total_price",
            "writer_type",
            "attachments",
        )

    def get_language(self, obj):
        return {"id": obj.language, "name": obj.get_language_display()}

    def get_price(self, obj):
        return str(obj.price)

    def get_total_price(self, obj):
        return str(obj.total_price)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, allow_empty=False)
    coupon = CouponInlineSerializer(read_only=True)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        cart, _ = Cart.objects.get_or_create(owner=self.context["request"].user)

        for item_data in items_data:
            quantity = item_data.pop("quantity", 1)
            update_quantity = item_data.pop("update_quantity")
            level = item_data.get("level")
            deadline = item_data.get("deadline")
            paper = item_data.get("paper")
            writer_type = item_data.get("writer_type")
            level_id = None

            if level:
                level_id = level.id

            service = get_service(paper.id, deadline.id, level_id)
            defaults = {
                "page_price": service.amount,
            }

            if writer_type:
                writer_type_service = get_writer_type_service(
                    paper.id, deadline.id, writer_type.id, level_id
                )
                defaults.update({"writer_type_price": writer_type_service.amount})

            item, _ = Item.objects.get_or_create(
                **item_data, cart=cart, defaults=defaults
            )

            if update_quantity:
                item.quantity = quantity

            else:
                item.quantity += quantity

            item.save()

        return cart

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["items"] = CartItemInlineSerializer(
            instance.items.all(), many=True
        ).data
        representation["subtotal"] = f"{instance.subtotal}"
        representation["total"] = f"{instance.total}"
        representation["discount"] = f"{instance.discount}"
        representation["best_match_coupon"] = None
        coupon = get_best_match_coupon(instance.subtotal, instance.owner)

        if coupon:
            representation["best_match_coupon"] = {
                "code": coupon.code,
                "discount": f"{calculate_discount(coupon, instance.subtotal)}",
            }

        return representation

    class Meta:
        model = Cart
        fields = (
            "id",
            "subtotal",
            "total",
            "discount",
            "coupon",
            "items",
        )


class CartItemRemoveSerializer(serializers.Serializer):
    item = serializers.UUIDField()

    def validate_item(self, item_id):
        return check_model_or_throw_validation_error(Item, item_id, "id")


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ("id", "cart_item", "attachment", "comment")

    def to_representation(self, instance):
        """Override to_representation to customize serialization"""
        return {
            "id": str(instance.id),
            "cart_item": str(instance.cart_item),
            "filename": instance.filename,
            "comment": instance.comment,
        }

    def validate(self, attrs):
        # Make sure max number of attachments for item does not exceed 6
        cart_item = attrs.get("cart_item")

        if cart_item.attachments.count() >= settings.ORDER_ATTACHMENT_MAX_FILES:
            raise serializers.ValidationError(
                _(
                    f"The maximum number of attachments ({settings.ORDER_ATTACHMENT_MAX_FILES}) for this item has been exceeded"
                )
            )

        return super().validate(attrs)


class DownloadAttachmentSerializer(serializers.Serializer):
    attachment = serializers.UUIDField()
    item = serializers.UUIDField()

    def validate_attachment(self, attachment_id):
        return check_model_or_throw_validation_error(Attachment, attachment_id, "id")

    def validate_item(self, item_id):
        return check_model_or_throw_validation_error(Item, item_id, "id")

    def validate(self, attrs):
        attachment = Attachment.objects.get(pk=attrs["attachment"])
        item = Item.objects.get(pk=attrs["item"])

        if attachment.cart_item != item:
            raise serializers.ValidationError(_("Attachment does not belong to item"))

        return super().validate(attrs)
