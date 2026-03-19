from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.asset.models import Category, Model, NetworkDevice, Vendor
from apps.config_center.models import ConfigComplianceResult
from apps.network_analysis.models import AddressTraceSnapshot
from apps.network_analysis.services import DriftAnalysisService, TopologyReconcileService


class NetworkAnalysisIntegrationTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name="华为", alias="Huawei")
        self.category = Category.objects.create(name="交换机")
        self.model = Model.objects.create(name="CE12800", vendor=self.vendor)
        self.device_a = NetworkDevice.objects.create(
            serial_num="NA-INT-001",
            manage_ip="10.10.10.1",
            name="edge-a",
            vendor=self.vendor,
            category=self.category,
            model=self.model,
            soft_version="V200R001",
            patch_version="P001",
            status=0,
        )
        self.device_b = NetworkDevice.objects.create(
            serial_num="NA-INT-002",
            manage_ip="10.10.10.2",
            name="edge-b",
            vendor=self.vendor,
            category=self.category,
            model=self.model,
            soft_version="V200R001",
            patch_version="P001",
            status=0,
        )

    def test_config_drift_replays_latest_database_batch(self):
        old_time = timezone.make_aware(datetime(2026, 3, 19, 19, 0, 0))
        latest_time = timezone.make_aware(datetime(2026, 3, 19, 20, 0, 0))
        ConfigComplianceResult.objects.create(
            manage_ip=self.device_a.manage_ip,
            hostname=self.device_a.name,
            vendor="Huawei",
            rule="ntp",
            rule_id=1,
            compliance="合规",
            log_time=old_time,
        )
        ConfigComplianceResult.objects.create(
            manage_ip=self.device_a.manage_ip,
            hostname=self.device_a.name,
            vendor="Huawei",
            rule="aaa",
            rule_id=2,
            compliance="不合规",
            log_time=latest_time,
        )
        ConfigComplianceResult.objects.create(
            manage_ip=self.device_b.manage_ip,
            hostname=self.device_b.name,
            vendor="Huawei",
            rule="snmp",
            rule_id=3,
            compliance="合规",
            log_time=latest_time,
        )

        result = DriftAnalysisService.config_drift()

        self.assertEqual(result["summary"]["analysis_kind"], "config_drift")
        self.assertEqual(result["summary"]["items"], 2)
        self.assertEqual(result["summary"]["non_compliant"], 1)
        self.assertEqual(result["summary"]["execute_time"], "2026-03-19 20:00:00")
        self.assertEqual(result["summary"]["source_task_id"], "config-drift://2026-03-19 20:00:00")
        self.assertEqual(result["summary"]["device_set"], ["10.10.10.1", "10.10.10.2"])
        self.assertEqual(result["payload"]["results"][0]["manage_ip"], "10.10.10.1")
        self.assertEqual(result["severity"], "HIGH")

    @patch("apps.network_analysis.services._latest_batch_rows")
    def test_route_health_replays_batch_with_fixed_trace_fields(self, mock_latest_batch_rows):
        mock_latest_batch_rows.return_value = [
            {"hostip": self.device_a.manage_ip, "execute_time": "2026-03-19 21:00:00", "prefix": "0.0.0.0/0"},
            {"hostip": self.device_a.manage_ip, "execute_time": "2026-03-19 21:00:00", "prefix": "10.0.0.0/24"},
        ]

        result = DriftAnalysisService.route_health()

        self.assertEqual(result["summary"]["analysis_kind"], "route_health")
        self.assertEqual(result["summary"]["devices"], 2)
        self.assertEqual(result["summary"]["degraded_devices"], 1)
        self.assertEqual(result["summary"]["execute_time"], "2026-03-19 21:00:00")
        self.assertEqual(result["summary"]["source_task_id"], "batch://2026-03-19 21:00:00")
        self.assertEqual(result["summary"]["device_set"], ["10.10.10.1", "10.10.10.2"])
        self.assertEqual(
            result["payload"]["results"],
            [
                {"manage_ip": "10.10.10.1", "route_count": 2, "status": "healthy"},
                {"manage_ip": "10.10.10.2", "route_count": 0, "status": "degraded"},
            ],
        )
        self.assertEqual(result["severity"], "MEDIUM")

    @patch("apps.network_analysis.services.timezone.now")
    def test_device_health_replays_database_snapshot_with_fixed_trace_fields(self, mock_now):
        NetworkDevice.objects.filter(pk=self.device_b.pk).update(status=1)
        mock_now.return_value = timezone.make_aware(datetime(2026, 3, 19, 22, 0, 0))

        result = DriftAnalysisService.device_health()

        self.assertEqual(result["summary"]["analysis_kind"], "device_health")
        self.assertEqual(result["summary"]["devices"], 2)
        self.assertEqual(result["summary"]["degraded_devices"], 1)
        self.assertEqual(result["summary"]["execute_time"], "2026-03-19 22:00:00")
        self.assertEqual(result["summary"]["source_task_id"], "device-health://2026-03-19 22:00:00")
        self.assertEqual(result["summary"]["device_set"], ["10.10.10.1", "10.10.10.2"])
        self.assertEqual(result["payload"]["results"][1]["health"], "degraded")
        self.assertEqual(result["severity"], "MEDIUM")

    @patch.object(TopologyReconcileService, "_latest_rows")
    def test_topology_reconcile_replays_database_traces_without_legacy_topology_dependency(self, mock_latest_rows):
        AddressTraceSnapshot.objects.create(
            ip_address="10.1.1.10",
            manage_ip=self.device_a.manage_ip,
            device_serial_num=self.device_a.serial_num,
            device_name=self.device_a.name,
            interface_name="GE1/0/1",
            trace_status=AddressTraceSnapshot.STATUS_PARTIAL,
            trace_method="lldp-neighbor",
            source_execute_time="2026-03-19 23:00:00",
        )
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": self.device_a.manage_ip,
                    "local_interface": "GE1/0/1",
                    "neighbor_ip": self.device_b.manage_ip,
                    "neighbor_port": "GE1/0/2",
                    "neighborsysname": self.device_b.name,
                    "execute_time": "2026-03-19 23:00:00",
                }
            ],
            [{"hostip": self.device_a.manage_ip, "interface": "GE1/0/1", "execute_time": "2026-03-19 23:00:00"}],
            [{"hostip": self.device_a.manage_ip, "ipaddress": "10.1.1.1", "interface": "GE1/0/1", "execute_time": "2026-03-19 23:00:00"}],
        ]

        result = TopologyReconcileService.reconcile()

        self.assertEqual(result["summary"]["analysis_kind"], "topology_reconcile")
        self.assertEqual(result["summary"]["execute_time"], "2026-03-19 23:00:00")
        self.assertEqual(result["summary"]["source_task_id"], "batch://2026-03-19 23:00:00")
        self.assertEqual(result["summary"]["device_set"], ["10.10.10.1", "10.10.10.2"])
        self.assertEqual(result["summary"]["drift_counts"]["missing_in_facts"], 1)
        self.assertEqual(result["summary"]["drift_counts"]["unresolved_traces"], 1)
        self.assertEqual(result["payload"]["reconcile"]["missing_in_facts"], ["10.10.10.2"])
