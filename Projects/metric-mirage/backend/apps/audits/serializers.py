from rest_framework import serializers

from .models import AuditRun, Dataset, MetricDefinition


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = (
            "id",
            "name",
            "source_file",
            "row_count",
            "column_schema",
            "preview",
            "created_at",
        )
        read_only_fields = ("row_count", "column_schema", "preview", "created_at")

    def validate_source_file(self, value):
        if not value.name.lower().endswith(".csv"):
            raise serializers.ValidationError(
                "Only CSV files are supported in this release."
            )
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("The maximum upload size is 10 MB.")
        return value


class MetricDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricDefinition
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")

    def validate(self, attrs):
        dataset = attrs["dataset"]
        available = {item["name"] for item in dataset.column_schema}
        requested = {
            attrs["numerator_column"],
            attrs["denominator_column"],
            attrs["date_column"],
            *attrs.get("segment_columns", []),
        }
        missing = sorted(requested - available)
        if missing:
            raise serializers.ValidationError(
                {"columns": f"Unknown columns: {', '.join(missing)}"}
            )
        return attrs


class AuditRunSerializer(serializers.ModelSerializer):
    metric_name = serializers.CharField(source="metric.name", read_only=True)
    claim = serializers.CharField(source="metric.claim", read_only=True)

    class Meta:
        model = AuditRun
        fields = (
            "id",
            "metric",
            "metric_name",
            "claim",
            "status",
            "confidence_score",
            "headline",
            "findings",
            "stress_tests",
            "result",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        )
        read_only_fields = (
            "status",
            "confidence_score",
            "headline",
            "findings",
            "stress_tests",
            "result",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        )
