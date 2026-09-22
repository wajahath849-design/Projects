from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalyzeUploadView,
    AuditRunViewSet,
    DatasetViewSet,
    DemoView,
    HealthView,
    LoginView,
    MetricDefinitionViewSet,
)


router = DefaultRouter()
router.register("datasets", DatasetViewSet)
router.register("metrics", MetricDefinitionViewSet)
router.register("audits", AuditRunViewSet)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("demo/", DemoView.as_view(), name="demo"),
    path("analyze/", AnalyzeUploadView.as_view(), name="analyze-upload"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("", include(router.urls)),
]
