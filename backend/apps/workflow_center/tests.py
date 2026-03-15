import json
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.workflow_center.management.commands.import_legacy_workflow_data import Command as ImportLegacyWorkflowDataCommand
from apps.workflow_center.inspection import (
    inspection_payload,
    inspection_scope,
    inspection_summary,
    inspection_task_result,
    inspection_type,
)
from apps.workflow_center.views import WorkflowExecutionViewSet
from apps.workflow_center.views import (
    WorkflowAddressLocationView,
    WorkflowDiagnoseView,
    WorkflowSecurityView,
)


class FakeQuerySet(list):
    def filter(self, **kwargs):
        result = list(self)
        for key, value in kwargs.items():
            if key.endswith("__gte"):
                field_name = key[:-5]
                result = [item for item in result if getattr(item, field_name) >= value]
            elif key.endswith("__lte"):
                field_name = key[:-5]
                result = [item for item in result if getattr(item, field_name) <= value]
            else:
                result = [item for item in result if getattr(item, key) == value]
        return FakeQuerySet(result)

    def order_by(self, *args, **kwargs):
        return self


class WorkflowCenterExecutionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @staticmethod
    def _build_flow(**kwargs):
        now = timezone.now()
        data = {
            "id": 1,
            "task_id": "inspection-1",
            "origin": "NetClaw-CN",
            "task_result": json.dumps({"results": [{"status": "pass"}, {"status": "failed"}]}, ensure_ascii=False),
            "order_code": "",
            "device": "10.0.0.1",
            "device_id": None,
            "commit_user": "tester",
            "commit_time": now,
            "task": "巡检",
            "method": "RESTAPI",
            "class_method": "inspection_result",
            "remote_ip": "127.0.0.1",
            "event": None,
            "kwargs": json.dumps(
                {
                    "inspection_scope": "device",
                    "inspection_type": "baseline",
                    "summary": {"total": 2, "passed": 1, "failed": 1},
                },
                ensure_ascii=False,
            ),
            "ttp": "{}",
            "commands": "[]",
            "back_off_commands": "[]",
            "state": "Finish",
            "code": 9008,
        }
        data.update(kwargs)
        return SimpleNamespace(**data)

    def test_inspection_helpers_parse_scope_type_and_summary(self):
        flow = self._build_flow()

        self.assertEqual(inspection_scope(flow), "device")
        self.assertEqual(inspection_type(flow), "baseline")
        self.assertEqual(inspection_summary(flow), {"total": 2, "passed": 1, "failed": 1})
        self.assertEqual(inspection_task_result(flow)["results"][0]["status"], "pass")
        self.assertEqual(inspection_payload(flow)["inspection_type"], "baseline")

    @patch.object(WorkflowExecutionViewSet, "get_queryset")
    def test_inspection_results_action_filters_scope_and_type(self, mock_get_queryset):
        flow_device = self._build_flow(task_id="inspection-device")
        flow_fleet = self._build_flow(
            id=2,
            task_id="inspection-fleet",
            device=None,
            kwargs=json.dumps({"inspection_scope": "fleet", "inspection_type": "routing"}, ensure_ascii=False),
        )
        mock_get_queryset.return_value = FakeQuerySet([flow_device, flow_fleet])

        request = self.factory.get(
            "/base_platform/workflow_center/executions/inspection_results/",
            {"inspection_scope": "fleet", "inspection_type": "routing", "limit": "20"},
        )
        response = WorkflowExecutionViewSet.as_view({"get": "inspection_results"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["data"][0]["task_id"], "inspection-fleet")

    @patch.object(WorkflowExecutionViewSet, "get_object")
    def test_inspection_detail_action_returns_payload(self, mock_get_object):
        mock_get_object.return_value = self._build_flow()

        request = self.factory.get("/base_platform/workflow_center/executions/1/inspection_detail/")
        response = WorkflowExecutionViewSet.as_view({"get": "inspection_detail"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["inspection_type"], "baseline")
        self.assertEqual(payload["data"]["inspection_summary"]["failed"], 1)

    @patch("apps.workflow_center.views.WorkflowExecution.objects.create")
    def test_write_inspection_result_action_creates_workflow_execution(self, mock_create):
        created_flow = self._build_flow(
            task_id="inspection-new",
            kwargs=json.dumps({"inspection_scope": "fleet", "inspection_type": "config"}, ensure_ascii=False),
            task_result=json.dumps({"summary": {"total": 3, "passed": 3}}, ensure_ascii=False),
        )
        mock_create.return_value = created_flow

        request = self.factory.post(
            "/base_platform/workflow_center/executions/write_inspection_result/",
            {
                "task_id": "inspection-new",
                "device_ip": "10.0.0.8",
                "inspection_scope": "fleet",
                "inspection_type": "config",
                "summary": {"total": 3, "passed": 3},
                "task_result": {"summary": {"total": 3, "passed": 3}},
                "ttp": {"details": []},
                "commands": ["show run"],
            },
            format="json",
        )
        response = WorkflowExecutionViewSet.as_view({"post": "write_inspection_result"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 201)
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs["task"], "巡检")
        self.assertEqual(create_kwargs["device"], "10.0.0.8")

    @patch.object(WorkflowExecutionViewSet, "get_queryset")
    def test_inspection_results_action_respects_time_window(self, mock_get_queryset):
        now = timezone.now()
        old_flow = self._build_flow(id=1, commit_time=now - timedelta(days=5), task_id="old")
        new_flow = self._build_flow(id=2, commit_time=now, task_id="new")
        mock_get_queryset.return_value = FakeQuerySet([old_flow, new_flow])

        request = self.factory.get(
            "/base_platform/workflow_center/executions/inspection_results/",
            {"start_time": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")},
        )
        response = WorkflowExecutionViewSet.as_view({"get": "inspection_results"})(request)
        payload = json.loads(response.content)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["data"][0]["task_id"], "new")


class WorkflowCenterServiceViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.workflow_center.views.get_firewall_list")
    def test_security_view_uses_workflow_service(self, mock_get_firewall_list):
        mock_get_firewall_list.return_value = [{"manage_ip": "10.0.0.1"}]

        request = self.factory.get(
            "/base_platform/workflow_center/sec-main/",
            {"get_firewall_list": "1"},
        )
        response = WorkflowSecurityView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        mock_get_firewall_list.assert_called_once_with()

    @patch("apps.workflow_center.views.WorkflowDiagnoseService")
    def test_diagnose_view_uses_workflow_service(self, mock_service_cls):
        service = mock_service_cls.return_value
        service.get_address_traces.return_value = [{"manage_ip": "10.0.0.1", "device_name": "sw-a"}]
        service.get_cmdb.return_value = [{"manage_ip": "10.0.0.1"}]
        service.get_log.return_value = [{"message": "ok"}]
        service.get_lldp.return_value = [{"hostip": "10.0.0.1"}]

        request = self.factory.get(
            "/base_platform/workflow_center/diagnose/",
            {"server_ip_address": "10.0.0.8"},
        )
        response = WorkflowDiagnoseView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["cmdb"][0]["manage_ip"], "10.0.0.1")
        mock_service_cls.assert_called_once_with("10.0.0.8")

    @patch("apps.workflow_center.views.query_address_traces")
    def test_address_location_view_uses_network_analysis_snapshot(self, mock_query_traces):
        mock_query_traces.return_value = ([{"ip_address": "10.1.1.1", "manage_ip": "10.0.0.1"}], 1)

        request = self.factory.get(
            "/base_platform/workflow_center/address-location/",
            {"server_ip_address": "10.1.1.1", "page_size": "10", "start": "0"},
        )
        response = WorkflowAddressLocationView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["manage_ip"], "10.0.0.1")

    @patch("apps.workflow_center.views.get_address_trace_columns")
    def test_address_location_columns_return_new_semantic_keys(self, mock_columns):
        mock_columns.return_value = [{"title": "目标IP", "key": "ip_address"}]

        request = self.factory.get(
            "/base_platform/workflow_center/address-location/",
            {"get_table_columns": "1"},
        )
        response = WorkflowAddressLocationView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["results"][0]["key"], "ip_address")


