"""serializers"""
from django.db import transaction
from rest_framework import serializers

from apps.blog.utils import is_category_descendant

from .models import Category, Image, Post, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            "id",
            "name",
            "slug",
            "description",
        )


class TagListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = (
            "id",
            "name",
            "slug",
        )


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "parent",
            "description",
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        if validated_data.get("parent") and instance.parent != validated_data.get(
            "parent"
        ):

            if validated_data.get("parent") == instance:
                raise serializers.ValidationError("Parent cannot be self")

            # we ensure a descendant category cannot be set as parent
            if is_category_descendant(validated_data.get("parent"), instance):
                raise serializers.ValidationError(
                    "A descendant category cannot be set as parent"
                )

        return super().update(instance, validated_data)


class CategoryInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
        )


class CategoryListSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    def get_children(self, obj):
        return CategoryListSerializer(obj.children.all(), many=True).data

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "children",
        )


class CategoryDetailSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    parent = CategoryInlineSerializer(read_only=True)

    def get_children(self, obj):
        return CategoryInlineSerializer(obj.children.all(), many=True).data

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "children",
        )


class ImageInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = (
            "id",
            "image",
        )


class PostListSerializer(serializers.ModelSerializer):
    featured_image = ImageInlineSerializer()

    class Meta:
        model = Post
        fields = (
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "featured_image",
            "is_published",
        )


class PostDetailSerializer(serializers.ModelSerializer):
    """Post full information serializer"""

    tags = TagListSerializer(many=True)
    categories = CategoryInlineSerializer(many=True)
    previous_post = serializers.SerializerMethodField()
    next_post = serializers.SerializerMethodField()
    featured_image = ImageInlineSerializer()

    def get_previous_post(self, obj):
        """Get previous post"""
        if obj.previous_post:
            return {"title": obj.previous_post.title, "slug": obj.previous_post.slug}

        return None

    def get_next_post(self, obj):
        """Get next post"""
        if obj.next_post:
            return {"title": obj.next_post.title, "slug": obj.next_post.slug}

        return None

    class Meta:
        model = Post
        fields = (
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "featured_image",
            "is_published",
            "is_featured",
            "is_pinned",
            "tags",
            "categories",
            "previous_post",
            "next_post",
            "content",
            "draft",
        )


class PostSerializer(serializers.ModelSerializer):
    publish = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Post
        fields = (
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "featured_image",
            "is_published",
            "is_featured",
            "is_pinned",
            "categories",
            "tags",
            "content",
            "draft",
            "publish",
        )
        read_only_fields = ("content",)

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


class SlugUniqueSerializer(serializers.Serializer):
    slug = serializers.SlugField()


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
