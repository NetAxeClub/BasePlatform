import json
import importlib
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import requests
from bson import ObjectId
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory
from textfsm import TextFSM

from apps.asset.models import Category, Model, NetworkDevice, Vendor
from apps.device_api.fields_mapping import (
    DEFAULT_COLLECTION_TYPES,
    RAW_NETMIKO_COLLECTION_TYPES,
    get_collection_output_fields,
)
from apps.device_api.connection_manager import DeviceConnectionManager
from apps.device_api.models import (
    DeviceCollectionPlans,
    DeviceDiscoveryState,
    DeviceSubCollectionPlan,
    PlansToDevice,
)
from apps.device_api.models_api import (
    COLLECTION_TYPE_MONGO_MAP,
    apply_field_mappings,
    ensure_processors_bootstrapped,
    resolve_raw_data,
)
from apps.device_api.processors.base import get_processor, normalize_processed_data
from apps.device_api.processors.h3c import (
    process_aggre_port_netconf as process_h3c_aggre_port_netconf,
    process_bgp_summary_netconf as process_h3c_bgp_summary_netconf,
    process_cli_output_capability_netmiko as process_h3c_cli_output_capability_netmiko,
    process_clock_status_netmiko as process_h3c_clock_status_netmiko,
    process_fan_status_netmiko as process_h3c_fan_status_netmiko,
    process_ip_interface_netconf as process_h3c_ip_interface_netconf,
    process_lldp_netconf as process_h3c_lldp_netconf,
    process_mac_netconf as process_h3c_mac_netconf,
    process_netconf_capability_netconf as process_h3c_netconf_capability_netconf,
    process_power_status_netmiko as process_h3c_power_status_netmiko,
    process_route_table_netconf as process_h3c_route_table_netconf,
    process_version_netmiko as process_h3c_version_netmiko,
)
from apps.device_api.processors.huawei import (
    process_aggre_port_netconf as process_huawei_aggre_port_netconf,
    process_arp_netconf as process_huawei_arp_netconf,
    process_ip_interface_netconf as process_huawei_ip_interface_netconf,
    process_isis_neighbors_netmiko as process_huawei_isis_neighbors_netmiko,
    process_lldp_netconf as process_huawei_lldp_netconf,
    process_mac_bd_netconf as process_huawei_mac_bd_netconf,
    process_mac_netconf as process_huawei_mac_netconf,
    process_mac_vxlan_control_netconf as process_huawei_mac_vxlan_control_netconf,
    process_mac_vxlan_netconf as process_huawei_mac_vxlan_netconf,
    process_power_status_netmiko as process_huawei_power_status_netmiko,
    process_route_table_netconf as process_huawei_route_table_netconf,
    process_temperature_status_netmiko as process_huawei_temperature_status_netmiko,
)
from apps.device_api.processors.ruijie import (
    process_ruijie_fan_status_netmiko,
    process_ruijie_power_status_netmiko,
)
from apps.device_api.services_new import DeviceCollectionService
from apps.device_api.serializers import (
    DeviceCollectionPlansCreateSerializer,
    DeviceSubCollectionPlanCreateSerializer,
    DeviceSubCollectionPlanSerializer,
    DeviceSubCollectionPlanUpdateSerializer,
    NetconfXMLTemplateSerializer,
)
from apps.device_api.management.commands.sync_legacy_plan_bindings import Command as SyncLegacyPlanBindingsCommand
from apps.device_api.management.commands.ensure_device_api_indexes import Command as EnsureDeviceApiIndexesCommand
from apps.device_api.management.commands.audit_device_api_coverage import (
    Command as AuditDeviceApiCoverageCommand,
)
from apps.device_api.management.commands.refresh_capability_discovery import (
    Command as RefreshCapabilityDiscoveryCommand,
)
from apps.device_api.apps import DeviceApiConfig
from apps.device_api.indexes import (
    bootstrap_device_api_mongo_indexes,
    ensure_device_api_mongo_indexes,
    should_auto_ensure_device_api_indexes,
)
from apps.device_api.platform_profiles import (
    BUILTIN_PLATFORM_PROFILES,
    DeviceFactService,
    PROFILE_NETMIKO_SUB_PLAN_DEFAULTS,
    TEMPLATE_BASE_DIR,
    PlatformProfileService,
)
from apps.device_api.tasks import (
    _process_and_save_result,
    plan_collect_device,
    plan_collect_device_main,
    split_runtime_control_kwargs,
    should_clear_history_before_batch,
)
from apps.device_api.tools.collect_device import get_auto_device
from apps.device_api.tools.centec import CentecPlan
from apps.device_api.tools.maipu import MaipuPlan
from apps.device_api.tools.mellanox import MellanoxPlan
from apps.device_api.tools.ruijie import RuiJiePlan
from apps.device_api.tools.zte import ZtePlan
from apps.device_api.management.commands.import_legacy_collection_rules import (
    Command as ImportLegacyCollectionRulesCommand,
)
from apps.device_api.management.commands.device_api_p5_rollout import (
    Command as DeviceApiP5RolloutCommand,
)
from apps.device_api.management.commands.audit_legacy_time_anchor import (
    Command as AuditLegacyTimeAnchorCommand,
)
from apps.device_api.management.commands.backfill_legacy_execute_time import (
    Command as BackfillLegacyExecuteTimeCommand,
)
from apps.device_api.views import (
    CollectionResultViewSet,
    DeviceCollectionRuleToolView,
    DeviceCollectionPlansViewSet,
    DeviceSubCollectionPlanViewSet,
    DeviceFactsAPIView,
    DeviceCapabilitiesAPIView,
    PlansToDeviceViewSet,
)


class FakeQuerySet(list):
    def exists(self):
        return bool(self)


class DeviceApiViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.device_api.views.DeviceCollectionService.execute_both_collection")
    @patch("apps.device_api.views.NetworkDevice.objects.get")
    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_execute_all_collections_passes_south_driver(
        self,
        mock_get_object,
        mock_get_device,
        mock_execute_both_collection,
    ):
        plan = SimpleNamespace(id=11, name="arp-plan", netconf_enabled=False, netmiko_enabled=True)
        summary_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            is_active=True,
            collect_plans=SimpleNamespace(all=lambda: FakeQuerySet([plan])),
        )
        mock_get_object.return_value = summary_plan
        mock_get_device.return_value = SimpleNamespace(ssh_account=object(), netconf_account=None)
        mock_execute_both_collection.return_value = {
            "success": True,
            "message": "ok",
            "netconf_result": None,
            "netmiko_result": {"success": True},
        }

        request = self.factory.post(
            "/base_platform/device_api/collection-plans/1/execute_all_collections/",
            {"device_ip": "10.0.0.1", "south_driver": "10.0.0.10"},
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"post": "execute_all_collections"})(request, pk="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        mock_execute_both_collection.assert_called_once_with(plan, mock_get_device.return_value, "10.0.0.10")

    @patch("apps.device_api.views.DeviceCollectionService.execute_both_collection_local")
    @patch("apps.device_api.views.DeviceSubCollectionPlanViewSet.validate_execution_params")
    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_validate_plan_groups_results_by_collection_type(
        self,
        mock_get_object,
        mock_validate_params,
        mock_execute_local,
    ):
        arp_plan = SimpleNamespace(
            id=11,
            name="summary-plan-arp",
            collection_type="arp",
            netmiko_enabled=True,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )
        mac_plan = SimpleNamespace(
            id=12,
            name="summary-plan-mac",
            collection_type="mac",
            netmiko_enabled=True,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )
        summary_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            is_active=True,
            collect_plans=SimpleNamespace(all=lambda: [arp_plan, mac_plan]),
        )
        mock_get_object.return_value = summary_plan
        device = SimpleNamespace(manage_ip="10.0.0.1")
        mock_validate_params.side_effect = [
            (True, "验证通过", device),
            (False, "设备 10.0.0.1 未配置SSH账号", None),
        ]
        mock_execute_local.return_value = {
            "success": True,
            "message": "NETMIKO 采集成功",
            "netconf_result": None,
            "netmiko_result": {"success": True},
            "snmp_result": None,
            "restconf_result": None,
            "telemetry_result": None,
        }

        request = self.factory.post(
            "/base_platform/device_api/collection-plans/1/validate/",
            {"device_ip": "10.0.0.1", "use_local": True},
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"post": "validate_plan"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["success_count"], 1)
        self.assertEqual(payload["data"]["skipped_count"], 1)
        self.assertEqual(payload["data"]["results"]["arp"][0]["status"], "success")
        self.assertEqual(payload["data"]["results"]["mac"][0]["status"], "skipped")
        mock_execute_local.assert_called_once_with(arp_plan, device)

    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_validate_plan_requires_south_driver_when_not_local(self, mock_get_object):
        summary_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            is_active=True,
            collect_plans=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id=11,
                        name="summary-plan-arp",
                        collection_type="arp",
                        netmiko_enabled=True,
                        netconf_enabled=False,
                        snmp_enabled=False,
                        restconf_enabled=False,
                        telemetry_enabled=False,
                    )
                ]
            ),
        )
        mock_get_object.return_value = summary_plan

        request = self.factory.post(
            "/base_platform/device_api/collection-plans/1/validate/",
            {"device_ip": "10.0.0.1"},
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"post": "validate_plan"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertIn("south_driver", payload["message"])

    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_validate_execution_params_allows_local_snmp_when_community_configured(
        self,
        mock_device_objects,
    ):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            ssh_account=None,
            netconf_account=None,
            snmp_community="public",
        )
        queryset = Mock()
        queryset.exists.return_value = True
        queryset.first.return_value = device
        mock_device_objects.select_related.return_value.filter.return_value = queryset
        plan = SimpleNamespace(
            netmiko_enabled=False,
            netconf_enabled=False,
            snmp_enabled=True,
            restconf_enabled=False,
            telemetry_enabled=False,
        )

        is_valid, message, result_device = DeviceSubCollectionPlanViewSet.validate_execution_params(
            plan,
            "10.0.0.1",
            "both",
            use_local=True,
        )

        self.assertTrue(is_valid)
        self.assertEqual(message, "验证通过")
        self.assertIs(result_device, device)

    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_validate_execution_params_rejects_snmp_only_plan_for_southbound(
        self,
        mock_device_objects,
    ):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            ssh_account=None,
            netconf_account=None,
            snmp_community="public",
        )
        queryset = Mock()
        queryset.exists.return_value = True
        queryset.first.return_value = device
        mock_device_objects.select_related.return_value.filter.return_value = queryset
        plan = SimpleNamespace(
            netmiko_enabled=False,
            netconf_enabled=False,
            snmp_enabled=True,
            restconf_enabled=False,
            telemetry_enabled=False,
        )

        is_valid, message, result_device = DeviceSubCollectionPlanViewSet.validate_execution_params(
            plan,
            "10.0.0.1",
            "both",
            use_local=False,
        )

        self.assertFalse(is_valid)
        self.assertIn("南向驱动验证当前仅支持NETMIKO/NETCONF", message)
        self.assertIsNone(result_device)

    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_validate_execution_params_rejects_telemetry_only_plan_for_local(
        self,
        mock_device_objects,
    ):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            ssh_account=None,
            netconf_account=None,
            snmp_community="public",
        )
        queryset = Mock()
        queryset.exists.return_value = True
        queryset.first.return_value = device
        mock_device_objects.select_related.return_value.filter.return_value = queryset
        plan = SimpleNamespace(
            netmiko_enabled=False,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=True,
        )

        is_valid, message, result_device = DeviceSubCollectionPlanViewSet.validate_execution_params(
            plan,
            "10.0.0.1",
            "both",
            use_local=True,
        )

        self.assertFalse(is_valid)
        self.assertIn("Telemetry 仍在延期范围", message)
        self.assertIsNone(result_device)

    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_validate_execution_params_rejects_ambiguous_manage_ip_without_serial_num(
        self,
        mock_device_objects,
    ):
        queryset = Mock()
        queryset.exists.return_value = True
        queryset.count.return_value = 2
        mock_device_objects.select_related.return_value.filter.return_value = queryset
        plan = SimpleNamespace(
            netmiko_enabled=True,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )

        is_valid, message, result_device = DeviceSubCollectionPlanViewSet.validate_execution_params(
            plan,
            "10.0.0.1",
            "both",
            use_local=True,
        )

        self.assertFalse(is_valid)
        self.assertIn("命中多条资产", message)
        self.assertIsNone(result_device)

    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_validate_execution_params_allows_serial_num_to_disambiguate_manage_ip(
        self,
        mock_device_objects,
    ):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            ssh_account=SimpleNamespace(id=1),
            netconf_account=None,
            snmp_community="public",
        )
        queryset = Mock()
        queryset.exists.return_value = True
        queryset.first.return_value = device
        mock_device_objects.select_related.return_value.filter.return_value = queryset
        plan = SimpleNamespace(
            netmiko_enabled=True,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )

        is_valid, message, result_device = DeviceSubCollectionPlanViewSet.validate_execution_params(
            plan,
            "10.0.0.1",
            "both",
            use_local=True,
            serial_num="SER-1",
        )

        self.assertTrue(is_valid)
        self.assertEqual(message, "验证通过")
        self.assertIs(result_device, device)

    @patch("apps.device_api.views.DeviceCollectionService.execute_both_collection_local")
    @patch("apps.device_api.views.DeviceSubCollectionPlanViewSet.validate_execution_params")
    @patch.object(DeviceSubCollectionPlanViewSet, "get_object")
    def test_execute_sub_plan_local_uses_local_executor(
        self,
        mock_get_object,
        mock_validate_params,
        mock_execute_local,
    ):
        plan = SimpleNamespace(name="arp-plan")
        device = SimpleNamespace(manage_ip="10.0.0.1")
        mock_get_object.return_value = plan
        mock_validate_params.return_value = (True, "验证通过", device)
        mock_execute_local.return_value = {
            "success": True,
            "message": "NETMIKO 采集成功",
            "netconf_result": None,
            "netmiko_result": {"success": True},
            "snmp_result": None,
            "restconf_result": None,
            "telemetry_result": None,
        }

        request = self.factory.post(
            "/base_platform/device_api/sub-collection-plan/11/execute_sub_plan/",
            {"device_ip": "10.0.0.1", "use_local": True},
            format="json",
        )
        response = DeviceSubCollectionPlanViewSet.as_view({"post": "execute_sub_plan"})(request, pk="11")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        mock_execute_local.assert_called_once_with(plan, device)

    @patch("apps.device_api.views.MongoOps")
    @patch("apps.device_api.views.COLLECTION_SUB_PLAN")
    def test_sub_collection_detail_filters_latest_batch(self, mock_sub_plan_collection, mock_mongo_ops):
        mock_sub_plan_collection.coll.find_one.return_value = {
            "summary_plan_id": 1,
            "collection_type": "arp",
            "collection_method": "netmiko",
            "execute_time": "2026-03-12T10:00:00",
        }
        collection_db = Mock()
        collection_db.coll.count_documents.return_value = 0
        collection_db.coll.aggregate.return_value = []
        mock_mongo_ops.return_value = collection_db

        request = self.factory.get(
            "/base_platform/device_api/collection-results/sub_collection_detail/",
            {"summary_plan_id": "1", "collection_type": "arp", "page": "1", "page_size": "10"},
        )
        response = CollectionResultViewSet.as_view({"get": "sub_collection_detail"})(request)

        self.assertEqual(response.status_code, 200)
        expected_query = {
            "summary_plan_id": 1,
            "collection_type": "arp",
            "execute_time": "2026-03-12T10:00:00",
        }
        collection_db.coll.count_documents.assert_called_once_with(expected_query)
        pipeline = collection_db.coll.aggregate.call_args[0][0]
        self.assertEqual(pipeline[0], {"$match": expected_query})

    @patch("apps.device_api.views.COLLECTION_SUB_PLAN")
    def test_parent_collection_list_returns_empty_when_sub_plan_filter_has_no_runs(
        self,
        mock_sub_plan_collection,
    ):
        mock_sub_plan_collection.coll.find.return_value = []

        request = self.factory.get(
            "/base_platform/device_api/collection-results/parent_collection_list/",
            {"sub_plan_id": "11"},
        )
        response = CollectionResultViewSet.as_view({"get": "parent_collection_list"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["results"], [])
        self.assertEqual(payload["data"]["total"], 0)

    def test_parent_collection_list_rejects_invalid_page(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/parent_collection_list/",
            {"page": "bad"},
        )
        response = CollectionResultViewSet.as_view({"get": "parent_collection_list"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["message"], "分页参数无效")

    def test_sub_collection_detail_rejects_invalid_page(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/sub_collection_detail/",
            {"summary_plan_id": "1", "page": "bad"},
        )
        response = CollectionResultViewSet.as_view({"get": "sub_collection_detail"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["message"], "分页参数无效")

    @patch("apps.device_api.views.COLLECTION_SUB_PLAN")
    @patch("apps.device_api.views.COLLECTION_PLAN")
    @patch("apps.device_api.views.PlansToDevice.objects")
    def test_device_traceability_returns_latest_execution_chain(
        self,
        mock_plan_to_device_objects,
        mock_collection_plan,
        mock_collection_sub_plan,
    ):
        summary_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            vendor="Huawei",
            device_type="switch",
            is_active=True,
            collect_plans=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id=11,
                        name="summary-plan-arp",
                        collection_type="arp",
                        description="ARP collect",
                        netmiko_enabled=True,
                        netconf_enabled=False,
                        snmp_enabled=False,
                        restconf_enabled=False,
                        telemetry_enabled=False,
                    )
                ]
            ),
        )
        relation = SimpleNamespace(
            id=101,
            manage_ip="10.0.0.1",
            use_local=True,
            execute_node="",
            plan=summary_plan,
        )
        mock_plan_to_device_objects.select_related.return_value.filter.return_value = [relation]
        mock_collection_plan.coll.find.return_value = [
            {
                "summary_plan_id": 1,
                "device_ip": "10.0.0.1",
                "device_name": "sw-a",
                "idc_name": "IDC-A",
                "task_status": "success",
                "execute_time": "2026-03-14 10:00:00",
                "sub_plans_count": 1,
                "log_time": 100.0,
            }
        ]
        mock_collection_sub_plan.coll.find.return_value = [
            {
                "summary_plan_id": 1,
                "plan_id": 11,
                "device_ip": "10.0.0.1",
                "collection_type": "arp",
                "collection_method": "netmiko",
                "task_status": "finished",
                "task_errors": [],
                "execute_time": "2026-03-14 10:00:00",
                "log_time": 101.0,
            }
        ]

        request = self.factory.get(
            "/base_platform/device_api/collection-results/device_traceability/",
            {"manage_ip": "10.0.0.1"},
        )
        response = CollectionResultViewSet.as_view({"get": "device_traceability"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["count"], 1)
        plan_item = payload["data"]["results"][0]
        self.assertEqual(plan_item["summary_plan"]["name"], "summary-plan")
        self.assertEqual(plan_item["latest_execution"]["device_name"], "sw-a")
        self.assertEqual(plan_item["sub_plans"][0]["latest_run"]["task_status"], "finished")
        self.assertEqual(
            plan_item["sub_plans"][0]["latest_run"]["detail_query"]["collection_type"],
            "arp",
        )

    def test_device_traceability_requires_manage_ip(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/device_traceability/",
            {},
        )
        response = CollectionResultViewSet.as_view({"get": "device_traceability"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertIn("manage_ip", payload["message"])

    @patch("apps.device_api.views.DeviceCollectionPlansDetailSerializer")
    @patch("apps.device_api.views.DeviceCollectionService.sync_summary_plan_sub_plans")
    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_sync_collect_plans_returns_sync_summary(
        self,
        mock_get_object,
        mock_sync,
        mock_serializer_cls,
    ):
        summary_plan = SimpleNamespace(id=1, name="summary-plan", refresh_from_db=Mock())
        mock_get_object.return_value = summary_plan
        mock_sync.return_value = {
            "created_count": 2,
            "created_types": ["route_table", "bgp_neighbors"],
            "total_types": 15,
        }
        mock_serializer_cls.return_value = SimpleNamespace(data={"id": 1, "name": "summary-plan"})

        request = self.factory.post(
            "/base_platform/device_api/collection-plans/1/sync_collect_plans/",
            {},
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"post": "sync_collect_plans"})(request, pk="1")

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["created_count"], 2)
        self.assertEqual(payload["data"]["created_types"], ["route_table", "bgp_neighbors"])
        mock_sync.assert_called_once_with(summary_plan)
        summary_plan.refresh_from_db.assert_called_once()

    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_collection_plan_field_mappings_returns_grouped_payload(self, mock_get_object):
        arp_plan = SimpleNamespace(
            id=11,
            name="summary-plan-arp",
            collection_type="arp",
            netmiko_path="data.arp",
            netmiko_field_mappings={"ipaddress": "ip"},
            netconf_path="top.arp",
            netconf_field_mappings={"ipaddress": "Ipv4Address"},
            snmp_path="",
            snmp_field_mappings={},
            restconf_path="",
            restconf_field_mappings={},
            telemetry_path="",
            telemetry_field_mappings={},
        )
        mac_plan = SimpleNamespace(
            id=12,
            name="summary-plan-mac",
            collection_type="mac",
            netmiko_path="",
            netmiko_field_mappings={},
            netconf_path="",
            netconf_field_mappings={},
            snmp_path="",
            snmp_field_mappings={},
            restconf_path="",
            restconf_field_mappings={},
            telemetry_path="",
            telemetry_field_mappings={},
        )
        summary_plan = SimpleNamespace(
            enabled_collection_types=["arp"],
            collect_plans=SimpleNamespace(all=lambda: [arp_plan, mac_plan]),
        )
        mock_get_object.return_value = summary_plan

        request = self.factory.get("/base_platform/device_api/collection-plans/1/field-mappings/")
        response = DeviceCollectionPlansViewSet.as_view({"get": "field_mappings"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["arp"]["netmiko_path"], "data.arp")
        self.assertTrue(payload["data"]["arp"]["enabled"])
        self.assertFalse(payload["data"]["mac"]["enabled"])
        self.assertIn("ipaddress", payload["data"]["arp"]["output_fields"])

    @patch("apps.device_api.views.DeviceCollectionService.sync_summary_plan_sub_plans")
    @patch.object(DeviceCollectionPlansViewSet, "get_object")
    def test_collection_plan_field_mappings_patch_updates_sub_plan_fields(
        self,
        mock_get_object,
        mock_sync,
    ):
        arp_plan = SimpleNamespace(
            id=11,
            name="summary-plan-arp",
            collection_type="arp",
            netmiko_path="old.path",
            netmiko_field_mappings={"old": "value"},
            netconf_path="",
            netconf_field_mappings={},
            snmp_path="",
            snmp_field_mappings={},
            restconf_path="",
            restconf_field_mappings={},
            telemetry_path="",
            telemetry_field_mappings={},
            save=Mock(),
        )
        summary_plan = SimpleNamespace(
            enabled_collection_types=["arp"],
            collection_method="both",
            collect_plans=SimpleNamespace(all=lambda: [arp_plan]),
        )
        mock_get_object.return_value = summary_plan
        mock_sync.return_value = {
            "created_count": 0,
            "created_types": [],
            "updated_count": 0,
            "updated_types": [],
            "disabled_count": 0,
            "disabled_types": [],
        }

        request = self.factory.patch(
            "/base_platform/device_api/collection-plans/1/field-mappings/",
            {
                "arp": {
                    "netmiko_path": "data.items[*]",
                    "netmiko_field_mappings": {"ipaddress": "ip"},
                }
            },
            format="json",
        )
        response = DeviceCollectionPlansViewSet.as_view({"patch": "field_mappings"})(request, pk="1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(arp_plan.netmiko_path, "data.items[*]")
        self.assertEqual(arp_plan.netmiko_field_mappings, {"ipaddress": "ip"})
        arp_plan.save.assert_called_once()
        self.assertEqual(payload["data"]["arp"]["netmiko_path"], "data.items[*]")

    @patch("apps.device_api.views.PlatformProfileService.auto_bind_devices")
    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_plans_to_device_auto_bind_endpoint(self, mock_device_objects, mock_auto_bind):
        mock_queryset = Mock()
        filtered_devices = [SimpleNamespace(serial_num="SER-1", manage_ip="10.0.0.1")]
        mock_device_objects.filter.return_value.select_related.return_value = mock_queryset
        mock_queryset.filter.return_value = filtered_devices
        mock_auto_bind.return_value = {"created": 1, "updated": 0, "skipped": 0, "results": []}

        request = self.factory.post(
            "/base_platform/device_api/plans-to-device/auto_bind/",
            {"manage_ip": "10.0.0.1"},
            format="json",
        )
        response = PlansToDeviceViewSet.as_view({"post": "auto_bind"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        mock_auto_bind.assert_called_once_with(filtered_devices)

    def test_collection_rule_tool_returns_cmdb_fields(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-rule-tools/",
            {"get_cmdb_field": "1"},
        )
        response = DeviceCollectionRuleToolView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        values = {item["value"] for item in payload["data"]}
        self.assertIn("manage_ip", values)

    @patch("apps.device_api.views.MongoOps")
    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_collection_results_latest_returns_grouped_records(self, mock_device_objects, mock_mongo_ops):
        mock_device_objects.filter.return_value.first.return_value = SimpleNamespace(
            serial_num="SER-1",
            manage_ip="10.0.0.1",
        )
        collection_db = Mock()
        collection_db.coll.find.return_value.sort.return_value.limit.return_value = [
            {"hostip": "10.0.0.1", "execute_time": "2026-03-15 10:00:00"}
        ]
        mock_mongo_ops.return_value = collection_db

        request = self.factory.get(
            "/base_platform/device_api/collection-results/latest/",
            {"serial_num": "SER-1", "collection_type": "arp"},
        )
        response = CollectionResultViewSet.as_view({"get": "latest"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["manage_ip"], "10.0.0.1")
        self.assertEqual(payload["data"]["results"][0]["collection_type"], "arp")
        collection_db.coll.find.return_value.sort.assert_called_once_with(
            [("execute_time", -1), ("log_time", -1)]
        )

    @patch("apps.device_api.views.MongoOps")
    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_collection_results_latest_accepts_manage_ip_without_serial_num(
        self,
        mock_device_objects,
        mock_mongo_ops,
    ):
        mock_device_objects.filter.return_value.first.return_value = SimpleNamespace(
            serial_num="SER-1",
            manage_ip="10.0.0.1",
        )
        collection_db = Mock()
        collection_db.coll.find.return_value.sort.return_value.limit.return_value = [
            {"hostip": "10.0.0.1", "execute_time": "2026-03-15 10:00:00"}
        ]
        mock_mongo_ops.return_value = collection_db

        request = self.factory.get(
            "/base_platform/device_api/collection-results/latest/",
            {"manage_ip": "10.0.0.1", "collection_type": "arp"},
        )
        response = CollectionResultViewSet.as_view({"get": "latest"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["serial_num"], "SER-1")
        self.assertEqual(payload["data"]["manage_ip"], "10.0.0.1")

    @patch("apps.device_api.views.COLLECTION_PLAN")
    def test_collection_results_batch_gate_metrics_returns_latest_batch_summary(
        self,
        mock_collection_plan,
    ):
        latest_find_cursor = Mock()
        latest_find_cursor.sort.return_value.limit.return_value = [
            {"execute_time": "2026-03-17 01:00:00"}
        ]

        detail_find_cursor = [
            {
                "task_status": "success",
                "failed_details": [],
                "skipped_details": [],
            },
            {
                "task_status": "partial_success",
                "failed_details": [{"collection_method": "netmiko", "reason": "ssh_timeout"}],
                "skipped_details": [{"collection_method": "telemetry", "reason": "telemetry_deferred"}],
            },
        ]

        def _find_side_effect(query, projection=None):
            if projection and "execute_time" in projection:
                return latest_find_cursor
            return detail_find_cursor

        mock_collection_plan.coll.find.side_effect = _find_side_effect

        request = self.factory.get(
            "/base_platform/device_api/collection-results/batch_gate_metrics/",
            {},
        )
        response = CollectionResultViewSet.as_view({"get": "batch_gate_metrics"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["execute_time"], "2026-03-17 01:00:00")
        self.assertEqual(payload["data"]["parent_metrics"]["total"], 2)
        self.assertEqual(payload["data"]["parent_metrics"]["success"], 1)
        self.assertEqual(payload["data"]["parent_metrics"]["partial_success"], 1)
        self.assertEqual(payload["data"]["parent_metrics"]["success_rate"], 50.0)
        self.assertEqual(payload["data"]["protocol_failures"]["netmiko"], 1)
        self.assertEqual(payload["data"]["skip_reasons"]["telemetry_deferred"], 1)

    @patch("apps.device_api.views.COLLECTION_RESULTS_DB")
    def test_collection_results_by_plan_uses_filters(self, mock_results_db):
        record = {
            "_id": ObjectId(),
            "plan_id": 11,
            "plan_name": "arp-plan",
            "device_ip": "10.0.0.1",
            "device_name": "sw-a",
            "idc_name": "IDC-A",
            "device_type": "switch",
            "vendor": "Huawei",
            "collection_method": "netmiko",
            "method_name": "display arp",
            "collected_at": "2026-03-16T10:00:00",
            "status": "success",
            "data": [],
            "processed_data": [],
        }
        mock_results_db.coll.find.return_value.sort.return_value.limit.return_value = [record]

        request = self.factory.get(
            "/base_platform/device_api/collection-results/by_plan/",
            {"plan_id": "11", "collection_method": "netmiko", "status": "success"},
        )
        response = CollectionResultViewSet.as_view({"get": "by_plan"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        mock_results_db.coll.find.assert_called_once_with(
            {"plan_id": 11, "collection_method": "netmiko", "status": "success"}
        )
        self.assertEqual(payload["latest_count"], 1)

    def test_collection_results_list_rejects_invalid_query_params(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/list_results/",
            {"page": "bad"},
        )
        response = CollectionResultViewSet.as_view({"get": "list_results"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertIn("page", payload["data"])

    def test_collection_results_result_detail_rejects_invalid_object_id(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/result_detail/",
            {"result_id": "not-an-object-id"},
        )
        response = CollectionResultViewSet.as_view({"get": "result_detail"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertIn("无效的结果ID格式", payload["message"])

    @patch("apps.device_api.views.COLLECTION_RESULTS_DB")
    def test_collection_results_result_detail_returns_not_found(self, mock_results_db):
        mock_results_db.find.return_value = []
        result_id = str(ObjectId())

        request = self.factory.get(
            "/base_platform/device_api/collection-results/result_detail/",
            {"result_id": result_id},
        )
        response = CollectionResultViewSet.as_view({"get": "result_detail"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 404)
        self.assertEqual(payload["message"], "采集结果不存在")

    def test_sub_collection_detail_requires_query_filters(self):
        request = self.factory.get(
            "/base_platform/device_api/collection-results/sub_collection_detail/",
            {},
        )
        response = CollectionResultViewSet.as_view({"get": "sub_collection_detail"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["message"], "缺少查询条件")

    @patch("apps.device_api.views.DeviceDiscoveryState.objects")
    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_device_facts_api_returns_discovered_fields(self, mock_device_objects, mock_state_objects):
        vendor = Vendor(name="Huawei", alias="Huawei")
        category = Category(name="switch")
        model = Model(name="CE8850", vendor=vendor)
        device = NetworkDevice(
            serial_num="SER-1",
            manage_ip="10.0.0.1",
            name="sw-a",
            vendor=vendor,
            category=category,
            model=model,
            soft_version="V200",
            patch_version="SP1",
        )
        mock_device_objects.select_related.return_value.filter.return_value.first.return_value = device
        mock_state_objects.filter.return_value.first.return_value = DeviceDiscoveryState(
            device_serial_num="SER-1",
            profile_code="Huawei-CE",
            last_discovery_status="success",
            last_discovery_error="",
        )

        request = self.factory.get("/base_platform/device_api/devices/SER-1/facts/")
        response = DeviceFactsAPIView.as_view()(request, serial_num="SER-1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["profile_code"], "Huawei-CE")
        self.assertEqual(payload["data"]["vendor_alias"], "Huawei")

    @patch("apps.device_api.views.PlatformProfileService.build_capabilities")
    @patch("apps.device_api.views.NetworkDevice.objects")
    def test_device_capabilities_api_returns_profile_payload(
        self,
        mock_device_objects,
        mock_build_capabilities,
    ):
        mock_device_objects.select_related.return_value.filter.return_value.first.return_value = SimpleNamespace(
            serial_num="SER-1",
            manage_ip="10.0.0.1",
        )
        mock_build_capabilities.return_value = {
            "serial_num": "SER-1",
            "manage_ip": "10.0.0.1",
            "profile_code": "Huawei-CE",
            "supported_collection_types": ["device_identity", "arp"],
            "preferred_methods": {"arp": ["netconf", "netmiko"]},
            "fallback_methods": {"arp": ["netmiko"]},
            "bindings": [],
        }

        request = self.factory.get("/base_platform/device_api/devices/SER-1/capabilities/")
        response = DeviceCapabilitiesAPIView.as_view()(request, serial_num="SER-1")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["profile_code"], "Huawei-CE")


class DeviceApiSerializerTests(SimpleTestCase):
    def test_plan_create_serializer_rejects_unknown_enabled_collection_type(self):
        serializer = DeviceCollectionPlansCreateSerializer(
            data={
                "name": "summary-plan",
                "vendor": "Huawei",
                "device_type": "switch",
                "enabled_collection_types": ["arp", "not-supported"],
                "collection_method": "both",
                "is_active": True,
            }
        )
        serializer.fields["name"].validators = []

        with patch("apps.device_api.serializers.DeviceCollectionPlans.objects.filter") as mock_filter:
            mock_filter.return_value.exists.return_value = False
            self.assertFalse(serializer.is_valid())

        self.assertIn("enabled_collection_types", serializer.errors)

    @patch("apps.device_api.serializers.transaction.atomic")
    @patch("apps.device_api.serializers.DeviceCollectionService.sync_summary_plan_sub_plans")
    @patch("apps.device_api.serializers.DeviceCollectionPlans.objects")
    def test_plan_create_serializer_calls_parent_sync_service(
        self,
        mock_plan_objects,
        mock_sync_sub_plans,
        mock_atomic,
    ):
        serializer = DeviceCollectionPlansCreateSerializer(
            data={
                "name": "summary-plan",
                "vendor": "Huawei",
                "device_type": "switch",
                "enabled_collection_types": ["arp", "mac"],
                "collection_method": "both",
                "is_active": True,
            }
        )
        serializer.fields["name"].validators = []
        mock_plan_objects.filter.return_value.exists.return_value = False
        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = False
        created_plan = SimpleNamespace(
            id=1,
            name="summary-plan",
            vendor="Huawei",
            device_type="switch",
            enabled_collection_types=["arp", "mac"],
            collection_method="both",
            profile_code="",
        )
        mock_plan_objects.create.return_value = created_plan

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        mock_sync_sub_plans.assert_called_once_with(created_plan)

    def test_sub_plan_serializer_exposes_extended_protocol_fields(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        sub_plan = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan",
            collection_type="arp",
            description="desc",
            snmp_enabled=True,
            snmp_version="v2c",
            snmp_oids=["1.3.6.1.2.1.1.1.0"],
            restconf_enabled=True,
            restconf_endpoint="/restconf/data/example",
            telemetry_enabled=True,
            telemetry_subscription_path="/interfaces/interface/state",
        )

        data = DeviceSubCollectionPlanSerializer(sub_plan).data

        self.assertTrue(data["snmp_enabled"])
        self.assertEqual(data["snmp_version"], "v2c")
        self.assertEqual(data["snmp_oids"], ["1.3.6.1.2.1.1.1.0"])
        self.assertTrue(data["restconf_enabled"])
        self.assertEqual(data["restconf_endpoint"], "/restconf/data/example")
        self.assertTrue(data["telemetry_enabled"])
        self.assertEqual(data["telemetry_subscription_path"], "/interfaces/interface/state")

    def test_update_serializer_allows_partial_update_with_existing_xml_templates(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        instance = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan",
            collection_type="arp",
            netmiko_enabled=False,
            netconf_enabled=True,
        )

        serializer = DeviceSubCollectionPlanUpdateSerializer(
            instance=instance,
            data={"description": "updated"},
            partial=True,
        )

        with patch.object(serializer, "_instance_has_xml_templates", return_value=True):
            self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_serializer_allows_partial_update_for_snmp_only_plan(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        instance = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan-snmp",
            collection_type="arp",
            netmiko_enabled=False,
            netconf_enabled=False,
            snmp_enabled=True,
            snmp_oids=["1.3.6.1.2.1.1.1.0"],
        )

        serializer = DeviceSubCollectionPlanUpdateSerializer(
            instance=instance,
            data={"description": "updated"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_serializer_rejects_non_get_restconf_method(self):
        serializer = DeviceSubCollectionPlanCreateSerializer(
            data={
                "summary_plan_id": "1",
                "name": "sub-plan-restconf",
                "collection_type": "arp",
                "restconf_enabled": True,
                "restconf_endpoint": "/restconf/data/example",
                "restconf_method": "POST",
            }
        )
        serializer.fields["name"].validators = []

        with patch("apps.device_api.serializers.DeviceCollectionPlans.objects.get", return_value=DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")):
            self.assertFalse(serializer.is_valid())
        self.assertIn("当前RESTCONF仅支持GET方法", str(serializer.errors))

    def test_update_serializer_rejects_existing_non_get_restconf_method(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        instance = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan-restconf",
            collection_type="arp",
            restconf_enabled=True,
            restconf_endpoint="/restconf/data/example",
            restconf_method="POST",
        )

        serializer = DeviceSubCollectionPlanUpdateSerializer(
            instance=instance,
            data={"description": "updated"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("当前RESTCONF仅支持GET方法", str(serializer.errors))

    def test_create_serializer_requires_summary_plan_id(self):
        serializer = DeviceSubCollectionPlanCreateSerializer(
            data={
                "name": "sub-plan-netmiko",
                "collection_type": "arp",
                "netmiko_enabled": True,
            }
        )
        serializer.fields["name"].validators = []

        self.assertFalse(serializer.is_valid())
        self.assertIn("summary_plan_id", serializer.errors)

    def test_create_serializer_requires_xml_templates_when_netconf_enabled(self):
        serializer = DeviceSubCollectionPlanCreateSerializer(
            data={
                "summary_plan_id": "1",
                "name": "sub-plan-netconf",
                "collection_type": "arp",
                "netconf_enabled": True,
                "xml_templates": [],
            }
        )
        serializer.fields["name"].validators = []

        with patch(
            "apps.device_api.serializers.DeviceCollectionPlans.objects.get",
            return_value=DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch"),
        ):
            self.assertFalse(serializer.is_valid())

        self.assertIn("启用NETCONF时必须提供XML模板", str(serializer.errors))

    def test_create_serializer_requires_snmp_oids_when_snmp_enabled(self):
        serializer = DeviceSubCollectionPlanCreateSerializer(
            data={
                "summary_plan_id": "1",
                "name": "sub-plan-snmp",
                "collection_type": "arp",
                "snmp_enabled": True,
                "snmp_oids": [],
            }
        )
        serializer.fields["name"].validators = []

        with patch(
            "apps.device_api.serializers.DeviceCollectionPlans.objects.get",
            return_value=DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch"),
        ):
            self.assertFalse(serializer.is_valid())

        self.assertIn("启用SNMP时必须提供至少一个OID", str(serializer.errors))

    def test_update_serializer_requires_existing_templates_when_netconf_remains_enabled(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        instance = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan-netconf",
            collection_type="arp",
            netconf_enabled=True,
        )

        serializer = DeviceSubCollectionPlanUpdateSerializer(
            instance=instance,
            data={"description": "updated"},
            partial=True,
        )

        with patch.object(serializer, "_instance_has_xml_templates", return_value=False):
            self.assertFalse(serializer.is_valid())

        self.assertIn("启用NETCONF时必须提供XML模板", str(serializer.errors))

    def test_update_serializer_requires_telemetry_path_when_enabled(self):
        summary_plan = DeviceCollectionPlans(name="summary", vendor="Huawei", device_type="switch")
        instance = DeviceSubCollectionPlan(
            summary_plan=summary_plan,
            name="sub-plan-telemetry",
            collection_type="arp",
            telemetry_enabled=True,
            telemetry_subscription_path="",
        )

        serializer = DeviceSubCollectionPlanUpdateSerializer(
            instance=instance,
            data={"description": "updated"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("启用Telemetry时必须提供订阅路径", str(serializer.errors))


class DeviceApiModelApiTests(SimpleTestCase):
    @staticmethod
    def _build_plan(vendor="Huawei", device_type="switch", collection_type="arp"):
        return SimpleNamespace(
            name=f"{vendor}-{collection_type}-plan",
            collection_type=collection_type,
            summary_plan=SimpleNamespace(vendor=vendor, device_type=device_type),
        )

    def test_apply_field_mappings_supports_nested_array_paths(self):
        raw_data = {
            "device_ip": "10.0.0.1",
            "meta": {"hostname": "switch-a"},
            "top": {
                "ARP": {
                    "ARPTable": {
                        "ARPEntry": [
                            {
                                "Ipv4": {"Address": "10.0.0.2"},
                                "Interface": {"Name": "GE1/0/1"},
                            },
                            {
                                "Ipv4": {"Address": "10.0.0.3"},
                                "Interface": {"Name": "GE1/0/2"},
                            },
                        ]
                    }
                }
            },
        }
        field_mappings = {
            "ipaddress": {"sort": 1, "value": "top.ARP.ARPTable.ARPEntry[*].Ipv4.Address"},
            "hostname": {"sort": 2, "value": "meta.hostname"},
            "interface": {"sort": 3, "value": "top.ARP.ARPTable.ARPEntry[*].Interface.Name"},
        }

        result = apply_field_mappings(raw_data, field_mappings)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ipaddress"], "10.0.0.2")
        self.assertEqual(result[0]["hostname"], "switch-a")
        self.assertEqual(result[0]["interface"], "GE1/0/1")
        self.assertEqual(result[0]["hostip"], "10.0.0.1")
        self.assertIsInstance(result[0]["log_time"], datetime)

    def test_apply_field_mappings_supports_path_config_and_literal_values(self):
        raw_data = {
            "device_ip": "10.0.0.1",
            "payload": {
                "items": [
                    {"ip": "10.0.0.2", "meta": {"port": "GE1/0/1"}},
                    {"ip": "10.0.0.3", "meta": {"port": "GE1/0/2"}},
                ]
            },
        }
        field_mappings = {
            "interface": {"sort": 1, "value": "meta.port"},
            "ipaddress": {"sort": 2, "value": "ip"},
            "type": {"sort": 3, "value": "dynamic"},
        }

        result = apply_field_mappings(
            raw_data,
            field_mappings,
            path_config="payload.items",
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["interface"], "GE1/0/1")
        self.assertEqual(result[0]["ipaddress"], "10.0.0.2")
        self.assertEqual(result[0]["type"], "dynamic")

    def test_apply_field_mappings_returns_empty_for_missing_nested_array(self):
        result = apply_field_mappings(
            {"payload": {"items": {"ip": "10.0.0.2"}}},
            {"ipaddress": {"sort": 1, "value": "payload.items[*].ip"}},
        )

        self.assertEqual(result, [])

    @patch("apps.device_api.models_api.get_vendor_class")
    @patch("apps.device_api.processors.base.ProcessorRegistry.get_processor")
    def test_resolve_raw_data_prefers_registered_processor_and_skips_tools(
        self,
        mock_get_processor,
        mock_get_vendor_class,
    ):
        plan = self._build_plan(collection_type="arp")
        mock_get_processor.return_value = lambda raw: [{"ipaddress": "10.0.0.2"}]

        status, error, processed = resolve_raw_data(
            plan,
            {"data": [{"ipaddress": "10.0.0.2"}], "device_ip": "10.0.0.1"},
            "netmiko",
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["ipaddress"], "10.0.0.2")
        self.assertEqual(processed[0]["manage_ip"], "10.0.0.1")
        mock_get_vendor_class.assert_not_called()

    @patch("apps.device_api.processors.base.ProcessorRegistry.get_processor")
    def test_resolve_raw_data_falls_back_to_tools_after_not_implemented_processor(
        self,
        mock_get_processor,
    ):
        def todo_processor(_):
            raise NotImplementedError("todo")

        plan = self._build_plan(vendor="Huawei", collection_type="arp")
        mock_get_processor.return_value = todo_processor

        status, error, processed = resolve_raw_data(
            plan,
            {
                "data": [
                    {
                        "ipaddress": "10.0.0.2",
                        "interface": "GE1/0/1",
                        "macaddress": "aaaa-bbbb-cccc",
                    }
                ],
                "device_ip": "10.0.0.1",
            },
            "netmiko",
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["ipaddress"], "10.0.0.2")
        self.assertEqual(processed[0]["manage_ip"], "10.0.0.1")

    @patch("apps.device_api.models_api.get_vendor_class")
    @patch("apps.device_api.processors.base.ProcessorRegistry.get_processor", return_value=None)
    def test_resolve_raw_data_returns_netconf_error_when_processor_missing(
        self,
        mock_get_processor,
        mock_get_vendor_class,
    ):
        plan = self._build_plan(vendor="Cisco", collection_type="arp")

        status, error, processed = resolve_raw_data(
            plan,
            {"data": {"top": {}}, "device_ip": "10.0.0.1"},
            "netconf",
        )

        self.assertFalse(status)
        self.assertIn("netconf_no_processor", error)
        self.assertEqual(processed, [])
        mock_get_vendor_class.assert_not_called()

    @patch("apps.device_api.models_api.importlib.import_module")
    def test_ensure_processors_bootstrapped_imports_once(self, mock_import_module):
        with patch("apps.device_api.models_api._processors_bootstrapped", False):
            ensure_processors_bootstrapped()
            ensure_processors_bootstrapped()

        self.assertEqual(mock_import_module.call_count, 6)

    def test_ruijie_cisco_hillstone_processors_registered_for_main_matrix_types(self):
        for vendor in (
            "Ruijie",
            "Cisco",
            "Hillstone",
            "ZTE",
            "Maipu",
            "Mellanox",
            "centec",
        ):
            for collection_type in (
                "arp",
                "mac",
                "lldp",
                "interface_brief",
                "ip_interface",
                "aggre_port",
            ):
                with self.subTest(vendor=vendor, collection_type=collection_type):
                    processor = get_processor(vendor, "switch", collection_type, "netmiko")
                    self.assertIsNotNone(processor)


class DeviceApiP3GoldenSampleTests(SimpleTestCase):
    @staticmethod
    def _build_plan(collection_type):
        return SimpleNamespace(
            name=f"Ruijie-{collection_type}-plan",
            collection_type=collection_type,
            summary_plan=SimpleNamespace(vendor="Ruijie", device_type="switch"),
        )

    def _assert_ruijie_golden_sample(self, collection_type, command_result):
        plan = self._build_plan(collection_type=collection_type)
        status, error, processed = resolve_raw_data(
            plan,
            {"data": command_result, "device_ip": "10.0.0.1"},
            "netmiko",
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        legacy_result = getattr(RuiJiePlan, f"get_{collection_type}")(command_result)
        expected = normalize_processed_data(collection_type, legacy_result)
        for item in expected:
            item["manage_ip"] = "10.0.0.1"
        self.assertEqual(processed, expected)

    def _assert_vendor_golden_sample(self, vendor, collection_type, command_result, tool_class):
        plan = SimpleNamespace(
            name=f"{vendor}-{collection_type}-plan",
            collection_type=collection_type,
            summary_plan=SimpleNamespace(vendor=vendor, device_type="switch"),
        )
        status, error, processed = resolve_raw_data(
            plan,
            {"data": command_result, "device_ip": "10.0.0.1"},
            "netmiko",
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        legacy_result = getattr(tool_class, f"get_{collection_type}")(command_result)
        expected = normalize_processed_data(collection_type, legacy_result)
        for item in expected:
            item["manage_ip"] = "10.0.0.1"
        self.assertEqual(processed, expected)

    def test_ruijie_golden_sample_arp(self):
        self._assert_ruijie_golden_sample(
            "arp",
            [
                {
                    "address": "10.0.0.2",
                    "hardware": "aaaa.bbbb.cccc",
                    "agemin": "10",
                    "type": "dynamic",
                    "vlan": "100",
                    "interface": "Gi1/0/1",
                }
            ],
        )

    def test_ruijie_golden_sample_mac(self):
        self._assert_ruijie_golden_sample(
            "mac",
            [
                {
                    "macaddress": "aaaa.bbbb.cccc",
                    "vlan": "100",
                    "interface": "Gi1/0/1",
                    "type": "dynamic",
                }
            ],
        )

    def test_ruijie_golden_sample_lldp(self):
        self._assert_ruijie_golden_sample(
            "lldp",
            [
                {
                    "local_interface": "Te1/0/1",
                    "chassis_id": "0011.2233.4455",
                    "neighbor_port": "Eth1/1",
                    "portdescription": "uplink",
                    "neighborsysname": "core-a",
                    "management_ip": "10.0.0.254",
                    "management_type": "ipv4",
                    "neighbor_ip": "10.0.0.254",
                }
            ],
        )

    def test_ruijie_golden_sample_interface_brief(self):
        self._assert_ruijie_golden_sample(
            "interface_brief",
            [
                {
                    "interface": "Gi1/0/1",
                    "status": "up",
                    "speed": "1000M",
                    "duplex": "full",
                    "description": "uplink",
                }
            ],
        )

    def test_ruijie_golden_sample_ip_interface(self):
        self._assert_ruijie_golden_sample(
            "ip_interface",
            [
                {
                    "interface": "Vlanif100",
                    "status": "up",
                    "protocol": "up",
                    "priipaddr": "10.0.0.1/24",
                    "secipaddr": "no address",
                }
            ],
        )

    def test_ruijie_golden_sample_aggre_port(self):
        self._assert_ruijie_golden_sample(
            "aggre_port",
            [
                {
                    "aggregateport": "Ag1",
                    "ports": "Gi1/0/1,Te1/0/1",
                }
            ],
        )

    def test_long_tail_vendor_golden_sample_arp(self):
        sample = [
            {
                "address": "10.0.0.2",
                "ipaddress": "10.0.0.2",
                "hardware": "aaaa.bbbb.cccc",
                "macaddress": "aaaa.bbbb.cccc",
                "agemin": "5",
                "age": "5",
                "interface": "Eth1/0/1",
                "vlan": "100",
                "type": "dynamic",
                "typeflag": "dynamic",
            }
        ]
        for vendor, tool_class in (
            ("ZTE", ZtePlan),
            ("Maipu", MaipuPlan),
            ("Mellanox", MellanoxPlan),
            ("centec", CentecPlan),
        ):
            with self.subTest(vendor=vendor):
                self._assert_vendor_golden_sample(vendor, "arp", list(sample), tool_class)


class DeviceApiHillstoneGoldenSampleTests(SimpleTestCase):
    def _build_plan(self, collection_type):
        return SimpleNamespace(
            name=f"Hillstone-{collection_type}-plan",
            collection_type=collection_type,
            summary_plan=SimpleNamespace(vendor="Hillstone", device_type="firewall"),
        )

    def _resolve(self, collection_type, data):
        return resolve_raw_data(
            self._build_plan(collection_type),
            {"data": data, "device_ip": "10.0.0.1"},
            "netmiko",
        )

    def test_hillstone_golden_sample_device_identity(self):
        status, error, processed = self._resolve(
            "device_identity",
            [{"version": "5.5R10", "product": "SG-6000-E3960", "sn": "HS123456"}],
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["soft_version"], "5.5R10")
        self.assertEqual(processed[0]["model_name"], "SG-6000-E3960")
        self.assertEqual(processed[0]["serial_num"], "HS123456")
        self.assertEqual(processed[0]["manage_ip"], "10.0.0.1")

    def test_hillstone_golden_sample_zone(self):
        status, error, processed = self._resolve(
            "zone",
            [{"name": "trust", "type": "layer3", "vswitch": "root", "ifcount": "2", "shared": "N"}],
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["name"], "trust")
        self.assertEqual(processed[0]["type"], "layer3")
        self.assertEqual(processed[0]["ifcount"], "2")

    def test_hillstone_golden_sample_service_predefined(self):
        status, error, processed = self._resolve(
            "service_predefined",
            [
                {"name": "HTTP", "protocol": "TCP", "dstport": "80", "srcport": "Any", "timeout": "1800"},
                {"name": "NTP", "protocol": "UDP", "dstport": "123", "srcport": "Any", "timeout": "300"},
            ],
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["name"], "HTTP")
        self.assertEqual(processed[0]["dst_port_min"], 80)
        self.assertEqual(processed[0]["dst_port_max"], 80)
        self.assertEqual(processed[0]["src_port_min"], 0)
        self.assertEqual(processed[1]["protocol"], "udp")

    def test_hillstone_golden_sample_policy_hit_count(self):
        status, error, processed = self._resolve(
            "policy_hit_count",
            [{"id": "100", "name": "allow-web", "count": "25"}],
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["id"], "100")
        self.assertEqual(processed[0]["count"], 25)

    def test_hillstone_golden_sample_security_policy_from_raw_config(self):
        raw_config = """
address "inside-net"
 ip 10.10.10.0/24
exit
service "tcp 80"
 tcp dst-port 80
exit
policy-global
 rule id 100
  action permit
  src-zone "trust"
  dst-zone "untrust"
  src-addr "inside-net"
  dst-ip 203.0.113.10
  service "tcp 80"
  description "allow-web"
 exit
exit
""".strip()

        status, error, processed = self._resolve("security_policy", raw_config)

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["rule_id"], "100")
        self.assertEqual(processed[0]["action"], "permit")
        self.assertEqual(processed[0]["src_zone"], "trust")
        self.assertEqual(processed[0]["dst_zone"], "untrust")
        self.assertEqual(processed[0]["src_addr"][0]["name"], "inside-net")
        self.assertEqual(processed[0]["service"][0]["items"][0]["result"], "80")

    def test_hillstone_golden_sample_dnat_from_raw_config(self):
        raw_config = """
address "公网对象"
 ip 203.0.113.10/32
exit
address "内网主机"
 host 10.0.0.10
exit
ip vrouter "trust-vr"
 dnatrule id 10 from address-book "Any" to address-book "公网对象" service "tcp 8443" trans-to address-book "内网主机" port 443 description "web-dnat"
exit
""".strip()

        status, error, processed = self._resolve("dnat", raw_config)

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["rule_id"], "10")
        self.assertEqual(processed[0]["global_ip"][0]["result"], "203.0.113.10/32")
        self.assertEqual(processed[0]["local_ip"][0]["result"], "10.0.0.10/32")
        self.assertEqual(processed[0]["local_port"][0]["result"], "443")

    def test_hillstone_golden_sample_snat_from_raw_config(self):
        raw_config = """
address "源地址"
 ip 10.0.0.0/24
 exclude ip 10.0.0.254/32
exit
address "目的地址"
 ip 198.51.100.10/32
exit
address "转换地址"
 ip 203.0.113.20/32
exit
service "tcp 80"
 tcp dst-port 80
exit
ip vrouter "trust-vr"
 snatrule id 20 from-zone "trust" to-zone "untrust" from address-book "源地址" to address-book "目的地址" service "tcp 80" trans-to address-book "转换地址" mode dynamicport description "web-snat"
exit
""".strip()

        status, error, processed = self._resolve("snat", raw_config)

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["rule_id"], "20")
        self.assertEqual(processed[0]["mode"], "dynamicport")
        self.assertEqual(processed[0]["source_zone"], "trust")
        self.assertEqual(processed[0]["trans_ip"][0]["result"], "203.0.113.20/32")
        self.assertEqual(processed[0]["local_exclude_ip"][0]["result"], "10.0.0.254/32")


class DeviceApiConnectionManagerTests(SimpleTestCase):
    def test_get_netmiko_connection_requires_ssh_account(self):
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {"vendor__alias": "Huawei"},
        )

        with self.assertRaisesRegex(ValueError, "SSH/Telnet账号信息不存在"):
            manager.get_netmiko_connection()

    @patch("apps.device_api.connection_manager.ZetmikoConnectHandler")
    def test_get_netmiko_connection_uses_telnet_account_when_present(self, mock_handler):
        mock_handler.return_value = Mock()
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {
                "vendor__alias": "Hillstone",
                "telnet": {"username": "ops", "password": "secret", "port": 23},
            },
        )

        manager.get_netmiko_connection()

        self.assertEqual(mock_handler.call_args.kwargs["device_type"], "hillstone_telnet")
        self.assertEqual(mock_handler.call_args.kwargs["username"], "ops")
        self.assertEqual(mock_handler.call_args.kwargs["port"], 23)

    @patch("apps.device_api.connection_manager.snmp_get_oid")
    def test_execute_snmp_get_uses_v3_username_and_collects_failures(
        self,
        mock_snmp_get_oid,
    ):
        calls = []

        def _fake_snmp_get_oid(**kwargs):
            calls.append(kwargs)
            if kwargs["oid"] == "1.3.6.1.2.1.1.1.0":
                return True, "switch-a"
            if kwargs["oid"] == "1.3.6.1.2.1.1.5.0":
                return False, "timeout"
            raise RuntimeError("boom")

        mock_snmp_get_oid.side_effect = _fake_snmp_get_oid
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {
                "snmp_version": "v3",
                "snmp_username": "snmp-user",
                "snmp_auth_key": "auth-secret",
                "snmp_priv_key": "priv-secret",
                "snmp_port": 162,
            },
        )

        result = manager.execute_snmp_get(
            [
                "1.3.6.1.2.1.1.1.0",
                "1.3.6.1.2.1.1.5.0",
                "1.3.6.1.2.1.1.6.0",
            ]
        )

        self.assertEqual(result["1.3.6.1.2.1.1.1.0"], "switch-a")
        self.assertIsNone(result["1.3.6.1.2.1.1.5.0"])
        self.assertIsNone(result["1.3.6.1.2.1.1.6.0"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call["snmp_community"] == "snmp-user" for call in calls))
        self.assertTrue(all(call["port"] == 162 for call in calls))
        self.assertTrue(all(call["auth_key"] == "auth-secret" for call in calls))
        self.assertTrue(all(call["priv_key"] == "priv-secret" for call in calls))

    def test_get_restconf_session_configures_token_auth(self):
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {
                "restconf_config": {
                    "port": 8443,
                    "auth_type": "token",
                    "token": "secret-token",
                    "verify_ssl": True,
                }
            },
        )

        session = manager.get_restconf_session()

        self.assertEqual(session.base_url, "https://10.0.0.1:8443")
        self.assertEqual(session.headers["Authorization"], "Bearer secret-token")
        self.assertTrue(session.verify)

    @patch("apps.device_api.connection_manager.grpc", None)
    def test_get_telemetry_channel_requires_grpc_dependency(self):
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {"telemetry_config": {"port": 57400}},
        )

        with self.assertRaisesRegex(ImportError, "grpcio"):
            manager.get_telemetry_channel()

    @patch("apps.device_api.connection_manager.grpc", Mock())
    def test_execute_telemetry_subscribe_raises_not_implemented(self):
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {"telemetry_config": {"port": 57400}},
        )

        with self.assertRaisesRegex(NotImplementedError, "telemetry_not_implemented"):
            manager.execute_telemetry_subscribe("/interfaces/interface/state", 5)

    def test_execute_restconf_get_retries_before_success(self):
        manager = DeviceConnectionManager(
            "10.0.0.1",
            {
                "connection_policy": {
                    "restconf_retry_times": 2,
                    "restconf_timeout_seconds": 3,
                }
            },
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}

        session = Mock()
        session.base_url = "https://10.0.0.1:443"
        session.get.side_effect = [
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.Timeout("timeout"),
            response,
        ]
        manager._restconf_session = session

        data = manager.execute_restconf_get("/restconf/data/interfaces")

        self.assertEqual(data, {"ok": True})
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(session.get.call_args.kwargs["timeout"], 3)


class DeviceApiCollectDeviceTests(SimpleTestCase):
    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlanSerializer")
    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlan.objects")
    @patch("apps.device_api.tools.collect_device.AssetAccount.objects")
    @patch("apps.device_api.tools.collect_device.PlansToDevice.objects")
    @patch("apps.device_api.tools.collect_device.NetworkDevice.objects")
    def test_get_auto_device_uses_plans_to_device_as_binding_source(
        self,
        mock_device_objects,
        mock_relation_objects,
        mock_account_objects,
        mock_sub_plan_objects,
        mock_sub_plan_serializer,
    ):
        device_row = {
            "id": 1,
            "serial_num": "SER-1",
            "manage_ip": "10.0.0.1",
            "name": "switch-a",
            "soft_version": "v1",
            "vendor__name": "Huawei",
            "vendor__alias": "Huawei",
            "category__name": "switch",
            "model__name": "CE8850",
            "ssh_enable": "account",
            "ssh_account": 101,
            "netconf_enable": "account",
            "netconf_account": 102,
            "patch_version": "p1",
            "status": 0,
            "idc__name": "IDC-A",
            "auto_enable": True,
            "ha_status": 0,
            "chassis": 1,
            "slot": 1,
        }
        mock_device_objects.filter.return_value.select_related.return_value.values.return_value = [device_row]

        relation_one = SimpleNamespace(manage_ip="10.0.0.1", plan_id=201, use_local=True, execute_node="", plan=SimpleNamespace(id=201))
        relation_two = SimpleNamespace(manage_ip="10.0.0.1", plan_id=202, use_local=False, execute_node="10.0.0.9", plan=SimpleNamespace(id=202))
        mock_relation_objects.select_related.return_value.filter.return_value = [relation_one, relation_two]

        mock_account_objects.filter.return_value.values.return_value = [
            {"id": 101, "name": "ssh", "username": "u1", "password": "gAAAA", "protocol": "ssh", "port": 22},
            {"id": 102, "name": "netconf", "username": "u2", "password": "gBBBB", "protocol": "netconf", "port": 830},
        ]
        mock_sub_plan_objects.filter.return_value.select_related.return_value.order_by.return_value = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
        mock_sub_plan_serializer.return_value.data = [
            {"summary_plan": 201, "id": 11, "collection_type": "arp"},
            {"summary_plan": 202, "id": 12, "collection_type": "mac"},
        ]

        with patch("apps.device_api.tools.collect_device.CryptPwd.decrypt_pwd", side_effect=lambda value: f"decoded-{value}"):
            result = get_auto_device(manage_ip="10.0.0.1", plan_id=201, use_local=False)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["manage_ip"], "10.0.0.1")
        self.assertEqual(result[0]["plan_id"], 201)
        self.assertEqual(result[0]["sub_plans"], [{"summary_plan": 201, "id": 11, "collection_type": "arp"}])
        self.assertTrue(result[0]["use_local"])
        self.assertEqual(result[1]["plan_id"], 202)
        self.assertEqual(result[1]["execute_node"], "10.0.0.9")
        self.assertEqual(result[1]["sub_plans"], [{"summary_plan": 202, "id": 12, "collection_type": "mac"}])

        network_filter_kwargs = mock_device_objects.filter.call_args.kwargs
        self.assertNotIn("plan_id", network_filter_kwargs)
        self.assertNotIn("use_local", network_filter_kwargs)

        relation_filter_kwargs = mock_relation_objects.select_related.return_value.filter.call_args.kwargs
        self.assertEqual(relation_filter_kwargs["manage_ip__in"], ["10.0.0.1"])
        self.assertEqual(relation_filter_kwargs["device_serial_num__in"], ["SER-1"])
        self.assertTrue(relation_filter_kwargs["is_active"])
        self.assertEqual(relation_filter_kwargs["plan_id"], 201)
        self.assertFalse(relation_filter_kwargs["use_local"])

    @patch("apps.device_api.tools.collect_device.PlansToDevice.objects")
    @patch("apps.device_api.tools.collect_device.NetworkDevice.objects")
    def test_get_auto_device_skips_devices_without_plan_binding(
        self,
        mock_device_objects,
        mock_relation_objects,
    ):
        device_row = {
            "id": 1,
            "serial_num": "SER-1",
            "manage_ip": "10.0.0.1",
            "name": "switch-a",
            "soft_version": "v1",
            "vendor__name": "Huawei",
            "vendor__alias": "Huawei",
            "category__name": "switch",
            "model__name": "CE8850",
            "ssh_enable": "0",
            "ssh_account": None,
            "netconf_enable": "0",
            "netconf_account": None,
            "patch_version": "p1",
            "status": 0,
            "idc__name": "IDC-A",
            "auto_enable": True,
            "ha_status": 0,
            "chassis": 1,
            "slot": 1,
        }
        mock_device_objects.filter.return_value.select_related.return_value.values.return_value = [device_row]
        mock_relation_objects.select_related.return_value.filter.return_value = []

        result = get_auto_device(manage_ip="10.0.0.1")

        self.assertEqual(result, [])

    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlanSerializer")
    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlan.objects")
    @patch("apps.device_api.tools.collect_device.AssetAccount.objects")
    @patch("apps.device_api.tools.collect_device.PlansToDevice.objects")
    @patch("apps.device_api.tools.collect_device.NetworkDevice.objects")
    def test_get_auto_device_exposes_binding_metadata_for_batch_dedupe(
        self,
        mock_device_objects,
        mock_relation_objects,
        mock_account_objects,
        mock_sub_plan_objects,
        mock_sub_plan_serializer,
    ):
        device_row = {
            "id": 1,
            "serial_num": "SER-1",
            "manage_ip": "10.0.0.1",
            "name": "switch-a",
            "soft_version": "v1",
            "vendor__name": "Huawei",
            "vendor__alias": "Huawei",
            "category__name": "switch",
            "model__name": "CE8850",
            "ssh_enable": "0",
            "ssh_account": None,
            "netconf_enable": "0",
            "netconf_account": None,
            "patch_version": "p1",
            "status": 0,
            "idc__name": "IDC-A",
            "auto_enable": True,
            "ha_status": 0,
            "chassis": 1,
            "slot": 1,
        }
        mock_device_objects.filter.return_value.select_related.return_value.values.return_value = [device_row]
        relation = SimpleNamespace(
            manage_ip="10.0.0.1",
            plan_id=201,
            use_local=True,
            execute_node="",
            device_serial_num="SER-1",
            profile_code="Huawei-CE",
            binding_source="manual",
            last_bound_at=datetime(2026, 3, 20, 10, 0, 0),
            created_at=datetime(2026, 3, 18, 10, 0, 0),
            updated_at=datetime(2026, 3, 21, 10, 0, 0),
        )
        mock_relation_objects.select_related.return_value.filter.return_value = [relation]
        mock_account_objects.filter.return_value.values.return_value = []
        mock_sub_plan_objects.filter.return_value.select_related.return_value.order_by.return_value = []
        mock_sub_plan_serializer.return_value.data = []

        result = get_auto_device(manage_ip="10.0.0.1")

        self.assertEqual(result[0]["binding_source"], "manual")
        self.assertEqual(result[0]["last_bound_at"], relation.last_bound_at)
        self.assertEqual(result[0]["binding_created_at"], relation.created_at)
        self.assertEqual(result[0]["binding_updated_at"], relation.updated_at)


class DeviceApiBridgeCommandTests(SimpleTestCase):
    @patch("apps.device_api.management.commands.sync_legacy_plan_bindings.PlansToDevice.objects")
    @patch("apps.device_api.management.commands.sync_legacy_plan_bindings.DeviceCollectionPlans.objects")
    @patch("apps.device_api.management.commands.sync_legacy_plan_bindings.NetworkDevice.objects")
    @patch("apps.device_api.management.commands.sync_legacy_plan_bindings.PlatformProfileService.match_profile_for_device")
    def test_sync_legacy_plan_bindings_creates_bridge_relation(
        self,
        mock_match_profile,
        mock_network_device_objects,
        mock_device_plan_objects,
        mock_relation_objects,
    ):
        mock_match_profile.return_value = SimpleNamespace(code="Huawei-CE")
        legacy_plan = SimpleNamespace(id=9, name="legacy-switch-plan")
        device = SimpleNamespace(
            serial_num="SER-1",
            manage_ip="10.0.0.1",
            plan=legacy_plan,
            vendor=SimpleNamespace(alias="Huawei"),
            category=SimpleNamespace(name="switch"),
        )
        mock_queryset = mock_network_device_objects.filter.return_value.select_related.return_value
        mock_queryset.iterator.return_value = [device]
        mock_device_plan_objects.filter.return_value.first.return_value = SimpleNamespace(id=101)
        mock_relation_objects.filter.return_value.exists.return_value = False

        command = SyncLegacyPlanBindingsCommand()
        command.handle(dry_run=False, manage_ip=None)

        mock_relation_objects.create.assert_called_once_with(
            device_serial_num="SER-1",
            manage_ip="10.0.0.1",
            plan=mock_device_plan_objects.filter.return_value.first.return_value,
            profile_code="Huawei-CE",
            binding_source="legacy_bridge",
            is_active=True,
            use_local=True,
            execute_node="",
            last_bound_at=None,
        )

    @patch("apps.device_api.management.commands.audit_device_api_coverage.PlatformProfileService.audit_device_coverage")
    @patch("apps.device_api.management.commands.audit_device_api_coverage.Command.collect_schema_blockers")
    @patch("apps.device_api.management.commands.audit_device_api_coverage.NetworkDevice.objects")
    def test_audit_device_api_coverage_command_outputs_summary(
        self,
        mock_network_device_objects,
        mock_collect_schema_blockers,
        mock_audit_device_coverage,
    ):
        queryset = mock_network_device_objects.filter.return_value.select_related.return_value
        queryset.filter.return_value = queryset
        queryset.__iter__ = Mock(return_value=iter([SimpleNamespace(manage_ip="10.0.0.1")]))
        mock_collect_schema_blockers.return_value = []
        mock_audit_device_coverage.return_value = {
            "summary": {
                "total": 1,
                "ready": 0,
                "blocked": 1,
                "profile_not_matched": 1,
                "missing_default_plan": 0,
                "missing_binding": 0,
            },
            "results": [
                {
                    "manage_ip": "10.0.0.1",
                    "serial_num": "SER-1",
                    "profile_code": "",
                    "plan_name": "",
                    "blockers": [{"code": "profile_not_matched"}],
                }
            ],
        }

        command = AuditDeviceApiCoverageCommand()
        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                manage_ip=None,
                serial_num=None,
                vendor_alias=None,
                sync_default_plans=False,
                auto_bind=False,
                sample_limit=20,
            )

        written = "\n".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("summary: total=1 ready=0 blocked=1", written)
        self.assertIn("blockers=profile_not_matched", written)

    @patch("apps.device_api.management.commands.audit_device_api_coverage.PlatformProfileService.audit_device_coverage")
    @patch("apps.device_api.management.commands.audit_device_api_coverage.Command.collect_schema_blockers")
    @patch("apps.device_api.management.commands.audit_device_api_coverage.NetworkDevice.objects")
    def test_audit_device_api_coverage_command_writes_json_report(
        self,
        mock_network_device_objects,
        mock_collect_schema_blockers,
        mock_audit_device_coverage,
    ):
        queryset = mock_network_device_objects.filter.return_value.select_related.return_value
        queryset.filter.return_value = queryset
        queryset.__iter__ = Mock(return_value=iter([]))
        mock_collect_schema_blockers.return_value = []
        mock_audit_device_coverage.return_value = {
            "summary": {
                "total": 0,
                "ready": 0,
                "blocked": 0,
                "profile_not_matched": 0,
                "missing_default_plan": 0,
                "missing_binding": 0,
            },
            "results": [],
        }

        command = AuditDeviceApiCoverageCommand()
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"
            command.handle(
                manage_ip=None,
                serial_num=None,
                vendor_alias=None,
                sync_default_plans=False,
                auto_bind=False,
                sample_limit=20,
                output=str(output_path),
            )
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total"], 0)

    @patch("apps.device_api.management.commands.audit_device_api_coverage.Command.collect_schema_blockers")
    @patch("apps.device_api.management.commands.audit_device_api_coverage.NetworkDevice.objects")
    def test_audit_device_api_coverage_command_reports_schema_blockers(
        self,
        mock_network_device_objects,
        mock_collect_schema_blockers,
    ):
        queryset = mock_network_device_objects.filter.return_value.select_related.return_value
        queryset.filter.return_value = queryset
        queryset.__iter__ = Mock(return_value=iter([SimpleNamespace(manage_ip="10.0.0.1")]))
        mock_collect_schema_blockers.return_value = [
            {"code": "missing_table", "message": "缺少数据表: device_api_platform_profile"}
        ]

        command = AuditDeviceApiCoverageCommand()
        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                manage_ip=None,
                serial_num=None,
                vendor_alias=None,
                sync_default_plans=True,
                auto_bind=True,
                sample_limit=20,
                output=None,
            )

        written = "\n".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("schema blockers:", written)
        self.assertIn("skip sync_default_plans: schema blockers detected", written)
        self.assertIn("skip auto_bind: schema blockers detected", written)


class RefreshCapabilityDiscoveryCommandTests(SimpleTestCase):
    class _FakeCollectPlans:
        def __init__(self, mapping):
            self.mapping = mapping

        def filter(self, collection_type=None):
            return SimpleNamespace(first=lambda: self.mapping.get(collection_type))

    @patch("apps.device_api.management.commands.refresh_capability_discovery.PlatformProfileService.auto_bind_devices")
    @patch("apps.device_api.management.commands.refresh_capability_discovery.DeviceCollectionService.execute_both_collection_local")
    @patch("apps.device_api.management.commands.refresh_capability_discovery.PlatformProfileService.ensure_default_plan_for_profile")
    @patch("apps.device_api.management.commands.refresh_capability_discovery.PlatformProfileService.match_profile_for_device")
    @patch("apps.device_api.management.commands.refresh_capability_discovery.PlatformProfileService.ensure_builtin_profiles")
    @patch("apps.device_api.management.commands.refresh_capability_discovery.NetworkDevice.objects")
    def test_refresh_capability_discovery_outputs_vendor_heartbeat_and_auto_bind_summary(
        self,
        mock_network_device_objects,
        mock_ensure_builtin_profiles,
        mock_match_profile_for_device,
        mock_ensure_default_plan_for_profile,
        mock_execute_collection_local,
        mock_auto_bind_devices,
    ):
        huawei_profile = SimpleNamespace(code="hua", vendor_alias="Huawei")
        h3c_profile = SimpleNamespace(code="h3c", vendor_alias="H3C")
        devices = [
            SimpleNamespace(
                manage_ip="10.0.0.1",
                serial_num="SER-HW-1",
                vendor=SimpleNamespace(alias="Huawei"),
                netconf_enable="account",
                netconf_account=object(),
                ssh_enable="disable",
                ssh_account=None,
            ),
            SimpleNamespace(
                manage_ip="10.0.0.2",
                serial_num="SER-H3C-1",
                vendor=SimpleNamespace(alias="H3C"),
                netconf_enable="account",
                netconf_account=object(),
                ssh_enable="account",
                ssh_account=object(),
            ),
            SimpleNamespace(
                manage_ip="10.0.0.3",
                serial_num="SER-H3C-2",
                vendor=SimpleNamespace(alias="H3C"),
                netconf_enable="disable",
                netconf_account=None,
                ssh_enable="disable",
                ssh_account=None,
            ),
        ]

        queryset = mock_network_device_objects.filter.return_value.select_related.return_value
        queryset.__iter__ = Mock(return_value=iter(devices))
        mock_ensure_builtin_profiles.return_value = [huawei_profile, h3c_profile]

        def match_profile(device, profiles=None):
            if device.serial_num == "SER-HW-1":
                return huawei_profile
            if device.serial_num == "SER-H3C-1":
                return h3c_profile
            return None

        mock_match_profile_for_device.side_effect = match_profile

        def build_plan(profile):
            netconf_sub_plan = SimpleNamespace(collection_type="netconf_capability")
            cli_sub_plan = SimpleNamespace(collection_type="cli_output_capability")
            mapping = {"netconf_capability": netconf_sub_plan}
            if profile.vendor_alias == "H3C":
                mapping["cli_output_capability"] = cli_sub_plan
            return SimpleNamespace(
                name=f"{profile.vendor_alias}-plan",
                collect_plans=self._FakeCollectPlans(mapping),
            )

        mock_ensure_default_plan_for_profile.side_effect = build_plan

        def execute_collection(sub_plan, device, connection_policy=None):
            self.assertIsNotNone(connection_policy)
            self.assertEqual(connection_policy["netconf_retry_times"], 0)
            if device.serial_num == "SER-HW-1":
                return {"success": True}
            if sub_plan.collection_type == "netconf_capability":
                return {"success": False, "error": "schema timeout"}
            return {"success": True}

        mock_execute_collection_local.side_effect = execute_collection
        mock_auto_bind_devices.return_value = {
            "created": 1,
            "updated": 2,
            "skipped": 0,
            "retired": 1,
            "results": [],
        }

        command = RefreshCapabilityDiscoveryCommand()
        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                vendor_aliases=[],
                manage_ip=None,
                serial_num=None,
                limit=0,
                heartbeat_every=2,
                skip_rebind=False,
            )

        written = "\n".join(str(call.args[0]) for call in mock_write.call_args_list)
        self.assertIn("phase=discovery heartbeat progress=2/3 total=3", written)
        self.assertIn("phase=discovery heartbeat progress=2/3 vendor=Huawei total=1", written)
        self.assertIn("phase=discovery heartbeat progress=2/3 vendor=H3C total=1", written)
        self.assertIn("phase=discovery summary vendor=Huawei total=1", written)
        self.assertIn("phase=discovery summary vendor=H3C total=2", written)
        self.assertIn("phase=auto_bind summary created=1 updated=2 retired=1", written)
        self.assertIn("phase=auto_bind skipped=0", written)


class DeviceApiP5RolloutCommandTests(SimpleTestCase):
    @patch("apps.device_api.management.commands.device_api_p5_rollout.NetworkDevice.objects")
    def test_build_wave_plan_counts_devices_by_vendor(
        self,
        mock_network_device_objects,
    ):
        queryset = Mock()
        mock_network_device_objects.filter.return_value = queryset
        queryset.count.side_effect = [10, 6, 3]

        waves = DeviceApiP5RolloutCommand._build_wave_plan()

        self.assertEqual(len(waves), 3)
        self.assertEqual(waves[0]["wave"], 1)
        self.assertEqual(waves[0]["device_count"], 10)
        self.assertEqual(waves[1]["device_count"], 6)
        self.assertEqual(waves[2]["device_count"], 3)

    @patch("apps.device_api.management.commands.device_api_p5_rollout.MongoOps")
    def test_build_parallel_comparison_calculates_mismatch_summary(
        self,
        mock_mongo_ops,
    ):
        mongo_one = Mock()
        mongo_two = Mock()
        mongo_three = Mock()
        mongo_four = Mock()
        mongo_five = Mock()
        mongo_six = Mock()
        mongo_seven = Mock()
        mongo_eight = Mock()
        mongo_nine = Mock()
        mongo_ten = Mock()
        mongo_eleven = Mock()
        mongo_twelve = Mock()
        mock_mongo_ops.side_effect = [
            mongo_one, mongo_two,
            mongo_three, mongo_four,
            mongo_five, mongo_six,
            mongo_seven, mongo_eight,
            mongo_nine, mongo_ten,
            mongo_eleven, mongo_twelve,
        ]
        mongo_one.coll.count_documents.return_value = 10
        mongo_two.coll.count_documents.return_value = 9
        mongo_three.coll.count_documents.return_value = 8
        mongo_four.coll.count_documents.return_value = 8
        mongo_five.coll.count_documents.return_value = 7
        mongo_six.coll.count_documents.return_value = 7
        mongo_seven.coll.count_documents.return_value = 6
        mongo_eight.coll.count_documents.return_value = 5
        mongo_nine.coll.count_documents.return_value = 4
        mongo_ten.coll.count_documents.return_value = 4
        mongo_eleven.coll.count_documents.return_value = 3
        mongo_twelve.coll.count_documents.return_value = 1

        legacy_scope = DeviceApiP5RolloutCommand._build_legacy_time_scope(
            execute_time="2026-03-17 10:00:00",
            legacy_window_minutes=60,
        )
        result = DeviceApiP5RolloutCommand._build_parallel_comparison(
            execute_time="2026-03-17 10:00:00",
            manage_ips=["10.0.0.1", "10.0.0.2"],
            legacy_time_scope=legacy_scope,
        )

        self.assertEqual(result["summary"]["checked_collections"], 6)
        self.assertEqual(result["summary"]["matched_collections"], 3)
        self.assertEqual(result["summary"]["mismatch_collections"], 3)
        self.assertTrue(result["legacy_time_scope"]["enabled"])
        self.assertEqual(result["legacy_time_scope"]["source"], "execute_time_window")
        legacy_query = mongo_two.coll.count_documents.call_args_list[0][0][0]
        self.assertIn("$or", legacy_query)

    @patch("apps.device_api.management.commands.device_api_p5_rollout.MongoOps")
    def test_build_parallel_comparison_strict_mode_uses_batch_anchor(
        self,
        mock_mongo_ops,
    ):
        mongo_objects = []
        for _ in range(12):
            mongo = Mock()
            mongo.coll.count_documents.return_value = 1
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects

        result = DeviceApiP5RolloutCommand._build_parallel_comparison(
            execute_time="2026-03-17 10:00:00",
            manage_ips=["10.0.0.1", "10.0.0.2"],
            legacy_time_scope={"enabled": True},
            comparison_mode="strict",
            legacy_batch_field="execute_time",
        )

        self.assertEqual(result["comparison_mode"], "strict")
        self.assertTrue(result["legacy_batch_anchor"]["enabled"])
        self.assertEqual(result["legacy_batch_anchor"]["field"], "execute_time")
        legacy_queries = [call.args[0] for call in mongo_objects[1].coll.count_documents.call_args_list]
        exact_match_query = next(
            (query for query in legacy_queries if query.get("execute_time") == "2026-03-17 10:00:00"),
            None,
        )
        self.assertIsNotNone(exact_match_query)
        self.assertNotIn("$or", exact_match_query)
        self.assertIn("diagnostics", result)
        self.assertIn("strict_anchor_missing_collections", result["diagnostics"])

    @patch("apps.device_api.management.commands.device_api_p5_rollout.plan_collect_device_main")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._sample_manage_ips_by_vendor")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._count_active_devices_by_vendor")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._latest_execute_time")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.MongoOps")
    def test_handle_generates_report_and_can_run_gray(
        self,
        mock_mongo_ops,
        mock_latest_execute_time,
        mock_count_by_vendor,
        mock_sample_ips,
        mock_run_main,
    ):
        mock_latest_execute_time.return_value = "2026-03-17 10:00:00"
        mock_count_by_vendor.side_effect = [2, 1, 1]
        mock_sample_ips.side_effect = [
            ["10.0.0.1", "10.0.0.2"],
            ["10.0.0.3"],
            ["10.0.0.4"],
            ["10.0.0.1", "10.0.0.2"],
        ]
        mongo_objects = []
        for idx in range(12):
            mongo = Mock()
            mongo.coll.count_documents.return_value = 2 if idx % 2 == 0 else 2
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects
        mock_run_main.return_value = {"total": 2, "tasks": 2}
        command = DeviceApiP5RolloutCommand()

        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                wave=1,
                execute_time="",
                sample_limit=10,
                skip_compare=False,
                run_gray=True,
                gray_sample_limit=5,
                dry_run=False,
                output=None,
                legacy_window_minutes=120,
                legacy_start=None,
                legacy_end=None,
                evidence_dir=None,
                drill_executed=False,
                drill_start="",
                drill_end="",
                drill_scope="",
                drill_operator="",
                drill_result="pass",
                drill_notes="",
                drill_verify_item=[],
                release_owner="",
                release_observer="",
                release_rollback_owner="",
                release_risk="medium",
                release_change="",
                release_observation_item=[],
            )

        mock_run_main.assert_called_once()
        writes = "\n".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("P5 灰度/对比/回退报告生成完成", writes)
        self.assertIn("default_entry=device_api fallback_entry=automation", writes)
        self.assertIn("legacy_scope: enabled=True source=execute_time_window", writes)
        self.assertIn("acceptance_gate: status=fail", writes)
        self.assertIn("gray_done=True", writes)

    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._sample_manage_ips_by_vendor")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._count_active_devices_by_vendor")
    @patch("apps.device_api.management.commands.device_api_p5_rollout.Command._latest_execute_time")
    def test_handle_writes_p5_evidence_files(self, mock_latest_execute_time, mock_count_by_vendor, mock_sample_ips):
        mock_latest_execute_time.return_value = "2026-03-17 10:00:00"
        mock_count_by_vendor.side_effect = [2, 1, 1]
        mock_sample_ips.side_effect = [
            ["10.0.0.1", "10.0.0.2"],
            ["10.0.0.3"],
            ["10.0.0.4"],
        ]
        command = DeviceApiP5RolloutCommand()
        with TemporaryDirectory() as temp_dir:
            command.handle(
                wave=1,
                execute_time="",
                sample_limit=5,
                skip_compare=True,
                run_gray=False,
                dry_run=True,
                output=None,
                legacy_window_minutes=120,
                legacy_start=None,
                legacy_end=None,
                evidence_dir=temp_dir,
                drill_executed=True,
                drill_start="2026-03-17 09:00:00",
                drill_end="2026-03-17 09:20:00",
                drill_scope="Wave-1 Huawei/H3C",
                drill_operator="codex",
                drill_result="pass",
                drill_notes="rollback drill completed",
                drill_verify_item=["回退后 success_rate >= 95%"],
                release_owner="codex",
                release_observer="ops",
                release_rollback_owner="ops",
                release_risk="medium",
                release_change="默认入口切换到 device_api",
                release_observation_item=["batch_gate_metrics success_rate"],
            )

            rollout_report = Path(temp_dir) / "p5_rollout_report.json"
            fallback_record = Path(temp_dir) / "p5_fallback_drill_record.json"
            release_notes = Path(temp_dir) / "p5_release_notes.json"
            self.assertTrue(rollout_report.exists())
            self.assertTrue(fallback_record.exists())
            self.assertTrue(release_notes.exists())

            fallback_payload = json.loads(fallback_record.read_text(encoding="utf-8"))
            release_payload = json.loads(release_notes.read_text(encoding="utf-8"))
            rollout_payload = json.loads(rollout_report.read_text(encoding="utf-8"))
            self.assertTrue(fallback_payload["executed"])
            self.assertEqual(fallback_payload["result"], "pass")
            self.assertEqual(fallback_payload["operator"], "codex")
            self.assertEqual(release_payload["owner"], "codex")
            self.assertEqual(release_payload["rollback_owner"], "ops")
            self.assertEqual(rollout_payload["acceptance_gate"]["status"], "fail")


class AuditLegacyTimeAnchorCommandTests(SimpleTestCase):
    @patch("apps.device_api.management.commands.audit_legacy_time_anchor.Command._resolve_manage_ips")
    @patch("apps.device_api.management.commands.audit_legacy_time_anchor.MongoOps")
    def test_audit_legacy_time_anchor_reports_fail_when_anchor_missing(self, mock_mongo_ops, mock_resolve_manage_ips):
        mock_resolve_manage_ips.return_value = ["10.0.0.1"]

        mongo_objects = []
        for _ in range(6):
            mongo = Mock()
            mongo.coll.count_documents.side_effect = [10, 0, 3]
            mongo.coll.find_one.return_value = {"hostip": "10.0.0.1"}
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects

        command = AuditLegacyTimeAnchorCommand()
        with TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "legacy_anchor_report.json"
            with patch.object(command.stdout, "write") as mock_write:
                command.handle(
                    manage_ips=[],
                    sample_limit=10,
                    batch_field="execute_time",
                    require_anchor_coverage=1.0,
                    require_time_coverage=1.0,
                    output=str(output_file),
                )

            self.assertTrue(output_file.exists())
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate"]["status"], "fail")
            self.assertEqual(len(payload["gate"]["anchor_failed_collections"]), 6)
            writes = "\n".join(call.args[0] for call in mock_write.call_args_list)
            self.assertIn("gate: status=fail", writes)

    @patch("apps.device_api.management.commands.audit_legacy_time_anchor.Command._resolve_manage_ips")
    @patch("apps.device_api.management.commands.audit_legacy_time_anchor.MongoOps")
    def test_audit_legacy_time_anchor_reports_pass_when_coverage_meets_gate(self, mock_mongo_ops, mock_resolve_manage_ips):
        mock_resolve_manage_ips.return_value = ["10.0.0.1", "10.0.0.2"]

        mongo_objects = []
        for _ in range(6):
            mongo = Mock()
            mongo.coll.count_documents.side_effect = [10, 10, 10]
            mongo.coll.find_one.return_value = {"hostip": "10.0.0.1", "execute_time": "2026-03-17 10:00:00"}
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects

        command = AuditLegacyTimeAnchorCommand()
        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                manage_ips=[],
                sample_limit=10,
                batch_field="execute_time",
                require_anchor_coverage=1.0,
                require_time_coverage=1.0,
                output=None,
            )

        writes = "\n".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("gate: status=pass", writes)


class BackfillLegacyExecuteTimeCommandTests(SimpleTestCase):
    @patch("apps.device_api.management.commands.backfill_legacy_execute_time.Command._resolve_manage_ips")
    @patch("apps.device_api.management.commands.backfill_legacy_execute_time.MongoOps")
    def test_backfill_dry_run_only_reports_missing_docs(self, mock_mongo_ops, mock_resolve_manage_ips):
        mock_resolve_manage_ips.return_value = ["10.0.0.1"]

        mongo_objects = []
        for _ in range(6):
            mongo = Mock()
            mongo.coll.count_documents.side_effect = [10, 4]
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects

        command = BackfillLegacyExecuteTimeCommand()
        with TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "backfill_report.json"
            with patch.object(command.stdout, "write") as mock_write:
                command.handle(
                    manage_ips=[],
                    sample_limit=5,
                    collections=[],
                    execute_time="2026-03-17 02:22:48",
                    batch_field="execute_time",
                    max_update_docs=20000,
                    force=False,
                    apply=False,
                    output=str(output_file),
                )

            self.assertTrue(output_file.exists())
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertFalse(payload["summary"]["apply_mode"])
            self.assertEqual(payload["summary"]["total_to_update"], 24)
            self.assertEqual(payload["summary"]["total_updated"], 0)
            writes = "\n".join(call.args[0] for call in mock_write.call_args_list)
            self.assertIn("dry_run: use --apply to execute backfill", writes)
            for mongo in mongo_objects:
                mongo.coll.update_many.assert_not_called()

    @patch("apps.device_api.management.commands.backfill_legacy_execute_time.Command._resolve_manage_ips")
    @patch("apps.device_api.management.commands.backfill_legacy_execute_time.MongoOps")
    def test_backfill_apply_updates_only_missing_docs(self, mock_mongo_ops, mock_resolve_manage_ips):
        mock_resolve_manage_ips.return_value = ["10.0.0.1", "10.0.0.2"]

        mongo_objects = []
        for _ in range(6):
            mongo = Mock()
            mongo.coll.count_documents.side_effect = [20, 3]
            mongo.coll.update_many.return_value = SimpleNamespace(modified_count=3)
            mongo_objects.append(mongo)
        mock_mongo_ops.side_effect = mongo_objects

        command = BackfillLegacyExecuteTimeCommand()
        with patch.object(command.stdout, "write") as mock_write:
            command.handle(
                manage_ips=[],
                sample_limit=5,
                collections=[],
                execute_time="2026-03-17 02:22:48",
                batch_field="execute_time",
                max_update_docs=20000,
                force=False,
                apply=True,
                output=None,
            )

        writes = "\n".join(call.args[0] for call in mock_write.call_args_list)
        self.assertIn("apply_mode=True", writes)
        self.assertIn("updated=18", writes)
        self.assertIn("post_check: run audit_legacy_time_anchor", writes)
        first_update_args = mongo_objects[0].coll.update_many.call_args[0]
        self.assertIn("$or", first_update_args[0])
        self.assertEqual(first_update_args[1]["$set"]["execute_time"], "2026-03-17 02:22:48")


class DeviceApiTaskTests(SimpleTestCase):
    @patch("apps.device_api.tasks.COLLECTION_SUB_PLAN.insert_one")
    @patch("apps.device_api.tasks.resolve_raw_data")
    @patch("apps.device_api.models.DeviceSubCollectionPlan.objects")
    def test_process_and_save_result_injects_context_and_device_metadata(
        self,
        mock_plan_objects,
        mock_resolve_raw_data,
        mock_insert_sub_task,
    ):
        mock_plan_objects.select_related.return_value.get.return_value = SimpleNamespace()
        mock_resolve_raw_data.return_value = (True, "", [{"ipaddress": "10.0.0.2"}])
        collection_db = Mock()

        plan = {
            "id": 2,
            "summary_plan": 1,
            "collection_type": "arp",
            "summary_plan_vendor": "Huawei",
            "summary_plan_device_type": "switch",
        }
        device_info = {
            "manage_ip": "10.0.0.1",
            "name": "device-1",
            "idc__name": "IDC-A",
            "execute_time": "2026-03-12T11:00:00",
        }

        with patch("apps.device_api.tasks.COLLECTION_TYPE_MONGO_MAP", {"arp": collection_db}):
            _process_and_save_result(plan, device_info, raw_result=[{"raw": "data"}], collection_method="netmiko")

        inserted_docs = collection_db.insert_many.call_args[0][0]
        self.assertEqual(inserted_docs[0]["hostip"], "10.0.0.1")
        self.assertEqual(inserted_docs[0]["hostname"], "device-1")
        self.assertEqual(inserted_docs[0]["idc_name"], "IDC-A")
        self.assertEqual(inserted_docs[0]["summary_plan_id"], 1)
        self.assertEqual(inserted_docs[0]["plan_id"], 2)
        self.assertEqual(inserted_docs[0]["collection_type"], "arp")
        self.assertEqual(inserted_docs[0]["collection_method"], "netmiko")
        self.assertEqual(inserted_docs[0]["execute_time"], "2026-03-12T11:00:00")
        mock_insert_sub_task.assert_called_once()

    @patch("apps.device_api.tasks.DeviceFactService.update_from_processed_data")
    @patch("apps.device_api.tasks.COLLECTION_SUB_PLAN.insert_one")
    @patch("apps.device_api.tasks.resolve_raw_data")
    @patch("apps.device_api.models.DeviceSubCollectionPlan.objects")
    def test_process_and_save_result_normalizes_version_to_device_identity(
        self,
        mock_plan_objects,
        mock_resolve_raw_data,
        mock_insert_sub_task,
        mock_update_facts,
    ):
        mock_plan_objects.select_related.return_value.get.return_value = SimpleNamespace()
        mock_resolve_raw_data.return_value = (True, "", [{"serial_num": "SER-1"}])
        collection_db = Mock()

        plan = {
            "id": 9,
            "summary_plan": 2,
            "collection_type": "version",
            "summary_plan_vendor": "Huawei",
            "summary_plan_device_type": "switch",
        }
        device_info = {
            "manage_ip": "10.0.0.9",
            "name": "device-9",
            "idc__name": "IDC-B",
            "execute_time": "2026-03-17T10:00:00",
        }

        with patch("apps.device_api.tasks.COLLECTION_TYPE_MONGO_MAP", {"device_identity": collection_db}):
            _process_and_save_result(
                plan,
                device_info,
                raw_result=[{"version": "V1R1"}],
                collection_method="netmiko",
            )

        inserted_docs = collection_db.insert_many.call_args[0][0]
        self.assertEqual(inserted_docs[0]["collection_type"], "device_identity")
        self.assertEqual(inserted_docs[0]["summary_plan_id"], 2)
        self.assertEqual(inserted_docs[0]["plan_id"], 9)
        mock_update_facts.assert_called_once()
        self.assertEqual(
            mock_update_facts.call_args.kwargs["collection_type"],
            "device_identity",
        )
        mock_insert_sub_task.assert_called_once()

    @patch("apps.device_api.tasks.COLLECTION_PLAN")
    @patch("apps.device_api.tasks._process_and_save_result")
    @patch("apps.device_api.tasks.DeviceCollectionService.insert_parent_plan_data")
    @patch("apps.device_api.tasks.DeviceConnectionManager")
    def test_plan_collect_device_marks_failed_when_processing_result_is_not_saved(
        self,
        mock_connection_manager_cls,
        mock_insert_parent,
        mock_process_result,
        mock_collection_plan,
    ):
        conn_mgr = Mock()
        conn_mgr.execute_netmiko_command.return_value = [{"raw": "data"}]
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False
        mock_insert_parent.return_value = {"success": True, "action": "inserted"}
        mock_process_result.return_value = {"success": False, "reason": "resolve_failed"}

        result = plan_collect_device(
            manage_ip="10.0.0.1",
            plan_id=100,
            execute_time="2026-03-17T11:00:00",
            sub_plans=[
                {
                    "id": 1,
                    "name": "arp-netmiko",
                    "summary_plan": 100,
                    "netmiko_enabled": True,
                    "netmiko_method": "display arp",
                }
            ],
        )

        self.assertEqual(result["task_status"], "failed")
        self.assertEqual(result["successful_sub_plans"], 0)
        self.assertEqual(result["failed_sub_plans"], 1)
        self.assertEqual(result["failed_details"][0]["reason"], "resolve_failed")
        mock_collection_plan.update_one.assert_called_once()

    @patch("apps.device_api.tasks.COLLECTION_PLAN")
    @patch("apps.device_api.tasks.DeviceCollectionService.insert_parent_plan_data")
    @patch("apps.device_api.tasks.DeviceConnectionManager")
    def test_plan_collect_device_marks_parent_failed_when_device_level_exception_occurs(
        self,
        mock_connection_manager_cls,
        mock_insert_parent,
        mock_collection_plan,
    ):
        mock_connection_manager_cls.return_value.__enter__.side_effect = RuntimeError("connect failed")
        mock_insert_parent.return_value = {"success": True, "action": "inserted"}

        result = plan_collect_device(
            manage_ip="10.0.0.1",
            plan_id=100,
            execute_time="2026-03-17T11:00:00",
            sub_plans=[
                {
                    "id": 1,
                    "name": "arp-netmiko",
                    "summary_plan": 100,
                    "netmiko_enabled": True,
                    "netmiko_method": "display arp",
                }
            ],
        )

        self.assertEqual(result["task_status"], "failed")
        mock_collection_plan.update_one.assert_called_once()
        update_kwargs = mock_collection_plan.update_one.call_args.kwargs
        self.assertEqual(update_kwargs["update"]["$set"]["task_status"], "failed")
        self.assertEqual(
            update_kwargs["update"]["$set"]["failed_details"][0]["collection_method"],
            "device",
        )

    @patch("apps.device_api.tasks.COLLECTION_PLAN")
    @patch("apps.device_api.tasks.DeviceCollectionService.insert_parent_plan_data")
    @patch("apps.device_api.tasks.DeviceConnectionManager")
    def test_plan_collect_device_rejects_invalid_netconf_collect_method(
        self,
        mock_connection_manager_cls,
        mock_insert_parent,
        mock_collection_plan,
    ):
        conn_mgr = Mock()
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False
        mock_insert_parent.return_value = {"success": True, "action": "inserted"}

        result = plan_collect_device(
            manage_ip="10.0.0.1",
            plan_id=100,
            execute_time="2026-03-17T11:00:00",
            sub_plans=[
                {
                    "id": 1,
                    "name": "arp-netconf",
                    "summary_plan": 100,
                    "netconf_enabled": True,
                    "xml_templates": [
                        {
                            "collect_method": "rpc",
                            "xml_template": "<top />",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(result["task_status"], "failed")
        self.assertEqual(result["failed_sub_plans"], 1)
        self.assertIn("仅允许 get/get_config", result["failed_details"][0]["reason"])
        conn_mgr.execute_netconf_get.assert_not_called()
        mock_collection_plan.update_one.assert_called_once()

    @patch("apps.device_api.tasks.COLLECTION_PLAN")
    @patch("apps.device_api.tasks._process_and_save_result")
    @patch("apps.device_api.tasks.DeviceCollectionService.insert_parent_plan_data")
    @patch("apps.device_api.tasks.DeviceConnectionManager")
    def test_plan_collect_device_updates_parent_status_with_partial_success(
        self,
        mock_connection_manager_cls,
        mock_insert_parent,
        mock_process_result,
        mock_collection_plan,
    ):
        conn_mgr = Mock()
        conn_mgr.execute_netmiko_command.side_effect = RuntimeError("ssh failed")
        conn_mgr.execute_restconf_get.return_value = {"ok": True}
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False

        result = plan_collect_device(
            manage_ip="10.0.0.1",
            plan_id=100,
            execute_time="2026-03-17T11:00:00",
            sub_plans=[
                {
                    "id": 1,
                    "name": "arp-netmiko",
                    "summary_plan": 100,
                    "netmiko_enabled": True,
                    "netmiko_method": "display arp",
                },
                {
                    "id": 2,
                    "name": "arp-restconf",
                    "summary_plan": 100,
                    "restconf_enabled": True,
                    "restconf_endpoint": "/restconf/data/example",
                },
            ],
        )

        self.assertEqual(result["task_status"], "partial_success")
        self.assertEqual(result["successful_sub_plans"], 1)
        self.assertEqual(result["failed_sub_plans"], 1)
        self.assertEqual(result["skipped_sub_plans"], 0)
        mock_insert_parent.assert_called_once()
        mock_process_result.assert_called_once()
        mock_collection_plan.update_one.assert_called_once()
        update_kwargs = mock_collection_plan.update_one.call_args.kwargs
        self.assertEqual(update_kwargs["filter"]["execute_time"], "2026-03-17T11:00:00")
        self.assertEqual(update_kwargs["update"]["$set"]["task_status"], "partial_success")

    @patch("apps.device_api.tasks.COLLECTION_PLAN")
    @patch("apps.device_api.tasks.DeviceCollectionService.insert_parent_plan_data")
    @patch("apps.device_api.tasks.DeviceConnectionManager")
    def test_plan_collect_device_marks_skipped_when_all_sub_plans_deferred(
        self,
        mock_connection_manager_cls,
        mock_insert_parent,
        mock_collection_plan,
    ):
        conn_mgr = Mock()
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False

        result = plan_collect_device(
            manage_ip="10.0.0.1",
            plan_id=101,
            execute_time="2026-03-17T11:30:00",
            sub_plans=[
                {
                    "id": 9,
                    "name": "telemetry-plan",
                    "summary_plan": 101,
                    "telemetry_enabled": True,
                    "telemetry_subscription_path": "/interfaces/interface/state",
                }
            ],
        )

        self.assertEqual(result["task_status"], "skipped")
        self.assertEqual(result["successful_sub_plans"], 0)
        self.assertEqual(result["failed_sub_plans"], 0)
        self.assertEqual(result["skipped_sub_plans"], 1)
        self.assertEqual(result["skipped_details"][0]["reason"], "telemetry_deferred")
        mock_insert_parent.assert_called_once()
        mock_collection_plan.update_one.assert_called_once()

    @patch("apps.device_api.tasks.schedule_batch_network_analysis")
    @patch("apps.device_api.tasks.plan_collect_device.apply_async")
    @patch("apps.device_api.tasks.clear_his_collect_res")
    @patch("apps.device_api.tasks.MainIn.cmdb_to_mongo")
    @patch("apps.device_api.tasks.datas_to_cache")
    @patch("apps.device_api.tasks.get_auto_device")
    def test_plan_collect_device_main_schedules_network_analysis_followup(
        self,
        mock_get_auto_device,
        mock_datas_to_cache,
        mock_cmdb_to_mongo,
        mock_clear_his_collect_res,
        mock_plan_collect_apply_async,
        mock_schedule_batch_network_analysis,
    ):
        mock_get_auto_device.return_value = [
            {
                "manage_ip": "10.0.0.1",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 1, "collection_type": "interface_brief"}, {"id": 2, "collection_type": "arp"}],
            },
            {
                "manage_ip": "10.0.0.2",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 3, "collection_type": "arp"}],
            },
        ]
        mock_plan_collect_apply_async.return_value = SimpleNamespace(id="task-1")
        mock_schedule_batch_network_analysis.return_value = {"scheduled": True, "reason": "scheduled"}

        from apps.device_api.tasks import plan_collect_device_main
        from apps.device_api.tasks import CELERY_QUEUE

        result = plan_collect_device_main()

        self.assertEqual(result["total"], 2)
        mock_clear_his_collect_res.assert_called_once_with(execute_time="2026-03-15 10:00:00")
        mock_schedule_batch_network_analysis.assert_called_once_with(
            execute_time="2026-03-15 10:00:00",
            expected_devices=2,
            expected_subtasks=3,
            expected_interface_devices=1,
            triggered_by="device_api-plan_collect_device_main",
        )
        self.assertTrue(result["clear_history"])
        self.assertTrue(result["analysis_trigger"]["scheduled"])
        mock_plan_collect_apply_async.assert_any_call(
            kwargs=mock_get_auto_device.return_value[0],
            queue=CELERY_QUEUE,
            retry=True,
        )

    @patch("apps.device_api.tasks.schedule_batch_network_analysis")
    @patch("apps.device_api.tasks.plan_collect_device.apply_async")
    @patch("apps.device_api.tasks.clear_his_collect_res")
    @patch("apps.device_api.tasks.MainIn.cmdb_to_mongo")
    @patch("apps.device_api.tasks.datas_to_cache")
    @patch("apps.device_api.tasks.get_auto_device")
    def test_plan_collect_device_main_can_keep_history_for_gray_run(
        self,
        mock_get_auto_device,
        mock_datas_to_cache,
        mock_cmdb_to_mongo,
        mock_clear_his_collect_res,
        mock_plan_collect_apply_async,
        mock_schedule_batch_network_analysis,
    ):
        mock_get_auto_device.return_value = [
            {
                "manage_ip": "10.0.0.1",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 1, "collection_type": "arp"}],
            }
        ]
        mock_plan_collect_apply_async.return_value = SimpleNamespace(id="task-1")
        mock_schedule_batch_network_analysis.return_value = {
            "scheduled": True,
            "reason": "scheduled",
        }

        from apps.device_api.tasks import plan_collect_device_main

        result = plan_collect_device_main(clear_history=False)

        mock_clear_his_collect_res.assert_not_called()
        self.assertFalse(result["clear_history"])
        self.assertEqual(result["tasks"], 1)

    @patch("apps.device_api.tasks.schedule_batch_network_analysis")
    @patch("apps.device_api.tasks.plan_collect_device.apply_async")
    @patch("apps.device_api.tasks.clear_his_collect_res")
    @patch("apps.device_api.tasks.MainIn.cmdb_to_mongo")
    @patch("apps.device_api.tasks.datas_to_cache")
    @patch("apps.device_api.tasks.get_auto_device")
    def test_plan_collect_device_main_deduplicates_devices_and_skips_empty_sub_plans(
        self,
        mock_get_auto_device,
        mock_datas_to_cache,
        mock_cmdb_to_mongo,
        mock_clear_his_collect_res,
        mock_plan_collect_apply_async,
        mock_schedule_batch_network_analysis,
    ):
        mock_get_auto_device.return_value = [
            {
                "manage_ip": "10.0.0.1",
                "device_serial_num": "SER-1",
                "plan_id": 101,
                "binding_source": "auto",
                "use_local": True,
                "last_bound_at": datetime(2026, 3, 20, 10, 0, 0),
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 1, "collection_type": "arp"}],
            },
            {
                "manage_ip": "10.0.0.1",
                "device_serial_num": "SER-1",
                "plan_id": 102,
                "binding_source": "manual",
                "use_local": True,
                "last_bound_at": datetime(2026, 3, 21, 10, 0, 0),
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 2, "collection_type": "interface_brief"}],
            },
            {
                "manage_ip": "10.0.0.2",
                "device_serial_num": "SER-2",
                "plan_id": 103,
                "binding_source": "manual",
                "use_local": True,
                "last_bound_at": datetime(2026, 3, 21, 10, 0, 0),
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [],
            },
        ]
        mock_plan_collect_apply_async.return_value = SimpleNamespace(id="task-1")
        mock_schedule_batch_network_analysis.return_value = {"scheduled": True, "reason": "scheduled"}

        result = plan_collect_device_main(clear_history=False)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["tasks"], 1)
        self.assertEqual(result["deduplicated_devices"], 1)
        self.assertEqual(result["skipped_without_sub_plans"], 1)
        dispatched_host = mock_plan_collect_apply_async.call_args.kwargs["kwargs"]
        self.assertEqual(dispatched_host["plan_id"], 102)
        mock_schedule_batch_network_analysis.assert_called_once_with(
            execute_time="2026-03-15 10:00:00",
            expected_devices=1,
            expected_subtasks=1,
            expected_interface_devices=1,
            triggered_by="device_api-plan_collect_device_main",
        )

    @patch("apps.device_api.tasks.clear_his_collect_res", side_effect=RuntimeError("mongo down"))
    @patch("apps.device_api.tasks.MainIn.cmdb_to_mongo")
    @patch("apps.device_api.tasks.datas_to_cache")
    @patch("apps.device_api.tasks.get_auto_device")
    def test_plan_collect_device_main_raises_when_clear_history_fails(
        self,
        mock_get_auto_device,
        mock_datas_to_cache,
        mock_cmdb_to_mongo,
        mock_clear_his_collect_res,
    ):
        mock_get_auto_device.return_value = [
            {
                "manage_ip": "10.0.0.1",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 1, "collection_type": "arp"}],
            }
        ]

        with self.assertRaises(RuntimeError):
            plan_collect_device_main()

    @patch("apps.device_api.tasks.schedule_batch_network_analysis")
    @patch("apps.device_api.tasks.plan_collect_device.apply_async")
    @patch("apps.device_api.tasks.clear_his_collect_res")
    @patch("apps.device_api.tasks.MainIn.cmdb_to_mongo")
    @patch("apps.device_api.tasks.datas_to_cache")
    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlanSerializer")
    @patch("apps.device_api.tools.collect_device.DeviceSubCollectionPlan.objects")
    @patch("apps.device_api.tools.collect_device.AssetAccount.objects")
    @patch("apps.device_api.tools.collect_device.PlansToDevice.objects")
    @patch("apps.device_api.tools.collect_device.NetworkDevice.objects")
    def test_plan_collect_device_main_strips_runtime_options_before_device_filtering(
        self,
        mock_device_objects,
        mock_relation_objects,
        mock_account_objects,
        mock_sub_plan_objects,
        mock_sub_plan_serializer,
        mock_datas_to_cache,
        mock_cmdb_to_mongo,
        mock_clear_his_collect_res,
        mock_plan_collect_apply_async,
        mock_schedule_batch_network_analysis,
    ):
        device_row = {
            "id": 1,
            "serial_num": "SER-1",
            "manage_ip": "10.0.0.1",
            "name": "switch-a",
            "soft_version": "v1",
            "vendor__name": "Huawei",
            "vendor__alias": "Huawei",
            "category__name": "switch",
            "model__name": "CE8850",
            "ssh_enable": "0",
            "ssh_account": None,
            "netconf_enable": "0",
            "netconf_account": None,
            "patch_version": "p1",
            "status": 0,
            "idc__name": "IDC-A",
            "auto_enable": True,
            "ha_status": 0,
            "chassis": 1,
            "slot": 1,
            "bind_ip__ipaddr": None,
        }
        base_queryset = mock_device_objects.filter.return_value
        selected_queryset = base_queryset.select_related.return_value
        filtered_queryset = selected_queryset.filter.return_value
        filtered_queryset.values.return_value = [device_row]

        mock_relation_objects.select_related.return_value.filter.return_value = [
            SimpleNamespace(
                manage_ip="10.0.0.1",
                plan_id=201,
                use_local=True,
                execute_node="",
                device_serial_num="SER-1",
                profile_code="Huawei-CE",
                binding_source="legacy_bridge",
            )
        ]
        mock_account_objects.filter.return_value.values.return_value = []
        mock_sub_plan_objects.filter.return_value.select_related.return_value.order_by.return_value = [
            SimpleNamespace(id=11)
        ]
        mock_sub_plan_serializer.return_value.data = [
            {"summary_plan": 201, "id": 11, "collection_type": "arp"}
        ]
        mock_plan_collect_apply_async.return_value = SimpleNamespace(id="task-1")
        mock_schedule_batch_network_analysis.return_value = {
            "scheduled": True,
            "reason": "scheduled",
        }

        from apps.device_api.tasks import plan_collect_device_main

        result = plan_collect_device_main(clear_history=False)

        network_filter_kwargs = mock_device_objects.filter.call_args.kwargs
        self.assertEqual(network_filter_kwargs, {"status": 0, "auto_enable": True})
        selected_queryset.filter.assert_called_once_with(
            vendor__alias__in=[
                "H3C",
                "Huawei",
                "Ruijie",
                "Maipu",
                "Hillstone",
                "Mellanox",
                "centec",
                "Cisco",
                "CISCO",
                "cisco",
                "ZTE",
            ]
        )
        mock_clear_his_collect_res.assert_not_called()
        self.assertFalse(result["clear_history"])
        self.assertEqual(result["total"], 1)


