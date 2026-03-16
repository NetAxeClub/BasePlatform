from unittest.mock import patch

from django.test import SimpleTestCase

from apps.workflow_center.services import query_address_traces


class WorkflowAddressLocationConsistencyTests(SimpleTestCase):
    @patch("apps.workflow_center.services.AddressTraceSnapshotSerializer")
    @patch("apps.workflow_center.services.AddressTraceSnapshot.objects")
    def test_query_address_traces_maps_new_semantic_filters(
        self,
        mock_objects,
        mock_serializer,
    ):
        queryset = mock_objects.filter.return_value
        ordered_queryset = queryset.order_by.return_value
        ordered_queryset.__getitem__.return_value = []
        ordered_queryset.count.return_value = 0
        mock_serializer.return_value.data = []

        query_address_traces(
            {
                "server_ip_address": "10.1.1.1",
                "node_ip": "10.0.0.1",
                "trace_status": "partial",
            }
        )

        mock_objects.filter.assert_called_once_with(
            ip_address="10.1.1.1",
            manage_ip="10.0.0.1",
            trace_status="partial",
        )

    @patch("apps.workflow_center.services.AddressTraceSnapshotSerializer")
    @patch("apps.workflow_center.services.AddressTraceSnapshot.objects")
    def test_query_address_traces_maps_execute_time_to_source_batch(
        self,
        mock_objects,
        mock_serializer,
    ):
        queryset = mock_objects.filter.return_value
        ordered_queryset = queryset.order_by.return_value
        ordered_queryset.__getitem__.return_value = []
        ordered_queryset.count.return_value = 0
        mock_serializer.return_value.data = []

        query_address_traces(
            {
                "server_ip_address": "10.1.1.1",
                "execute_time": "2026-03-16 10:00:00",
            }
        )

        mock_objects.filter.assert_called_once_with(
            ip_address="10.1.1.1",
            source_execute_time="2026-03-16 10:00:00",
        )
