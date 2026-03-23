from unittest.mock import patch

from django.test import TestCase

from apps.asset.models import AssetAccount, NetworkDevice
from apps.asset.tasks import check_network_device_protocol_connectivity


class _FakeTransport:
    def close(self):
        return None


class _FakeSSHClient:
    def __init__(self):
        self.connected = False

    def set_missing_host_key_policy(self, policy):
        return None

    def connect(
        self,
        hostname,
        port,
        username,
        password,
        timeout,
        allow_agent,
        look_for_keys,
    ):
        if hostname == '10.0.0.2':
            raise RuntimeError('ssh unreachable')
        self.connected = True

    def get_transport(self):
        if self.connected:
            return _FakeTransport()
        return None

    def close(self):
        self.connected = False


class NetworkDeviceProtocolConnectivityTaskTestCase(TestCase):
    def setUp(self):
        self.ssh_account = AssetAccount.objects.create(
            name='ssh-admin',
            username='admin',
            password='secret',
            protocol='ssh',
            port=22,
        )
        self.invalid_ssh_account = AssetAccount.objects.create(
            name='ssh-invalid',
            username='',
            password='',
            protocol='ssh',
            port=22,
        )

    @patch('apps.asset.tasks.paramiko.SSHClient', return_value=_FakeSSHClient())
    @patch('apps.asset.tasks.probe_snmp')
    def test_check_network_device_protocol_connectivity_updates_status_fields(
        self,
        mock_probe_snmp,
        mock_ssh_client,
    ):
        success_device = NetworkDevice.objects.create(
            serial_num='ND-001',
            manage_ip='10.0.0.1',
            name='old-name',
            snmp_version='v2c',
            snmp_community='public',
            snmp_port=161,
            ssh_enable='account',
            ssh_account=self.ssh_account,
        )
        failed_device = NetworkDevice.objects.create(
            serial_num='ND-002',
            manage_ip='10.0.0.2',
            name='failed-name',
            snmp_version='v2c',
            snmp_community='public',
            snmp_port=161,
            ssh_enable='account',
            ssh_account=self.ssh_account,
        )
        invalid_account_device = NetworkDevice.objects.create(
            serial_num='ND-003',
            manage_ip='10.0.0.3',
            name='invalid-account',
            snmp_version='v2c',
            snmp_community='-',
            snmp_port=161,
            ssh_enable='account',
            ssh_account=self.invalid_ssh_account,
        )
        unmanaged_device = NetworkDevice.objects.create(
            serial_num='ND-004',
            manage_ip='0.0.0.0',
            name='unmanaged-device',
            snmp_version='v2c',
            snmp_community='-',
            snmp_port=161,
            ssh_enable='0',
        )

        def probe_side_effect(ip, snmp_version, snmp_community, port, timeout, retries):
            if ip == '10.0.0.1':
                return True, 'core-sw-01'
            return False, 'snmp timeout'

        mock_probe_snmp.side_effect = probe_side_effect

        result = check_network_device_protocol_connectivity.run()

        success_device.refresh_from_db()
        failed_device.refresh_from_db()
        invalid_account_device.refresh_from_db()
        unmanaged_device.refresh_from_db()

        self.assertEqual(result['device_total'], 4)
        self.assertEqual(result['snmp_candidate'], 2)
        self.assertEqual(result['snmp_success'], 1)
        self.assertEqual(result['snmp_failed'], 1)
        self.assertEqual(result['ssh_candidate'], 3)
        self.assertEqual(result['ssh_success'], 1)
        self.assertEqual(result['ssh_failed'], 2)
        self.assertEqual(result['updated_devices'], 1)

        self.assertTrue(success_device.snmp_status)
        self.assertTrue(success_device.ssh_status)
        self.assertEqual(success_device.name, 'core-sw-01')

        self.assertFalse(failed_device.snmp_status)
        self.assertFalse(failed_device.ssh_status)
        self.assertEqual(failed_device.name, 'failed-name')

        self.assertFalse(invalid_account_device.ssh_status)
        self.assertFalse(unmanaged_device.snmp_status)
        self.assertFalse(unmanaged_device.ssh_status)

        self.assertEqual(mock_probe_snmp.call_count, 2)
        self.assertEqual(mock_ssh_client.call_count, 2)
