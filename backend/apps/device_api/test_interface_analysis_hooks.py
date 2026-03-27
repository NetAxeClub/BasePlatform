import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.device_api.analysis_hooks import maybe_schedule_interface_utilization
from apps.device_api.views import DeviceCollectionPlansViewSet, DeviceSubCollectionPlanViewSet


class FakeQuerySet(list):
    def exists(self):
        return bool(self)


class DeviceApiInterfaceAnalysisHookTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.device_api.analysis_hooks.refresh_interface_utilization.apply_async")
    @patch("apps.device_api.analysis_hooks.InterfaceUtilizationAnalysisService.has_ready_source_data")
    def test_maybe_schedule_interface_utilization_only_for_ready_interface_types(
        self,
        mock_has_ready_source_data,
        mock_apply_async,
    ):
        mock_has_ready_source_data.return_value = True

        scheduled = maybe_schedule_interface_utilization(
            collection_type="interface_brief",
            device_ip="10.0.0.1",
            execute_time="2026-03-16 10:00:00",
            triggered_by="test",
        )
        skipped = maybe_schedule_interface_utilization(
            collection_type="arp",
            device_ip="10.0.0.1",
            execute_time="2026-03-16 10:00:00",
            triggered_by="test",
        )

        self.assertTrue(scheduled["scheduled"])
        self.assertFalse(skipped["scheduled"])
        mock_apply_async.assert_called_once()

    @patch("apps.device_api.views._store_runtime_task_snapshot")
    @patch("apps.device_api.views.run_sub_plan_execute_task.apply_async")
    @patch("apps.device_api.views.DeviceSubCollectionPlanViewSet.validate_execution_params")
    @patch.object(DeviceSubCollectionPlanViewSet, "get_object")
    def test_execute_sub_plan_local_dispatches_async_task(
        self,
        mock_get_object,
        mock_validate_params,
        mock_apply_async,
        _mock_store_snapshot,
    ):
        plan = SimpleNamespace(
            id=11,
            name="interface-plan",
            collection_type="interface_brief",
            summary_plan_id=1,
            summary_plan=None,
        )
        device = SimpleNamespace(manage_ip="10.0.0.1")
        device.id = 101
        device.serial_num = "SER-1"
        mock_get_object.return_value = plan
        mock_validate_params.return_value = (True, "验证通过", device)
        mock_apply_async.return_value = "task-subplan-async-1"

        request = self.factory.post(
            "/base_platform/device_api/sub-collection-plan/11/execute_sub_plan/",
            {"device_ip": "10.0.0.1", "use_local": True},
            format="json",
        )
        response = DeviceSubCollectionPlanViewSet.as_view({"post": "execute_sub_plan"})(request, pk="11")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["task_id"], "task-subplan-async-1")
        self.assertTrue(payload["data"]["async"])
        mock_apply_async.assert_called_once()

    @patch("apps.device_api.views.maybe_schedule_interface_utilization")
    @patch("apps.device_api.views.DeviceCollectionService.execute_both_collection_local")
    @patch("apps.device_api.views.NetworkDevice.objects.get")
    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_execute_all_collections_local_returns_interface_analysis_trigger(
        self,
        mock_get_object,
        mock_get_device,
        mock_execute_local,
        mock_schedule_analysis,
    ):
        interface_plan = SimpleNamespace(
            id=11,
            name="interface-plan",
            collection_type="interface_brief",
            netconf_enabled=False,
            netmiko_enabled=True,
        )
        summary_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            is_active=True,
            collect_plans=SimpleNamespace(all=lambda: FakeQuerySet([interface_plan])),
        )
        device = SimpleNamespace(ssh_account=object(), netconf_account=None)
        mock_get_object.return_value = summary_plan
        mock_get_device.return_value = device
        mock_execute_local.return_value = {
            "success": True,
            "message": "NETMIKO 采集成功",
            "netconf_result": None,
            "netmiko_result": {"success": True},
            "snmp_result": None,
            "restconf_result": None,
            "telemetry_result": None,
            "execute_time": "2026-03-16 10:00:00",
        }
        mock_schedule_analysis.return_value = {"scheduled": True, "reason": "scheduled"}

        request = self.factory.post(
            "/base_platform/device_api/collection-plans/1/execute_all_collections/",
            {"device_ip": "10.0.0.1", "use_local": True},
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"post": "execute_all_collections"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["data"]["analysis_trigger"]["scheduled"])
        mock_schedule_analysis.assert_called_once_with(
            collection_type="interface_brief",
            device_ip="10.0.0.1",
            execute_time="2026-03-16 10:00:00",
            triggered_by="device_api-execute_all_collections-local",
        )

    @patch("apps.device_api.views.maybe_schedule_interface_utilization")
    @patch("apps.device_api.views.plan_data_to_mongodb")
    def test_record_plan_data_schedules_analysis_after_successful_interface_callback(
        self,
        mock_plan_data_to_mongodb,
        mock_schedule_analysis,
    ):
        from apps.device_api.views import DeviceSubCollectionPlanViewSet

        mock_plan_data_to_mongodb.return_value = {"status": "success", "message": "ok"}
        mock_schedule_analysis.return_value = {"scheduled": True, "reason": "scheduled"}
        request = self.factory.post(
            "/base_platform/device_api/sub-collection-plan/record_plan_data/",
            {
                "webhook_args": {
                    "collection_type": "interface_brief",
                    "device_ip": "10.0.0.1",
                    "execute_time": "2026-03-16 10:00:00",
                }
            },
            format="json",
        )

        response = DeviceSubCollectionPlanViewSet.as_view({"post": "record_plan_data"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["data"]["analysis_trigger"]["scheduled"])
        mock_schedule_analysis.assert_called_once_with(
            collection_type="interface_brief",
            device_ip="10.0.0.1",
            execute_time="2026-03-16 10:00:00",
            triggered_by="device_api-record_plan_data",
            countdown=5,
        )

    @patch("apps.device_api.views.maybe_schedule_interface_utilization")
    @patch("apps.device_api.views.celery_data_mongodb")
    def test_record_collection_schedules_analysis_after_successful_interface_callback(
        self,
        mock_celery_data_mongodb,
        mock_schedule_analysis,
    ):
        mock_celery_data_mongodb.return_value = {"status": "success", "message": "ok"}
        mock_schedule_analysis.return_value = {"scheduled": True, "reason": "scheduled"}
        request = self.factory.post(
            "/base_platform/device_api/sub-collection-plan/record_collection/",
            {
                "webhook_args": {
                    "collection_type": "ip_interface",
                    "device_ip": "10.0.0.1",
                    "execute_time": "2026-03-16 10:00:00",
                }
            },
            format="json",
        )

        response = DeviceSubCollectionPlanViewSet.as_view({"post": "record_collection"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["data"]["analysis_trigger"]["scheduled"])
        mock_schedule_analysis.assert_called_once_with(
            collection_type="ip_interface",
            device_ip="10.0.0.1",
            execute_time="2026-03-16 10:00:00",
            triggered_by="device_api-record_collection",
            countdown=5,
        )
