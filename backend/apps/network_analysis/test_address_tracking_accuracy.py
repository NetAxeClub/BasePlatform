from unittest.mock import patch

from django.test import SimpleTestCase

from apps.network_analysis.models import AddressTraceSnapshot
from apps.network_analysis.services import AddressTrackingAnalysisService


class AddressTrackingAccuracyTests(SimpleTestCase):
    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_build_traces_keeps_same_execute_time_across_tables(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "ipaddress": "10.1.1.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.9",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/9",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 11:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.9",
                    "local_interface": "GigabitEthernet1/0/9",
                    "neighbor_ip": "10.0.0.2",
                    "neighbor_port": "GigabitEthernet1/0/1",
                    "execute_time": "2026-03-16 11:00:00",
                }
            ],
            [],
            [
                {
                    "hostip": "10.0.0.2",
                    "ipaddress": "10.1.1.1",
                    "interface": "GigabitEthernet1/0/1",
                    "execute_time": "2026-03-16 11:00:00",
                }
            ],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {
                "serial_num": "SER-1",
                "manage_ip": "10.0.0.1",
                "name": "sw-a",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M1",
                "rack__name": "R1",
                "u_location_start": 1,
                "u_location_end": 2,
                "category__name": "switch",
            }
        ]

        traces = AddressTrackingAnalysisService.build_traces(
            ip_address="10.1.1.1")

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["trace_status"],
                         AddressTraceSnapshot.STATUS_UNRESOLVED)
        self.assertEqual(
            traces[0]["source_execute_time"], "2026-03-16 10:00:00")

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_build_traces_prefers_same_device_mac_candidate(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "ipaddress": "10.1.1.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.9",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/48",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                },
                {
                    "hostip": "10.0.0.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                },
            ],
            [],
            [],
            [],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {
                "serial_num": "SER-1",
                "manage_ip": "10.0.0.1",
                "name": "sw-a",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M1",
                "rack__name": "R1",
                "u_location_start": 1,
                "u_location_end": 2,
                "category__name": "switch",
            }
        ]

        traces = AddressTrackingAnalysisService.build_traces(
            ip_address="10.1.1.1")

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["manage_ip"], "10.0.0.1")
        self.assertEqual(traces[0]["interface_name"], "GigabitEthernet1/0/1")
        self.assertEqual(traces[0]["trace_status"],
                         AddressTraceSnapshot.STATUS_PARTIAL)

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_build_traces_marks_aggregation_without_neighbor_closure_as_partial(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "ipaddress": "10.1.1.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "Bridge-Aggregation1.100",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [],
            [],
            [
                {
                    "hostip": "10.0.0.1",
                    "aggregroup": "Bridge-Aggregation1",
                    "memberports": ["GigabitEthernet1/0/1"],
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {
                "serial_num": "SER-1",
                "manage_ip": "10.0.0.1",
                "name": "sw-a",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M1",
                "rack__name": "R1",
                "u_location_start": 1,
                "u_location_end": 2,
                "category__name": "switch",
            }
        ]

        traces = AddressTrackingAnalysisService.build_traces(
            ip_address="10.1.1.1")

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["interface_name"], "Bridge-Aggregation1")
        self.assertEqual(traces[0]["member_ports"], ["GigabitEthernet1/0/1"])
        self.assertEqual(traces[0]["trace_status"],
                         AddressTraceSnapshot.STATUS_PARTIAL)
        self.assertEqual(traces[0]["trace_method"], "aggregation")

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_build_traces_locates_ip_via_aggregation_and_lldp(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "ipaddress": "10.1.1.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "Bridge-Aggregation1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "Bridge-Aggregation1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.1",
                    "local_interface": "GigabitEthernet1/0/1",
                    "neighbor_ip": "10.0.0.2",
                    "neighbor_port": "GigabitEthernet1/0/24",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.1",
                    "aggregroup": "Bridge-Aggregation1",
                    "memberports": ["GigabitEthernet1/0/1"],
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.2",
                    "ipaddress": "10.1.1.1",
                    "interface": "GigabitEthernet1/0/24",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {
                "serial_num": "SER-1",
                "manage_ip": "10.0.0.1",
                "name": "sw-a",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M1",
                "rack__name": "R1",
                "u_location_start": 1,
                "u_location_end": 2,
                "category__name": "switch",
            }
        ]

        traces = AddressTrackingAnalysisService.build_traces(
            ip_address="10.1.1.1")

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["trace_status"],
                         AddressTraceSnapshot.STATUS_LOCATED)
        self.assertEqual(traces[0]["trace_method"], "lldp-neighbor")
        self.assertEqual(traces[0]["trace_details"]["neighbor_ip"], "10.0.0.2")

    @patch("apps.network_analysis.services.NetworkDevice.objects")
    @patch.object(AddressTrackingAnalysisService, "_latest_rows")
    def test_build_traces_prefers_located_candidate_over_higher_scored_partial_candidate(
        self,
        mock_latest_rows,
        mock_device_objects,
    ):
        mock_latest_rows.side_effect = [
            [
                {
                    "hostip": "10.0.0.1",
                    "ipaddress": "10.1.1.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [
                {
                    "hostip": "10.0.0.1",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/1",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                },
                {
                    "hostip": "10.0.0.9",
                    "macaddress": "aaaa-bbbb-cccc",
                    "interface": "GigabitEthernet1/0/48",
                    "idc_name": "IDC-A",
                    "execute_time": "2026-03-16 10:00:00",
                },
            ],
            [
                {
                    "hostip": "10.0.0.9",
                    "local_interface": "GigabitEthernet1/0/48",
                    "neighbor_ip": "10.0.0.2",
                    "neighbor_port": "GigabitEthernet1/0/24",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
            [],
            [
                {
                    "hostip": "10.0.0.2",
                    "ipaddress": "10.1.1.1",
                    "interface": "GigabitEthernet1/0/24",
                    "execute_time": "2026-03-16 10:00:00",
                }
            ],
        ]
        mock_device_objects.filter.return_value.values.return_value = [
            {
                "serial_num": "SER-1",
                "manage_ip": "10.0.0.1",
                "name": "sw-a",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M1",
                "rack__name": "R1",
                "u_location_start": 1,
                "u_location_end": 2,
                "category__name": "switch",
            },
            {
                "serial_num": "SER-9",
                "manage_ip": "10.0.0.9",
                "name": "sw-b",
                "chassis": 1,
                "slot": 1,
                "idc__name": "IDC-A",
                "idc_model__name": "M2",
                "rack__name": "R2",
                "u_location_start": 3,
                "u_location_end": 4,
                "category__name": "switch",
            },
        ]

        traces = AddressTrackingAnalysisService.build_traces(
            ip_address="10.1.1.1")

        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["manage_ip"], "10.0.0.9")
        self.assertEqual(traces[0]["interface_name"], "GigabitEthernet1/0/48")
        self.assertEqual(traces[0]["trace_status"],
                         AddressTraceSnapshot.STATUS_LOCATED)
