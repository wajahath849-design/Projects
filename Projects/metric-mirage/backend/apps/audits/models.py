from django.conf import settings
from django.db import models


class Dataset(models.Model):
    name = models.CharField(max_length=160)
    source_file = models.FileField(upload_to="datasets/%Y/%m/")
    row_count = models.PositiveIntegerField(default=0)
    column_schema = models.JSONField(default=list)
    preview = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="metric_mirage_datasets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class MetricDefinition(models.Model):
    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name="metrics"
    )
    name = models.CharField(max_length=120)
    claim = models.TextField()
    numerator_column = models.CharField(max_length=120)
    denominator_column = models.CharField(max_length=120)
    date_column = models.CharField(max_length=120)
    segment_columns = models.JSONField(default=list)
    split_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="metric_mirage_metrics",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class AuditRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    metric = models.ForeignKey(
        MetricDefinition, on_delete=models.CASCADE, related_name="audit_runs"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    confidence_score = models.PositiveSmallIntegerField(default=0)
    headline = models.JSONField(default=dict)
    findings = models.JSONField(default=list)
    stress_tests = models.JSONField(default=list)
    result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.metric.name} — {self.get_status_display()}"
