from django.urls import include, path
from rest_framework_extensions.routers import ExtendedDefaultRouter as DefaultRouter

from apps.workflow_center.views import (
    WorkflowExecutionViewSet,
    WorkflowInventoryViewSet,
    WorkflowHostVarViewSet,
    WorkflowAutomationChartView,
    WorkflowAddressLocationView,
    WorkflowSecurityView,
    WorkflowDiagnoseView,
)

app_name = "workflow_center"

router = DefaultRouter()
router.register(r"executions", WorkflowExecutionViewSet, basename="workflow-executions")
router.register(r"inventories", WorkflowInventoryViewSet, basename="workflow-inventories")
router.register(r"host-vars", WorkflowHostVarViewSet, basename="workflow-host-vars")

urlpatterns = [
    path("", include(router.urls)),
    path("v1/", include(router.urls)),
    path("automation-chart/", WorkflowAutomationChartView.as_view(), name="automation-chart"),
    path("v1/automation-chart/", WorkflowAutomationChartView.as_view(), name="automation-chart-v1"),
    path("address-location/", WorkflowAddressLocationView.as_view(), name="address-location"),
    path("v1/address-location/", WorkflowAddressLocationView.as_view(), name="address-location-v1"),
    path("sec-main/", WorkflowSecurityView.as_view(), name="sec-main"),
    path("v1/sec-main/", WorkflowSecurityView.as_view(), name="sec-main-v1"),
    path("diagnose/", WorkflowDiagnoseView.as_view(), name="diagnose"),
    path("v1/diagnose/", WorkflowDiagnoseView.as_view(), name="diagnose-v1"),
]
