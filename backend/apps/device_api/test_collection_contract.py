from django.test import SimpleTestCase

from apps.device_api.contract import (
    REQUIRED_STANDARD_COLLECTION_FIELDS,
    STANDARD_COLLECTION_CONTEXT_FIELDS,
    STANDARD_PLAN_COLLECTIONS,
    build_plan_collection_name,
    normalize_collection_type_for_storage,
)
from apps.device_api.models_api import inject_collection_context, inject_metadata
from apps.device_api.platform_profiles import BUILTIN_PLATFORM_PROFILES


class DeviceApiCollectionContractTests(SimpleTestCase):
    def test_standard_plan_collections_cover_core_result_sets(self):
        expected = {
            "plan_arp",
            "plan_mac",
            "plan_lldp",
            "plan_aggre_port",
            "plan_ip_interface",
            "plan_interface_brief",
        }

        self.assertTrue(expected.issubset(set(STANDARD_PLAN_COLLECTIONS)))

    def test_required_standard_collection_fields_cover_metadata_and_context(self):
        self.assertIn("hostip", REQUIRED_STANDARD_COLLECTION_FIELDS)
        self.assertIn("hostname", REQUIRED_STANDARD_COLLECTION_FIELDS)
        self.assertIn("idc_name", REQUIRED_STANDARD_COLLECTION_FIELDS)
        self.assertIn("log_time", REQUIRED_STANDARD_COLLECTION_FIELDS)
        self.assertEqual(
            STANDARD_COLLECTION_CONTEXT_FIELDS,
            ("summary_plan_id", "plan_id", "collection_type", "collection_method", "execute_time"),
        )

    def test_contract_builds_plan_collection_name_from_standard_type(self):
        self.assertEqual(build_plan_collection_name("arp"), "plan_arp")

    def test_storage_aliases_normalize_to_standard_collection_type(self):
        self.assertEqual(normalize_collection_type_for_storage("version"), "device_identity")
        self.assertEqual(build_plan_collection_name("version"), "plan_device_identity")

    def test_inject_collection_context_backfills_required_fields(self):
        data = [{}]

        result = inject_collection_context(
            data,
            {
                "plan_id": 12,
                "collection_type": "arp",
            },
        )

        self.assertEqual(result[0]["summary_plan_id"], "")
        self.assertEqual(result[0]["plan_id"], 12)
        self.assertEqual(result[0]["collection_type"], "arp")
        self.assertEqual(result[0]["collection_method"], "")
        self.assertEqual(result[0]["execute_time"], "")

    def test_inject_collection_context_normalizes_storage_collection_type(self):
        data = [{}]

        result = inject_collection_context(
            data,
            {
                "plan_id": 12,
                "collection_type": "version",
            },
        )

        self.assertEqual(result[0]["collection_type"], "device_identity")

    def test_metadata_and_context_together_produce_frozen_contract_fields(self):
        data = [{}]

        inject_metadata(
            data,
            {
                "hostip": "10.0.0.1",
                "hostname": "switch-a",
                "idc_name": "IDC-A",
            },
        )
        inject_collection_context(
            data,
            {
                "summary_plan_id": 1,
                "plan_id": 2,
                "collection_type": "arp",
                "collection_method": "netmiko",
                "execute_time": "2026-03-16 10:00:00",
            },
        )

        for field_name in REQUIRED_STANDARD_COLLECTION_FIELDS:
            self.assertIn(field_name, data[0])

    def test_builtin_platform_profiles_cover_current_vendor_scope(self):
        vendors = {item["vendor_alias"] for item in BUILTIN_PLATFORM_PROFILES}
        codes = {item["code"] for item in BUILTIN_PLATFORM_PROFILES}

        self.assertTrue(
            {"Huawei", "H3C", "Ruijie", "Hillstone", "Cisco", "ZTE", "Maipu", "Mellanox", "centec"}.issubset(
                vendors
            )
        )
        self.assertTrue(
            {
                "Huawei-S",
                "Huawei-CE",
                "Huawei-router-cli",
                "Huawei-USG",
                "Huawei-YunShan",
                "H3C-legacy-cli",
                "H3C-modern-netconf",
                "Ruijie-switch",
                "Hillstone-firewall",
                "Cisco-switch",
                "ZTE-switch",
                "Maipu-switch",
                "Mellanox-switch",
                "Centec-switch",
            }.issubset(codes)
        )
