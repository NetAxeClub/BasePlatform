import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.int_utilization.views import InterfaceUsedNewViewSet, InterfaceView


class InterfaceUtilizationCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("apps.int_utilization.views.InterfaceUtilizationSnapshot.objects")
    def test_interface_used_queryset_reads_network_analysis_snapshot(self, mock_objects):
        mock_objects.all.return_value.order_by.return_value = Mock()

        request = self.factory.get("/base_platform/int_utilization/interfaceused/")
        view = InterfaceUsedNewViewSet()
        view.request = request
        view.queryset = mock_objects.all.return_value.order_by.return_value

        view.get_queryset()

        mock_objects.all.assert_called_once()

    @patch("apps.int_utilization.views.interface_mongo.find")
    @patch("apps.int_utilization.views.show_ip_mongo.find")
    def test_interface_view_reads_plan_collections(
        self,
        mock_show_ip_find,
        mock_interface_find,
    ):
        mock_show_ip_find.return_value = [{"interface": "GigabitEthernet1/0/1", "line_status": "up"}]
        mock_interface_find.return_value = [{"interface": "GigabitEthernet1/0/2", "status": "down"}]

        request = self.factory.get(
            "/base_platform/int_utilization/interface/",
            {"get_interface_by_hostip": "10.0.0.1"},
        )
        response = InterfaceView.as_view()(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 200)
        self.assertIn("1", payload["results"])
