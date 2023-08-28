"""serializers"""
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.cart.models import Cart
from apps.common.utils import check_model_or_throw_validation_error
from apps.orders.models import (
    Order,
    OrderCoupon,
    OrderItem,
    OrderItemAttachment,
    OrderItemPaper,
    Rating,
)
from apps.payments.models import PaymentMethod
from apps.users.serializers import UserInlineSerializer

from .tasks import (
    send_admin_email_new_order,
    send_email_order_item_status,
    send_email_order_received,
)


class RatingInlineSerializer(serializers.ModelSerializer):
    """Rating model inline serializer"""

    class Meta:
        model = Rating
        fields = ("rating", "comment")


class OrderItemPaperInlineSerializer(serializers.ModelSerializer):
    """OrderItemPaper model inline serializer"""

    rating = RatingInlineSerializer()
    file_name = serializers.SerializerMethodField()

    def get_file_name(self, obj):
        return obj.paper.name.split("/")[-1]

    class Meta:
        model = OrderItemPaper
        fields = (
            "id",
            "file_name",
            "comment",
            "rating",
        )


class OrderItemAttachmentInlineSerializer(serializers.ModelSerializer):
    """OrderItemAttachment inline serializer"""

    class Meta:
        model = OrderItemAttachment
        fields = (
            "id",
            "file_path",
            "comment",
        )


class OrderInlineSerializer(serializers.ModelSerializer):
    owner = UserInlineSerializer()

    class Meta:
        model = Order
        fields = (
            "id",
            "owner",
            "status",
        )


class OrderItemSerializer(serializers.ModelSerializer):
    papers = OrderItemPaperInlineSerializer(read_only=True, many=True)
    price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    writer_type_price = serializers.SerializerMethodField()
    attachments = OrderItemAttachmentInlineSerializer(many=True, read_only=True)
    order = OrderInlineSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "order",
            "topic",
            "level",
            "course",
            "paper",
            "paper_format",
            "deadline",
            "language",
            "pages",
            "references",
            "quantity",
            "comment",
            "due_date",
            "status",
            "days_left",
            "price",
            "total_price",
            "writer_type",
            "writer_type_price",
            "is_overdue",
            "created_at",
            "attachments",
            "papers",
        )

    def get_price(self, obj):
        """Get item unit price"""
        return str(obj.price)

    def get_total_price(self, obj):
        """Get item total total"""
        return str(obj.total_price)

    def get_writer_type_price(self, obj):
        """Get price for the type of writer"""
        if not obj.writer_type_price:
            return obj.writer_type_price

        return str(obj.writer_type_price)

    def get_due_date(self, obj):
        """Get item due date"""
        if obj.order.status == Order.Status.UNPAID:
            return None

        return obj.due_date.isoformat().replace("+00:00", "Z")

    @transaction.atomic
    def update(self, instance, validated_data):
        # status is the only editable field
        status_changed = False
        status = validated_data.pop("status")

        if status != instance.status:
            status_changed = True

        instance.status = status
        instance.save()

        if status_changed:
            send_email_order_item_status.delay(
                self.context["request"].tenant.schema_name,
                str(instance.pk),
            )

        return instance


class OrderCouponSerializer(serializers.ModelSerializer):
    """OrderCoupon model serializer"""

    discount = serializers.SerializerMethodField()

    def get_discount(self, obj):
        return str(obj.discount)

    class Meta:
        model = OrderCoupon
        fields = ("code", "discount")


class OrderSerializer(serializers.ModelSerializer):
    owner = UserInlineSerializer()
    earliest_due = serializers.DateTimeField()
    no_of_items = serializers.SerializerMethodField()
    amount_payable = serializers.SerializerMethodField()

    def get_no_of_items(self, obj):
        return obj.items.count()

    def get_amount_payable(self, obj):
        """Get final amount payable"""
        return str(obj.amount_payable)

    class Meta:
        model = Order
        fields = (
            "id",
            "owner",
            "status",
            "is_complete",
            "created_at",
            "earliest_due",
            "amount_payable",
            "no_of_items",
        )


