from __future__ import annotations

import io
import json

import pandas as pd
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .demo import build_demo_result
from .engine import AuditInputError, AuditSpec, analyze_dataframe
from .scope import analyze_scoped
from .models import AuditRun, Dataset, MetricDefinition
from .serializers import (
    AuditRunSerializer,
    DatasetSerializer,
    MetricDefinitionSerializer,
)


def _read_csv(source) -> pd.DataFrame:
    try:
        return pd.read_csv(source, dtype=str, keep_default_na=False, na_values=[""])
    except pd.errors.EmptyDataError as exc:
        raise AuditInputError(
            "The CSV is empty. Include column headers and data rows."
        ) from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise AuditInputError(
            "The file could not be read as CSV. Use UTF-8 encoding and consistent comma-separated columns."
        ) from exc


def _schema_for(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "name": str(column),
            "type": str(frame[column].dtype),
            "missing": int(frame[column].isna().sum()),
        }
        for column in frame.columns
    ]


def _run_saved_audit(audit: AuditRun) -> AuditRun:
    audit.status = AuditRun.Status.RUNNING
    audit.started_at = timezone.now()
    audit.error_message = ""
    audit.save(update_fields=["status", "started_at", "error_message"])
    metric = audit.metric
    try:
        frame = _read_csv(metric.dataset.source_file.path)
        result = analyze_dataframe(
            frame,
            AuditSpec(
                metric_name=metric.name,
                claim=metric.claim,
                numerator=metric.numerator_column,
                denominator=metric.denominator_column,
                date_column=metric.date_column,
                segment_columns=metric.segment_columns,
                split_date=metric.split_date,
                source_name=metric.dataset.name,
            ),
        )
        audit.status = AuditRun.Status.COMPLETE
        audit.confidence_score = result["confidence_score"]
        audit.headline = result["headline"]
        audit.findings = result["findings"]
        audit.stress_tests = result["stress_tests"]
        audit.result = result
    except (
        Exception
    ) as exc:  # Stored runs should preserve diagnostic context for the owner.
        audit.status = AuditRun.Status.FAILED
        audit.error_message = str(exc)
    audit.completed_at = timezone.now()
    audit.save()
    return audit


class HealthView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return Response(
            {"status": "ok", "service": "metric-mirage-api", "version": "1.0.0"}
        )


class DemoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(build_demo_result())


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = authenticate(
            username=request.data.get("username"), password=request.data.get("password")
        )
        if not user:
            return Response(
                {"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": {"id": user.id, "username": user.username}}
        )


class AnalyzeUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"detail": "Attach a CSV in the 'file' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > 10 * 1024 * 1024:
            return Response(
                {"detail": "The maximum upload size is 10 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            frame = _read_csv(io.BytesIO(upload.read()))
            segments = [
                value.strip()
                for value in request.data.get("segment_columns", "").split(",")
                if value.strip()
            ]
            if "primary_segment_column" in request.data:
                primary = request.data["primary_segment_column"]
                segments = [primary] if primary else []
            try:
                if "group_columns" in request.data:
                    segments = json.loads(request.data["group_columns"])
                filters = json.loads(request.data.get("filters", "{}"))
            except (ValueError, TypeError) as exc:
                raise AuditInputError("Grouping and filters must contain valid JSON.") from exc
            if not isinstance(segments, list) or any(not isinstance(column, str) for column in segments):
                raise AuditInputError("Grouping must be a list of column names.")
            result = analyze_scoped(
                frame,
                AuditSpec(
                    metric_name=request.data.get("metric_name", "Uploaded metric"),
                    claim=request.data.get(
                        "claim", "The metric improved between periods."
                    ),
                    numerator=request.data.get("numerator_column", "conversions"),
                    denominator=request.data.get("denominator_column", "sessions"),
                    date_column=request.data.get("date_column", "date"),
                    segment_columns=segments,
                    split_date=request.data.get("split_date") or None,
                    source_name=upload.name,
                ),
                filters,
            )
            return Response(result)
        except AuditInputError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.select_related("created_by")
    serializer_class = DatasetSerializer

    def perform_create(self, serializer):
        dataset = serializer.save(created_by=self.request.user)
        try:
            frame = _read_csv(dataset.source_file.path)
            dataset.row_count = len(frame)
            dataset.column_schema = _schema_for(frame)
            dataset.preview = (
                frame.head(5).where(pd.notna(frame), None).to_dict(orient="records")
            )
            dataset.save(update_fields=["row_count", "column_schema", "preview"])
        except AuditInputError as exc:
            dataset.delete()
            raise ValidationError({"source_file": str(exc)}) from exc
        except Exception:
            dataset.delete()
            raise


class MetricDefinitionViewSet(viewsets.ModelViewSet):
    queryset = MetricDefinition.objects.select_related("dataset", "created_by")
    serializer_class = MetricDefinitionSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AuditRunViewSet(viewsets.ModelViewSet):
    queryset = AuditRun.objects.select_related("metric", "metric__dataset")
    serializer_class = AuditRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        audit = serializer.save()
        _run_saved_audit(audit)

    @action(detail=True, methods=["post"])
    def rerun(self, request, pk=None):
        audit = _run_saved_audit(self.get_object())
        return Response(self.get_serializer(audit).data)