class DeviceApiProcessorOnlyTests(SimpleTestCase):
    def test_resolve_raw_data_requires_registered_processor(self):
        plan = SimpleNamespace(
            name="h3c-board-status-plan",
            collection_type="board_status",
            summary_plan=SimpleNamespace(vendor="H3C", device_type="switch"),
        )

        status, error, processed = resolve_raw_data(
            plan,
            {"data": [{"BOARD_TYPE": "S6860-54HF"}], "device_ip": "10.0.0.1"},
            "netmiko",
        )

        self.assertFalse(status)
        self.assertEqual(error, "processor_not_found: H3C:board_status:netmiko")
        self.assertEqual(processed, [])


class DeviceApiH3CIdentityTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name="华三", alias="H3C")
        self.category = Category.objects.create(name="switch")
        self.old_model = Model.objects.create(name="OLD-MODEL", vendor=self.vendor)
        self.device = NetworkDevice.objects.create(
            name="old-name",
            manage_ip="10.254.22.173",
            serial_num="SER-H3C-001",
            vendor=self.vendor,
            category=self.category,
            model=self.old_model,
            soft_version="old-version",
            patch_version="old-patch",
        )

    def test_h3c_version_processor_extracts_identity_fields(self):
        result = process_h3c_version_netmiko(
            [
                {
                    "Slot": "1",
                    "BOARD_TYPE": "S6860-54HF",
                    "Version": "7.1.070, Feature 2707",
                    "Patch_Ver": "Feature 2707H17",
                }
            ]
        )

        self.assertEqual(
            result,
            [
                {
                    "vendor_alias": "H3C",
                    "model_name": "S6860-54HF",
                    "soft_version": "7.1.070 Feature 2707",
                    "patch_version": "Feature 2707H17",
                }
            ],
        )

    def test_h3c_device_identity_updates_network_device(self):
        plan = SimpleNamespace(
            name="h3c-device-identity-plan",
            collection_type="device_identity",
            summary_plan=SimpleNamespace(vendor="H3C", device_type="switch"),
        )
        status, error, processed = resolve_raw_data(
            plan,
            {
                "data": [
                    {
                        "Slot": "1",
                        "BOARD_TYPE": "S6860-54HF",
                        "Version": "7.1.070, Feature 2707",
                        "Patch_Ver": "Feature 2707H17",
                    }
                ],
                "device_ip": self.device.manage_ip,
            },
            "netmiko",
        )

        self.assertTrue(status)
        self.assertEqual(error, "")
        self.assertEqual(processed[0]["model_name"], "S6860-54HF")
        self.assertEqual(processed[0]["soft_version"], "7.1.070 Feature 2707")

        DeviceFactService.update_from_processed_data(
            collection_type="device_identity",
            device_info={
                "manage_ip": self.device.manage_ip,
                "serial_num": self.device.serial_num,
                "vendor__alias": "H3C",
                "platform_profile_code": "H3C-legacy-cli",
            },
            processed_data=processed,
        )

        self.device.refresh_from_db()
        self.assertEqual(self.device.model.name, "S6860-54HF")
        self.assertEqual(self.device.soft_version, "7.1.070 Feature 2707")
        self.assertEqual(self.device.patch_version, "Feature 2707H17")


class DeviceApiAutoBindingCutoverTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name="华三", alias="H3C")
        self.category = Category.objects.create(name="switch")
        self.model = Model.objects.create(name="S9825-64D", vendor=self.vendor)
        self.device = NetworkDevice.objects.create(
            name="s98-core-a",
            manage_ip="10.254.11.101",
            serial_num="SER-S98-001",
            vendor=self.vendor,
            category=self.category,
            model=self.model,
            soft_version="9.1.043 Release 9131",
            patch_version="-",
        )
        self.legacy_plan = DeviceCollectionPlans.objects.create(
            name="default-h3c-legacy-switch",
            vendor="H3C",
            device_type="switch",
            profile_code="H3C-legacy-cli",
            plan_kind=DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
            generated_by_system=True,
            is_default=True,
            enabled_collection_types=["device_identity"],
            collection_method=DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
            is_active=True,
        )
        PlansToDevice.objects.create(
            device_serial_num=self.device.serial_num,
            manage_ip=self.device.manage_ip,
            plan=self.legacy_plan,
            profile_code="H3C-legacy-cli",
            binding_source=PlansToDevice.BINDING_SOURCE_AUTO,
            is_active=True,
            use_local=True,
        )

    def test_auto_bind_devices_retires_stale_auto_binding_for_new_profile(self):
        PlatformProfileService.ensure_builtin_profiles()

        result = PlatformProfileService.auto_bind_devices([self.device])

        active_relations = list(
            PlansToDevice.objects.filter(
                device_serial_num=self.device.serial_num,
                is_active=True,
            ).values_list("profile_code", flat=True)
        )
        inactive_relations = list(
            PlansToDevice.objects.filter(
                device_serial_num=self.device.serial_num,
                is_active=False,
            ).values_list("profile_code", flat=True)
        )

        self.assertIn("H3C-S98xx-cli", active_relations)
        self.assertIn("H3C-legacy-cli", inactive_relations)
        self.assertEqual(result["retired"], 1)
        self.assertEqual(result["results"][0]["retired_auto_bindings"], 1)


