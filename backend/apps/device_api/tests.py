import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.device_api.fields_mapping import (
    DEFAULT_COLLECTION_TYPES,
    get_collection_output_fields,
)
from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan
from apps.device_api.models_api import COLLECTION_TYPE_MONGO_MAP
from apps.device_api.processors.h3c import (
    process_bgp_summary_netconf as process_h3c_bgp_summary_netconf,
    process_clock_status_netmiko as process_h3c_clock_status_netmiko,
    process_fan_status_netmiko as process_h3c_fan_status_netmiko,
    process_power_status_netmiko as process_h3c_power_status_netmiko,
    process_route_table_netconf as process_h3c_route_table_netconf,
)
from apps.device_api.processors.huawei import (
    process_isis_neighbors_netmiko as process_huawei_isis_neighbors_netmiko,
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
    DeviceSubCollectionPlanCreateSerializer,
    DeviceSubCollectionPlanSerializer,
    DeviceSubCollectionPlanUpdateSerializer,
)
from apps.device_api.tasks import _process_and_save_result
from apps.device_api.views import CollectionResultViewSet, DeviceCollectionPlansViewSet


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
    @patch("apps.device_api.views.DeviceCollectionService.ensure_default_sub_plans")
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


class DeviceApiSerializerTests(SimpleTestCase):
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
