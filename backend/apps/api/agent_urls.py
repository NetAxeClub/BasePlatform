from django.urls import path

from apps.api.agent_views import (
    AgentAnalysisAPIView,
    AgentDeviceCapabilitiesAPIView,
    AgentDeviceFactsAPIView,
    AgentExecutionDetailAPIView,
    AgentInspectionTaskAPIView,
    AgentSecurityAuditTaskAPIView,
)


urlpatterns = [
    path("devices/<str:serial_num>/facts/", AgentDeviceFactsAPIView.as_view(), name="agent-device-facts"),
    path(
        "devices/<str:serial_num>/capabilities/",
        AgentDeviceCapabilitiesAPIView.as_view(),
        name="agent-device-capabilities",
    ),
    path("tasks/inspect/", AgentInspectionTaskAPIView.as_view(), name="agent-inspect"),
    path(
        "tasks/audit/security-policy/",
        AgentSecurityAuditTaskAPIView.as_view(),
        name="agent-security-audit",
    ),
    path("analysis/", AgentAnalysisAPIView.as_view(), name="agent-analysis"),
    path("executions/<int:execution_id>/", AgentExecutionDetailAPIView.as_view(), name="agent-execution-detail"),
]
