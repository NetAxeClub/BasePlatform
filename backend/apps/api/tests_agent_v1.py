import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory

from apps.api import throttles as agent_throttles
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
            resolve("/base_platform/agent/v1/tasks/change/").func.view_class,
            AgentChangeTaskAPIView,
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
            resolve("/base_platform/agent/v1/tools/catalog/").func.view_class,
            AgentToolCatalogAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/topology/reconcile/").func.view_class,
            AgentTopologyReconcileAPIView,
        )
        self.assertIs(
            resolve("/base_platform/agent/v1/executions/12/").func.view_class,
            AgentExecutionDetailAPIView,
        )


class AgentApiViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        agent_throttles.cache.clear()

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
        data = {
            "id": 1,
            "serial_num": "SN123",
            "manage_ip": "10.0.0.1",
            "name": "edge-1",
            "vendor": vendor,
            "category": category,
            "model": model,
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
        self.assertEqual(payload["payload"]["model_name"], "NE8000")

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

    @patch.object(AgentAnalysisAPIView, "_build_config_drift_items")
    def test_analysis_view_supports_config_drift(self, mock_build_config_drift_items):
        mock_build_config_drift_items.return_value = (
            {
                "analysis_kind": "config_drift",
                "items": 1,
                "non_compliant": 1,
                "execute_time": "2026-03-19 20:00:00",
                "source_task_id": "config-drift://2026-03-19 20:00:00",
                "device_set": ["10.0.0.1"],
            },
            [{"manage_ip": "10.0.0.1", "compliance": "不合规"}],
            [{"type": "source_task", "ref": "config-drift://2026-03-19 20:00:00"}],
            "HIGH",
        )

        request = self._with_iam(self.factory.get("/base_platform/agent/v1/analysis/", {"kind": "config_drift"}))
        response = AgentAnalysisAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["summary"]["analysis_kind"], "config_drift")
        self.assertEqual(payload["severity"], "HIGH")

    @patch("apps.api.agent_views.TopologyReconcileService.reconcile")
    def test_topology_reconcile_view_returns_unified_payload(self, mock_reconcile):
        mock_reconcile.return_value = {
            "severity": "MEDIUM",
            "summary": {
                "analysis_kind": "topology_reconcile",
                "execute_time": "2026-03-19 20:00:00",
                "source_task_id": "batch://2026-03-19 20:00:00",
                "device_set": ["10.0.0.1", "10.0.0.2"],
                "fact_counts": {"devices": 2, "lldp_edges": 1, "interfaces": 3, "ip_facts": 2, "address_traces": 1},
                "drift_counts": {"missing_in_facts": 1, "unregistered_devices": 0, "unresolved_traces": 1, "conflicts": 0},
            },
            "payload": {"reconcile": {"missing_in_facts": ["10.0.0.9"]}},
            "artifacts": [{"type": "execute_time", "ref": "execute-time://2026-03-19 20:00:00"}],
        }

        request = self._with_iam(self.factory.get("/base_platform/agent/v1/topology/reconcile/"))
        response = AgentTopologyReconcileAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["summary"]["analysis_kind"], "topology_reconcile")
        self.assertEqual(payload["severity"], "MEDIUM")
        self.assertEqual(payload["payload"]["reconcile"]["missing_in_facts"][0], "10.0.0.9")

    def test_tool_catalog_view_returns_mcp_ready_metadata(self):
        request = self._with_iam(self.factory.get("/base_platform/agent/v1/tools/catalog/"))
        response = AgentToolCatalogAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "SUCCEEDED")
        self.assertEqual(payload["summary"]["tool_count"], 5)
        self.assertIn("change_run", payload["summary"]["high_risk_tools"])
        self.assertEqual(payload["payload"]["tools"][0]["tool_name"], "device_facts")
        self.assertEqual(payload["payload"]["error_codes"]["RATE_LIMITED"]["http_status"], 429)
        self.assertTrue(payload["payload"]["tools"][0]["rate_limit"]["enforced"])
        self.assertTrue(all("automation" not in json.dumps(item, ensure_ascii=False) for item in payload["payload"]["tools"]))

    @patch("apps.api.throttles.cache", new_callable=lambda: LocMemCache("device-facts-throttle", {}))
    @patch("apps.api.agent_views.DeviceDiscoveryState.objects.filter")
    @patch.object(AgentDeviceFactsAPIView, "_get_device")
    def test_device_facts_view_enforces_runtime_throttle(self, mock_get_device, mock_filter, _cache):
        mock_get_device.return_value = self._device()
        mock_filter.return_value.first.return_value = None

        with patch.object(AgentDeviceFactsAPIView, "throttle_burst_limit", 1), patch.object(
            AgentDeviceFactsAPIView, "throttle_sustained_limit", None
        ):
            request_a = self._with_iam(self.factory.get("/base_platform/agent/v1/devices/SN123/facts/"))
            response_a = AgentDeviceFactsAPIView.as_view()(request_a, serial_num="SN123")
            request_b = self._with_iam(self.factory.get("/base_platform/agent/v1/devices/SN123/facts/"))
            response_b = AgentDeviceFactsAPIView.as_view()(request_b, serial_num="SN123")

        payload_b = self._json_payload(response_b)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 429)
        self.assertEqual(payload_b["summary"]["error_code"], "RATE_LIMITED")

    @patch("apps.api.throttles.cache", new_callable=lambda: LocMemCache("inspection-throttle", {}))
    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    @patch.object(AgentInspectionTaskAPIView, "_build_results")
    @patch.object(AgentInspectionTaskAPIView, "_load_devices")
    def test_inspection_view_enforces_runtime_throttle(self, mock_load_devices, mock_build_results, mock_create, _cache):
        mock_load_devices.return_value = [self._device(serial_num="SN123", manage_ip="10.0.0.1")]
        mock_build_results.return_value = {
            "ready": 1,
            "blocked": 0,
            "results": [{"serial_num": "SN123", "status": "success", "blockers": []}],
        }
        mock_create.return_value = SimpleNamespace(id=111)

        with patch.object(AgentInspectionTaskAPIView, "throttle_burst_limit", 1), patch.object(
            AgentInspectionTaskAPIView, "throttle_sustained_limit", None
        ):
            request_a = self._with_iam(
                self.factory.post("/base_platform/agent/v1/tasks/inspect/", {"serial_num": "SN123"}, format="json")
            )
            response_a = AgentInspectionTaskAPIView.as_view()(request_a)
            request_b = self._with_iam(
                self.factory.post("/base_platform/agent/v1/tasks/inspect/", {"serial_num": "SN123"}, format="json")
            )
            response_b = AgentInspectionTaskAPIView.as_view()(request_b)

        payload_b = self._json_payload(response_b)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 429)
        self.assertEqual(payload_b["summary"]["error_code"], "RATE_LIMITED")

    @patch("apps.api.throttles.cache", new_callable=lambda: LocMemCache("change-throttle", {}))
    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    def test_change_view_enforces_runtime_throttle(self, mock_create, _cache):
        mock_create.return_value = SimpleNamespace(id=211)

        with patch.object(AgentChangeTaskAPIView, "throttle_burst_limit", 1), patch.object(
            AgentChangeTaskAPIView, "throttle_sustained_limit", None
        ):
            request_a = self._with_iam(
                self.factory.post(
                    "/base_platform/agent/v1/tasks/change/",
                    {
                        "change_template": "sec_policy_low_risk",
                        "approval_status": "approved",
                        "baseline_ref": "baseline://change-throttle-1",
                        "verify": {"passed": True, "message": "ok"},
                    },
                    format="json",
                )
            )
            response_a = AgentChangeTaskAPIView.as_view()(request_a)
            request_b = self._with_iam(
                self.factory.post(
                    "/base_platform/agent/v1/tasks/change/",
                    {
                        "change_template": "sec_policy_low_risk",
                        "approval_status": "approved",
                        "baseline_ref": "baseline://change-throttle-2",
                        "verify": {"passed": True, "message": "ok"},
                    },
                    format="json",
                )
            )
            response_b = AgentChangeTaskAPIView.as_view()(request_b)

        payload_b = self._json_payload(response_b)
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 429)
        self.assertEqual(payload_b["summary"]["error_code"], "RATE_LIMITED")

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

    def test_change_view_blocks_execution_without_approval(self):
        request = self._with_iam(
            self.factory.post(
                "/base_platform/agent/v1/tasks/change/",
                {"change_template": "sec_policy_low_risk", "baseline_ref": "baseline://1"},
                format="json",
            )
        )
        response = AgentChangeTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["summary"]["error_code"], "APPROVAL_REQUIRED")

    def test_change_view_blocks_execution_without_baseline(self):
        request = self._with_iam(
            self.factory.post(
                "/base_platform/agent/v1/tasks/change/",
                {"change_template": "sec_policy_low_risk", "approval_status": "approved"},
                format="json",
            )
        )
        response = AgentChangeTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["summary"]["error_code"], "BASELINE_REQUIRED")

    def test_change_view_rejects_unregistered_template(self):
        request = self._with_iam(
            self.factory.post(
                "/base_platform/agent/v1/tasks/change/",
                {
                    "change_template": "unknown_template",
                    "approval_status": "approved",
                    "baseline_ref": "baseline://change-unknown",
                },
                format="json",
            )
        )
        response = AgentChangeTaskAPIView.as_view()(request)
        payload = self._json_payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["summary"]["error_code"], "UNSUPPORTED_CHANGE_TEMPLATE")

    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    def test_change_view_returns_succeeded_when_verify_passes(self, mock_create):
        templates = [
            ("sec_policy_low_risk", "security_policy", "安全策略"),
            ("address_object_low_risk", "address_object", "地址对象"),
            ("service_object_low_risk", "service_object", "服务对象"),
            ("dnat_low_risk", "dnat", "DNAT"),
        ]

        for index, (template_code, category, workflow_task) in enumerate(templates, start=31):
            mock_create.return_value = SimpleNamespace(id=index)
            request = self._with_iam(
                self.factory.post(
                    "/base_platform/agent/v1/tasks/change/",
                    {
                        "change_template": template_code,
                        "approval_status": "approved",
                        "baseline_ref": f"baseline://change-{index}",
                        "verify": {"passed": True, "message": "post-check passed"},
                        "order_code": f"OC-{index}",
                    },
                    format="json",
                ),
                username=f"iam-change-success-{index}",
            )
            response = AgentChangeTaskAPIView.as_view()(request)
            payload = self._json_payload(response)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["status"], "SUCCEEDED")
            self.assertEqual(payload["summary"]["change_template"], template_code)
            self.assertEqual(payload["summary"]["template_category"], category)
            self.assertEqual(payload["summary"]["workflow_task"], workflow_task)
            self.assertEqual(payload["summary"]["baseline_ref"], f"baseline://change-{index}")
            self.assertTrue(payload["summary"]["verify_passed"])
            self.assertTrue(payload["summary"]["verify_ref"].startswith("verify://"))
            self.assertTrue(payload["summary"]["rollback_ref"].startswith("rollback://"))
            self.assertTrue(payload["summary"]["audit_ref"].startswith("audit://change/"))
            self.assertEqual(payload["payload"]["template_spec"]["code"], template_code)

    @patch("apps.api.agent_views.WorkflowExecution.objects.create")
    def test_change_view_rolls_back_when_verify_fails(self, mock_create):
        templates = [
            "sec_policy_low_risk",
            "address_object_low_risk",
            "service_object_low_risk",
            "dnat_low_risk",
        ]

        for index, template_code in enumerate(templates, start=41):
            mock_create.return_value = SimpleNamespace(id=index)
            request = self._with_iam(
                self.factory.post(
                    "/base_platform/agent/v1/tasks/change/",
                    {
                        "change_template": template_code,
                        "approval_status": "approved",
                        "baseline_ref": f"baseline://rollback-{index}",
                        "verify": {"passed": False, "message": "verify failed"},
                        "rollback_requested": True,
                    },
                    format="json",
                ),
                username=f"iam-change-rollback-{index}",
            )
            response = AgentChangeTaskAPIView.as_view()(request)
            payload = self._json_payload(response)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["status"], "ROLLED_BACK")
            self.assertEqual(payload["summary"]["change_template"], template_code)
            self.assertEqual(payload["summary"]["rollback_status"], "executed")
            self.assertEqual(payload["payload"]["rollback"]["status"], "executed")
            self.assertEqual(payload["payload"]["verify_ref"], payload["summary"]["verify_ref"])
            self.assertEqual(payload["payload"]["rollback_ref"], payload["summary"]["rollback_ref"])
            self.assertEqual(payload["payload"]["audit_ref"], payload["summary"]["audit_ref"])