class DeviceApiDefaultPlanAliasTests(TestCase):
    def test_ensure_default_plan_for_profile_renames_huawei_ce_legacy_alias(self):
        legacy_plan = DeviceCollectionPlans.objects.create(
            name="default-huawei-ce-switch",
            vendor="Huawei",
            device_type="switch",
            profile_code="Huawei-CE",
            plan_kind=DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
            generated_by_system=True,
            is_default=True,
            enabled_collection_types=["device_identity"],
            collection_method=DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
            is_active=True,
        )

        profile = next(
            item
            for item in PlatformProfileService.ensure_builtin_profiles()
            if item.code == "Huawei-CE"
        )
        plan = PlatformProfileService.ensure_default_plan_for_profile(profile)

        legacy_plan.refresh_from_db()
        self.assertEqual(plan.id, legacy_plan.id)
        self.assertEqual(plan.name, "default-huawei-ce-netconf-switch")
        self.assertEqual(plan.collection_method, DeviceCollectionPlans.COLLECTION_METHOD_NETCONF)
        self.assertFalse(DeviceCollectionPlans.objects.filter(name="default-huawei-ce-switch").exists())

    def test_ensure_default_plan_for_profile_retires_unused_huawei_ce88_alias(self):
        legacy_plan = DeviceCollectionPlans.objects.create(
            name="default-huawei-ce88xx-switch",
            vendor="Huawei",
            device_type="switch",
            profile_code="Huawei-CE88xx",
            plan_kind=DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
            generated_by_system=True,
            is_default=True,
            enabled_collection_types=["device_identity"],
            collection_method=DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
            is_active=True,
        )
        DeviceCollectionPlans.objects.create(
            name="default-huawei-ce88xx-netconf-switch",
            vendor="Huawei",
            device_type="switch",
            profile_code="Huawei-CE88xx",
            plan_kind=DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
            generated_by_system=True,
            is_default=True,
            enabled_collection_types=["device_identity"],
            collection_method=DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
            is_active=True,
        )

        profile = next(
            item
            for item in PlatformProfileService.ensure_builtin_profiles()
            if item.code == "Huawei-CE88xx"
        )
        PlatformProfileService.ensure_default_plan_for_profile(profile)

        legacy_plan.refresh_from_db()
        self.assertFalse(legacy_plan.is_active)
        self.assertFalse(legacy_plan.is_default)


