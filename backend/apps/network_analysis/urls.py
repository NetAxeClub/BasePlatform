from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.network_analysis.views import (
    AddressTraceSnapshotViewSet,
    AnalysisRunViewSet,
    InterfaceUtilizationLegacyViewSet,
    InterfaceUtilizationSnapshotViewSet,
)

router = DefaultRouter()
router.register(r"analysis-runs", AnalysisRunViewSet, basename="analysis-runs")
router.register(r"interfaceused", InterfaceUtilizationLegacyViewSet, basename="interfaceused")
router.register(r"interface-utilization", InterfaceUtilizationSnapshotViewSet, basename="interface-utilization")
router.register(r"address-traces", AddressTraceSnapshotViewSet, basename="address-traces")

urlpatterns = [
    path("", include(router.urls)),
]
