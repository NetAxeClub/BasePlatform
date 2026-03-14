import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.automation.inspection import (
    inspection_payload,
    inspection_scope,
    inspection_summary,
    inspection_task_result,
    inspection_type,
)
from apps.automation.views import AutoFlowViewSet


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


class AutomationInspectionTests(SimpleTestCase):
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

    @patch.object(AutoFlowViewSet, "get_queryset")
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
            "/base_platform/automation/api/auto_work_flow/inspection_results/",
            {"inspection_scope": "fleet", "inspection_type": "routing", "limit": "20"},
        )
        response = AutoFlowViewSet.as_view({"get": "inspection_results"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["data"][0]["task_id"], "inspection-fleet")
        self.assertEqual(payload["data"][0]["inspection_scope"], "fleet")

    @patch.object(AutoFlowViewSet, "get_object")
    def test_inspection_detail_action_returns_parsed_payload(self, mock_get_object):
        mock_get_object.return_value = self._build_flow()

        request = self.factory.get(
            "/base_platform/automation/api/auto_work_flow/1/inspection_detail/",
        )
        response = AutoFlowViewSet.as_view({"get": "inspection_detail"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["inspection_type"], "baseline")
        self.assertEqual(payload["data"]["inspection_summary"]["failed"], 1)

    @patch("apps.automation.views.AutoFlow.objects.create")
    def test_write_inspection_result_action_creates_autoflow_record(self, mock_create):
        created_flow = self._build_flow(
            task_id="inspection-new",
            kwargs=json.dumps({"inspection_scope": "fleet", "inspection_type": "config"}, ensure_ascii=False),
            task_result=json.dumps({"summary": {"total": 3, "passed": 3}}, ensure_ascii=False),
        )
        mock_create.return_value = created_flow

        request = self.factory.post(
            "/base_platform/automation/api/auto_work_flow/write_inspection_result/",
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
        response = AutoFlowViewSet.as_view({"post": "write_inspection_result"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 201)
        mock_create.assert_called_once()
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs["task"], "巡检")
        self.assertEqual(create_kwargs["device"], "10.0.0.8")
        self.assertEqual(json.loads(create_kwargs["kwargs"])["inspection_type"], "config")
        self.assertEqual(payload["data"]["inspection_scope"], "fleet")

    @patch.object(AutoFlowViewSet, "get_queryset")
    def test_inspection_results_action_respects_time_window(self, mock_get_queryset):
        now = timezone.now()
        old_flow = self._build_flow(id=1, commit_time=now - timedelta(days=5), task_id="old")
        new_flow = self._build_flow(id=2, commit_time=now, task_id="new")
        mock_get_queryset.return_value = FakeQuerySet([old_flow, new_flow])

        request = self.factory.get(
            "/base_platform/automation/api/auto_work_flow/inspection_results/",
            {"start_time": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")},
        )
        response = AutoFlowViewSet.as_view({"get": "inspection_results"})(request)
        payload = json.loads(response.content)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["data"][0]["task_id"], "new")