class CustomerOrderSerializer(serializers.ModelSerializer):
    """Order model serializer"""

    cart = serializers.UUIDField(write_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "created_at",
            "items",
            "cart",
        )

    def validate_cart(self, cart_id):
        """Validate field cart"""
        check_model_or_throw_validation_error(Cart, cart_id, "id")
        cart = Cart.objects.get(pk=cart_id)

        if cart.owner != self.context["request"].user:
            raise serializers.ValidationError(_("This cart does not belong to you"))

        return cart_id

    def run_on_commit_callbacks(self, schema_name: str, order_id: int):
        """Run callbacks after the current transaction commits"""
        send_email_order_received.delay(schema_name, order_id)

        if PaymentMethod.objects.filter(
            code=PaymentMethod.Code.INSTRUCTIONS,
            is_active=True,
        ).exists():
            send_admin_email_new_order.delay(schema_name, order_id)

    @transaction.atomic
    def create(self, validated_data):
        cart = Cart.objects.get(pk=validated_data["cart"])
        order = Order.objects.create(owner=cart.owner)

        if cart.coupon and not cart.coupon.is_expired:
            OrderCoupon.objects.create(
                order=order, code=cart.coupon.code, discount=cart.discount
            )

        start_date = timezone.now()

        for item in cart.items.all():
            writer_type = None
            level = None

            if item.writer_type:
                writer_type = item.writer_type.name

            if item.level:
                level = item.level.name

            order_item = OrderItem.objects.create(
                order=order,
                topic=item.topic,
                level=level,
                course=item.course.name,
                paper=item.paper.name,
                paper_format=item.paper_format.name,
                deadline=item.deadline.full_name,
                language=item.get_language_display(),
                pages=item.pages,
                references=item.references,
                comment=item.comment,
                quantity=item.quantity,
                page_price=item.page_price,
                due_date=item.deadline.get_due_date(start_date),
                writer_type=writer_type,
                writer_type_price=item.writer_type_price,
            )
            # For each item create corresponding attachments
            attachments_to_create = []

            for attachment in item.attachments.all():
                attachments_to_create.append(
                    OrderItemAttachment(
                        order_item=order_item,
                        attachment=File(attachment.attachment, attachment.filename),
                        comment=attachment.comment,
                    )
                )

            OrderItemAttachment.objects.bulk_create(attachments_to_create)

        cart.delete()
        transaction.on_commit(
            lambda: self.run_on_commit_callbacks(
                self.context["request"].tenant.schema_name, order.id
            )
        )

        return order


class SelfOrderListSerializer(serializers.ModelSerializer):
    earliest_due = serializers.DateTimeField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "is_complete",
            "created_at",
            "earliest_due",
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    """Order full details serializer"""

    items = OrderItemSerializer(read_only=True, many=True)
    coupon = OrderCouponSerializer(read_only=True)
    earliest_due = serializers.DateTimeField()
    amount_payable = serializers.SerializerMethodField()
    original_amount_payable = serializers.SerializerMethodField()
    owner = UserInlineSerializer()

    class Meta:
        model = Order
        fields = (
            "id",
            "owner",
            "status",
            "is_complete",
            "created_at",
            "earliest_due",
            "coupon",
            "balance",
            "amount_payable",
            "original_amount_payable",
            "items",
        )

    def get_amount_payable(self, obj):
        """Get final amount payable"""
        return str(obj.amount_payable)

    def get_original_amount_payable(self, obj):
        """Get original amount payable"""
        return str(obj.original_amount_payable)


class RatingSerializer(serializers.ModelSerializer):
    """Rating model serializer"""

    class Meta:
        model = Rating
        fields = (
            "paper",
            "rating",
            "comment",
        )


class DownloadAttachmentSerializer(serializers.Serializer):
    """Download order item attachment file serializer"""

    attachment = serializers.UUIDField()

    def validate_attachment(self, attachment_id):
        """Validate attachment field"""
        return check_model_or_throw_validation_error(
            OrderItemAttachment, attachment_id, "id"
        )

    def validate(self, attrs):
        attachment = OrderItemAttachment.objects.get(pk=attrs["attachment"])

        if attachment.order_item.order.owner != self.context["request"].user:
            raise serializers.ValidationError(_("Permission denied"))

        return super().validate(attrs)


class OrderItemPaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemPaper
        fields = (
            "order_item",
            "paper",
            "comment",
        )
        extra_kwargs = {
            "comment": {
                "required": False,
                "allow_blank": True,
            }
        }
