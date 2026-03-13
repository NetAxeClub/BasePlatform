import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan
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
