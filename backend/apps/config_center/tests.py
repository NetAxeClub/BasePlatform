import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.config_center.config_parse.structured.drifting import assess_structured_drift_risk
from apps.config_center.config_parse.structured.policy import load_effective_drift_policy
from apps.config_center.config_parse.structured.service import (
    StructuredConfigParseService,
    build_parse_context_from_backup,
)
from apps.config_center.management.commands.init_security_baselines import (
    load_baseline_data,
    upsert_compliance_rows,
)
from apps.config_center.tasks import parse_config_backup_structured
from apps.config_center.views import (
    ConfigBackupViewSet,
    ConfigComplianceViewSet,
    StructuredDriftPolicyViewSet,
    build_backup_compare_payload,
    build_backup_snapshot_payload,
    build_backup_timeline_payload,
    build_structured_compare_payload,
    build_structured_drift_payload,
    build_structured_snapshot_payload,
    build_structured_timeline_payload,
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
            result = [item for item in result if getattr(
                item, "vendor", None) == vendor]
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
        telnet_rule = SimpleNamespace(
            id=12, name="管理面-Telnet", parent=root_rule)
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
        self.assertEqual(payload["vendors"][0]["rules"]
                         [0]["parent_rule"], "管理面硬化基线")
        self.assertEqual(payload["vendors"][0]["rules"]
                         [0]["items"][0]["intent"], "启用 SSH 管理面")

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
        response = ConfigComplianceViewSet.as_view(
            {"get": "security_baselines"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["vendor_count"], 1)
        self.assertEqual(payload["data"]["vendors"][0]["vendor"], "H3C")
        self.assertEqual(payload["data"]["vendors"][0]
                         ["rules"][0]["items"][0]["regex"], "ssh1")

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

        created, existing_count, updated = upsert_compliance_rows(
            items, child_rules, dry_run=False)

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
            last_time=SimpleNamespace(
                strftime=lambda fmt: '2026-03-14 10:00:00'),
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
                backup_time=SimpleNamespace(
                    strftime=lambda fmt: '2026-03-14 10:00:00'),
                config_backup_id=11,
                config_file_path='current-configuration/10.0.0.1/H3C_10.0.0.1.txt',
                rule_regex='match-compliance: ^ssh',
            )
        ]
        commits = [{'label': '2026-03-14 10:00:00', 'value': 'abc123'}]

        payload = build_backup_snapshot_payload(
            backup, compliance_results, commits, preview_content='line1')

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
            last_time=SimpleNamespace(
                strftime=lambda fmt: '2026-03-14 09:00:00'),
            config_status='SUCCESS',
            file_path='startup-configuration/10.0.0.2/Huawei_10.0.0.2.txt',
        )
        compliance_results_by_backup = {
            21: [SimpleNamespace(compliance='不合规')]
        }
        commits_by_path = {
            'startup-configuration/10.0.0.2/Huawei_10.0.0.2.txt': [{'label': '2026-03-14 09:00:00', 'value': 'def456'}]
        }

        payload = build_backup_timeline_payload(
            [backup], compliance_results_by_backup, commits_by_path)

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

        payload = build_backup_compare_payload(
            backup, 'oldsha', 'newsha', diff_result)

        self.assertEqual(payload['config_backup_id'], 51)
        self.assertEqual(payload['from_commit'], 'oldsha')
        self.assertEqual(payload['to_commit'], 'newsha')
        self.assertEqual(payload['old_line_count'], 2)
        self.assertEqual(payload['new_line_count'], 3)
        self.assertEqual(payload['added_lines'], 1)

    def test_build_structured_snapshot_payload_returns_standardized_view(self):
        document = {
            'schema_version': 'config_backup_structured/v1',
            'config_backup_id': 71,
            'device': {
                'manage_ip': '10.0.0.7',
                'name': 'sw-structured',
                'vendor': 'H3C',
                'vendor_family': 'h3c_comware',
                'model_name': 'S5560',
                'idc_name': 'IDC-X',
            },
            'backup': {
                'config_type': 'running',
                'backup_time': '2026-03-23 10:00:00',
                'file_path': 'current-configuration/10.0.0.7/H3C_10.0.0.7.txt',
                'content_sha1': 'abc',
            },
            'parser': {
                'status': 'SUCCESS',
                'profile': 'h3c_comware',
            },
            'summary': {
                'interface_count': 12,
            },
        }

        payload = build_structured_snapshot_payload(document)

        self.assertEqual(payload['config_backup_id'], 71)
        self.assertEqual(payload['manage_ip'], '10.0.0.7')
        self.assertEqual(payload['vendor_family'], 'h3c_comware')
        self.assertEqual(payload['summary']['interface_count'], 12)

    def test_build_structured_timeline_payload_returns_items(self):
        documents = [
            {
                'config_backup_id': 72,
                'device': {'manage_ip': '10.0.0.8', 'name': 'sw-2', 'vendor': 'Huawei', 'vendor_family': 'huawei_vrp'},
                'backup': {'config_type': 'running', 'backup_time': '2026-03-23 11:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'huawei_vrp'},
                'summary': {'vlan_count': 3},
            }
        ]

        payload = build_structured_timeline_payload(documents)

        self.assertEqual(payload[0]['config_backup_id'], 72)
        self.assertEqual(payload[0]['vendor'], 'Huawei')
        self.assertEqual(payload[0]['summary']['vlan_count'], 3)

    def test_build_structured_compare_payload_returns_object_level_diff(self):
        from_document = {
            'config_backup_id': 91,
            'device': {'manage_ip': '10.0.0.11', 'name': 'sw-old', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
            'backup': {'config_type': 'running', 'backup_time': '2026-03-23 09:00:00'},
            'parser': {'status': 'SUCCESS', 'profile': 'h3c_comware'},
            'config': {
                'system': {'hostname': 'sw-old'},
                'features': {'ssh_enabled': True},
                'routing_instances': [{'name': 'MGMT'}],
                'vlans': [{'vlan_id': 100}],
                'zones': [],
                'services': [],
                'ntp_servers': [],
                'log_hosts': [],
                'aaa_servers': [],
                'interfaces': [{'name': 'Gig1/0/1', 'access_vlan': 100}],
                'access_lists': [],
                'snmp': {},
                'vendor_specific': {},
            },
        }
        to_document = {
            'config_backup_id': 92,
            'device': {'manage_ip': '10.0.0.11', 'name': 'sw-new', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
            'backup': {'config_type': 'running', 'backup_time': '2026-03-23 10:00:00'},
            'parser': {'status': 'SUCCESS', 'profile': 'h3c_comware'},
            'config': {
                'system': {'hostname': 'sw-new'},
                'features': {'ssh_enabled': True},
                'routing_instances': [{'name': 'MGMT'}],
                'vlans': [{'vlan_id': 100}, {'vlan_id': 200}],
                'zones': [],
                'services': [],
                'ntp_servers': [],
                'log_hosts': [],
                'aaa_servers': [],
                'interfaces': [{'name': 'Gig1/0/1', 'access_vlan': 200}],
                'access_lists': [],
                'snmp': {},
                'vendor_specific': {},
            },
        }

        payload = build_structured_compare_payload(from_document, to_document)

        self.assertTrue(payload['diff']['is_changed'])
        self.assertIn('system', payload['diff']['summary']['changed_sections'])
        self.assertIn('vlans', payload['diff']['summary']['changed_sections'])
        self.assertEqual(payload['diff']['sections']['vlans']['added'][0]['item']['vlan_id'], 200)
        self.assertEqual(payload['diff']['sections']['interfaces']['changed'][0]['key'], 'name=Gig1/0/1')
        self.assertEqual(payload['risk_assessment']['risk_level'], 'MEDIUM')
        self.assertEqual(payload['risk_assessment']['policy_version'], '2026-03-23')

    def test_build_structured_drift_payload_returns_standardized_view(self):
        document = {
            'from_config_backup_id': 121,
            'to_config_backup_id': 122,
            'device': {'manage_ip': '10.0.0.14', 'name': 'sw-c', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
            'backup': {'config_type': 'running', 'from_backup_time': '2026-03-23 09:00:00', 'to_backup_time': '2026-03-23 10:00:00'},
            'diff_summary': {'changed_sections': ['features']},
            'risk_assessment': {'risk_level': 'HIGH', 'risk_score': 80},
            'policy': {'version': '2026-03-23'},
        }

        payload = build_structured_drift_payload(document)

        self.assertEqual(payload['from_config_backup_id'], 121)
        self.assertEqual(payload['to_config_backup_id'], 122)
        self.assertEqual(payload['manage_ip'], '10.0.0.14')
        self.assertEqual(payload['risk_assessment']['risk_level'], 'HIGH')
        self.assertEqual(payload['policy']['version'], '2026-03-23')

    def test_assess_structured_drift_risk_supports_whitelist(self):
        diff = {
            'summary': {'changed_sections': ['features']},
            'sections': {
                'features': {
                    'changed_fields': [
                        {'path': 'features.telnet_enabled', 'from': False, 'to': True}
                    ],
                    'added_fields': [],
                    'removed_fields': [],
                }
            },
        }
        policy = {
            'version': 'test-policy',
            'section_rules': {
                'features': {'severity': 'HIGH', 'title': '基础能力开关发生变化'}
            },
            'signal_rules': [
                {
                    'section': 'features',
                    'path_suffix': 'telnet_enabled',
                    'when_to': True,
                    'severity': 'CRITICAL',
                    'title': 'Telnet 管理面被启用',
                }
            ],
            'whitelist': [
                {
                    'name': 'lab-telnet-waiver',
                    'reason': '实验设备允许启用 Telnet',
                    'match': {
                        'section': 'features',
                        'manage_ip': '10.255.*',
                        'path_suffix': 'telnet_enabled',
                    },
                }
            ],
        }

        result = assess_structured_drift_risk(
            diff,
            policy_context={'manage_ip': '10.255.1.10', 'vendor': 'H3C', 'config_type': 'running'},
            policy=policy,
        )

        self.assertEqual(result['policy_version'], 'test-policy')
        self.assertEqual(result['risk_level'], 'LOW')
        self.assertEqual(result['finding_count'], 0)
        self.assertEqual(result['suppressed_count'], 1)
        self.assertEqual(result['suppressed_findings'][0]['suppressed_by'], 'lab-telnet-waiver')

    def test_load_effective_drift_policy_merges_local_override(self):
        with patch('apps.config_center.config_parse.structured.policy.load_default_drift_policy') as mock_default, \
                patch('apps.config_center.config_parse.structured.policy.load_local_drift_policy_override') as mock_override, \
                patch('apps.config_center.config_parse.structured.policy.load_active_db_drift_policy_override') as mock_db_override:
            mock_default.return_value = {
                'version': 'base',
                'section_rules': {'features': {'severity': 'HIGH'}},
                'signal_rules': [],
                'whitelist': [],
            }
            mock_override.return_value = {
                'version': 'override',
                'section_rules': {'features': {'severity': 'LOW'}},
                'whitelist': [{'name': 'lab'}],
            }
            mock_db_override.return_value = {
                'section_rules': {'features': {'title': 'DB title'}},
            }
            load_effective_drift_policy.cache_clear()
            policy = load_effective_drift_policy()
            load_effective_drift_policy.cache_clear()

        self.assertEqual(policy['version'], 'override')
        self.assertEqual(policy['section_rules']['features']['severity'], 'LOW')
        self.assertEqual(policy['section_rules']['features']['title'], 'DB title')
        self.assertEqual(policy['whitelist'][0]['name'], 'lab')

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
            last_time=SimpleNamespace(
                strftime=lambda fmt: '2026-03-14 08:00:00'),
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
                backup_time=SimpleNamespace(
                    strftime=lambda fmt: '2026-03-14 08:00:00'),
                config_backup_id=31,
                config_file_path=backup.file_path,
                rule_regex='mismatch-compliance: ^http',
            )
        ]
        mock_get_commits.return_value = [
            {'label': '2026-03-14 08:00:00', 'value': 'fff111'}]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/latest_snapshot/",
            {"manage_ip": "10.0.0.3", "config_type": "running"},
        )
        response = ConfigBackupViewSet.as_view(
            {"get": "latest_snapshot"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['manage_ip'], '10.0.0.3')
        self.assertEqual(payload['data']['latest_commit']['value'], 'fff111')
        self.assertEqual(
            payload['data']['compliance_summary']['non_compliant'], 1)

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
                last_time=SimpleNamespace(
                    strftime=lambda fmt: '2026-03-14 07:00:00'),
                config_status='SUCCESS',
                file_path='current-configuration/10.0.0.4/H3C_10.0.0.4.txt',
            )
        ]
        mock_backup_objects.filter.return_value.order_by.return_value = backups
        mock_compliance_objects.filter.return_value.order_by.return_value = [
            SimpleNamespace(config_backup_id=41, compliance='合规')
        ]
        mock_get_commits.return_value = [
            {'label': '2026-03-14 07:00:00', 'value': 'ggg222'}]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/history_timeline/",
            {"manage_ip": "10.0.0.4", "limit": "10"},
        )
        response = ConfigBackupViewSet.as_view(
            {"get": "history_timeline"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['count'], 1)
        self.assertEqual(payload['data']['items'][0]
                         ['latest_commit']['value'], 'ggg222')
        self.assertEqual(payload['data']['items'][0]
                         ['compliance_summary']['compliant'], 1)

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
        response = ConfigBackupViewSet.as_view(
            {'get': 'version_compare'})(request)
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

    @patch("apps.config_center.views._StructuredConfigRepository")
    def test_latest_structured_action_returns_structured_snapshot(self, mock_repository):
        mock_repository.find_latest_by_device.return_value = {
            'config_backup_id': 81,
            'device': {'manage_ip': '10.0.0.9', 'name': 'sw-3', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
            'backup': {'config_type': 'running', 'backup_time': '2026-03-23 12:00:00'},
            'parser': {'status': 'SUCCESS', 'profile': 'h3c_comware'},
            'summary': {'interface_count': 24},
        }

        request = self.factory.get(
            "/base_platform/config_center/config_backup/latest_structured/",
            {"manage_ip": "10.0.0.9", "config_type": "running"},
        )
        response = ConfigBackupViewSet.as_view({"get": "latest_structured"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['config_backup_id'], 81)
        self.assertEqual(payload['data']['summary']['interface_count'], 24)
        mock_repository.find_latest_by_device.assert_called_once_with(manage_ip='10.0.0.9', config_type='running')

    @patch("apps.config_center.views._StructuredConfigRepository")
    def test_structured_timeline_action_returns_items(self, mock_repository):
        mock_repository.find_history.return_value = [
            {
                'config_backup_id': 82,
                'device': {'manage_ip': '10.0.0.10', 'name': 'sw-4', 'vendor': 'Huawei', 'vendor_family': 'huawei_vrp'},
                'backup': {'config_type': 'startup', 'backup_time': '2026-03-23 13:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'huawei_vrp'},
                'summary': {'vlan_count': 5},
            }
        ]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/structured_timeline/",
            {"manage_ip": "10.0.0.10", "limit": "10"},
        )
        response = ConfigBackupViewSet.as_view({"get": "structured_timeline"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['count'], 1)
        self.assertEqual(payload['data']['items'][0]['summary']['vlan_count'], 5)
        mock_repository.find_history.assert_called_once_with(manage_ip='10.0.0.10', config_type=None, limit=10)

    @patch("apps.config_center.views._StructuredConfigRepository")
    def test_structured_compare_action_returns_diff_between_explicit_versions(self, mock_repository):
        mock_repository.find_by_backup_id.side_effect = [
            {
                'config_backup_id': 101,
                'device': {'manage_ip': '10.0.0.12', 'name': 'sw-a', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
                'backup': {'config_type': 'running', 'backup_time': '2026-03-23 08:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'h3c_comware'},
                'config': {'system': {'hostname': 'sw-a'}, 'features': {}, 'routing_instances': [], 'vlans': [], 'zones': [], 'services': [], 'ntp_servers': [], 'log_hosts': [], 'aaa_servers': [], 'interfaces': [], 'access_lists': [], 'snmp': {}, 'vendor_specific': {}},
            },
            {
                'config_backup_id': 102,
                'device': {'manage_ip': '10.0.0.12', 'name': 'sw-a', 'vendor': 'H3C', 'vendor_family': 'h3c_comware'},
                'backup': {'config_type': 'running', 'backup_time': '2026-03-23 09:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'h3c_comware'},
                'config': {'system': {'hostname': 'sw-a-new'}, 'features': {}, 'routing_instances': [], 'vlans': [], 'zones': [], 'services': [], 'ntp_servers': [], 'log_hosts': [], 'aaa_servers': [], 'interfaces': [], 'access_lists': [], 'snmp': {}, 'vendor_specific': {}},
            },
        ]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/structured_compare/",
            {"from_config_backup_id": "101", "to_config_backup_id": "102"},
        )
        response = ConfigBackupViewSet.as_view({"get": "structured_compare"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertTrue(payload['data']['diff']['is_changed'])
        self.assertEqual(payload['data']['to_snapshot']['config_backup_id'], 102)

    @patch("apps.config_center.views._StructuredConfigRepository")
    def test_structured_compare_action_uses_latest_two_versions_by_device(self, mock_repository):
        mock_repository.find_history.return_value = [
            {
                'config_backup_id': 112,
                'device': {'manage_ip': '10.0.0.13', 'name': 'sw-b', 'vendor': 'Huawei', 'vendor_family': 'huawei_vrp'},
                'backup': {'config_type': 'running', 'backup_time': '2026-03-23 11:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'huawei_vrp'},
                'config': {'system': {'hostname': 'sw-b-2'}, 'features': {}, 'routing_instances': [], 'vlans': [], 'zones': [], 'services': [], 'ntp_servers': [], 'log_hosts': [], 'aaa_servers': [], 'interfaces': [], 'access_lists': [], 'snmp': {}, 'vendor_specific': {}},
            },
            {
                'config_backup_id': 111,
                'device': {'manage_ip': '10.0.0.13', 'name': 'sw-b', 'vendor': 'Huawei', 'vendor_family': 'huawei_vrp'},
                'backup': {'config_type': 'running', 'backup_time': '2026-03-23 10:00:00'},
                'parser': {'status': 'SUCCESS', 'profile': 'huawei_vrp'},
                'config': {'system': {'hostname': 'sw-b-1'}, 'features': {}, 'routing_instances': [], 'vlans': [], 'zones': [], 'services': [], 'ntp_servers': [], 'log_hosts': [], 'aaa_servers': [], 'interfaces': [], 'access_lists': [], 'snmp': {}, 'vendor_specific': {}},
            },
        ]

        request = self.factory.get(
            "/base_platform/config_center/config_backup/structured_compare/",
            {"manage_ip": "10.0.0.13", "config_type": "running"},
        )
        response = ConfigBackupViewSet.as_view({"get": "structured_compare"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['from_snapshot']['config_backup_id'], 111)
        self.assertEqual(payload['data']['to_snapshot']['config_backup_id'], 112)
        mock_repository.find_history.assert_called_once_with(manage_ip='10.0.0.13', config_type='running', limit=2)

    @patch("apps.config_center.views._StructuredDriftRepository")
    def test_latest_structured_drift_action_returns_latest_drift(self, mock_repository):
        mock_repository.find_latest_by_device.return_value = {
            'from_config_backup_id': 131,
            'to_config_backup_id': 132,
            'device': {'manage_ip': '10.0.0.15', 'name': 'sw-d', 'vendor': 'Huawei', 'vendor_family': 'huawei_vrp'},
            'backup': {'config_type': 'running', 'from_backup_time': '2026-03-23 08:00:00', 'to_backup_time': '2026-03-23 09:00:00'},
            'diff_summary': {'changed_sections': ['interfaces']},
            'risk_assessment': {'risk_level': 'MEDIUM', 'risk_score': 50},
        }

        request = self.factory.get(
            "/base_platform/config_center/config_backup/latest_structured_drift/",
            {"manage_ip": "10.0.0.15", "config_type": "running"},
        )
        response = ConfigBackupViewSet.as_view({"get": "latest_structured_drift"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['risk_assessment']['risk_level'], 'MEDIUM')
        mock_repository.find_latest_by_device.assert_called_once_with(manage_ip='10.0.0.15', config_type='running')

    @patch("apps.config_center.views.load_local_drift_policy_override")
    @patch("apps.config_center.views.load_effective_drift_policy")
    @patch("apps.config_center.views.validate_drift_policy")
    def test_structured_drift_policy_action_returns_effective_policy(
        self,
        mock_validate,
        mock_load_effective,
        mock_load_override,
    ):
        mock_load_effective.return_value = {'version': '2026-03-23', 'section_rules': {}, 'signal_rules': [], 'whitelist': []}
        mock_load_override.return_value = {'whitelist': [{'name': 'lab'}]}
        mock_validate.return_value = {'is_valid': True, 'errors': [], 'warnings': []}

        request = self.factory.get(
            "/base_platform/config_center/config_backup/structured_drift_policy/",
        )
        response = ConfigBackupViewSet.as_view({"get": "structured_drift_policy"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['policy']['version'], '2026-03-23')
        self.assertTrue(payload['data']['source']['local_override_loaded'])

    @patch("apps.config_center.views.preview_merged_drift_policy")
    def test_validate_structured_drift_policy_action_returns_preview(self, mock_preview):
        mock_preview.return_value = {
            'policy': {'version': 'preview', 'section_rules': {}, 'signal_rules': [], 'whitelist': []},
            'validation': {'is_valid': False, 'errors': ['bad severity'], 'warnings': []},
        }

        request = self.factory.post(
            "/base_platform/config_center/config_backup/validate_structured_drift_policy/",
            {'section_rules': {'features': {'severity': 'SEVERE'}}},
            format='json',
        )
        response = ConfigBackupViewSet.as_view({"post": "validate_structured_drift_policy"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        self.assertFalse(payload['data']['validation']['is_valid'])
        self.assertEqual(payload['data']['policy']['version'], 'preview')

    @patch('apps.config_center.views.clear_drift_policy_caches')
    @patch('apps.config_center.views.StructuredDriftPolicy.objects')
    @patch.object(StructuredDriftPolicyViewSet, 'get_object')
    def test_structured_drift_policy_activate_action_marks_single_active(
        self,
        mock_get_object,
        mock_objects,
        mock_clear_cache,
    ):
        policy = SimpleNamespace(
            pk=9,
            is_active=False,
            save=Mock(),
        )
        mock_get_object.return_value = policy
        mock_objects.exclude.return_value.filter.return_value.update = Mock()

        request = self.factory.post(
            "/base_platform/config_center/structured_drift_policy_profile/9/activate/",
            {},
            format='json',
        )
        with patch.object(StructuredDriftPolicyViewSet, 'get_serializer', return_value=SimpleNamespace(data={'id': 9, 'is_active': True})):
            response = StructuredDriftPolicyViewSet.as_view({'post': 'activate'})(request, pk='9')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        mock_objects.exclude.return_value.filter.return_value.update.assert_called_once_with(is_active=False)
        policy.save.assert_called_once()
        mock_clear_cache.assert_called_once()

    @patch('apps.config_center.views.clear_drift_policy_caches')
    @patch('apps.config_center.views.load_effective_drift_policy')
    @patch('apps.config_center.views.StructuredDriftPolicyAudit.objects')
    @patch('apps.config_center.views.StructuredDriftPolicy.objects')
    @patch.object(StructuredDriftPolicyViewSet, 'get_object')
    def test_structured_drift_policy_rollback_to_previous_activates_previous(
        self,
        mock_get_object,
        mock_policy_objects,
        mock_audit_objects,
        mock_load_effective,
        mock_clear_cache,
    ):
        current = SimpleNamespace(pk=11, is_active=True)
        previous = SimpleNamespace(pk=10, is_active=False, save=Mock())
        transition = SimpleNamespace(previous_policy=previous)
        mock_get_object.return_value = current
        mock_audit_objects.filter.return_value.order_by.return_value.first.return_value = transition
        mock_policy_objects.filter.return_value.update = Mock()
        mock_policy_objects.exclude.return_value.filter.return_value.update = Mock()
        mock_load_effective.side_effect = [
            {'version': 'before'},
            {'version': 'after'},
        ]

        request = self.factory.post(
            "/base_platform/config_center/structured_drift_policy_profile/11/rollback_to_previous/",
            {},
            format='json',
        )
        with patch.object(StructuredDriftPolicyViewSet, '_record_policy_audit') as mock_record_audit, \
                patch.object(StructuredDriftPolicyViewSet, 'get_serializer', return_value=SimpleNamespace(data={'id': 10, 'is_active': True})):
            response = StructuredDriftPolicyViewSet.as_view({'post': 'rollback_to_previous'})(request, pk='11')
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 200)
        mock_policy_objects.filter.return_value.update.assert_called_once_with(is_active=False)
        mock_policy_objects.exclude.return_value.filter.return_value.update.assert_called_once_with(is_active=False)
        previous.save.assert_called_once()
        mock_record_audit.assert_called_once()
        mock_clear_cache.assert_called_once()


class ConfigCenterStructuredParseTests(SimpleTestCase):
    def setUp(self):
        self.service = StructuredConfigParseService(repository=Mock())

    def test_h3c_profile_normalizes_vendor_agnostic_schema(self):
        text = """#
 version 7.1.070, Release 6349P03
#
 sysname ACCESS-SW-01
#
 clock timezone Asia/Shanghai add 08:00:00
 clock protocol ntp
#
 ip unreachables enable
#
 lldp global enable
#
 stp global enable
#
 ip vpn-instance MGMT
#
 vlan 100
#
interface GigabitEthernet1/0/1
 description Uplink
 port link-type access
 port access vlan 100
 stp edged-port
 ip address 10.10.10.1 255.255.255.0
#"""
        context = build_parse_context_from_backup(SimpleNamespace(
            id=1,
            manage_ip='10.10.10.10',
            name='sw-1',
            vendor='H3C',
            model_name='S5560',
            idc_name='IDC-A',
            config_type='running',
            file_path='current-configuration/10.10.10.10/H3C_10.10.10.10.txt',
            last_time=None,
            status=0,
            config_status='SUCCESS',
            detail='',
        ))

        document = self.service.parse_text(text=text, context=context)

        self.assertEqual(document['device']['vendor_family'], 'h3c_comware')
        self.assertEqual(document['config']['system']
                         ['hostname'], 'ACCESS-SW-01')
        self.assertTrue(document['config']['features']['lldp_enabled'])
        self.assertEqual(document['config']
                         ['routing_instances'][0]['name'], 'MGMT')
        self.assertEqual(document['config']['vlans'][0]['vlan_id'], 100)
        self.assertEqual(document['config']
                         ['interfaces'][0]['access_vlan'], 100)
        self.assertEqual(document['summary']['interface_count'], 1)

    def test_huawei_profile_normalizes_same_top_level_schema(self):
        text = """#
sysname CE6885-01
#
clock timezone Asia/Shanghai add 08:00:00
#
stelnet server enable
telnet server disable
#
vlan batch 100 200
#
stp mode rstp
stp v-stp enable
#
ip vpn-instance MGMT
 description MGMT
 ipv4-family
#
ntp unicast-server 10.254.0.13 vpn-instance MGMT preferred
#
info-center loghost 10.254.12.215 vpn-instance MGMT
#
acl number 2001
 description ssh
 rule 5 permit vpn-instance MGMT source 10.0.0.0 0.0.0.255
#
interface 10GE1/0/1
 description TO_CORE
 port link-type trunk
 port trunk permit vlan 100 to 200
#"""
        context = build_parse_context_from_backup(SimpleNamespace(
            id=2,
            manage_ip='10.20.20.20',
            name='ce-1',
            vendor='Huawei',
            model_name='CE6885',
            idc_name='IDC-B',
            config_type='running',
            file_path='current-configuration/10.20.20.20/Huawei_10.20.20.20.txt',
            last_time=None,
            status=0,
            config_status='SUCCESS',
            detail='',
        ))

        document = self.service.parse_text(text=text, context=context)

        self.assertEqual(document['device']['vendor_family'], 'huawei_vrp')
        self.assertEqual(document['config']['system']['hostname'], 'CE6885-01')
        self.assertTrue(document['config']['features']['ssh_enabled'])
        self.assertFalse(document['config']['features']['telnet_enabled'])
        self.assertEqual(document['config']['ntp_servers']
                         [0]['address'], '10.254.0.13')
        self.assertEqual(document['config']['log_hosts']
                         [0]['address'], '10.254.12.215')
        self.assertEqual(document['config']['access_lists'][0]['name'], '2001')
        self.assertEqual(document['summary']['vlan_count'], 2)

    def test_hillstone_profile_normalizes_firewall_objects(self):
        text = """Version 5.5R10
ip vrouter "mgt-vr"
exit
zone "mgt"
exit
zone "l2-trust" l2
exit
interface ethernet0/0
exit
service "TCP_18080"
  tcp dst-port 18080
exit
aaa-server "network" type tacacs+
exit
"""
        context = build_parse_context_from_backup(SimpleNamespace(
            id=3,
            manage_ip='10.30.30.30',
            name='fw-1',
            vendor='Hillstone',
            model_name='SG6000',
            idc_name='IDC-C',
            config_type='running',
            file_path='current-configuration/10.30.30.30/Hillstone_10.30.30.30.txt',
            last_time=None,
            status=0,
            config_status='SUCCESS',
            detail='',
        ))

        document = self.service.parse_text(text=text, context=context)

        self.assertEqual(document['device']['vendor_family'], 'hillstone_sg')
        self.assertEqual(document['config']['system']['version'], '5.5R10')
        self.assertEqual(document['config']
                         ['routing_instances'][0]['name'], 'mgt-vr')
        self.assertEqual(document['config']['zones'][0]['name'], 'mgt')
        self.assertEqual(document['config']['services']
                         [0]['name'], 'TCP_18080')
        self.assertEqual(document['config']
                         ['aaa_servers'][0]['type'], 'tacacs+')

    @patch('apps.config_center.tasks.git_push_config.apply_async')
    @patch('apps.config_center.tasks.config_compliance.apply_async')
    @patch('apps.config_center.tasks.parse_config_backup_structured.apply_async')
    @patch('apps.config_center.tasks.get_device_info_v2')
    @patch('apps.config_center.tasks.BackupPolicy.objects')
    def test_backup_device_config_enqueues_structured_parse_task(
        self,
        mock_policy_objects,
        mock_get_device_info,
        mock_parse_async,
        mock_compliance_async,
        mock_git_async,
    ):
        from apps.config_center.tasks import backup_device_config

        mock_get_device_info.return_value = []
        mock_policy_objects.all.return_value.values.return_value = []

        backup_device_config()

        mock_parse_async.assert_called_once()
        mock_compliance_async.assert_called_once()
        mock_git_async.assert_called_once()

    @patch('apps.config_center.tasks.analyze_structured_config_drift.apply_async')
    @patch('apps.config_center.tasks.ConfigBackup.objects')
    def test_parse_config_backup_structured_enqueues_drift_analysis(self, mock_backup_objects, mock_drift_async):
        queryset = Mock()
        queryset.order_by.return_value = queryset
        queryset.filter.return_value = queryset
        queryset.iterator.return_value = []
        mock_backup_objects.filter.return_value = queryset

        with patch('apps.config_center.tasks.StructuredConfigParseService') as mock_service_class:
            mock_service_class.return_value.parse_backups.return_value = {
                'total': 0,
                'parsed': 0,
                'failed': 0,
                'skipped': 0,
            }
            parse_config_backup_structured(today='2026-03-23T00:00:00+08:00')

        mock_drift_async.assert_called_once()

    @patch('apps.config_center.tasks.ConfigBackup.objects')
    def test_parse_config_backup_structured_filters_success_backups(self, mock_backup_objects):
        queryset = Mock()
        queryset.order_by.return_value = queryset
        queryset.filter.return_value = queryset
        queryset.iterator.return_value = ['backup-1']
        mock_backup_objects.filter.return_value = queryset

        with patch('apps.config_center.tasks.StructuredConfigParseService') as mock_service_class:
            mock_service_class.return_value.parse_backups.return_value = {
                'total': 1,
                'parsed': 1,
                'failed': 0,
                'skipped': 0,
            }

            result = parse_config_backup_structured(
                today='2026-03-23T00:00:00+08:00')

        mock_backup_objects.filter.assert_called_once_with(
            config_status='SUCCESS')
        queryset.filter.assert_called_once_with(
            last_time='2026-03-23T00:00:00+08:00')
        mock_service_class.return_value.parse_backups.assert_called_once_with([
                                                                              'backup-1'])
        self.assertEqual(result['parsed'], 1)

    @patch('apps.config_center.config_parse.structured.service.default_storage')
    def test_parse_backup_reads_file_and_upserts_document(self, mock_storage):
        repository = Mock()
        service = StructuredConfigParseService(repository=repository)
        backup = SimpleNamespace(
            id=11,
            manage_ip='10.40.40.40',
            name='ios-1',
            vendor='Cisco_ios',
            model_name='NPB',
            idc_name='IDC-D',
            config_type='running',
            file_path='current-configuration/10.40.40.40/Cisco_ios_10.40.40.40.txt',
            last_time=None,
            status=0,
            config_status='SUCCESS',
            detail='',
        )
        mock_storage.exists.return_value = True
        mock_storage.open.return_value = BytesIO(
            b"hostname TAP-01\nservice http disable\nservice https enable\ninterface eth-0-1\n!\n"
        )

        document = service.parse_backup(backup)

        repository.upsert.assert_called_once()
        self.assertEqual(document['config']['system']['hostname'], 'TAP-01')
        self.assertFalse(document['config']['features']['http_enabled'])
