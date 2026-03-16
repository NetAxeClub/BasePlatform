from unittest.mock import patch

from django.test import SimpleTestCase

from apps.network_analysis.services import NetworkAnalysisOrchestratorService


class InterfaceAnalysisTriggeringTests(SimpleTestCase):
    @patch("apps.network_analysis.services.time.sleep")
    @patch("apps.network_analysis.services.NetworkAnalysisOrchestratorService.refresh_all")
    @patch("apps.network_analysis.services.InterfaceUtilizationAnalysisService.ready_device_count")
    @patch("apps.device_api.COLLECTION_SUB_PLAN")
    @patch("apps.device_api.COLLECTION_PLAN")
    def test_wait_and_refresh_batch_waits_until_expected_interface_sources_are_ready(
        self,
        mock_collection_plan,
        mock_collection_sub_plan,
        mock_ready_device_count,
        mock_refresh_all,
        mock_sleep,
    ):
        mock_refresh_all.return_value = {"run_id": 1}
        mock_collection_plan.count_documents.side_effect = [2, 2, 2]
        mock_collection_sub_plan.count_documents.side_effect = [2, 2, 2]
        mock_ready_device_count.side_effect = [1, 2, 2]

        result = NetworkAnalysisOrchestratorService.wait_and_refresh_batch(
            execute_time="2026-03-16 10:00:00",
            expected_devices=2,
            expected_subtasks=2,
            expected_interface_devices=2,
            wait_seconds=1,
            max_attempts=2,
        )

        self.assertEqual(result["run_id"], 1)
        self.assertEqual(result["monitor"]["interface_device_count"], 2)
        self.assertEqual(result["monitor"]["expected_interface_devices"], 2)
        mock_sleep.assert_called_once_with(1)
        mock_refresh_all.assert_called_once_with(
            triggered_by="device_api-batch",
            execute_time="2026-03-16 10:00:00",
        )
