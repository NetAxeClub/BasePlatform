import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.asset.models import Category, Model, NetworkDevice, Vendor
from apps.device_api.fields_mapping import (
    DEFAULT_COLLECTION_TYPES,
    get_collection_output_fields,
)
from apps.device_api.models import DeviceCollectionPlans, DeviceDiscoveryState, DeviceSubCollectionPlan
from apps.device_api.models_api import COLLECTION_TYPE_MONGO_MAP
from apps.device_api.processors.h3c import (
    process_aggre_port_netconf as process_h3c_aggre_port_netconf,
    process_bgp_summary_netconf as process_h3c_bgp_summary_netconf,
    process_clock_status_netmiko as process_h3c_clock_status_netmiko,
    process_fan_status_netmiko as process_h3c_fan_status_netmiko,
    process_ip_interface_netconf as process_h3c_ip_interface_netconf,
    process_lldp_netconf as process_h3c_lldp_netconf,
    process_mac_netconf as process_h3c_mac_netconf,
    process_power_status_netmiko as process_h3c_power_status_netmiko,
    process_route_table_netconf as process_h3c_route_table_netconf,
)
from apps.device_api.processors.huawei import (
    process_aggre_port_netconf as process_huawei_aggre_port_netconf,
    process_arp_netconf as process_huawei_arp_netconf,
    process_ip_interface_netconf as process_huawei_ip_interface_netconf,
    process_isis_neighbors_netmiko as process_huawei_isis_neighbors_netmiko,
    process_lldp_netconf as process_huawei_lldp_netconf,
    process_mac_netconf as process_huawei_mac_netconf,
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
)
from apps.device_api.management.commands.sync_legacy_plan_bindings import Command as SyncLegacyPlanBindingsCommand
from apps.device_api.platform_profiles import PlatformProfileService
from apps.device_api.tasks import _process_and_save_result
from apps.device_api.tools.collect_device import get_auto_device
from apps.device_api.management.commands.import_legacy_collection_rules import (
    Command as ImportLegacyCollectionRulesCommand,
)
from apps.device_api.views import (
    CollectionResultViewSet,
    DeviceCollectionRuleToolView,
    DeviceCollectionPlansViewSet,
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

    @patch("apps.device_api.tasks.refresh_network_analysis_for_batch.apply_async")
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
        mock_analysis_apply_async,
    ):
        mock_get_auto_device.return_value = [
            {
                "manage_ip": "10.0.0.1",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 1}, {"id": 2}],
            },
            {
                "manage_ip": "10.0.0.2",
                "execute_time": "2026-03-15 10:00:00",
                "sub_plans": [{"id": 3}],
            },
        ]
        mock_plan_collect_apply_async.return_value = SimpleNamespace(id="task-1")

        from apps.device_api.tasks import plan_collect_device_main

        result = plan_collect_device_main()

        self.assertEqual(result["total"], 2)
        mock_analysis_apply_async.assert_called_once()
        kwargs = mock_analysis_apply_async.call_args.kwargs["kwargs"]
        self.assertEqual(kwargs["execute_time"], "2026-03-15 10:00:00")
        self.assertEqual(kwargs["expected_devices"], 2)
        self.assertEqual(kwargs["expected_subtasks"], 3)


class DeviceApiProtocolExtensionTests(SimpleTestCase):
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


class DeviceApiHealthExtensionTests(SimpleTestCase):
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
