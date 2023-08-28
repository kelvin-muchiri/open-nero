from django.db import transaction
from rest_framework import serializers

from .models import FooterGroup, FooterLink, Image, NavbarLink, Page
from .utils import is_descendant


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = (
            "id",
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "blocks",
        )
        read_only_fields = ("blocks",)


class DraftPageSerializer(serializers.ModelSerializer):
    publish = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Page
        fields = (
            "id",
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "is_public",
            "publish",
            "is_active",
            "metadata",
            "blocks",
            "draft",
        )
        read_only_fields = ("blocks",)

    def create(self, validated_data):
        publish = validated_data.pop("publish", False)
        instance = super().create(validated_data)

        if publish:
            instance.publish()

        return instance

    def update(self, instance, validated_data):
        publish = validated_data.pop("publish", False)
        instance = super().update(instance, validated_data)

        if publish:
            instance.publish()

        return instance


class ImageSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.file_name

        return data

    class Meta:
        model = Image
        fields = (
            "id",
            "image",
        )


class SlugUniqueSerializer(serializers.Serializer):
    slug = serializers.SlugField()


class PageInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = (
            "id",
            "title",
            "slug",
        )


class NavbarLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = NavbarLink
        fields = (
            "id",
            "title",
            "link_to",
            "parent",
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        if validated_data.get("parent") and instance.parent != validated_data.get(
            "parent"
        ):
            if validated_data.get("parent") == instance:
                raise serializers.ValidationError("A link's parent cannot be itself")

            # we ensure a descendant link cannot be set as parent of link
            # being updated
            if is_descendant(validated_data.get("parent"), instance):
                raise serializers.ValidationError(
                    "A descendant link cannot be set as parent"
                )

        return super().update(instance, validated_data)


class NavbarLinkInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = NavbarLink
        fields = (
            "id",
            "title",
        )


class NavbarLinkDetailSerializer(serializers.ModelSerializer):
    link_to = PageInlineSerializer(read_only=True)
    children = serializers.SerializerMethodField()
    parent = NavbarLinkInlineSerializer(read_only=True)

    def get_children(self, obj):
        return NavbarLinkDetailSerializer(obj.children.all(), many=True).data

    class Meta:
        model = NavbarLink
        fields = (
            "id",
            "title",
            "link_to",
            "parent",
            "children",
        )


class FooterGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterGroup
        fields = (
            "id",
            "title",
            "sort_order",
        )


class FooterGroupInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterGroup
        fields = (
            "id",
            "title",
        )


class FooterLinkInlineSerializer(serializers.ModelSerializer):
    link_to = PageInlineSerializer(read_only=True)

    class Meta:
        model = FooterLink
        fields = (
            "id",
            "title",
            "link_to",
        )


class FooterGroupDetailSerializer(serializers.ModelSerializer):
    links = FooterLinkInlineSerializer(read_only=True, many=True)

    class Meta:
        model = FooterGroup
        fields = (
            "id",
            "title",
            "links",
            "sort_order",
        )


class FooterLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterLink
        fields = (
            "id",
            "title",
            "link_to",
            "group",
            "sort_order",
        )


class FooterLinkDetailSerializer(serializers.ModelSerializer):
    link_to = PageInlineSerializer(read_only=True)
    group = FooterGroupInlineSerializer(read_only=True)

    class Meta:
        model = FooterLink
        fields = (
            "id",
            "title",
            "link_to",
            "group",
            "sort_order",
        )