class DeviceApiCapabilityDiscoveryStateTests(TestCase):
    def test_update_capability_facts_persists_into_discovery_state(self):
        vendor, _ = Vendor.objects.get_or_create(name="华三", defaults={"alias": "H3C"})
        category, _ = Category.objects.get_or_create(name="switch")
        model, _ = Model.objects.get_or_create(name="S6860-54HF", vendor=vendor)
        device = NetworkDevice.objects.create(
            name="h3c-cap-a",
            manage_ip="10.0.0.88",
            serial_num="SER-H3C-CAP-001",
            vendor=vendor,
            category=category,
            model=model,
            soft_version="7.1.070 Feature 2707",
        )

        PlatformProfileService.update_capability_facts(
            collection_type="netconf_capability",
            device_info={
                "manage_ip": device.manage_ip,
                "serial_num": device.serial_num,
                "vendor__alias": "H3C",
            },
            processed_data=[
                {
                    "schema_count": 99,
                    "openconfig_schema_count": 49,
                    "has_bgp_schema": True,
                    "has_l2vpn_schema": True,
                    "has_ifmgr_schema": True,
                    "has_telemetry_schema": False,
                    "schema_samples": ["openconfig-bgp", "h3c-l2vpn"],
                }
            ],
        )

        state = DeviceDiscoveryState.objects.get(device_serial_num=device.serial_num)

        self.assertIn("netconf_capability", state.capability_facts["probes"])
        self.assertEqual(
            state.capability_facts["probes"]["netconf_capability"]["schema_count"],
            99,
        )
        self.assertTrue(state.capability_facts["protocols"]["netconf"] is False)


