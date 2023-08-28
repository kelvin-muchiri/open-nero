from django.contrib import admin

from apps.catalog.models import (
    Course,
    Deadline,
    Format,
    Level,
    Paper,
    Service,
    WriterType,
    WriterTypeService,
)


class LevelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
    )
    search_fields = ("name",)


class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
    )
    search_fields = ("name",)


class DeadlineAdmin(admin.ModelAdmin):
    list_display = ("value", "deadline_type", "sort_order")
    search_fields = ("value", "deadline_type")
    list_filter = ("deadline_type",)


class PaperAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
    )
    search_fields = ("name",)


class FormatAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
    )
    search_fields = ("name",)


class WriterTypeServiceInline(admin.StackedInline):
    model = WriterTypeService
    extra = 2


class ServiceAdmin(admin.ModelAdmin):
    list_display = ("paper", "level", "deadline", "amount")
    search_fields = ("paper__name", "level__name", "deadline__value", "amount")
    inlines = (WriterTypeServiceInline,)
    ordering = (
        "paper__name",
        "level__sort_order",
        "level__name",
        "deadline__type",
        "deadline__value",
    )


class WriterTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
    )
    search_fields = ("name",)


admin.site.register(Level, LevelAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Deadline, DeadlineAdmin)
admin.site.register(Paper, PaperAdmin)
admin.site.register(Format, FormatAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(WriterType, WriterTypeAdmin)
