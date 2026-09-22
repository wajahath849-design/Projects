from django.contrib import admin

from .models import AuditRun, Dataset, MetricDefinition


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "row_count", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(MetricDefinition)
class MetricDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "dataset",
        "numerator_column",
        "denominator_column",
        "created_at",
    )
    search_fields = ("name", "claim")


@admin.register(AuditRun)
class AuditRunAdmin(admin.ModelAdmin):
    list_display = (
        "metric",
        "status",
        "confidence_score",
        "created_at",
        "completed_at",
    )
    list_filter = ("status",)
