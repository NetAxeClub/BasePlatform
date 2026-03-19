import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.api.agent_views import (
    AgentExecutionDetailAPIView,
    AgentInspectionTaskAPIView,
    AgentSecurityAuditTaskAPIView,
)
from apps.asset.models import Category, Model, NetworkDevice, Vendor
from apps.dcs_control.views import SecPolicyAuditRecordView
from apps.workflow_center.models import Tasks, WorkflowExecution


class AgentApiIntegrationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.vendor = Vendor.objects.create(name="华为", alias="Huawei")
        self.category = Category.objects.create(name="交换机")
        self.model = Model.objects.create(name="CE12800", vendor=self.vendor)
        self.device = NetworkDevice.objects.create(
            serial_num="SN-INT-001",
            manage_ip="10.10.10.1",
            name="edge-int-1",
            vendor=self.vendor,
            category=self.category,
            model=self.model,
            soft_version="V200R001",
            patch_version="P001",
        )

    @staticmethod
    def _attach_iam(request, username="integration-user"):
        request.user = SimpleNamespace(is_authenticated=False)
        request.iam = SimpleNamespace(is_authenticated=True, username=username)
        return request

    @staticmethod
    def _json_payload(response):
        if hasattr(response, "render"):
            response.render()
        return json.loads(response.content)

    @patch.object(
        AgentInspectionTaskAPIView,
        "_build_results",
        return_value={
            "ready": 1,
            "blocked": 0,
            "results": [
                {
                    "serial_num": "SN-INT-001",
                    "manage_ip": "10.10.10.1",
                    "profile_code": "Huawei-CE",
                    "plan_id": 1,
                    "plan_name": "default-huawei-ce-switch",
                    "status": "success",
                    "blockers": [],
                }
            ],
        },
    )
    def test_inspection_task_persists_execution_and_can_be_replayed(self, _mock_build_results):
        create_request = self._attach_iam(
            self.factory.post(
                "/base_platform/agent/v1/tasks/inspect/",
                {
                    "serial_num": self.device.serial_num,
                    "inspection_type": "baseline",
                    "inspection_scope": "device",
                },
                format="json",
            )
        )
        create_response = AgentInspectionTaskAPIView.as_view()(create_request)
        create_payload = self._json_payload(create_response)

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_payload["status"], "SUCCEEDED")

        execution_id = int(create_payload["execution_id"])
        execution = WorkflowExecution.objects.get(id=execution_id)
        self.assertEqual(execution.task, Tasks.INSPECTION)
        self.assertEqual(execution.device, self.device.manage_ip)

        replay_request = self._attach_iam(
            self.factory.get(f"/base_platform/agent/v1/executions/{execution_id}/")
        )
        replay_response = AgentExecutionDetailAPIView.as_view()(replay_request, execution_id=execution_id)
        replay_payload = self._json_payload(replay_response)

        self.assertEqual(replay_response.status_code, 200)
        self.assertEqual(replay_payload["status"], "SUCCEEDED")
        self.assertEqual(replay_payload["summary"]["ready_count"], 1)
        self.assertEqual(replay_payload["payload"]["task"], Tasks.INSPECTION)

    @patch.object(
        AgentSecurityAuditTaskAPIView,
        "_load_policies",
        return_value=[
            {
                "vendor": "huawei_usg",
                "hostip": "10.10.10.1",
                "id": "100",
                "name": "allow-any",
                "action": "permit",
                "enable": "true",
                "service": "Any",
                "src_addr": [],
                "dst_addr": [],
                "log": "false",
            }
        ],
    )
    def test_security_audit_persists_record_and_can_be_queried(self, _mock_load_policies):
        create_request = self._attach_iam(
            self.factory.post(
                "/base_platform/agent/v1/tasks/audit/security-policy/",
                {"device_ip": self.device.manage_ip, "vendor": "Huawei"},
                format="json",
            )
        )
        create_response = AgentSecurityAuditTaskAPIView.as_view()(create_request)
        create_payload = self._json_payload(create_response)

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_payload["status"], "SUCCEEDED")
        self.assertIn("audit://security-policy/", create_payload["audit_ref"])

        record_view_request = self.factory.get(
            "/base_platform/dcs_manage/sec_policy_audit_records/",
            {"device_ip": self.device.manage_ip, "limit": "5"},
        )
        record_view_response = SecPolicyAuditRecordView.as_view()(record_view_request)
        record_payload = self._json_payload(record_view_response)

        self.assertEqual(record_view_response.status_code, 200)
        self.assertGreaterEqual(record_payload["count"], 1)
        self.assertEqual(record_payload["data"][0]["device_ip"], self.device.manage_ip)
        self.assertEqual(record_payload["data"][0]["summary"]["permit_any_any_count"], 1)
