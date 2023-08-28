"""serializers"""
from rest_framework import serializers

from apps.common.utils import check_model_or_throw_validation_error

from .models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterType,
    WriterTypeService,
)
from .utils import get_service, get_writer_type_service


class LevelSerializer(serializers.ModelSerializer):
    """Default model Level serializer"""

    class Meta:
        model = Level
        fields = (
            "id",
            "name",
            "sort_order",
        )


class LevelInlineSerializer(serializers.ModelSerializer):
    """Serialzer for nesting Level objects within other serializers"""

    class Meta:
        model = Level
        fields = (
            "id",
            "name",
        )


class CourseSerializer(serializers.ModelSerializer):
    """Default serializer for Course model"""

    class Meta:
        model = Course
        fields = (
            "id",
            "name",
            "sort_order",
        )


class CourseInlineSerializer(serializers.ModelSerializer):
    """Serializer for nesting Course objects within other serializers"""

    class Meta:
        model = Course
        fields = (
            "id",
            "name",
        )


class FormatSerializer(serializers.ModelSerializer):
    """Default serializer for model Format"""

    class Meta:
        model = Format
        fields = (
            "id",
            "name",
            "sort_order",
        )


class FormatInlineSerializer(serializers.ModelSerializer):
    """Serializer for nesting Format objects within other serializers"""

    class Meta:
        model = Format
        fields = (
            "id",
            "name",
        )


class DeadlineSerializer(serializers.ModelSerializer):
    """Default serializer for model Deadline"""

    class Meta:
        model = Deadline
        fields = (
            "id",
            "full_name",
            "value",
            "deadline_type",
            "sort_order",
        )


class DeadlineInlineSerializer(serializers.ModelSerializer):
    """Serializer for nesting Deadline objects within other serializers"""

    class Meta:
        model = Deadline
        fields = (
            "id",
            "full_name",
        )


class DeadlineExistsSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    deadline_type = serializers.ChoiceField(choices=Deadline.DeadlineType)


class PaperInlineSerializer(serializers.ModelSerializer):
    """Serializer for nesting Paper objects within other serializers"""

    class Meta:
        model = Paper
        fields = (
            "id",
            "name",
        )


class PaperSerializer(serializers.ModelSerializer):
    levels = serializers.SerializerMethodField()
    deadlines = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = (
            "id",
            "name",
            "sort_order",
            "levels",
            "deadlines",
        )

    def get_levels(self, obj):
        """Get academic levels for paper

        For each academic level return the deadlines that match paper
        """
        levels = Level.objects.filter(services__paper=obj).distinct()
        output = []

        # for each level get the deadlines
        for level in levels:
            deadlines = Deadline.objects.filter(
                services__paper=obj, services__level=level
            ).distinct()
            serialized_level = LevelInlineSerializer(level).data
            serialized_level["deadlines"] = DeadlineInlineSerializer(
                deadlines, many=True
            ).data
            output.append(serialized_level)

        return output

    def get_deadlines(self, obj):
        """Get deadlines for paper

        If levels list is empty, return the deadlines, else the
        deadlines that should be referenced are the ones that associated
        with a level
        """
        if Level.objects.filter(services__paper=obj).exists():
            return []

        deadlines = Deadline.objects.filter(services__paper=obj).distinct()
        return DeadlineInlineSerializer(deadlines, many=True).data


class CalculatorSerializer(serializers.Serializer):
    """Calculator serializer"""

    level = serializers.UUIDField(required=False)
    deadline = serializers.UUIDField()
    paper = serializers.UUIDField()
    writer_type = serializers.UUIDField(required=False)
    pages = serializers.IntegerField(min_value=1, max_value=1000)

    def to_internal_value(self, data):
        if "level" in data and not data["level"]:
            del data["level"]

        if "writer_type" in data and not data["writer_type"]:
            del data["writer_type"]

        return super().to_internal_value(data)

    def validate_level(self, level_id):
        """Validate level field"""
        return check_model_or_throw_validation_error(Level, level_id, "id")

    def validate_deadline(self, deadline_id):
        """Validate deadline field"""
        return check_model_or_throw_validation_error(Deadline, deadline_id, "id")

    def validate_paper(self, paper_id):
        """Validate paper field"""
        return check_model_or_throw_validation_error(Paper, paper_id, "id")

    def validate_writer_type(self, writer_type_id):
        """Validate writer_type field"""
        return check_model_or_throw_validation_error(WriterType, writer_type_id, "id")

    def validate(self, attrs):
        if not get_service(attrs["paper"], attrs["deadline"], attrs.get("level")):
            raise serializers.ValidationError("Invalid service", code="invalid_service")

        if attrs.get("writer_type") and not get_writer_type_service(
            attrs["paper"],
            attrs["deadline"],
            attrs["writer_type"],
            attrs.get("level"),
        ):
            raise serializers.ValidationError("Invalid service", code="invalid_service")

        return super().validate(attrs)


