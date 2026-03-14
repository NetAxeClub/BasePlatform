import json
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.dcs_control.models import FirewallPolicyAuditRecord
from apps.dcs_control.policy_audit import (
    build_sec_policy_audit_payload,
    extract_sec_policy_audit_summary,
    extract_sec_policy_findings,
    get_vendor_aliases,
    normalize_sec_policy,
)
from apps.dcs_control.views import DestAddTranslate, SecPolicyAudit, SecPolicyAuditRecordView


class DcsControlPolicyAuditTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_normalize_sec_policy_marks_permit_any_any_and_logging_review(self):
        normalized = normalize_sec_policy(
            {
                "vendor": "H3C",
                "hostip": "10.0.0.1",
                "id": "100",
                "name": "allow-any",
                "description": "demo",
                "action": "permit",
                "enable": "true",
                "src_zone": "Trust",
                "dst_zone": "Untrust",
                "src_addr": [],
                "dst_addr": [],
                "service": "Any",
                "log": "false",
            }
        )

        self.assertTrue(normalized["is_permit_any_any"])
        self.assertTrue(normalized["has_any_source"])
        self.assertTrue(normalized["has_any_destination"])
        self.assertTrue(normalized["has_any_service"])
        self.assertEqual(normalized["logging_state"], "disabled")
        self.assertTrue(normalized["needs_logging_review"])
        self.assertIn("permit_any_any", normalized["findings"])
        self.assertIn("logging_missing", normalized["findings"])

    def test_normalize_sec_policy_detects_high_risk_service(self):
        normalized = normalize_sec_policy(
            {
                "vendor": "huawei_usg",
                "hostip": "10.0.0.2",
                "id": "",
                "name": "permit-ssh",
                "action": "permit",
                "enable": "true",
                "src_addr": [{"object": "office-net"}],
                "dst_addr": [{"ip": "192.0.2.10/32"}],
                "service": [{"item": {"Type": "tcp", "StartDestPort": "22", "EndDestPort": "22"}}],
            }
        )

        self.assertEqual(normalized["vendor"], "Huawei")
        self.assertTrue(normalized["has_high_risk_service"])
        self.assertEqual(normalized["high_risk_services"][0]["display"], "tcp/22")
        self.assertIn("high_risk_service", normalized["findings"])

    def test_build_sec_policy_audit_payload_summarizes_findings(self):
        payload = build_sec_policy_audit_payload(
            [
                {
                    "vendor": "H3C",
                    "hostip": "10.0.0.1",
                    "id": "1",
                    "name": "allow-any",
                    "action": "permit",
                    "enable": "true",
                    "service": "Any",
                    "src_addr": [],
                    "dst_addr": [],
                    "log": "false",
                },
                {
                    "vendor": "hillstone",
                    "hostip": "10.0.0.1",
                    "id": "2",
                    "name": "deny-web",
                    "action": "deny",
                    "enable": True,
                    "service": [{"item": {"Type": "tcp", "StartDestPort": "80", "EndDestPort": "80"}}],
                    "src_addr": [{"object": "branch"}],
                    "dst_addr": [{"object": "dc"}],
                    "log": "session-init",
                },
            ],
            hostip="10.0.0.1",
            vendor="H3C",
        )

        self.assertEqual(payload["hostip"], "10.0.0.1")
        self.assertEqual(payload["vendor"], "H3C")
        self.assertEqual(payload["total_rules"], 2)
        self.assertEqual(payload["permit_any_any_count"], 1)
        self.assertEqual(payload["logging_review_count"], 1)
        self.assertEqual(payload["high_risk_service_rule_count"], 0)

    def test_extract_summary_and_findings_from_payload(self):
        payload = build_sec_policy_audit_payload(
            [
                {
                    "vendor": "H3C",
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
            ],
            hostip="10.0.0.1",
            vendor="H3C",
        )

        summary = extract_sec_policy_audit_summary(payload)
        findings = extract_sec_policy_findings(payload)

        self.assertEqual(summary["permit_any_any_count"], 1)
        self.assertEqual(findings[0]["rule_name"], "allow-any")
        self.assertIn("permit_any_any", findings[0]["findings"])

    def test_get_vendor_aliases_supports_storage_vendor_names(self):
        self.assertEqual(get_vendor_aliases("H3C"), {"H3C", "h3c_secpath"})
        self.assertEqual(get_vendor_aliases("Huawei"), {"Huawei", "huawei_usg"})
        self.assertEqual(get_vendor_aliases("Hillstone"), {"Hillstone", "hillstone"})

    @patch("apps.dcs_control.views.sec_policy_mongo.find")
    def test_sec_policy_audit_view_filters_vendor_and_returns_payload(self, mock_find):
        mock_find.return_value = [
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
            },
            {
                "vendor": "hillstone",
                "hostip": "10.0.0.1",
                "id": "2",
                "name": "hillstone-rule",
                "action": "permit",
                "enable": True,
                "service": "Any",
                "src_addr": [],
                "dst_addr": [],
                "log": "session-init",
            },
        ]

        request = self.factory.get(
            "/base_platform/dcs_control/sec_policy_audit/",
            {"hostip": "10.0.0.1", "vendor": "H3C"},
        )
        response = SecPolicyAudit.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["total_rules"], 1)
        self.assertEqual(payload["data"]["results"][0]["vendor"], "H3C")
        self.assertEqual(payload["data"]["permit_any_any_count"], 1)

    def test_sec_policy_audit_view_requires_hostip(self):
        request = self.factory.get("/base_platform/dcs_control/sec_policy_audit/", {})
        response = SecPolicyAudit.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)

    @patch("apps.dcs_control.views.FirewallPolicyAuditRecordSerializer")
    @patch("apps.dcs_control.views.sec_policy_mongo.find")
    def test_sec_policy_audit_record_view_creates_record_from_device_snapshot(
        self,
        mock_find,
        mock_serializer_cls,
    ):
        mock_find.return_value = [
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
        serializer_instance = mock_serializer_cls.return_value
        serializer_instance.is_valid.return_value = True
        serializer_instance.save.return_value = type(
            "Record",
            (),
            {"id": 1},
        )()
        mock_serializer_cls.side_effect = [
            serializer_instance,
            type("RespSerializer", (), {"data": {"id": 1, "vendor": "H3C"}})(),
        ]

        request = self.factory.post(
            "/base_platform/dcs_control/sec_policy_audit_records/",
            {"device_ip": "10.0.0.1", "vendor": "H3C"},
            format="json",
        )
        response = SecPolicyAuditRecordView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 201)
        create_payload = serializer_instance.is_valid.call_args
        self.assertTrue(serializer_instance.is_valid.called)
        self.assertEqual(payload["data"]["vendor"], "H3C")

    @patch("apps.dcs_control.views.FirewallPolicyAuditRecordSerializer")
    @patch("apps.dcs_control.views.FirewallPolicyAuditRecord.objects")
    def test_sec_policy_audit_record_view_lists_records(
        self,
        mock_objects,
        mock_serializer_cls,
    ):
        queryset = mock_objects.all.return_value.order_by.return_value
        queryset.filter.return_value = queryset
        queryset.__getitem__.return_value = ["row1"]
        mock_serializer_cls.return_value = type(
            "RespSerializer",
            (),
            {"data": [{"device_ip": "10.0.0.1", "vendor": "H3C"}]},
        )()

        request = self.factory.get(
            "/base_platform/dcs_control/sec_policy_audit_records/",
            {"device_ip": "10.0.0.1", "vendor": "H3C", "limit": "10"},
        )
        response = SecPolicyAuditRecordView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["data"][0]["vendor"], "H3C")

    def test_firewall_policy_audit_record_status_choices_exposed(self):
        self.assertEqual(FirewallPolicyAuditRecord.Status.SUCCESS, "success")
        self.assertEqual(FirewallPolicyAuditRecord.AuditType.SECURITY_POLICY, "sec_policy")

    @patch("apps.dcs_control.views.dnat_mongo.find")
    def test_dnat_query_uses_exact_host_and_range_filters(self, mock_find):
        mock_find.return_value = [
            {
                "rule_id": "683",
                "hostip": "172.16.75.1",
            }
        ]

        request = self.factory.get(
            "/base_platform/dcs_control/dnat/",
            {
                "hostip": "172.16.75.1",
                "global_ip": "36.7.172.66",
                "global_port": "12183",
                "local_ip": "172.16.81.43",
                "local_port": "12181",
            },
        )
        response = DestAddTranslate.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["count"], 1)
        query = mock_find.call_args.kwargs["query_dict"]
        self.assertEqual(query["hostip"], "172.16.75.1")
        self.assertEqual(query["global_ip"]["$elemMatch"]["start_int"]["$lte"], 604482626)
        self.assertEqual(query["global_port"]["$elemMatch"]["start"]["$lte"], 12183)
        self.assertEqual(query["local_port"]["$elemMatch"]["end"]["$gte"], 12181)

    def test_dnat_query_returns_400_for_invalid_ip(self):
        request = self.factory.get(
            "/base_platform/dcs_control/dnat/",
            {"hostip": "172.16.75.1", "global_ip": "bad-ip"},
        )
        response = DestAddTranslate.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 400)
        self.assertIn("参数错误", payload["msg"])