class DeviceApiProtocolExtensionTests(SimpleTestCase):
    databases = {"default"}
    @staticmethod
    def _parse_textfsm_rows(template_name, raw_text):
        template_path = TEMPLATE_BASE_DIR / template_name
        with open(template_path, "r", encoding="utf-8") as template_file:
            parser = TextFSM(template_file)
        rows = parser.ParseText(raw_text)
        return [dict(zip(parser.header, row)) for row in rows]

    def test_split_runtime_control_kwargs_separates_device_filters(self):
        runtime_options, device_filters = split_runtime_control_kwargs(
            {
                "clear_history": False,
                "manage_ip": "10.0.0.1",
                "plan_id": 201,
            }
        )

        self.assertEqual(runtime_options, {"clear_history": False})
        self.assertEqual(
            device_filters,
            {"manage_ip": "10.0.0.1", "plan_id": 201},
        )

    def test_should_clear_history_before_batch_defaults_to_true(self):
        self.assertTrue(should_clear_history_before_batch())
        self.assertTrue(should_clear_history_before_batch({}))
        self.assertTrue(should_clear_history_before_batch({"clear_history": True}))
        self.assertTrue(should_clear_history_before_batch({"clear_history": "true"}))

    def test_should_clear_history_before_batch_supports_explicit_false_values(self):
        for value in (False, "false", "False", "0", "no", "off"):
            with self.subTest(value=value):
                self.assertFalse(
                    should_clear_history_before_batch({"clear_history": value})
                )

    def test_default_collection_types_include_routing_protocol_types(self):
        expected_types = {
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
        }

        self.assertTrue(expected_types.issubset(set(DEFAULT_COLLECTION_TYPES)))
        self.assertIn("prefix", get_collection_output_fields("route_table"))
        self.assertIn("dominant_state", get_collection_output_fields("bgp_summary"))
        self.assertIn("neighbor_router_id", get_collection_output_fields("ospf_neighbors"))
        self.assertIn("system_id", get_collection_output_fields("isis_neighbors"))

    def test_default_collection_types_include_overlay_mac_types(self):
        expected_types = {
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
        }

        self.assertTrue(expected_types.issubset(set(DEFAULT_COLLECTION_TYPES)))
        self.assertIn("bd_id", get_collection_output_fields("mac_bd"))
        self.assertIn("vn_id", get_collection_output_fields("mac_vxlan"))
        self.assertIn("tunnel_type", get_collection_output_fields("mac_vxlan_control"))

    def test_default_collection_types_include_vxlan_capability(self):
        self.assertIn("vxlan_capability", DEFAULT_COLLECTION_TYPES)
        self.assertIn("has_vxlan_vni", get_collection_output_fields("vxlan_capability"))
        self.assertIn("has_evpn_bgp", get_collection_output_fields("vxlan_capability"))

    def test_collection_type_mongo_map_contains_routing_protocol_collections(self):
        expected_types = {
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
        }

        self.assertTrue(expected_types.issubset(set(COLLECTION_TYPE_MONGO_MAP.keys())))

    def test_collection_type_mongo_map_contains_overlay_mac_collections(self):
        expected_types = {
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
        }

        self.assertTrue(expected_types.issubset(set(COLLECTION_TYPE_MONGO_MAP.keys())))

    def test_collection_type_mongo_map_contains_vxlan_capability(self):
        self.assertIn("vxlan_capability", COLLECTION_TYPE_MONGO_MAP.keys())

    def test_netconf_template_serializer_rejects_rpc_collect_method(self):
        serializer = NetconfXMLTemplateSerializer(
            data={
                "collect_method": "rpc",
                "xml_template": "<top></top>",
                "collection_plan": 1,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("collect_method", serializer.errors)

    def test_h3c_route_table_netconf_processor_maps_route_fields(self):
        result = process_h3c_route_table_netconf(
            {
                "top": {
                    "Ifmgr": {
                        "Interfaces": {
                            "Interface": [{"IfIndex": "101", "Name": "GigabitEthernet1/0/1"}]
                        }
                    },
                    "Route": {
                        "Ipv4Routes": {
                            "RouteEntry": [
                                {
                                    "Ipv4": {
                                        "Ipv4Address": "10.10.10.0",
                                        "Ipv4PrefixLength": "24",
                                    },
                                    "Nexthop": "192.0.2.1",
                                    "IfIndex": "101",
                                    "Protocol": {"ProtocolID": "64", "SubProtocolID": ""},
                                    "ProcessID": "100",
                                    "Preference": "255",
                                    "Metric": "10",
                                    "VRF": "_public_",
                                    "Topology": "base",
                                    "Neighbor": "192.0.2.2",
                                    "Age": "00:01:05",
                                    "ASNumber": {"OriginAS": "65001", "LastAS": "65002"},
                                }
                            ]
                        }
                    },
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["prefix"], "10.10.10.0/24")
        self.assertEqual(result[0]["next_hop"], "192.0.2.1")
        self.assertEqual(result[0]["interface"], "GigabitEthernet1/0/1")
        self.assertEqual(result[0]["protocol"], "bgp")
        self.assertEqual(result[0]["origin_as"], "65001")
        self.assertEqual(result[0]["last_as"], "65002")

    def test_h3c_mac_netconf_processor_maps_ifindex_and_status(self):
        result = process_h3c_mac_netconf(
            {
                "top": {
                    "Ifmgr": {
                        "Interfaces": {
                            "Interface": [{"IfIndex": "101", "Name": "GigabitEthernet1/0/1"}]
                        }
                    },
                    "L2FDB": {
                        "UnicastTables": {
                            "UnicastTable": [
                                {
                                    "MacAddress": "aa-bb-cc-dd-ee-ff",
                                    "VLANID": "100",
                                    "IfIndex": "101",
                                    "Status": "2",
                                }
                            ]
                        }
                    },
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["macaddress"], "aabb-ccdd-eeff")
        self.assertEqual(result[0]["vlan"], "100")
        self.assertEqual(result[0]["interface"], "GigabitEthernet1/0/1")
        self.assertEqual(result[0]["type"], "Learned")

    def test_h3c_ip_interface_netconf_processor_builds_location(self):
        result = process_h3c_ip_interface_netconf(
            {
                "top": {
                    "Ipv4AddressTable": {
                        "Ipv4Address": [
                            {
                                "Name": "Vlan-interface100",
                                "Ipv4Address": "10.10.10.1",
                                "Ipv4Mask": "255.255.255.0",
                                "type": "Primary",
                                "MTU": "1500",
                            }
                        ]
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["interface"], "Vlan-interface100")
        self.assertEqual(result[0]["ipaddress"], "10.10.10.1")
        self.assertEqual(result[0]["ipmask"], "255.255.255.0")
        self.assertEqual(result[0]["ip_type"], "Primary")
        self.assertEqual(result[0]["mtu"], "1500")
        self.assertEqual(result[0]["location"][0]["start"], 168430080)
        self.assertEqual(result[0]["location"][0]["end"], 168430335)

    @patch("apps.device_api.processors.h3c._lookup_neighbor_ip", return_value="192.0.2.10")
    def test_h3c_lldp_netconf_processor_enriches_neighbor_ip(self, mock_lookup_neighbor_ip):
        result = process_h3c_lldp_netconf(
            {
                "top": {
                    "Lldp": {
                        "Neighbors": {
                            "Neighbor": [
                                {
                                    "LocalPort": "GE1/0/1",
                                    "ChassisId": "0011-2233-4455",
                                    "PortId": "GE0/0/1",
                                    "SystemName": "core-sw-1",
                                    "Address": "192.0.2.10",
                                    "SubType": "ipv4",
                                }
                            ]
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["local_interface"], "GigabitEthernet1/0/1")
        self.assertEqual(result[0]["neighbor_port"], "GE0/0/1")
        self.assertEqual(result[0]["neighborsysname"], "core-sw-1")
        self.assertEqual(result[0]["neighbor_ip"], "192.0.2.10")
        mock_lookup_neighbor_ip.assert_called_once_with("core-sw-1")

    def test_h3c_aggre_port_netconf_processor_maps_members_and_mode(self):
        result = process_h3c_aggre_port_netconf(
            {
                "top": {
                    "LAGG": {
                        "Groups": {
                            "Group": [
                                {
                                    "GroupId": "47",
                                    "Name": "Bridge-Aggregation47",
                                    "LinkMode": "Dynamic",
                                    "Memberlist": [
                                        {"Name": "GE1/0/1", "SelectedStatus": "Selected."},
                                        {"Name": "GE1/0/2", "SelectedStatus": "Selected."},
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["aggregroup"], "Bridge-Aggregation47")
        self.assertEqual(
            result[0]["memberports"],
            ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"],
        )
        self.assertEqual(result[0]["status"], "Selected.,Selected.")
        self.assertEqual(result[0]["mode"], "Dynamic")

    def test_huawei_route_table_netconf_processor_extracts_static_routes(self):
        result = process_huawei_route_table_netconf(
            {
                "routing": {
                    "routing-instance": [
                        {
                            "name": "_public_",
                            "routing-protocols": {
                                "routing-protocol": [
                                    {
                                        "static-routes": {
                                            "v4ur:ipv4": {
                                                "v4ur:route": [
                                                    {
                                                        "v4ur:destination-prefix": "172.16.0.0/16",
                                                        "v4ur:next-hop": {
                                                            "v4ur:next-hop-address": "192.0.2.254"
                                                        },
                                                        "hw-v4sr:preference": "60",
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["prefix"], "172.16.0.0/16")
        self.assertEqual(result[0]["next_hop"], "192.0.2.254")
        self.assertEqual(result[0]["protocol"], "static")
        self.assertEqual(result[0]["preference"], "60")
        self.assertEqual(result[0]["vrf"], "")

    def test_huawei_arp_netconf_processor_maps_fields(self):
        result = process_huawei_arp_netconf(
            {
                "arpTable": {
                    "arpEntry": [
                        {
                            "ipAddr": "172.16.49.11",
                            "macAddr": "6c92-bf3b-d721",
                            "expireTime": "12",
                            "styleType": "DynamicArp",
                            "ifName": "Eth-Trunk416",
                            "peVid": "549",
                            "vrfName": "_public_",
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ipaddress"], "172.16.49.11")
        self.assertEqual(result[0]["macaddress"], "6c92-bf3b-d721")
        self.assertEqual(result[0]["vlan"], "549")
        self.assertEqual(result[0]["interface"], "Eth-Trunk416")
        self.assertEqual(result[0]["type"], "DynamicArp")

    def test_huawei_mac_netconf_processor_maps_vlan_and_interface(self):
        result = process_huawei_mac_netconf(
            {
                "macTable": {
                    "item": [
                        {
                            "slotId": "0",
                            "vlanId": "654",
                            "macAddress": "d4ae-52a7-b954",
                            "macType": "dynamic",
                            "outIfName": "Eth-Trunk227",
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["macaddress"], "d4ae-52a7-b954")
        self.assertEqual(result[0]["vlan"], "654")
        self.assertEqual(result[0]["interface"], "Eth-Trunk227")
        self.assertEqual(result[0]["type"], "dynamic")

    def test_huawei_mac_bd_netconf_processor_maps_bd_fields(self):
        result = process_huawei_mac_bd_netconf(
            {
                "mac": {
                    "bdFdbs": {
                        "bdFdb": {
                            "slotId": "0",
                            "macAddress": "00e0-ed73-81e0",
                            "bdId": "11003",
                            "vid": "100",
                            "macType": "dynamic",
                            "outIfName": "Eth-Trunk24.1",
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["macaddress"], "00e0-ed73-81e0")
        self.assertEqual(result[0]["bd_id"], "11003")
        self.assertEqual(result[0]["vlan"], "100")
        self.assertEqual(result[0]["interface"], "Eth-Trunk24")
        self.assertEqual(result[0]["type"], "dynamic")

    def test_huawei_mac_vxlan_netconf_processor_maps_overlay_fields(self):
        result = process_huawei_mac_vxlan_netconf(
            {
                "mac": {
                    "vxlanFdbs": {
                        "vxlanFdb": {
                            "slotId": "0",
                            "macAddress": "00e0-ed7a-5f38",
                            "bdId": "11003",
                            "macType": "evn",
                            "sourceIP": "10.1.1.1",
                            "peerIP": "10.1.1.2",
                            "vnId": "501001",
                            "tunnelType": "IPv4",
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bd_id"], "11003")
        self.assertEqual(result[0]["vn_id"], "501001")
        self.assertEqual(result[0]["source_ip"], "10.1.1.1")
        self.assertEqual(result[0]["peer_ip"], "10.1.1.2")
        self.assertEqual(result[0]["tunnel_type"], "IPv4")

    def test_huawei_mac_vxlan_control_netconf_processor_maps_ipv6_overlay_fields(self):
        result = process_huawei_mac_vxlan_control_netconf(
            {
                "mac": {
                    "vxlanControls": {
                        "vxlanControl": {
                            "slotId": "0",
                            "macAddress": "00e0-ed7a-5f38",
                            "bdId": "11003",
                            "macType": "evn",
                            "tunnelType": "IPv6",
                            "sourceIpv6": "2001:db8::1",
                            "peerIpv6": "2001:db8::2",
                            "vnId": "501001",
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bd_id"], "11003")
        self.assertEqual(result[0]["vn_id"], "501001")
        self.assertEqual(result[0]["source_ip"], "2001:db8::1")
        self.assertEqual(result[0]["peer_ip"], "2001:db8::2")
        self.assertEqual(result[0]["tunnel_type"], "IPv6")

    def test_huawei_vxlan_capability_netconf_processor_maps_capability_flags(self):
        from apps.device_api.processors.huawei import process_vxlan_capability_netconf

        result = process_vxlan_capability_netconf(
            {
                "bridge-domains": {
                    "bridge-domain": [
                        {"id": "11003"},
                        {"id": "11004"},
                    ]
                },
                "vxlan": {
                    "vni": [
                        {"vni": "501001"},
                        {"vni": "501002"},
                    ],
                    "nveIfName": "Nve1",
                },
                "bgp": {
                    "bgpcomm": {
                        "bgpVrfs": {
                            "bgpVrf": {
                                "vrfName": "_public_",
                                "bgpVrfAFs": {
                                    "bgpVrfAF": [
                                        {"afType": "l2vpn-evpn"},
                                        {"afType": "ipv4-unicast"},
                                    ]
                                },
                            }
                        }
                    }
                },
            }
        )

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["has_bd"])
        self.assertEqual(result[0]["bd_count"], 2)
        self.assertTrue(result[0]["has_vxlan_vni"])
        self.assertEqual(result[0]["vni_count"], 2)
        self.assertTrue(result[0]["has_nve"])
        self.assertTrue(result[0]["has_evpn_bgp"])
        self.assertEqual(result[0]["evpn_af_count"], 1)

    def test_huawei_ip_interface_netconf_processor_extracts_ipv4_oper(self):
        result = process_huawei_ip_interface_netconf(
            {
                "interfaces": {
                    "interface": [
                        {
                            "ifName": "Vlanif100",
                            "ifDynamicInfo": {
                                "ifLinkStatus": "up",
                                "ifV4State": "up",
                                "ifOpertMTU": "1500",
                            },
                            "ipv4Oper": {
                                "ipv4Addrs": {
                                    "ipv4Addr": {
                                        "ifIpAddr": "10.0.0.1",
                                        "subnetMask": "255.255.255.0",
                                        "addrType": "primary",
                                    }
                                }
                            },
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["interface"], "Vlanif100")
        self.assertEqual(result[0]["line_status"], "up")
        self.assertEqual(result[0]["protocol_status"], "up")
        self.assertEqual(result[0]["ipaddress"], "10.0.0.1")
        self.assertEqual(result[0]["ipmask"], "255.255.255.0")
        self.assertEqual(result[0]["location"][0]["start"], 167772160)
        self.assertEqual(result[0]["location"][0]["end"], 167772415)

    @patch("apps.device_api.processors.huawei._lookup_neighbor_ip", return_value="192.0.2.11")
    def test_huawei_lldp_netconf_processor_enriches_neighbor_ip(self, mock_lookup_neighbor_ip):
        result = process_huawei_lldp_netconf(
            {
                "lldpIfs": {
                    "lldpIf": [
                        {
                            "ifName": "GE1/0/1",
                            "lldpNeighbors": {
                                "lldpNeighbor": {
                                    "chassisId": "0011-2233-4455",
                                    "portId": "GE0/0/1",
                                    "portDescription": "uplink",
                                    "systemName": "agg-sw-1",
                                    "managementAddresss": {
                                        "managementAddress": {
                                            "manAddr": "192.0.2.11",
                                            "manAddrSubtype": "ipv4",
                                        }
                                    },
                                }
                            },
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["local_interface"], "GigabitEthernet1/0/1")
        self.assertEqual(result[0]["neighbor_port"], "GE0/0/1")
        self.assertEqual(result[0]["management_ip"], "192.0.2.11")
        self.assertEqual(result[0]["neighbor_ip"], "192.0.2.11")
        mock_lookup_neighbor_ip.assert_called_once_with("agg-sw-1")

    def test_huawei_aggre_port_netconf_processor_maps_members(self):
        result = process_huawei_aggre_port_netconf(
            {
                "trunks": {
                    "trunk": [
                        {
                            "ifName": "Eth-Trunk10",
                            "TrunkMemberIfs": {
                                "TrunkMemberIf": [
                                    {"memberIfName": "GE1/0/1", "memberIfState": "up"},
                                    {"memberIfName": "GE1/0/2", "memberIfState": "up"},
                                ]
                            },
                        }
                    ]
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["aggregroup"], "Eth-Trunk10")
        self.assertEqual(
            result[0]["memberports"],
            ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2"],
        )
        self.assertEqual(result[0]["status"], "up,up")

    def test_h3c_bgp_summary_netconf_processor_aggregates_neighbor_states(self):
        result = process_h3c_bgp_summary_netconf(
            {
                "top": {
                    "BGP": {
                        "Sessions": {
                            "Session": [
                                {"AF": "ipv4-unicast", "VRF": "_public_", "State": "Established"},
                                {"AF": "ipv4-unicast", "VRF": "_public_", "State": "Idle"},
                                {"AF": "ipv4-unicast", "VRF": "_public_", "State": "Established"},
                            ]
                        }
                    }
                }
            }
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["address_family"], "ipv4-unicast")
        self.assertEqual(result[0]["total_peers"], 3)
        self.assertEqual(result[0]["established_peers"], 2)
        self.assertEqual(result[0]["non_established_peers"], 1)
        self.assertEqual(result[0]["dominant_state"], "Established")

    def test_h3c_netconf_capability_processor_maps_schema_features(self):
        result = process_h3c_netconf_capability_netconf(
            {
                "netconf-state": {
                    "schemas": {
                        "schema": [
                            {
                                "identifier": "openconfig-bgp",
                                "namespace": "http://openconfig.net/yang/bgp",
                            },
                            {
                                "identifier": "h3c-bgp",
                                "namespace": "http://www.h3c.com/netconf/data:1.0/bgp",
                            },
                            {
                                "identifier": "h3c-l2vpn",
                                "namespace": "http://www.h3c.com/netconf/data:1.0/l2vpn",
                            },
                            {
                                "identifier": "h3c-ifmgr",
                                "namespace": "http://www.h3c.com/netconf/data:1.0/ifmgr",
                            },
                            {
                                "identifier": "openconfig-telemetry",
                                "namespace": "http://openconfig.net/yang/telemetry",
                            },
                        ]
                    }
                }
            }
        )

        self.assertEqual(result[0]["schema_count"], 5)
        self.assertEqual(result[0]["openconfig_schema_count"], 2)
        self.assertTrue(result[0]["has_bgp_schema"])
        self.assertTrue(result[0]["has_l2vpn_schema"])
        self.assertTrue(result[0]["has_ifmgr_schema"])
        self.assertTrue(result[0]["has_telemetry_schema"])

    def test_h3c_cli_output_capability_processor_detects_unrecognized_irf(self):
        result = process_h3c_cli_output_capability_netmiko(
            "% Unrecognized command found at '^' position."
        )

        self.assertFalse(result[0]["supports_irf_cli"])
        self.assertTrue(result[0]["command_unrecognized"])
        self.assertFalse(result[0]["has_irf_members"])

    def test_h3c_cli_output_capability_processor_detects_irf_members(self):
        result = process_h3c_cli_output_capability_netmiko(
            "MemberID  Role      Priority  CPU-Mac\n1         Master    1         0011-2233-4455"
        )

        self.assertTrue(result[0]["supports_irf_cli"])
        self.assertFalse(result[0]["command_unrecognized"])
        self.assertTrue(result[0]["has_irf_members"])

    def test_huawei_isis_neighbors_netmiko_processor_normalizes_peer_ip(self):
        result = process_huawei_isis_neighbors_netmiko(
            [
                {
                    "system_id": "0000.0000.0001",
                    "local_interface": "GE1/0/1",
                    "circuit_id": "10",
                    "state": "Up",
                    "hold_time": "24",
                    "neighbor_type": "L1L2",
                    "priority": "64",
                    "area": "49.0001",
                    "peer_ip": "192.0.2.10 secondary",
                    "uptime": "1d02h",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["peer_ip"], "192.0.2.10")
        self.assertEqual(result[0]["system_id"], "0000.0000.0001")
        self.assertEqual(result[0]["neighbor_type"], "L1L2")

    def test_textfsm_index_contains_new_routing_templates(self):
        index_path = (
            Path(__file__).resolve().parents[2]
            / "utils"
            / "connect_layer"
            / "zetmiko"
            / "templates"
            / "index"
        )
        index_content = index_path.read_text(encoding="utf-8")

        self.assertIn("hp_comware_display_ospf_peer.textfsm", index_content)
        self.assertIn("hp_comware_display_ospf_interface.textfsm", index_content)
        self.assertIn("hp_comware_display_isis_peer_verbose.textfsm", index_content)
        self.assertIn("huawei_vrp_display_ospf_peer_brief.textfsm", index_content)
        self.assertIn("huawei_vrp_display_ospf_interface.textfsm", index_content)
        self.assertIn("huawei_vrp_display_isis_peer_verbose.textfsm", index_content)

    def test_profile_netmiko_defaults_have_commands_templates_and_index_entries(self):
        index_content = (TEMPLATE_BASE_DIR / "index").read_text(encoding="utf-8")

        for profile_code, mapping in PROFILE_NETMIKO_SUB_PLAN_DEFAULTS.items():
            for collection_type, item in mapping.items():
                with self.subTest(profile=profile_code, collection_type=collection_type):
                    self.assertTrue(item.get("command"))
                    if collection_type in RAW_NETMIKO_COLLECTION_TYPES:
                        self.assertEqual(item.get("template", ""), "")
                    else:
                        self.assertTrue(item.get("template"))
                        self.assertTrue((TEMPLATE_BASE_DIR / item["template"]).exists())
                        self.assertIn(item["template"], index_content)

    def test_huawei_ospf_peer_brief_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "huawei_vrp_display_ospf_peer_brief.textfsm",
            (
                "Area Interface Router ID Address State Pri Dead-Time\n"
                "0.0.0.0 GE1/0/1 1.1.1.1 192.0.2.1 Full 1 00:00:31\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["AREA_ID"], "0.0.0.0")
        self.assertEqual(rows[0]["INTERFACE"], "GE1/0/1")
        self.assertEqual(rows[0]["NEIGHBOR_IP"], "192.0.2.1")

    def test_huawei_ospf_interface_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "huawei_vrp_display_ospf_interface.textfsm",
            (
                "Area Interface IP Address Type State Cost Pri DR BDR Hello/Dead\n"
                "0.0.0.0 GE1/0/1 192.0.2.2 P2P FULL 10 1 192.0.2.3 192.0.2.4 10 40\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["AREA"], "0.0.0.0")
        self.assertEqual(rows[0]["INTERFACE_IP"], "192.0.2.2")
        self.assertEqual(rows[0]["DEAD_INTERVAL"], "40")

    def test_huawei_isis_peer_verbose_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "huawei_vrp_display_isis_peer_verbose.textfsm",
            (
                "System Id Interface Circuit State Hold Type Pri Area PeerIP Uptime\n"
                "0000.0000.0001 GE1/0/1 001 Up 26 L1L2 64 49.0001 192.0.2.10 1d02h\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SYSTEM_ID"], "0000.0000.0001")
        self.assertEqual(rows[0]["LOCAL_INTERFACE"], "GE1/0/1")
        self.assertEqual(rows[0]["PEER_IP"], "192.0.2.10")

    def test_h3c_ospf_peer_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "hp_comware_display_ospf_peer.textfsm",
            (
                "Area Interface Router ID Address State Pri Dead-Time\n"
                "0.0.0.0 GE1/0/1 2.2.2.2 192.0.2.11 Full 1 00:00:39\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["AREA"], "0.0.0.0")
        self.assertEqual(rows[0]["ROUTER_ID"], "2.2.2.2")
        self.assertEqual(rows[0]["ADDRESS"], "192.0.2.11")

    def test_h3c_ospf_interface_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "hp_comware_display_ospf_interface.textfsm",
            (
                "Area Interface IP Address Type State Cost Pri DR BDR Hello/Dead\n"
                "0.0.0.0 GE1/0/2 192.0.2.12 BROADCAST DR 10 1 192.0.2.13 192.0.2.14 10 40\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["INTERFACE"], "GE1/0/2")
        self.assertEqual(rows[0]["NETWORK_TYPE"], "BROADCAST")
        self.assertEqual(rows[0]["HELLO_INTERVAL"], "10")

    def test_h3c_isis_peer_verbose_template_parses_cli_rows(self):
        rows = self._parse_textfsm_rows(
            "hp_comware_display_isis_peer_verbose.textfsm",
            (
                "System Id Interface Circuit State Hold Type Pri Area PeerIP Uptime\n"
                "0000.0000.0002 GE1/0/2 002 Up 23 L2 127 49.0002 192.0.2.15 2d03h\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SYSTEM_ID"], "0000.0000.0002")
        self.assertEqual(rows[0]["NEIGHBOR_TYPE"], "L2")
        self.assertEqual(rows[0]["UPTIME"], "2d03h")

    def test_h3c_version_template_parses_feature_patch(self):
        rows = self._parse_textfsm_rows(
            "hp_comware_display_version.textfsm",
            (
                "H3C Comware Software, Version 7.1.070, Feature 2707\n"
                "\n"
                "Slot 1:\n"
                "BOARD TYPE:         S6860-54HF\n"
                "Release Version:    H3C S6860-54HF-2707\n"
                "Patch Version:      Feature 2707H17\n"
                "\n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["BOARD_TYPE"], "S6860-54HF")
        self.assertEqual(rows[0]["Version"], "7.1.070, Feature 2707")
        self.assertEqual(rows[0]["Patch_Ver"], "Feature 2707H17")

    def test_h3c_link_aggregation_template_parses_local_members(self):
        rows = self._parse_textfsm_rows(
            "hp_comware_display_link-aggregation_verbose.textfsm",
            (
                "Aggregate Interface: Bridge-Aggregation53\n"
                "Aggregation Mode: Dynamic\n"
                "Local: \n"
                "  Port                Status   Priority Index    Oper-Key               Flag\n"
                "  FGE1/0/53           S        32768    1        1                      {ACDEF}\n"
                "  FGE1/0/54           S        32768    5        1                      {ACDEF}\n"
                "Remote: \n"
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["AGGNAME"], "Bridge-Aggregation53")
        self.assertEqual(rows[0]["MODE"], "Dynamic")
        self.assertEqual(rows[0]["MEMBERPORTS"], ["FGE1/0/53", "FGE1/0/54"])
        self.assertEqual(rows[0]["STATUS"], ["S", "S"])


class DeviceApiHealthExtensionTests(SimpleTestCase):
    databases = {"default"}

    def test_default_collection_types_include_health_types(self):
        expected_types = {
            "fan_status",
            "power_status",
            "temperature_status",
            "clock_status",
        }

        self.assertTrue(expected_types.issubset(set(DEFAULT_COLLECTION_TYPES)))
        self.assertIn("fan_id", get_collection_output_fields("fan_status"))
        self.assertIn("output_power", get_collection_output_fields("power_status"))
        self.assertIn("temperature", get_collection_output_fields("temperature_status"))
        self.assertIn("device_datetime", get_collection_output_fields("clock_status"))

    def test_collection_type_mongo_map_contains_health_collections(self):
        expected_types = {
            "fan_status",
            "power_status",
            "temperature_status",
            "clock_status",
        }

        self.assertTrue(expected_types.issubset(set(COLLECTION_TYPE_MONGO_MAP.keys())))

    def test_h3c_fan_status_processor_maps_textfsm_fields(self):
        result = process_h3c_fan_status_netmiko(
            [
                {
                    "Slot": "1",
                    "FanID": "2",
                    "State": "Normal",
                    "AirflowDirection": "front-to-back",
                    "PreferAirflowDirection": "front-to-back",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slot"], "1")
        self.assertEqual(result[0]["fan_id"], "2")
        self.assertEqual(result[0]["fan_name"], "Fan2")
        self.assertEqual(result[0]["status"], "Normal")
        self.assertEqual(result[0]["airflow_direction"], "front-to-back")

    def test_h3c_power_status_processor_maps_textfsm_fields(self):
        result = process_h3c_power_status_netmiko(
            [
                {
                    "Slot": "1",
                    "PowerID": "1",
                    "State": "Supply",
                    "Mode": "AC",
                    "Current": "4.2",
                    "Voltage": "220",
                    "Power": "600",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["power_id"], "1")
        self.assertEqual(result[0]["power_name"], "Power1")
        self.assertEqual(result[0]["status"], "Supply")
        self.assertEqual(result[0]["output_power"], "600")

    def test_huawei_power_status_processor_maps_textfsm_fields(self):
        result = process_huawei_power_status_netmiko(
            [
                {
                    "Chassis": "1",
                    "Slot": "2",
                    "PowerNo": "PWR1",
                    "Present": "Present",
                    "Mode": "AC",
                    "State": "Supply",
                    "Current": "2.3",
                    "Voltage": "220",
                    "RealPwr": "450",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chassis"], "1")
        self.assertEqual(result[0]["slot"], "2")
        self.assertEqual(result[0]["power_id"], "PWR1")
        self.assertEqual(result[0]["present"], "Present")
        self.assertEqual(result[0]["output_power"], "450")

    def test_huawei_temperature_status_processor_maps_textfsm_fields(self):
        result = process_huawei_temperature_status_netmiko(
            [
                {
                    "SLOTID": "SRU1",
                    "PCB": "PCB1",
                    "STATUS": "NORMAL",
                    "TEMPERATURE": "38",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slot"], "SRU1")
        self.assertEqual(result[0]["sensor"], "PCB1")
        self.assertEqual(result[0]["status"], "NORMAL")
        self.assertEqual(result[0]["temperature"], "38")

    def test_ruijie_fan_status_processor_maps_textfsm_fields(self):
        result = process_ruijie_fan_status_netmiko(
            [
                {
                    "Item": "1",
                    "Name": "FAN1",
                    "Slot": "1/1",
                    "Level": "auto",
                    "Status": "Normal",
                    "Speed": "9600RPM",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fan_id"], "1")
        self.assertEqual(result[0]["fan_name"], "FAN1")
        self.assertEqual(result[0]["slot"], "1/1")
        self.assertEqual(result[0]["status"], "Normal")
        self.assertEqual(result[0]["speed"], "9600RPM")

    def test_ruijie_power_status_processor_maps_textfsm_fields(self):
        result = process_ruijie_power_status_netmiko(
            [
                {
                    "Item": "1",
                    "Name": "RG-PA150I-F",
                    "Slot": "1/1",
                    "Type": "AC",
                    "OutPower": "112W",
                    "Vol": "220V",
                    "Status": "Normal",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["power_id"], "1")
        self.assertEqual(result[0]["power_name"], "RG-PA150I-F")
        self.assertEqual(result[0]["slot"], "1/1")
        self.assertEqual(result[0]["status"], "Normal")
        self.assertEqual(result[0]["output_power"], "112W")

    def test_h3c_clock_status_processor_maps_textfsm_fields(self):
        result = process_h3c_clock_status_netmiko(
            [
                {
                    "TIME": "12:34:56",
                    "TIMEZONE": "CST",
                    "DAYWEEK": "Thu",
                    "MONTH": "3",
                    "DAY": "14",
                    "YEAR": "2026",
                }
            ]
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device_time"], "12:34:56")
        self.assertEqual(result[0]["timezone"], "CST")
        self.assertEqual(result[0]["weekday"], "Thu")
        self.assertEqual(result[0]["device_date"], "2026-03-14")
        self.assertEqual(result[0]["device_datetime"], "2026-03-14 12:34:56")

    def test_apply_profile_defaults_populates_h3c_cli_templates(self):
        sub_plan = SimpleNamespace(
            collection_type="arp",
            description="",
            netmiko_method="",
            textfsm_template="",
            netmiko_enabled=False,
            save=Mock(),
        )
        plan = SimpleNamespace(collect_plans=SimpleNamespace(all=lambda: [sub_plan]))
        profile = SimpleNamespace(
            code="H3C-legacy-cli",
            vendor_alias="H3C",
            preferred_methods={"arp": ["netmiko"]},
            fallback_methods={},
            supported_collection_types=["arp"],
        )

        PlatformProfileService.apply_profile_defaults(plan, profile)

        self.assertEqual(sub_plan.netmiko_method, "display arp")
        self.assertEqual(sub_plan.textfsm_template, "hp_comware_display_arp.textfsm")
        self.assertTrue(sub_plan.netmiko_enabled)
        sub_plan.save.assert_called_once()

    def test_apply_profile_defaults_uses_huawei_cli_fallback(self):
        sub_plan = SimpleNamespace(
            collection_type="arp",
            description="",
            netmiko_method="",
            textfsm_template="",
            netmiko_enabled=False,
            save=Mock(),
        )
        plan = SimpleNamespace(collect_plans=SimpleNamespace(all=lambda: [sub_plan]))
        profile = SimpleNamespace(
            code="Huawei-CE",
            vendor_alias="Huawei",
            preferred_methods={"arp": ["netconf", "netmiko"]},
            fallback_methods={"arp": ["netmiko"]},
            supported_collection_types=["arp"],
        )

        PlatformProfileService.apply_profile_defaults(plan, profile)

        self.assertEqual(sub_plan.netmiko_method, "display arp")
        self.assertEqual(sub_plan.textfsm_template, "huawei_vrp_display_arp.textfsm")
        self.assertTrue(sub_plan.netmiko_enabled)

    def test_resolve_plan_collection_method_defaults_to_netmiko(self):
        profile = SimpleNamespace(
            preferred_methods={
                "arp": ["netconf", "netmiko"],
                "mac": ["netmiko"],
            }
        )

        result = PlatformProfileService.resolve_plan_collection_method(profile)

        self.assertEqual(result, DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO)

    def test_normalize_device_category_supports_localized_names(self):
        self.assertEqual(
            PlatformProfileService.normalize_device_category("交换机"),
            "switch",
        )
        self.assertEqual(
            PlatformProfileService.normalize_device_category("防火墙"),
            "firewall",
        )
        self.assertEqual(
            PlatformProfileService.normalize_device_category("TAP交换机"),
            "switch",
        )

    def test_match_profile_for_h3c_router_and_firewall_devices(self):
        profiles = [
            SimpleNamespace(
                code=item["code"],
                vendor_alias=item["vendor_alias"],
                category=item["category"],
                series_patterns=item["series_patterns"],
                version_patterns=item["version_patterns"],
            )
            for item in BUILTIN_PLATFORM_PROFILES
        ]
        router = SimpleNamespace(
            vendor=SimpleNamespace(alias="H3C"),
            category=SimpleNamespace(name="路由器"),
            model=SimpleNamespace(name="SR8802-X-S"),
            soft_version="7.1",
            name="router-a",
        )
        firewall = SimpleNamespace(
            vendor=SimpleNamespace(alias="H3C"),
            category=SimpleNamespace(name="防火墙"),
            model=SimpleNamespace(name="SecPath F5060"),
            soft_version="7.1",
            name="fw-a",
        )

        router_profile = PlatformProfileService.match_profile_for_device(router, profiles=profiles)
        firewall_profile = PlatformProfileService.match_profile_for_device(firewall, profiles=profiles)

        self.assertEqual(router_profile.code, "H3C-router-cli")
        self.assertEqual(firewall_profile.code, "H3C-firewall-cli")

    def test_match_profile_for_h3c_s98xx_switch_device(self):
        profiles = [
            SimpleNamespace(
                code=item["code"],
                vendor_alias=item["vendor_alias"],
                category=item["category"],
                series_patterns=item["series_patterns"],
                version_patterns=item["version_patterns"],
            )
            for item in BUILTIN_PLATFORM_PROFILES
        ]
        switch = SimpleNamespace(
            vendor=SimpleNamespace(alias="H3C"),
            category=SimpleNamespace(name="交换机"),
            model=SimpleNamespace(name="S9825-64D"),
            soft_version="9.1.043 Release 9131",
            name="s98-core-a",
        )

        profile = PlatformProfileService.match_profile_for_device(switch, profiles=profiles)

        self.assertEqual(profile.code, "H3C-S98xx-cli")

    def test_match_profile_for_huawei_router_device(self):
        profiles = [
            SimpleNamespace(
                code=item["code"],
                vendor_alias=item["vendor_alias"],
                category=item["category"],
                series_patterns=item["series_patterns"],
                version_patterns=item["version_patterns"],
            )
            for item in BUILTIN_PLATFORM_PROFILES
        ]
        router = SimpleNamespace(
            vendor=SimpleNamespace(alias="Huawei"),
            category=SimpleNamespace(name="路由器"),
            model=SimpleNamespace(name="AR6280"),
            soft_version="V300R021",
            name="huawei-router-a",
        )

        router_profile = PlatformProfileService.match_profile_for_device(router, profiles=profiles)

        self.assertEqual(router_profile.code, "Huawei-router-cli")

    def test_match_profile_for_huawei_ce98xx_device(self):
        profiles = [
            SimpleNamespace(
                code=item["code"],
                vendor_alias=item["vendor_alias"],
                category=item["category"],
                series_patterns=item["series_patterns"],
                version_patterns=item["version_patterns"],
            )
            for item in BUILTIN_PLATFORM_PROFILES
        ]
        switch = SimpleNamespace(
            vendor=SimpleNamespace(alias="Huawei"),
            category=SimpleNamespace(name="交换机"),
            model=SimpleNamespace(name="CE9860EI"),
            soft_version="V800R023C05SPC200",
            name="ce9860-a",
        )

        profile = PlatformProfileService.match_profile_for_device(switch, profiles=profiles)

        self.assertEqual(profile.code, "Huawei-CE98xx")

    def test_match_profile_for_huawei_ce88xx_device(self):
        profiles = [
            SimpleNamespace(
                code=item["code"],
                vendor_alias=item["vendor_alias"],
                category=item["category"],
                series_patterns=item["series_patterns"],
                version_patterns=item["version_patterns"],
            )
            for item in BUILTIN_PLATFORM_PROFILES
        ]
        switch = SimpleNamespace(
            vendor=SimpleNamespace(alias="Huawei"),
            category=SimpleNamespace(name="交换机"),
            model=SimpleNamespace(name="CE8850EI"),
            soft_version="V800R023C05SPC200",
            name="ce8850-a",
        )

        profile = PlatformProfileService.match_profile_for_device(switch, profiles=profiles)

        self.assertEqual(profile.code, "Huawei-CE88xx")

    @patch("apps.device_api.platform_profiles.PlatformProfileService.load_device_capability_facts")
    def test_match_profile_prefers_capability_profile_when_probe_succeeds(self, mock_load_capability_facts):
        profiles = [
            SimpleNamespace(
                code="Huawei-CE",
                vendor_alias="Huawei",
                category="switch",
                series_patterns=[r"^CE6\d+"],
                version_patterns=[r".*"],
            ),
            SimpleNamespace(
                code="Huawei-CE68xx-netconf",
                vendor_alias="Huawei",
                category="switch",
                series_patterns=[r"^CE6\d+"],
                version_patterns=[r".*"],
            ),
        ]
        switch = SimpleNamespace(
            vendor=SimpleNamespace(alias="Huawei"),
            category=SimpleNamespace(name="交换机"),
            model=SimpleNamespace(name="CE6857F"),
            soft_version="V800R022C05SPC500",
            name="ce6857-a",
        )
        mock_load_capability_facts.return_value = {
            "protocols": {"netconf": True, "ssh": True},
            "probes": {
                "netconf_capability": {
                    "ran_success": True,
                    "has_bd": False,
                    "has_vxlan_vni": False,
                    "has_nve": False,
                    "has_evpn_bgp": True,
                }
            },
        }

        profile = PlatformProfileService.match_profile_for_device(switch, profiles=profiles)

        self.assertEqual(profile.code, "Huawei-CE68xx-netconf")

    @patch("apps.device_api.platform_profiles.PlatformProfileService.load_device_capability_facts")
    def test_match_profile_prefers_h3c_s98xx_when_netconf_capability_is_richer(self, mock_load_capability_facts):
        profiles = [
            SimpleNamespace(
                code="H3C-modern-netconf",
                vendor_alias="H3C",
                category="switch",
                series_patterns=[r"^S\d+"],
                version_patterns=[r".*"],
            ),
            SimpleNamespace(
                code="H3C-S98xx-cli",
                vendor_alias="H3C",
                category="switch",
                series_patterns=[r"^S\d+"],
                version_patterns=[r".*"],
            ),
        ]
        switch = SimpleNamespace(
            vendor=SimpleNamespace(alias="H3C"),
            category=SimpleNamespace(name="交换机"),
            model=SimpleNamespace(name="S9825-64D"),
            soft_version="9.1.0439131",
            name="s98-core-a",
        )
        mock_load_capability_facts.return_value = {
            "protocols": {"netconf": True, "ssh": True},
            "probes": {
                "netconf_capability": {
                    "ran_success": True,
                    "schema_count": 425,
                    "has_l2vpn_schema": True,
                    "has_telemetry_schema": True,
                }
            },
        }

        profile = PlatformProfileService.match_profile_for_device(switch, profiles=profiles)

        self.assertEqual(profile.code, "H3C-S98xx-cli")

    @patch("apps.device_api.platform_profiles.PlatformProfileService.load_device_capability_facts")
    def test_build_capabilities_includes_capability_facts(self, mock_load_capability_facts):
        vendor, _ = Vendor.objects.get_or_create(name="华为", defaults={"alias": "Huawei"})
        category, _ = Category.objects.get_or_create(name="switch")
        model, _ = Model.objects.get_or_create(name="CE6857F", vendor=vendor)
        device, _ = NetworkDevice.objects.update_or_create(
            serial_num="SER-CAP-001",
            defaults={
                "name": "ce6857-a",
                "manage_ip": "10.0.0.9",
                "vendor": vendor,
                "category": category,
                "model": model,
                "soft_version": "V800R022C05SPC500",
            },
        )
        mock_load_capability_facts.return_value = {
            "protocols": {"netconf": True, "ssh": False},
            "probes": {"netconf_capability": {"ran_success": True, "has_evpn_bgp": True}},
        }

        payload = PlatformProfileService.build_capabilities(device)

        self.assertIn("capability_facts", payload)
        self.assertTrue(payload["capability_facts"]["probes"]["netconf_capability"]["has_evpn_bgp"])

    def test_audit_plan_readiness_flags_missing_templates(self):
        sub_plan = SimpleNamespace(
            collection_type="arp",
            netmiko_enabled=True,
            textfsm_template="",
            netconf_enabled=True,
            xml_templates=SimpleNamespace(all=lambda: []),
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )
        plan = SimpleNamespace(collect_plans=SimpleNamespace(all=lambda: [sub_plan]))

        blockers = PlatformProfileService.audit_plan_readiness(plan)
        blocker_codes = {item["code"] for item in blockers}

        self.assertIn("missing_textfsm_template", blocker_codes)
        self.assertIn("missing_netconf_template", blocker_codes)

    def test_audit_plan_readiness_flags_missing_template_file(self):
        sub_plan = SimpleNamespace(
            collection_type="arp",
            netmiko_enabled=True,
            netmiko_method="display arp",
            textfsm_template="not_exists.textfsm",
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )
        plan = SimpleNamespace(collect_plans=SimpleNamespace(all=lambda: [sub_plan]))

        blockers = PlatformProfileService.audit_plan_readiness(plan)
        blocker_codes = {item["code"] for item in blockers}

        self.assertIn("missing_textfsm_template_file", blocker_codes)

    @patch("apps.device_api.platform_profiles.PlatformProfileService.template_is_placeholder")
    def test_audit_plan_readiness_flags_placeholder_template_file(self, mock_template_is_placeholder):
        mock_template_is_placeholder.return_value = True
        sub_plan = SimpleNamespace(
            collection_type="ospf_neighbors",
            netmiko_enabled=True,
            netmiko_method="display ospf peer brief",
            textfsm_template="huawei_vrp_display_ospf_peer_brief.textfsm",
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
        )
        plan = SimpleNamespace(collect_plans=SimpleNamespace(all=lambda: [sub_plan]))

        blockers = PlatformProfileService.audit_plan_readiness(plan)
        blocker_codes = {item["code"] for item in blockers}

        self.assertIn("placeholder_textfsm_template", blocker_codes)

    def test_long_tail_profiles_only_expose_supported_cli_subset(self):
        profiles = {item["code"]: item for item in BUILTIN_PLATFORM_PROFILES}

        self.assertEqual(
            profiles["Cisco-switch"]["supported_collection_types"],
            ["device_identity", "arp", "mac"],
        )
        self.assertEqual(
            profiles["Centec-switch"]["supported_collection_types"],
            ["arp", "ip_interface"],
        )

    @patch("apps.device_api.platform_profiles.PlansToDevice.objects")
    @patch("apps.device_api.platform_profiles.DeviceCollectionPlans.objects")
    @patch("apps.device_api.platform_profiles.PlatformProfileService.match_profile_for_device")
    @patch("apps.device_api.platform_profiles.PlatformProfileService.ensure_builtin_profiles")
    def test_audit_device_coverage_reports_missing_binding(
        self,
        mock_ensure_builtin_profiles,
        mock_match_profile_for_device,
        mock_plan_objects,
        mock_binding_objects,
    ):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            serial_num="SER-1",
            vendor=SimpleNamespace(alias="Huawei"),
            model=SimpleNamespace(name="CE8850"),
            ssh_enable="account",
            ssh_account=101,
            netconf_enable="account",
            netconf_account=102,
        )
        profile = SimpleNamespace(code="Huawei-CE", default_plan_name="default-huawei-ce-netconf-switch")
        plan = SimpleNamespace(
            id=201,
            name="default-huawei-ce-netconf-switch",
            collect_plans=SimpleNamespace(all=lambda: []),
        )

        mock_ensure_builtin_profiles.return_value = [profile]
        mock_match_profile_for_device.return_value = profile
        mock_plan_objects.filter.return_value.prefetch_related.return_value.first.return_value = plan
        mock_binding_objects.select_related.return_value.filter.return_value = []

        result = PlatformProfileService.audit_device_coverage([device])

        self.assertEqual(result["summary"]["missing_binding"], 1)
        self.assertEqual(result["results"][0]["profile_code"], "Huawei-CE")
        blocker_codes = {item["code"] for item in result["results"][0]["blockers"]}
        self.assertIn("missing_binding", blocker_codes)


class DeviceCollectionServiceSyncTests(SimpleTestCase):
    @patch("apps.device_api.services_new.DeviceSubCollectionPlan.objects")
    def test_ensure_default_sub_plans_fills_missing_protocol_types_for_existing_plan(
        self,
        mock_objects,
    ):
        existing_names = {"sync-summary-arp"}
        created_records = []

        def filter_side_effect(**kwargs):
            name = kwargs.get("name")
            return SimpleNamespace(exists=lambda: name in existing_names)

        def create_side_effect(**kwargs):
            created_records.append(kwargs)
            existing_names.add(kwargs["name"])
            return SimpleNamespace(**kwargs)

        mock_objects.filter.side_effect = filter_side_effect
        mock_objects.create.side_effect = create_side_effect

        summary_plan = SimpleNamespace(
            name="sync-summary",
            collect_plans=SimpleNamespace(values_list=Mock(return_value=["arp"])),
        )

        sync_result = DeviceCollectionService.ensure_default_sub_plans(summary_plan)

        self.assertEqual(sync_result["created_count"], len(DEFAULT_COLLECTION_TYPES) - 1)
        self.assertIn("route_table", sync_result["created_types"])
        self.assertIn("bgp_neighbors", sync_result["created_types"])
        created_types = {item["collection_type"] for item in created_records}
        self.assertEqual(created_types, set(DEFAULT_COLLECTION_TYPES) - {"arp"})

    @patch("apps.device_api.services_new.DeviceSubCollectionPlan.objects")
    def test_sync_summary_plan_sub_plans_updates_method_and_disables_unselected_types(
        self,
        mock_objects,
    ):
        existing_names = {"sync-summary-route_table"}
        created_records = []

        def filter_side_effect(**kwargs):
            name = kwargs.get("name")
            return SimpleNamespace(exists=lambda: name in existing_names)

        def create_side_effect(**kwargs):
            record = SimpleNamespace(
                netmiko_enabled=False,
                netconf_enabled=False,
                snmp_enabled=False,
                restconf_enabled=False,
                telemetry_enabled=False,
                save=Mock(),
                **kwargs,
            )
            created_records.append(record)
            existing_names.add(kwargs["name"])
            return record

        mock_objects.filter.side_effect = filter_side_effect
        mock_objects.create.side_effect = create_side_effect

        selected_plan = SimpleNamespace(
            collection_type="arp",
            netmiko_enabled=False,
            netconf_enabled=False,
            snmp_enabled=False,
            restconf_enabled=False,
            telemetry_enabled=False,
            save=Mock(),
        )
        disabled_plan = SimpleNamespace(
            collection_type="route_table",
            netmiko_enabled=True,
            netconf_enabled=True,
            snmp_enabled=True,
            restconf_enabled=False,
            telemetry_enabled=False,
            save=Mock(),
        )

        summary_plan = SimpleNamespace(
            name="sync-summary",
            enabled_collection_types=["arp"],
            collection_method="both",
            collect_plans=SimpleNamespace(all=lambda: [selected_plan, disabled_plan]),
        )

        sync_result = DeviceCollectionService.sync_summary_plan_sub_plans(summary_plan)

        self.assertTrue(selected_plan.netmiko_enabled)
        self.assertTrue(selected_plan.netconf_enabled)
        selected_plan.save.assert_called_once()

        self.assertFalse(disabled_plan.netmiko_enabled)
        self.assertFalse(disabled_plan.netconf_enabled)
        self.assertFalse(disabled_plan.snmp_enabled)
        disabled_plan.save.assert_called_once()

        self.assertIn("arp", sync_result["updated_types"])
        self.assertIn("route_table", sync_result["disabled_types"])
        self.assertEqual(sync_result["collection_method"], "both")
        created_types = {item.collection_type for item in created_records}
        self.assertIn("mac", created_types)


class DeviceCollectionServiceExecutionTests(SimpleTestCase):
    def test_build_device_info_for_local_keeps_snmp_v3_credentials(self):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            name="sw-a",
            idc=SimpleNamespace(name="IDC-A"),
            vendor=SimpleNamespace(alias="Huawei"),
            ssh_account=None,
            netconf_account=None,
            snmp_version="v3",
            snmp_community="-",
            snmp_username="snmp-user",
            snmp_auth_key="auth-secret",
            snmp_priv_key="priv-secret",
            snmp_port=162,
        )

        info = DeviceCollectionService._build_device_info_for_local(device)

        self.assertEqual(info["snmp_version"], "v3")
        self.assertEqual(info["snmp_username"], "snmp-user")
        self.assertEqual(info["snmp_auth_key"], "auth-secret")
        self.assertEqual(info["snmp_priv_key"], "priv-secret")
        self.assertEqual(info["snmp_port"], 162)

    def test_build_device_info_for_local_keeps_connection_policy_override(self):
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            name="sw-a",
            idc=None,
            vendor=SimpleNamespace(alias="H3C"),
            ssh_account=None,
            netconf_account=None,
        )

        info = DeviceCollectionService._build_device_info_for_local(
            device,
            connection_policy={"netconf_timeout_seconds": 5, "netconf_retry_times": 0},
        )

        self.assertEqual(
            info["connection_policy"],
            {"netconf_timeout_seconds": 5, "netconf_retry_times": 0},
        )

    @patch("apps.device_api.platform_profiles.DeviceFactService.update_from_processed_data")
    @patch("apps.device_api.services_new.save_local_collection_result")
    @patch("apps.device_api.services_new.COLLECTION_SUB_PLAN.insert_one")
    @patch("apps.device_api.models_api.resolve_raw_data")
    def test_process_collection_result_persists_local_outputs(
        self,
        mock_resolve_raw_data,
        mock_insert_sub_plan,
        mock_save_local_result,
        mock_update_facts,
    ):
        mock_resolve_raw_data.return_value = (True, "", [{"ipaddress": "10.0.0.2"}])
        collection_db = Mock()
        plan = {
            "id": 2,
            "summary_plan": 1,
            "name": "arp-plan",
            "collection_type": "arp",
            "summary_plan_vendor": "Huawei",
            "summary_plan_device_type": "switch",
            "netmiko_method": "display arp",
        }
        device_info = {
            "manage_ip": "10.0.0.1",
            "name": "device-1",
            "idc__name": "IDC-A",
            "execute_time": "2026-03-16T10:00:00",
        }

        with patch.dict(
            "apps.device_api.services_new.COLLECTION_TYPE_MONGO_MAP",
            {"arp": collection_db},
            clear=False,
        ):
            result = DeviceCollectionService._process_collection_result(
                plan,
                device_info,
                raw_result=[{"raw": "data"}],
                collection_method="netmiko",
                execute_time="2026-03-16T10:00:00",
            )

        self.assertTrue(result["success"])
        inserted_docs = collection_db.insert_many.call_args[0][0]
        self.assertEqual(inserted_docs[0]["hostip"], "10.0.0.1")
        self.assertEqual(inserted_docs[0]["hostname"], "device-1")
        self.assertEqual(inserted_docs[0]["idc_name"], "IDC-A")
        self.assertEqual(inserted_docs[0]["plan_id"], 2)
        self.assertEqual(inserted_docs[0]["summary_plan_id"], 1)
        self.assertEqual(inserted_docs[0]["collection_type"], "arp")
        self.assertEqual(inserted_docs[0]["collection_method"], "netmiko")
        self.assertEqual(inserted_docs[0]["execute_time"], "2026-03-16T10:00:00")
        mock_insert_sub_plan.assert_called_once()
        mock_save_local_result.assert_called_once()
        mock_update_facts.assert_called_once()

    @patch("apps.device_api.services_new.save_local_collection_result")
    @patch("apps.device_api.services_new.COLLECTION_SUB_PLAN.insert_one")
    @patch("apps.device_api.models_api.resolve_raw_data")
    def test_process_collection_result_records_local_error_when_resolve_fails(
        self,
        mock_resolve_raw_data,
        mock_insert_sub_plan,
        mock_save_local_result,
    ):
        mock_resolve_raw_data.return_value = (False, "processor_failed", [])
        plan = {
            "id": 2,
            "summary_plan": 1,
            "name": "arp-plan",
            "collection_type": "arp",
            "summary_plan_vendor": "Huawei",
            "summary_plan_device_type": "switch",
            "netmiko_method": "display arp",
        }
        device_info = {
            "manage_ip": "10.0.0.1",
            "name": "device-1",
            "idc__name": "IDC-A",
        }

        result = DeviceCollectionService._process_collection_result(
            plan,
            device_info,
            raw_result=[{"raw": "data"}],
            collection_method="netmiko",
            execute_time="2026-03-16T10:00:00",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "processor_failed")
        mock_insert_sub_plan.assert_not_called()
        mock_save_local_result.assert_called_once()
        self.assertEqual(mock_save_local_result.call_args[0][6], "error")
        self.assertEqual(mock_save_local_result.call_args[0][7], "processor_failed")

    @patch("apps.device_api.services_new.DeviceCollectionService._process_collection_result")
    @patch("apps.device_api.services_new.DeviceConnectionManager")
    def test_collect_with_connection_manager_returns_partial_success(
        self,
        mock_connection_manager_cls,
        mock_process_collection_result,
    ):
        conn_mgr = Mock()
        conn_mgr.execute_netmiko_command.side_effect = RuntimeError("ssh failed")
        conn_mgr.execute_snmp_get.return_value = {"1.3.6.1.2.1.1.1.0": "switch-a"}
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False
        mock_process_collection_result.return_value = {"success": True, "data_count": 1}

        result = DeviceCollectionService.collect_with_connection_manager(
            {
                "name": "health-plan",
                "netmiko_enabled": True,
                "netmiko_method": "display version",
                "snmp_enabled": True,
                "snmp_oids": ["1.3.6.1.2.1.1.1.0"],
            },
            {
                "manage_ip": "10.0.0.1",
                "ssh_enable": True,
                "snmp_version": "v2c",
                "snmp_community": "public",
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["success_methods"], ["snmp"])
        self.assertFalse(result["results"]["netmiko"]["success"])
        self.assertTrue(result["results"]["snmp"]["success"])
        conn_mgr.execute_snmp_get.assert_called_once_with(["1.3.6.1.2.1.1.1.0"])

    @patch("apps.device_api.services_new.DeviceConnectionManager")
    def test_collect_with_connection_manager_marks_telemetry_as_deferred(
        self,
        mock_connection_manager_cls,
    ):
        conn_mgr = Mock()
        conn_mgr.execute_telemetry_subscribe.side_effect = NotImplementedError(
            "telemetry_not_implemented"
        )
        mock_connection_manager_cls.return_value.__enter__.return_value = conn_mgr
        mock_connection_manager_cls.return_value.__exit__.return_value = False

        result = DeviceCollectionService.collect_with_connection_manager(
            {
                "name": "telemetry-plan",
                "telemetry_enabled": True,
                "telemetry_subscription_path": "/interfaces/interface/state",
            },
            {
                "manage_ip": "10.0.0.1",
            },
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "all_methods_failed")
        self.assertEqual(
            result["results"]["telemetry"]["error_code"],
            "telemetry_not_implemented",
        )

    def test_execute_netmiko_south_builds_expected_payload(self):
        runner = Mock()
        runner.get_device_config.return_value = {"success": True}
        config = SimpleNamespace(south_http_port="18080")
        plan = SimpleNamespace(
            id=11,
            collection_type="arp",
            textfsm_template="hp_comware_display_arp.textfsm",
            get_netmiko_method=lambda: "display arp",
        )
        device = SimpleNamespace(
            manage_ip="10.0.0.1",
            name="sw-a",
            vendor=SimpleNamespace(alias="H3C"),
            idc=SimpleNamespace(name="IDC-A"),
            ssh_account=SimpleNamespace(username="ops", decode_password="secret"),
        )

        result = DeviceCollectionService._execute_netmiko_south(
            plan,
            device,
            "10.0.0.200",
            runner,
            config,
        )

        self.assertTrue(result["success"])
        kwargs = runner.get_device_config.call_args.kwargs
        self.assertEqual(kwargs["url_prefix"], "/getconfig")
        self.assertEqual(kwargs["host_info"], {"host": "10.0.0.200", "port": 18080})
        payload = kwargs["netpalm_info"]
        self.assertEqual(payload["library"], "netmiko")
        self.assertEqual(payload["command"], "display arp")
        self.assertEqual(payload["connection_args"]["device_type"], "hp_comware")
        self.assertEqual(payload["args"]["textfsm_template"], "hp_comware_display_arp.textfsm")
        self.assertEqual(payload["webhook"]["args"]["collection_method"], "netmiko")
        self.assertEqual(payload["webhook"]["args"]["vendor_alias"], "H3C")

    def test_execute_netconf_south_wraps_filter_and_uses_get_endpoint(self):
        runner = Mock()
        runner.get_device_config.return_value = {"success": True}
        config = SimpleNamespace(south_http_port="18080")
        xml_template = SimpleNamespace(
            xml_template="<top><ARP/></top>",
            collect_method="get",
        )
        plan = SimpleNamespace(
            id=12,
            collection_type="arp",
            xml_templates=SimpleNamespace(first=lambda: xml_template),
        )
        device = SimpleNamespace(
            manage_ip="10.0.0.2",
            name="sw-b",
            vendor=SimpleNamespace(alias="Huawei"),
            idc=SimpleNamespace(name="IDC-B"),
            netconf_account=SimpleNamespace(username="netconf", decode_password="secret"),
        )

        result = DeviceCollectionService._execute_netconf_south(
            plan,
            device,
            "10.0.0.200",
            runner,
            config,
        )

        self.assertTrue(result["success"])
        kwargs = runner.get_device_config.call_args.kwargs
        self.assertEqual(kwargs["url_prefix"], "/getconfig/ncclient/get")
        payload = kwargs["netpalm_info"]
        self.assertEqual(payload["library"], "ncclient")
        self.assertEqual(
            payload["args"]["filter"],
            '<filter type="subtree"><top><ARP/></top></filter>',
        )
        self.assertTrue(payload["args"]["get"])
        self.assertTrue(payload["args"]["render_json"])
        self.assertEqual(
            payload["connection_args"]["device_params"],
            {"name": "huaweiyang"},
        )
        self.assertEqual(payload["webhook"]["args"]["collection_method"], "netconf")

    def test_execute_netconf_south_uses_get_config_endpoint_for_existing_filter(self):
        runner = Mock()
        runner.get_device_config.return_value = {"success": True}
        config = SimpleNamespace(south_http_port="18080")
        xml_template = SimpleNamespace(
            xml_template='<filter type="subtree"><top><LLDP/></top></filter>',
            collect_method="get_config",
        )
        plan = SimpleNamespace(
            id=13,
            collection_type="lldp",
            xml_templates=SimpleNamespace(first=lambda: xml_template),
        )
        device = SimpleNamespace(
            manage_ip="10.0.0.3",
            name="sw-c",
            vendor=SimpleNamespace(alias="Cisco"),
            idc=SimpleNamespace(name="IDC-C"),
            netconf_account=SimpleNamespace(username="netconf", decode_password="secret"),
        )

        result = DeviceCollectionService._execute_netconf_south(
            plan,
            device,
            "10.0.0.200",
            runner,
            config,
        )

        self.assertTrue(result["success"])
        kwargs = runner.get_device_config.call_args.kwargs
        self.assertEqual(kwargs["url_prefix"], "/getconfig/ncclient")
        payload = kwargs["netpalm_info"]
        self.assertEqual(
            payload["args"]["filter"],
            '<filter type="subtree"><top><LLDP/></top></filter>',
        )
        self.assertEqual(payload["args"]["source"], "running")
        self.assertEqual(
            payload["connection_args"]["device_params"],
            {"name": "nexus"},
        )

    def test_execute_netconf_south_rejects_rpc_collect_method(self):
        runner = Mock()
        config = SimpleNamespace(south_http_port="18080")
        xml_template = SimpleNamespace(
            xml_template="<rpc></rpc>",
            collect_method="rpc",
        )
        plan = SimpleNamespace(
            id=15,
            collection_type="arp",
            xml_templates=SimpleNamespace(first=lambda: xml_template),
        )
        device = SimpleNamespace(
            manage_ip="10.0.0.5",
            name="sw-e",
            vendor=SimpleNamespace(alias="Huawei"),
            idc=SimpleNamespace(name="IDC-E"),
            netconf_account=SimpleNamespace(username="netconf", decode_password="secret"),
        )

        result = DeviceCollectionService._execute_netconf_south(
            plan,
            device,
            "10.0.0.200",
            runner,
            config,
        )

        self.assertFalse(result["success"])
        self.assertIn("仅允许 get/get_config", result["error"])
        runner.get_device_config.assert_not_called()

    @patch("apps.device_api.services_new.DeviceSubCollectionPlan.objects.filter")
    def test_build_sub_plan_name_falls_back_to_summary_plan_id_after_collision_limit(
        self,
        mock_filter,
    ):
        mock_filter.return_value.exists.side_effect = [True] * 1000 + [False]

        name = DeviceCollectionService._build_sub_plan_name(
            "default-h3c-s98xx-switch",
            "cli_output_capability",
            summary_plan_id=148,
        )

        self.assertEqual(name, "default-h3c-s98xx-switch-148-cli_output_capability")

    def test_execute_netconf_south_returns_explicit_error_when_template_missing(self):
        plan = SimpleNamespace(
            id=14,
            collection_type="arp",
            xml_templates=SimpleNamespace(first=lambda: None),
        )
        device = SimpleNamespace(
            manage_ip="10.0.0.4",
            name="sw-d",
            vendor=SimpleNamespace(alias="Huawei"),
            idc=SimpleNamespace(name="IDC-D"),
            netconf_account=SimpleNamespace(username="netconf", decode_password="secret"),
        )

        result = DeviceCollectionService._execute_netconf_south(
            plan,
            device,
            "10.0.0.200",
            Mock(),
            SimpleNamespace(south_http_port="18080"),
        )

        self.assertEqual(result, {"success": False, "error": "未配置XML模板"})


class DeviceApiMongoIndexTests(SimpleTestCase):
    def test_should_auto_ensure_device_api_indexes_skips_test_command(self):
        self.assertFalse(
            should_auto_ensure_device_api_indexes(["manage.py", "test"])
        )
        self.assertTrue(
            should_auto_ensure_device_api_indexes(["manage.py", "runserver"])
        )

    @patch("apps.device_api.indexes.build_device_api_index_targets")
    def test_ensure_device_api_mongo_indexes_creates_declared_indexes(
        self,
        mock_build_targets,
    ):
        mongo = Mock()
        mongo.create_index.side_effect = ["idx-one", "idx-two"]
        mock_build_targets.return_value = [
            (
                "plan_arp",
                mongo,
                [
                    ([("hostip", 1), ("execute_time", -1)], {"name": "idx-one"}),
                    ([("plan_id", 1), ("collection_method", 1)], {"name": "idx-two"}),
                ],
            )
        ]

        created = ensure_device_api_mongo_indexes()

        self.assertEqual(
            created,
            [
                {"collection": "plan_arp", "index": "idx-one"},
                {"collection": "plan_arp", "index": "idx-two"},
            ],
        )
        self.assertEqual(mongo.create_index.call_count, 2)

    @patch("apps.device_api.indexes.ensure_device_api_mongo_indexes", side_effect=RuntimeError("mongo down"))
    def test_bootstrap_device_api_mongo_indexes_swallows_errors(
        self,
        mock_ensure,
    ):
        with patch("apps.device_api.indexes._AUTO_INDEXES_BOOTSTRAPPED", False):
            created = bootstrap_device_api_mongo_indexes()

        self.assertEqual(created, [])
        mock_ensure.assert_called_once()

    @patch("apps.device_api.indexes.bootstrap_device_api_mongo_indexes")
    @patch("apps.device_api.indexes.should_auto_ensure_device_api_indexes", return_value=True)
    def test_device_api_config_ready_bootstraps_indexes(
        self,
        mock_should_auto,
        mock_bootstrap,
    ):
        config = DeviceApiConfig("apps.device_api", importlib.import_module("apps.device_api"))

        config.ready()

        mock_should_auto.assert_called_once()
        mock_bootstrap.assert_called_once()

    @patch("apps.device_api.indexes.bootstrap_device_api_mongo_indexes")
    @patch("apps.device_api.indexes.should_auto_ensure_device_api_indexes", return_value=False)
    def test_device_api_config_ready_respects_skip_condition(
        self,
        mock_should_auto,
        mock_bootstrap,
    ):
        config = DeviceApiConfig("apps.device_api", importlib.import_module("apps.device_api"))

        config.ready()

        mock_should_auto.assert_called_once()
        mock_bootstrap.assert_not_called()

    @patch("apps.device_api.management.commands.ensure_device_api_indexes.ensure_device_api_mongo_indexes")
    def test_ensure_device_api_indexes_command_reports_created_indexes(
        self,
        mock_ensure_indexes,
    ):
        mock_ensure_indexes.return_value = [
            {"collection": "plan_arp", "index": "idx_hostip_type_execute_time"},
            {"collection": "TestDeviceCollection", "index": "idx_plan_collected_at"},
        ]
        command = EnsureDeviceApiIndexesCommand()

        with patch.object(command.stdout, "write") as mock_write:
            command.handle()

        mock_ensure_indexes.assert_called_once()
        writes = [call.args[0] for call in mock_write.call_args_list]
        self.assertTrue(any("device_api Mongo 索引已确保" in line for line in writes))
        self.assertTrue(any("plan_arp: idx_hostip_type_execute_time" in line for line in writes))


class DeviceApiArchitectureGuardTests(SimpleTestCase):
    def test_runtime_modules_do_not_import_automation(self):
        runtime_paths = []
        root = Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/device_api")
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if "tests.py" in path.name:
                continue
            if relative.parts and relative.parts[0] == "migrations":
                continue
            source = path.read_text()
            self.assertNotIn("from apps.automation", source, f"forbidden legacy import in {path}")
            self.assertNotIn("import apps.automation", source, f"forbidden legacy import in {path}")


class DeviceApiRuleImportCommandTests(SimpleTestCase):
    @patch("apps.device_api.management.commands.import_legacy_collection_rules.DeviceCollectionMatchRule.objects")
    @patch("apps.device_api.management.commands.import_legacy_collection_rules.DeviceCollectionRule.objects")
    def test_import_legacy_collection_rules_reads_raw_tables(
        self,
        mock_rule_objects,
        mock_match_rule_objects,
    ):
        mock_rule_objects.update_or_create.return_value = (SimpleNamespace(id=10), False)
        mock_match_rule_objects.update_or_create.return_value = (SimpleNamespace(id=11), True)
        rules = [
            [{"id": 1, "name": "rule-a", "operation": "and", "module": "BASE", "method": "CLI", "execute": "show version", "plugin": "textfsm"}],
        ]
        match_rules = [{"id": 2, "name": "A", "fields": "vendor__alias", "operator": "__exact", "value": "Huawei", "rule_id": 1}]

        stats = ImportLegacyCollectionRulesCommand._import_rows(rules[0], match_rules)

        mock_rule_objects.update_or_create.assert_called_once()
        mock_match_rule_objects.update_or_create.assert_called_once()
        self.assertEqual(stats["rules"]["updated"], 1)
        self.assertEqual(stats["match_rules"]["created"], 1)