class WriterTypeSerializer(serializers.ModelSerializer):
    """Default serializer for model WriteType"""

    class Meta:
        model = WriterType
        fields = (
            "id",
            "name",
            "description",
        )


class WriterTypeInlineSerializer(serializers.ModelSerializer):
    """Serializer for nesting WriterType objects within other serializers"""

    class Meta:
        model = WriterType
        fields = (
            "id",
            "name",
            "description",
        )


class WriterTypeTagListField(serializers.RelatedField):
    def to_representation(self, value):
        return value.title


class WriterTypeListInlineSerializer(serializers.ModelSerializer):
    tags = WriterTypeTagListField(many=True, read_only=True)

    class Meta:
        model = WriterType
        fields = (
            "id",
            "name",
            "description",
            "tags",
        )


class WriterTypeServiceListSerializer(serializers.ModelSerializer):
    writer_type = WriterTypeListInlineSerializer()

    class Meta:
        model = WriterTypeService
        fields = (
            "writer_type",
            "amount",
        )


class WriterTypeServiceSerializer(serializers.Serializer):
    level = serializers.UUIDField(required=False)
    paper = serializers.UUIDField()
    deadline = serializers.UUIDField()

    def to_internal_value(self, data):
        if "level" in data and not data["level"]:
            del data["level"]

        return super().to_internal_value(data)

    def validate_level(self, level_id):
        """Validate level"""
        return check_model_or_throw_validation_error(Level, level_id, "id")

    def validate_deadline(self, deadline_id):
        """Validate deadline"""
        return check_model_or_throw_validation_error(Deadline, deadline_id, "id")

    def validate_paper(self, paper_id):
        """Validate paper"""
        return check_model_or_throw_validation_error(Paper, paper_id, "id")


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "level",
            "deadline",
            "paper",
            "amount",
        )


class CreatePricesAmountSerializer(serializers.Serializer):
    level_id = serializers.CharField(required=False, allow_null=True)
    deadline_id = serializers.CharField()
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    def validate_level_id(self, level_id):
        if level_id:
            check_model_or_throw_validation_error(Level, level_id, "id")

        return level_id

    def validate_deadline_id(self, deadline_id):
        return check_model_or_throw_validation_error(Deadline, deadline_id, "id")


class CreatePricesSerializer(serializers.Serializer):
    paper_id = serializers.CharField()
    prices = CreatePricesAmountSerializer(many=True, allow_empty=False)

    def validate_paper_id(self, paper_id):
        check_model_or_throw_validation_error(Paper, paper_id, "id")

        return paper_id

    def save(self, **kwargs):
        prices = self.validated_data.pop("prices")
        paper = Paper.objects.get(id=self.validated_data["paper_id"])

        # delete existing entries first
        Service.objects.filter(paper=paper).delete()

        for price in prices:
            level = None

            if price.get("level_id"):
                level = Level.objects.get(id=price["level_id"])

            deadline = Deadline.objects.get(id=price["deadline_id"])

            Service.objects.create(
                paper=paper, level=level, deadline=deadline, amount=price["amount"]
            )


class DeletePricesSerializer(serializers.Serializer):
    paper_id = serializers.CharField()

    def validate_paper_id(self, paper_id):
        check_model_or_throw_validation_error(Paper, paper_id, "id")

        return paper_id

    def save(self, **kwargs):
        Service.objects.filter(paper__id=self.validated_data["paper_id"]).delete()
