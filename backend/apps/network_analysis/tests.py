import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.network_analysis.services import (
    AddressTrackingAnalysisService,
    DriftAnalysisService,
    InterfaceUtilizationAnalysisService,
    NetworkAnalysisOrchestratorService,
    TopologyReconcileService,
)
from apps.network_analysis.serializers import InterfaceUtilizationLegacySerializer
from apps.network_analysis.views import (
    AddressTraceSnapshotViewSet,
    AnalysisRunViewSet,
    InterfaceUtilizationLegacyFilter,
    InterfaceUtilizationLegacyViewSet,
    InterfaceUtilizationSnapshotViewSet,
)


class NetworkAnalysisServiceTests(SimpleTestCase):
    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(InterfaceUtilizationAnalysisService, "_latest_interface_rows")
    def test_interface_utilization_builds_snapshot_rows(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.return_value = [
            {"hostip": "10.0.0.1", "interface": "GigabitEthernet1/0/1", "status": "UP", "speed": "1G", "execute_time": "2026-03-15 10:00:00"},
            {"hostip": "10.0.0.1", "interface": "GigabitEthernet1/0/2", "status": "DOWN", "speed": "1G", "execute_time": "2026-03-15 10:00:00"},
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {"serial_num": "SER-1", "manage_ip": "10.0.0.1", "name": "sw-a", "chassis": 1, "slot": 1, "idc__name": "IDC-A", "idc_model__name": "M1", "rack__name": "R1", "u_location_start": 1, "u_location_end": 2, "category__name": "switch"},
        ]

        rows = InterfaceUtilizationAnalysisService.build_snapshots(device_ip="10.0.0.1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["device_serial_num"], "SER-1")
        self.assertEqual(rows[0]["used_ports"], 1)
        self.assertEqual(rows[0]["unused_ports"], 1)
        self.assertEqual(rows[0]["utilization_percent"], 50.0)

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_address_tracking_builds_trace_rows(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [{"hostip": "10.0.0.1", "ipaddress": "10.1.1.1", "macaddress": "aaaa-bbbb-cccc", "interface": "GigabitEthernet1/0/1", "idc_name": "IDC-A", "execute_time": "2026-03-15 10:00:00"}],
            [{"hostip": "10.0.0.1", "macaddress": "aaaa-bbbb-cccc", "interface": "GigabitEthernet1/0/1", "idc_name": "IDC-A", "execute_time": "2026-03-15 10:00:00"}],
            [],
            [],
            [],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {"serial_num": "SER-1", "manage_ip": "10.0.0.1", "name": "sw-a", "chassis": 1, "slot": 1, "idc__name": "IDC-A", "idc_model__name": "M1", "rack__name": "R1", "u_location_start": 1, "u_location_end": 2, "category__name": "switch"},
        ]

        rows = AddressTrackingAnalysisService.build_traces(ip_address="10.1.1.1")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["device_serial_num"], "SER-1")
        self.assertEqual(rows[0]["trace_status"], "partial")
        self.assertEqual(rows[0]["interface_name"], "GigabitEthernet1/0/1")

    @patch("apps.network_analysis.services.AddressTraceSnapshot.objects")
    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(TopologyReconcileService, "_latest_rows")
    def test_topology_reconcile_summarizes_fact_sources_and_drift(
        self,
        mock_latest_rows,
        mock_device_objects,
        mock_trace_objects,
    ):
        mock_device_objects.filter.return_value.values.return_value = [
            {"serial_num": "SER-1", "manage_ip": "10.0.0.1", "name": "sw-a", "category__name": "switch"},
            {"serial_num": "SER-2", "manage_ip": "10.0.0.2", "name": "sw-b", "category__name": "switch"},
        ]
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "local_interface": "GE1/0/1",
                    "neighbor_ip": "10.0.0.2",
                    "neighbor_port": "GE1/0/2",
                    "neighborsysname": "sw-b",
                    "execute_time": "2026-03-19 20:00:00",
                }
            ],
            [{"hostip": "10.0.0.1", "interface": "GE1/0/1", "execute_time": "2026-03-19 20:00:00"}],
            [{"hostip": "10.0.0.1", "ipaddress": "10.1.1.1", "interface": "GE1/0/1", "execute_time": "2026-03-19 20:00:00"}],
        ]
        mock_trace_objects.all.return_value = [
            SimpleNamespace(
                ip_address="10.1.1.2",
                manage_ip="10.0.0.1",
                trace_status="partial",
                source_execute_time="2026-03-19 20:00:00",
            )
        ]

        result = TopologyReconcileService.reconcile()

        self.assertEqual(result["summary"]["analysis_kind"], "topology_reconcile")
        self.assertEqual(result["summary"]["fact_counts"]["lldp_edges"], 1)
        self.assertEqual(result["summary"]["drift_counts"]["missing_in_facts"], 1)
        self.assertEqual(result["payload"]["reconcile"]["missing_in_facts"][0], "10.0.0.2")

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    def test_device_health_returns_degraded_device_summary(self, mock_objects):
        mock_objects.all.return_value.order_by.return_value.values.return_value = [
            {"serial_num": "SER-1", "manage_ip": "10.0.0.1", "name": "sw-a", "status": 0, "soft_version": "V1", "patch_version": "P1"},
            {"serial_num": "SER-2", "manage_ip": "10.0.0.2", "name": "sw-b", "status": 1, "soft_version": "V1", "patch_version": "P1"},
        ]

        result = DriftAnalysisService.device_health()

        self.assertEqual(result["summary"]["analysis_kind"], "device_health")
        self.assertEqual(result["summary"]["degraded_devices"], 1)
        self.assertEqual(result["severity"], "MEDIUM")

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch("apps.network_analysis.services._latest_batch_rows")
    def test_route_health_marks_devices_without_routes_as_degraded(self, mock_latest_batch_rows, mock_device_objects):
        mock_device_objects.filter.return_value.values_list.return_value = ["10.0.0.1", "10.0.0.2"]
        mock_latest_batch_rows.return_value = [
            {"hostip": "10.0.0.1", "execute_time": "2026-03-19 20:00:00", "prefix": "0.0.0.0/0"},
            {"hostip": "10.0.0.1", "execute_time": "2026-03-19 20:00:00", "prefix": "10.0.0.0/24"},
        ]

        result = DriftAnalysisService.route_health()

        self.assertEqual(result["summary"]["analysis_kind"], "route_health")
        self.assertEqual(result["summary"]["devices"], 2)
        self.assertEqual(result["summary"]["degraded_devices"], 1)
        self.assertEqual(result["summary"]["device_set"], ["10.0.0.1", "10.0.0.2"])
        self.assertEqual(result["payload"]["results"][1]["status"], "degraded")


class NetworkAnalysisViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.network_analysis.views.InterfaceUtilizationAnalysisService.refresh")
    def test_interface_utilization_rebuild_endpoint(self, mock_refresh):
        mock_refresh.return_value = {"snapshots": 3}

        request = self.factory.post(
            "/base_platform/network_analysis/interface-utilization/rebuild/",
            {"manage_ip": "10.0.0.1"},
            format="json",
        )
        response = InterfaceUtilizationSnapshotViewSet.as_view({"post": "rebuild"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["snapshots"], 3)
        mock_refresh.assert_called_once_with(device_ip="10.0.0.1", execute_time=None)

    @patch("apps.network_analysis.views.AddressTrackingAnalysisService.refresh")
    def test_address_trace_rebuild_endpoint(self, mock_refresh):
        mock_refresh.return_value = {"traces": 5}

        request = self.factory.post(
            "/base_platform/network_analysis/address-traces/rebuild/",
            {"ip_address": "10.1.1.1"},
            format="json",
        )
        response = AddressTraceSnapshotViewSet.as_view({"post": "rebuild"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["traces"], 5)
        mock_refresh.assert_called_once_with(ip_address="10.1.1.1")

    @patch("apps.network_analysis.views.NetworkAnalysisOrchestratorService.refresh_all")
    def test_analysis_run_rebuild_all_endpoint(self, mock_refresh_all):
        mock_refresh_all.return_value = {
            "run_id": 1,
            "interface_utilization": {"refresh": {"snapshots": 3}},
            "address_tracking": {"refresh": {"traces": 5}},
        }

        request = self.factory.post(
            "/base_platform/network_analysis/analysis-runs/rebuild_all/",
            {"manage_ip": "10.0.0.1", "ip_address": "10.1.1.1"},
            format="json",
        )
        response = AnalysisRunViewSet.as_view({"post": "rebuild_all"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["run_id"], 1)
        mock_refresh_all.assert_called_once_with(
            manage_ip="10.0.0.1",
            ip_address="10.1.1.1",
            triggered_by="api",
        )

    @patch("apps.network_analysis.views.InterfaceUtilizationAnalysisService.overview")
    def test_interface_utilization_overview_endpoint(self, mock_overview):
        mock_overview.return_value = {"snapshots": 2, "devices": 1, "avg_utilization": 50.0}

        request = self.factory.get(
            "/base_platform/network_analysis/interface-utilization/overview/",
            {"manage_ip": "10.0.0.1"},
        )
        response = InterfaceUtilizationSnapshotViewSet.as_view({"get": "overview"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["snapshots"], 2)
        mock_overview.assert_called_once_with(device_ip="10.0.0.1", execute_time=None)

    def test_interface_utilization_legacy_view_uses_compat_contract(self):
        self.assertIs(InterfaceUtilizationLegacyViewSet.serializer_class, InterfaceUtilizationLegacySerializer)
        self.assertIs(InterfaceUtilizationLegacyViewSet.filterset_class, InterfaceUtilizationLegacyFilter)

    @patch("apps.network_analysis.views.AddressTrackingAnalysisService.quality_summary")
    def test_address_trace_quality_endpoint(self, mock_quality):
        mock_quality.return_value = {"traces": 5, "missing_mac": 1}

        request = self.factory.get(
            "/base_platform/network_analysis/address-traces/quality/",
            {"ip_address": "10.1.1.1"},
        )
        response = AddressTraceSnapshotViewSet.as_view({"get": "quality"})(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["data"]["missing_mac"], 1)
        mock_quality.assert_called_once_with(ip_address="10.1.1.1", execute_time=None)


class NetworkAnalysisArchitectureGuardTests(SimpleTestCase):
    def test_runtime_modules_do_not_import_automation(self):
        root = Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/network_analysis")
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if "tests.py" in path.name:
                continue
            if relative.parts and relative.parts[0] == "migrations":
                continue
            source = path.read_text()
            self.assertNotIn("from apps.automation", source, f"forbidden legacy import in {path}")
            self.assertNotIn("import apps.automation", source, f"forbidden legacy import in {path}")

    def test_phase3_runtime_does_not_import_legacy_topology_modules(self):
        guarded_files = [
            Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/network_analysis/services.py"),
            Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/api/agent_views.py"),
        ]
        for path in guarded_files:
            source = path.read_text()
            self.assertNotIn("from apps.topology", source, f"forbidden topology import in {path}")
            self.assertNotIn("import apps.topology", source, f"forbidden topology import in {path}")

    def test_phase3_runtime_does_not_use_legacy_topology_collections(self):
        guarded_files = [
            Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/network_analysis/services.py"),
            Path("/Users/lijiamin/PycharmProjects/BasePlatform/backend/apps/api/agent_views.py"),
        ]
        forbidden_markers = [
            'coll="topology"',
            "coll='topology'",
            'coll="layer2interface"',
            "coll='layer2interface'",
            "Automation.topology",
        ]
        for path in guarded_files:
            source = path.read_text()
            for marker in forbidden_markers:
                self.assertNotIn(marker, source, f"forbidden legacy topology collection usage in {path}")


class NetworkAnalysisBatchTaskTests(SimpleTestCase):
    @patch("apps.network_analysis.services.time.sleep")
    @patch("apps.network_analysis.services.NetworkAnalysisOrchestratorService.refresh_all")
    @patch("apps.network_analysis.services.InterfaceUtilizationAnalysisService.ready_device_count")
    @patch("apps.device_api.COLLECTION_SUB_PLAN")
    @patch("apps.device_api.COLLECTION_PLAN")
    def test_wait_and_refresh_batch_runs_after_expected_counts(
        self,
        mock_collection_plan,
        mock_collection_sub_plan,
        mock_ready_device_count,
        mock_refresh_all,
        mock_sleep,
    ):
        mock_refresh_all.return_value = {"run_id": 1}
        mock_collection_plan.count_documents.side_effect = [1, 2, 2]
        mock_collection_sub_plan.count_documents.side_effect = [1, 2, 2]
        mock_ready_device_count.return_value = 1

        result = NetworkAnalysisOrchestratorService.wait_and_refresh_batch(
            execute_time="2026-03-15 10:00:00",
            expected_devices=2,
            expected_subtasks=2,
            expected_interface_devices=1,
            wait_seconds=1,
            max_attempts=2,
        )

        self.assertEqual(result["run_id"], 1)
        self.assertEqual(result["monitor"]["expected_devices"], 2)
        self.assertEqual(result["monitor"]["expected_interface_devices"], 1)
        mock_refresh_all.assert_called_once_with(
            triggered_by="device_api-batch",
            execute_time="2026-03-15 10:00:00",
        )
        mock_sleep.assert_called_once_with(1)


class NetworkAnalysisSummaryTests(SimpleTestCase):
    @patch("apps.network_analysis.services.InterfaceUtilizationSnapshot.objects")
    def test_interface_utilization_overview_aggregates_metrics(self, mock_objects):
        mock_objects.all.return_value = [
            SimpleNamespace(
                device_serial_num="SER-1",
                component_scope="device",
                utilization_percent=85,
                source_execute_time="2026-03-15 10:00:00",
            ),
            SimpleNamespace(
                device_serial_num="SER-2",
                component_scope="slot",
                utilization_percent=15,
                source_execute_time="2026-03-15 10:00:00",
            ),
        ]

        result = InterfaceUtilizationAnalysisService.overview()

        self.assertEqual(result["devices"], 2)
        self.assertEqual(result["high_utilization"], 1)
        self.assertEqual(result["avg_utilization"], 50.0)

    @patch("apps.network_analysis.services.AddressTraceSnapshot.objects")
    def test_address_trace_overview_aggregates_metrics(self, mock_objects):
        mock_objects.all.return_value = [
            SimpleNamespace(
                ip_address="10.1.1.1",
                trace_status="located",
                trace_method="lldp-neighbor",
                source_execute_time="2026-03-15 10:00:00",
            ),
            SimpleNamespace(
                ip_address="10.1.1.2",
                trace_status="partial",
                trace_method="aggregation",
                source_execute_time="2026-03-15 10:00:00",
            ),
        ]

        result = AddressTrackingAnalysisService.overview()

        self.assertEqual(result["traces"], 2)
        self.assertEqual(result["located"], 1)
        self.assertEqual(result["coverage_rate"], 100.0)

    @patch("apps.network_analysis.services.NetworkAnalysisOrchestratorService._finish_run")
    @patch("apps.network_analysis.services.NetworkAnalysisOrchestratorService._start_run")
    @patch("apps.network_analysis.services.AddressTrackingAnalysisService")
    @patch("apps.network_analysis.services.InterfaceUtilizationAnalysisService")
    def test_orchestrator_refresh_all_returns_combined_summary(
        self,
        mock_interface_service,
        mock_trace_service,
        mock_start_run,
        mock_finish_run,
    ):
        run = SimpleNamespace(id=9)
        mock_start_run.return_value = run
        mock_interface_service.refresh.return_value = {"snapshots": 2}
        mock_interface_service.overview.return_value = {"devices": 1}
        mock_interface_service.quality_summary.return_value = {"missing_batch_marker": 0}
        mock_trace_service.refresh.return_value = {"traces": 3}
        mock_trace_service.overview.return_value = {"located": 2}
        mock_trace_service.quality_summary.return_value = {"missing_mac": 1}

        from apps.network_analysis.services import NetworkAnalysisOrchestratorService

        result = NetworkAnalysisOrchestratorService.refresh_all(
            manage_ip="10.0.0.1",
            ip_address="10.1.1.1",
            triggered_by="test",
        )

        self.assertEqual(result["run_id"], 9)
        self.assertEqual(result["interface_utilization"]["refresh"]["snapshots"], 2)
        self.assertEqual(result["address_tracking"]["refresh"]["traces"], 3)