class WorkflowCenterImportCommandTests(SimpleTestCase):
    @patch("apps.workflow_center.management.commands.import_legacy_workflow_data.WorkflowExecution.objects")
    @patch("apps.workflow_center.management.commands.import_legacy_workflow_data.WorkflowInventory.objects")
    @patch("apps.workflow_center.management.commands.import_legacy_workflow_data.WorkflowHostVar.objects")
    def test_import_legacy_workflow_data_reads_raw_tables(
        self,
        mock_host_var_objects,
        mock_inventory_objects,
        mock_execution_objects,
    ):
        execution_rows = [
            {"id": 1, "task_id": "t1", "origin": "legacy", "task_result": "{}", "order_code": "", "device": "10.0.0.1", "device_id": None, "commit_user": "u", "commit_time": timezone.now(), "task": "巡检", "method": "RESTAPI", "class_method": "x", "remote_ip": "127.0.0.1", "event_id": None, "kwargs": "{}", "ttp": "{}", "commands": "[]", "back_off_commands": "[]", "state": "Finish", "code": 9008},
        ]
        hostvar_rows = [
            {"id": 2, "ans_name": "host-a", "ans_host": "10.0.0.2", "ans_vars": "{}", "ans_obj": "obj", "ans_memo": "", "task": "地址对象"}
        ]
        inventory_rows = [
            {"id": 3, "ans_group_name": "inventory-a", "ans_group_vars": "{}", "ans_group_memo": "", "ans_group_datetime": timezone.now(), "task": "巡检"}
        ]
        inventory_host_rows = [
            {"id": 4, "automationinventory_id": 3, "autovars_id": 2}
        ]
        host_var = MagicMock()
        inventory = MagicMock()
        execution = MagicMock()
        mock_host_var_objects.update_or_create.return_value = (host_var, True)
        mock_inventory_objects.update_or_create.return_value = (inventory, False)
        mock_execution_objects.update_or_create.return_value = (execution, True)

        stats = ImportLegacyWorkflowDataCommand._import_rows(
            execution_rows,
            hostvar_rows,
            inventory_rows,
            inventory_host_rows,
        )

        mock_host_var_objects.update_or_create.assert_called()
        mock_inventory_objects.update_or_create.assert_called()
        mock_execution_objects.update_or_create.assert_called()
        self.assertEqual(stats["host_vars"]["created"], 1)
        self.assertEqual(stats["inventories"]["updated"], 1)
        self.assertEqual(stats["executions"]["created"], 1)
        self.assertEqual(stats["inventory_host_links"]["linked"], 1)


class WorkflowCenterArchitectureGuardTests(SimpleTestCase):
    def test_runtime_modules_do_not_import_automation(self):
        root = Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/workflow_center")
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if "tests.py" in path.name:
                continue
            if relative.parts and relative.parts[0] == "migrations":
                continue
            source = path.read_text()
            self.assertNotIn("from apps.automation", source, f"forbidden legacy import in {path}")
            self.assertNotIn("import apps.automation", source, f"forbidden legacy import in {path}")

    def test_core_modules_do_not_use_ans_prefix_fields(self):
        base = Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/workflow_center")
        for filename in ("models.py", "serializers.py", "views.py"):
            source = (base / filename).read_text()
            self.assertNotIn("ans_", source, f"legacy ans_ field leaked into {filename}")
