import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.config_center.management.commands.init_security_baselines import (
    load_baseline_data,
    upsert_compliance_rows,
)
from apps.config_center.views import (
    ConfigBackupViewSet,
    ConfigComplianceViewSet,
    build_backup_compare_payload,
    build_backup_snapshot_payload,
    build_backup_timeline_payload,
    build_security_baseline_payload,
    summarize_compliance_results,
)


class FakeComplianceQuerySet(list):
    def filter(self, **kwargs):
        result = list(self)
        root_rule_name = kwargs.get("rule__parent__name")
        if root_rule_name:
            result = [
                item for item in result
                if getattr(getattr(getattr(item, "rule", None), "parent", None), "name", None) == root_rule_name
            ]
        vendor = kwargs.get("vendor")
        if vendor:
            result = [item for item in result if getattr(item, "vendor", None) == vendor]
        return FakeComplianceQuerySet(result)


class FakeFilterResult:
    def __init__(self, compliance=None):
        self._compliance = compliance

    def first(self):
        return self._compliance


class ConfigCenterBaselineTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_load_baseline_data_contains_intent_for_every_item(self):
        data = load_baseline_data()

        self.assertIn("rule_tree", data)
        self.assertIn("compliance", data)
        self.assertTrue(data["compliance"])
        self.assertTrue(all(item.get("intent") for item in data["compliance"]))

    def test_build_security_baseline_payload_groups_by_vendor_and_rule(self):
        root_rule = SimpleNamespace(name="管理面硬化基线")
        ssh_rule = SimpleNamespace(id=11, name="管理面-SSH", parent=root_rule)
        telnet_rule = SimpleNamespace(id=12, name="管理面-Telnet", parent=root_rule)
        compliances = [
            SimpleNamespace(
                id=1,
                vendor="H3C",
                pattern="match-compliance",
                regex=r"^\s*ssh server enable\b",
                intent="启用 SSH 管理面",
                rule=ssh_rule,
            ),
            SimpleNamespace(
                id=2,
                vendor="H3C",
                pattern="match-compliance",
                regex=r"^\s*undo telnet server enable\b",
                intent="关闭 Telnet",
                rule=telnet_rule,
            ),
            SimpleNamespace(
                id=3,
                vendor="HUAWEI",
                pattern="match-compliance",
                regex=r"^\s*stelnet server enable\b",
                intent="启用 STelnet 管理面",
                rule=ssh_rule,
            ),
        ]

        payload = build_security_baseline_payload(compliances, "管理面硬化基线")

        self.assertEqual(payload["root_rule"], "管理面硬化基线")
        self.assertEqual(payload["vendor_count"], 2)
        self.assertEqual(payload["total_items"], 3)
        self.assertEqual(payload["vendors"][0]["vendor"], "H3C")
        self.assertEqual(payload["vendors"][0]["rule_count"], 2)
        self.assertEqual(payload["vendors"][0]["rules"][0]["parent_rule"], "管理面硬化基线")
        self.assertEqual(payload["vendors"][0]["rules"][0]["items"][0]["intent"], "启用 SSH 管理面")

    @patch("apps.config_center.views.ConfigCompliance.objects")
    def test_security_baselines_action_filters_vendor(self, mock_objects):
        root_rule = SimpleNamespace(name="管理面硬化基线")
        ssh_rule = SimpleNamespace(id=21, name="管理面-SSH", parent=root_rule)
        fake_qs = FakeComplianceQuerySet(
            [
                SimpleNamespace(
                    id=1,
                    vendor="H3C",
                    pattern="match-compliance",
                    regex="ssh1",
                    intent="h3c ssh",
                    rule=ssh_rule,
                ),
                SimpleNamespace(
                    id=2,
                    vendor="HUAWEI",
                    pattern="match-compliance",
                    regex="ssh2",
                    intent="hw ssh",
                    rule=ssh_rule,
                ),
            ]
        )
        mock_objects.select_related.return_value = fake_qs

        request = self.factory.get(
            "/base_platform/config_center/config_compliance/security_baselines/",
            {"vendor": "H3C"},
        )
        response = ConfigComplianceViewSet.as_view({"get": "security_baselines"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["vendor_count"], 1)
        self.assertEqual(payload["data"]["vendors"][0]["vendor"], "H3C")
        self.assertEqual(payload["data"]["vendors"][0]["rules"][0]["items"][0]["regex"], "ssh1")

    @patch("apps.config_center.management.commands.init_security_baselines.ConfigCompliance.objects")
    def test_upsert_compliance_rows_updates_existing_intent_and_creates_new_rows(self, mock_objects):
        existing = SimpleNamespace(intent="", save=Mock())

        def filter_side_effect(**kwargs):
            if kwargs.get("regex") == "existing-regex":
                return FakeFilterResult(existing)
            return FakeFilterResult(None)

        mock_objects.filter.side_effect = filter_side_effect
        mock_objects.create = Mock()

        child_rules = {
            "管理面-SSH": SimpleNamespace(id=1, name="管理面-SSH"),
            "管理面-Banner": SimpleNamespace(id=2, name="管理面-Banner"),
        }
        items = [
            {
                "vendor": "H3C",
                "rule": "管理面-SSH",
                "pattern": "match-compliance",
                "regex": "existing-regex",
                "intent": "更新后的设计意图",
            },
            {
                "vendor": "H3C",
                "rule": "管理面-Banner",
                "pattern": "match-compliance",
                "regex": "new-regex",
                "intent": "新增规则说明",
            },
        ]

        created, existing_count, updated = upsert_compliance_rows(items, child_rules, dry_run=False)

        self.assertEqual(created, 1)
        self.assertEqual(existing_count, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(existing.intent, "更新后的设计意图")
        existing.save.assert_called_once()
        mock_objects.create.assert_called_once()


class ConfigCenterBackupViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_summarize_compliance_results_counts_statuses(self):
        results = [
            SimpleNamespace(compliance='合规'),
            SimpleNamespace(compliance='不合规'),
            SimpleNamespace(compliance=''),
        ]

        summary = summarize_compliance_results(results)

        self.assertEqual(summary['total'], 3)
        self.assertEqual(summary['compliant'], 1)
        self.assertEqual(summary['non_compliant'], 1)
        self.assertEqual(summary['unknown'], 1)

    def test_build_backup_snapshot_payload_includes_compliance_and_git_summary(self):
        backup = SimpleNamespace(
            id=11,
            manage_ip='10.0.0.1',
            name='fw-a',
            vendor='H3C',
            model_name='SecPath',
            idc_name='IDC-A',
            config_type='running',
            last_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 10:00:00'),
            config_status='SUCCESS',
            file_path='current-configuration/10.0.0.1/H3C_10.0.0.1.txt',
            detail='ok',
        )
        compliance_results = [
            SimpleNamespace(
                id=1,
                rule_id=101,
                rule='管理面-SSH',
                compliance='合规',
                backup_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 10:00:00'),
                config_backup_id=11,
                config_file_path='current-configuration/10.0.0.1/H3C_10.0.0.1.txt',
                rule_regex='match-compliance: ^ssh',
            )
        ]
        commits = [{'label': '2026-03-14 10:00:00', 'value': 'abc123'}]

        payload = build_backup_snapshot_payload(backup, compliance_results, commits, preview_content='line1')

        self.assertEqual(payload['config_backup_id'], 11)
        self.assertEqual(payload['git_commit_count'], 1)
        self.assertEqual(payload['latest_commit']['value'], 'abc123')
        self.assertEqual(payload['compliance_summary']['compliant'], 1)
        self.assertEqual(payload['preview_content'], 'line1')

    def test_build_backup_timeline_payload_returns_stable_items(self):
        backup = SimpleNamespace(
            id=21,
            manage_ip='10.0.0.2',
            name='sw-a',
            vendor='HUAWEI',
            config_type='startup',
            last_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 09:00:00'),
            config_status='SUCCESS',
            file_path='startup-configuration/10.0.0.2/Huawei_10.0.0.2.txt',
        )
        compliance_results_by_backup = {
            21: [SimpleNamespace(compliance='不合规')]
        }
        commits_by_path = {
            'startup-configuration/10.0.0.2/Huawei_10.0.0.2.txt': [{'label': '2026-03-14 09:00:00', 'value': 'def456'}]
        }

        payload = build_backup_timeline_payload([backup], compliance_results_by_backup, commits_by_path)

        self.assertEqual(payload[0]['manage_ip'], '10.0.0.2')
        self.assertEqual(payload[0]['git_commit_count'], 1)
        self.assertEqual(payload[0]['latest_commit']['value'], 'def456')
        self.assertEqual(payload[0]['compliance_summary']['non_compliant'], 1)

    def test_build_backup_compare_payload_returns_standard_diff_structure(self):
        backup = SimpleNamespace(
            id=51,
            manage_ip='10.0.0.5',
            name='r2',
            vendor='H3C',
            config_type='running',
            file_path='current-configuration/10.0.0.5/H3C_10.0.0.5.txt',
        )
        diff_result = {
            'old_str': 'line1\nline2',
            'new_str': 'line1\nline2\nline3',
            'added_lines': 1,
            'deleted_lines': 0,
        }

        payload = build_backup_compare_payload(backup, 'oldsha', 'newsha', diff_result)

        self.assertEqual(payload['config_backup_id'], 51)
        self.assertEqual(payload['from_commit'], 'oldsha')
        self.assertEqual(payload['to_commit'], 'newsha')
        self.assertEqual(payload['old_line_count'], 2)
        self.assertEqual(payload['new_line_count'], 3)
        self.assertEqual(payload['added_lines'], 1)

    @patch("apps.config_center.views._ConfigGit.get_file_all_change_commmit")
    @patch("apps.config_center.views.ConfigComplianceResult.objects")
    @patch("apps.config_center.views.ConfigBackup.objects")
    def test_latest_snapshot_action_returns_standardized_snapshot(
        self,
        mock_backup_objects,
        mock_compliance_objects,
        mock_get_commits,
    ):
        backup = SimpleNamespace(
            id=31,
            manage_ip='10.0.0.3',
            name='fw-b',
            vendor='Hillstone',
            model_name='SG6000',
            idc_name='IDC-B',
            config_type='running',
            last_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 08:00:00'),
            config_status='SUCCESS',
            file_path='current-configuration/10.0.0.3/Hillstone_10.0.0.3.txt',
            detail='ok',
        )
        mock_backup_objects.filter.return_value.order_by.return_value.first.return_value = backup
        mock_compliance_objects.filter.return_value.order_by.return_value = [
            SimpleNamespace(
                id=2,
                rule_id=102,
                rule='管理面-HTTP',
                compliance='不合规',
                backup_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 08:00:00'),
                config_backup_id=31,
                config_file_path=backup.file_path,
                rule_regex='mismatch-compliance: ^http',
            )
        ]
        mock_get_commits.return_value = [{'label': '2026-03-14 08:00:00', 'value': 'fff111'}]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/latest_snapshot/",
            {"manage_ip": "10.0.0.3", "config_type": "running"},
        )
        response = ConfigBackupViewSet.as_view({"get": "latest_snapshot"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['manage_ip'], '10.0.0.3')
        self.assertEqual(payload['data']['latest_commit']['value'], 'fff111')
        self.assertEqual(payload['data']['compliance_summary']['non_compliant'], 1)

    @patch("apps.config_center.views._ConfigGit.get_file_all_change_commmit")
    @patch("apps.config_center.views.ConfigComplianceResult.objects")
    @patch("apps.config_center.views.ConfigBackup.objects")
    def test_history_timeline_action_returns_items(
        self,
        mock_backup_objects,
        mock_compliance_objects,
        mock_get_commits,
    ):
        backups = [
            SimpleNamespace(
                id=41,
                manage_ip='10.0.0.4',
                name='r1',
                vendor='H3C',
                config_type='running',
                last_time=SimpleNamespace(strftime=lambda fmt: '2026-03-14 07:00:00'),
                config_status='SUCCESS',
                file_path='current-configuration/10.0.0.4/H3C_10.0.0.4.txt',
            )
        ]
        mock_backup_objects.filter.return_value.order_by.return_value = backups
        mock_compliance_objects.filter.return_value.order_by.return_value = [
            SimpleNamespace(config_backup_id=41, compliance='合规')
        ]
        mock_get_commits.return_value = [{'label': '2026-03-14 07:00:00', 'value': 'ggg222'}]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/history_timeline/",
            {"manage_ip": "10.0.0.4", "limit": "10"},
        )
        response = ConfigBackupViewSet.as_view({"get": "history_timeline"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['count'], 1)
        self.assertEqual(payload['data']['items'][0]['latest_commit']['value'], 'ggg222')
        self.assertEqual(payload['data']['items'][0]['compliance_summary']['compliant'], 1)

    @patch("apps.config_center.views._ConfigGit.get_commit_by_file_new")
    @patch("apps.config_center.views._ConfigGit.get_file_all_change_commmit")
    @patch("apps.config_center.views.ConfigBackup.objects")
    def test_version_compare_action_uses_latest_two_commits_by_default(
        self,
        mock_backup_objects,
        mock_get_commits,
        mock_get_diff,
    ):
        backup = SimpleNamespace(
            id=61,
            manage_ip='10.0.0.6',
            name='fw-c',
            vendor='Huawei',
            config_type='running',
            file_path='current-configuration/10.0.0.6/Huawei_10.0.0.6.txt',
        )
        mock_backup_objects.filter.return_value.first.return_value = backup
        mock_get_commits.return_value = [
            {'label': '2026-03-14 10:00:00', 'value': 'newsha'},
            {'label': '2026-03-13 10:00:00', 'value': 'oldsha'},
        ]
        mock_get_diff.return_value = {
            'old_str': 'old',
            'new_str': 'new',
            'added_lines': 1,
            'deleted_lines': 1,
        }

        request = self.factory.get(
            "/base_platform/config_center/config_backup/version_compare/",
            {'config_backup_id': '61'},
        )
        response = ConfigBackupViewSet.as_view({'get': 'version_compare'})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['from_commit'], 'oldsha')
        self.assertEqual(payload['data']['to_commit'], 'newsha')
        mock_get_diff.assert_called_once_with(
            file=backup.file_path,
            from_commit='oldsha',
            to_commit='newsha',
        )
