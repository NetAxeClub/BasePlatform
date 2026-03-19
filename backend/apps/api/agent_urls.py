from django.urls import path

from apps.api.agent_views import (
    AgentAnalysisAPIView,
    AgentChangeTaskAPIView,
    AgentDeviceCapabilitiesAPIView,
    AgentDeviceFactsAPIView,
    AgentExecutionDetailAPIView,
    AgentInspectionTaskAPIView,
    AgentSecurityAuditTaskAPIView,
    AgentToolCatalogAPIView,
    AgentTopologyReconcileAPIView,
)


urlpatterns = [
    path("devices/<str:serial_num>/facts/", AgentDeviceFactsAPIView.as_view(), name="agent-device-facts"),
    path(
        "devices/<str:serial_num>/capabilities/",
        AgentDeviceCapabilitiesAPIView.as_view(),
        name="agent-device-capabilities",
    ),
    path("tasks/inspect/", AgentInspectionTaskAPIView.as_view(), name="agent-inspect"),
    path("tasks/change/", AgentChangeTaskAPIView.as_view(), name="agent-change"),
    path(
        "tasks/audit/security-policy/",
        AgentSecurityAuditTaskAPIView.as_view(),
        name="agent-security-audit",
    ),
    path("analysis/", AgentAnalysisAPIView.as_view(), name="agent-analysis"),
    path("tools/catalog/", AgentToolCatalogAPIView.as_view(), name="agent-tool-catalog"),
    path("topology/reconcile/", AgentTopologyReconcileAPIView.as_view(), name="agent-topology-reconcile"),
    path("executions/<int:execution_id>/", AgentExecutionDetailAPIView.as_view(), name="agent-execution-detail"),
]
