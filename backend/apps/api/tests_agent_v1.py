import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.api.agent_views import (
    AgentAnalysisAPIView,
    AgentDeviceCapabilitiesAPIView,
    AgentDeviceFactsAPIView,
    AgentExecutionDetailAPIView,
    AgentInspectionTaskAPIView,
    AgentSecurityAuditTaskAPIView,
)


class AgentApiRouteTests(SimpleTestCase):
    def test_agent_v1_routes_resolve_to_expected_views(self):
        self.assertIs(
            resolve("/base_platform/agent/v1/devices/SN123/facts/").func.view_class,
            AgentDeviceFactsAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/devices/SN123/capabilities/").func.view_class,
            AgentDeviceCapabilitiesAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/tasks/inspect/").func.view_class,
            AgentInspectionTaskAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/tasks/audit/security-policy/").func.view_class,
            AgentSecurityAuditTaskAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/analysis/").func.view_class,
            AgentAnalysisAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/executions/12/").func.view_class,
            AgentExecutionDetailAPIView,
        )


class AgentApiViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @staticmethod
    def _json_payload(response):
        if hasattr(response, "render"):
            response.render()
        return json.loads(response.content)

    @staticmethod
    def _with_iam(request, username="iam-user"):
        request.user = AnonymousUser()
        request.iam = SimpleNamespace(is_authenticated=True, username=username)
        return request

    @staticmethod
    def _device(**kwargs):
        vendor = kwargs.pop("vendor", SimpleNamespace(name="Huawei", alias="huawei"))
        category = kwargs.pop("category", SimpleNamespace(name="Router"))
        model = kwargs.pop("model", SimpleNamespace(name="NE8000"))
        plan = kwargs.pop("plan", SimpleNamespace(name="legacy-plan"))
        data = {
            "id": 1,
            "serial_num": "SN123",
            "manage_ip": "10.0.0.1",
            "name": "edge-1",
            "vendor": vendor,
            "category": category,
            "model": model,
            "plan": plan,
            "soft_version": "V1",
            "patch_version": "P1",
        }
        data.update(kwargs)
        return SimpleNamespace(**data)

    @patch("apps.api.agent_views.DeviceDiscoveryState.objects.filter")
    @patch.object(AgentDeviceFactsAPIView, "_get_device")
    def test_device_facts_view_returns_standard_contract(self, mock_get_device, mock_filter):
        mock_get_device.return_value = self._device()
        mock_filter.return_value.first.return_value = SimpleNamespace(
            profile_code="huawei-core",
            last_discovered_at="2026-03-19 10:00:00",
            last_discovery_status="success",
            last_discovery_error="",
        )

        request = self._with_iam(self.factory.get("/base_platform/agent/v1/devices/SN123/facts/"))
        response = AgentDeviceFactsAPIView.as_view()(request, serial_num="SN123")
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["summary"]["serial_num"], "SN123")
        self.assertEqual(payload["payload"]["profile_code"], "huawei-core")
        self.assertEqual(payload["payload"]["legacy_plan_name"], "legacy-plan")

    def test_device_facts_view_rejects_anonymous_request(self):
        request = self.factory.get("/base_platform/agent/v1/devices/SN123/facts/")
        request.user = AnonymousUser()
        response = AgentDeviceFactsAPIView.as_view()(request, serial_num="SN123")
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertTrue("detail" in payload or "msg" in payload or "message" in payload)

    @patch.object(AgentDeviceFactsAPIView, "_get_device")
    def test_device_facts_view_accepts_iam_identity(self, mock_get_device):
        mock_get_device.return_value = self._device()
        request = self._with_iam(self.factory.get("/base_platform/agent/v1/devices/SN123/facts/"))

        with patch("apps.api.agent_views.DeviceDiscoveryState.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = None
            response = AgentDeviceFactsAPIView.as_view()(request, serial_num="SN123")

        self.assertEqual(response.status_code, 200)

    @patch.object(AgentDeviceCapabilitiesAPIView, "_get_blockers")
    @patch("apps.api.agent_views.PlatformProfileService.build_capabilities")
    @patch.object(AgentDeviceCapabilitiesAPIView, "_get_device")
    def test_device_capabilities_view_returns_blocking_reasons(
        self,
        mock_get_device,
        mock_build_capabilities,
        mock_get_blockers,
    ):
        mock_get_device.return_value = self._device()
        mock_build_capabilities.return_value = {
            "serial_num": "SN123",
            "manage_ip": "10.0.0.1",
            "profile_code": "",
            "supported_collection_types": [],
            "preferred_methods": {},
            "fallback_methods": {},
            "bindings": [],
        }
        mock_get_blockers.return_value = [{"code": "profile_not_matched", "message": "设备未匹配到平台画像"}]

        request = self._with_iam(self.factory.get("/base_platform/agent/v1/devices/SN123/capabilities/"))
        response = AgentDeviceCapabilitiesAPIView.as_view()(request, serial_num="SN123")
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["severity"], "MEDIUM")
        self.assertFalse(payload["payload"]["is_ready"])
        self.assertEqual(payload["payload"]["blocking_reasons"][0]["code"], "profile_not_matched")

    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    @patch.object(AgentInspectionTaskAPIView, "_build_results")
    @patch.object(AgentInspectionTaskAPIView, "_load_devices")
    def test_inspection_view_supports_partial_success(self, mock_load_devices, mock_build_results, mock_create):
        mock_load_devices.return_value = [
            self._device(serial_num="SN123", manage_ip="10.0.0.1"),
            self._device(serial_num="SN456", manage_ip="10.0.0.2"),
        ]
        mock_build_results.return_value = {
            "ready": 1,
            "blocked": 1,
            "results": [
                {"serial_num": "SN123", "status": "success", "blockers": []},
                {
                    "serial_num": "SN456",
                    "status": "blocked",
                    "blockers": [{"code": "profile_not_matched", "message": "设备未匹配到平台画像"}],
                },
            ],
        }
        mock_create.return_value = SimpleNamespace(id=11)

        request = self._with_iam(self.factory.post(
            "/base_platform/agent/v1/tasks/inspect/",
            {"serial_nums": ["SN123", "SN456"], "inspection_type": "baseline"},
            format="json",
        ))
        response = AgentInspectionTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "PARTIAL_SUCCESS")
        self.assertEqual(payload["execution_id"], "11")
        self.assertEqual(payload["summary"]["blocked_count"], 1)
        self.assertEqual(payload["payload"]["results"][1]["serial_num"], "SN456")

    @patch.object(AgentExecutionDetailAPIView, "_get_execution")
    def test_execution_detail_view_returns_standardized_execution_payload(self, mock_get_execution):
        mock_get_execution.return_value = SimpleNamespace(
            id=21,
            task_id="inspect-1",
            task="巡检",
            method="RESTAPI",
            state="Finish",
            kwargs=json.dumps(
                {
                    "inspection_scope": "fleet",
                    "inspection_type": "baseline",
                    "summary": {"target_count": 2, "blocked_count": 1},
                },
                ensure_ascii=False,
            ),
            task_result=json.dumps({"summary": {"target_count": 2, "blocked_count": 1}}, ensure_ascii=False),
        )

        request = self._with_iam(self.factory.get("/base_platform/agent/v1/executions/21/"))
        response = AgentExecutionDetailAPIView.as_view()(request, execution_id=21)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["summary"]["blocked_count"], 1)
        self.assertEqual(payload["audit_ref"], "audit://inspection/21")

    @patch.object(AgentAnalysisAPIView, "_build_interface_items")
    def test_analysis_view_returns_unified_payload(self, mock_build_interface_items):
        mock_build_interface_items.return_value = (
            {
                "analysis_kind": "interface_utilization",
                "count": 1,
                "max_utilization_percent": 87.5,
                "analysis_run_status": "success",
            },
            [
                {
                    "device_serial_num": "SN123",
                    "manage_ip": "10.0.0.1",
                    "component_name": "slot1",
                    "utilization_percent": 87.5,
                    "source_execute_time": "20260319-100000",
                }
            ],
            [{"type": "analysis_run", "ref": "analysis-run://8"}],
        )

        request = self._with_iam(
            self.factory.get("/base_platform/agent/v1/analysis/", {"kind": "interface_utilization"})
        )
        response = AgentAnalysisAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["summary"]["analysis_kind"], "interface_utilization")
        self.assertEqual(payload["payload"]["results"][0]["device_serial_num"], "SN123")

    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    @patch("apps.api.agent_views.FirewallPolicyAuditRecord.objects.create")
    @patch.object(AgentSecurityAuditTaskAPIView, "_load_policies")
    def test_security_audit_view_returns_audit_ref(self, mock_load_policies, mock_record_create, mock_exec_create):
        mock_load_policies.return_value = [
            {
                "vendor": "h3c_secpath",
                "hostip": "10.0.0.1",
                "id": "1",
                "name": "allow-any",
                "action": "permit",
                "enable": "true",
                "service": "Any",
                "src_addr": [],
                "dst_addr": [],
                "log": "false",
            }
        ]
        mock_record_create.return_value = SimpleNamespace(id=9)
        mock_exec_create.return_value = SimpleNamespace(id=13)

        request = self._with_iam(self.factory.post(
            "/base_platform/agent/v1/tasks/audit/security-policy/",
            {"device_ip": "10.0.0.1", "vendor": "H3C"},
            format="json",
        ))
        response = AgentSecurityAuditTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["execution_id"], "13")
        self.assertEqual(payload["audit_ref"], "audit://security-policy/9")
        self.assertEqual(payload["summary"]["task_type"], "security_audit_run")

    def test_security_audit_view_rejects_anonymous_request(self):
        request = self.factory.post(
            "/base_platform/agent/v1/tasks/audit/security-policy/",
            {"device_ip": "10.0.0.1", "vendor": "H3C"},
            format="json",
        )
        request.user = AnonymousUser()
        response = AgentSecurityAuditTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertTrue("detail" in payload or "msg" in payload or "message" in payload)
