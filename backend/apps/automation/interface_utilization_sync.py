from apps.network_analysis.models import InterfaceUtilizationSnapshot


INTERFACE_SPEED_FIELD_MAP = {
    'int_used_1g': '1G',
    'int_used_10m': '10M',
    'int_used_100m': '100M',
    'int_used_10g': '10G',
    'int_used_20g': '20G',
    'int_used_25g': '25G',
    'int_used_40g': '40G',
    'int_used_100g': '100G',
    'int_used_200g': '200G',
    'int_used_400g': '400G',
    'int_unused_1g': '1G',
    'int_unused_10m': '10M',
    'int_unused_100m': '100M',
    'int_unused_10g': '10G',
    'int_unused_20g': '20G',
    'int_unused_25g': '25G',
    'int_unused_40g': '40G',
    'int_unused_100g': '100G',
    'int_unused_200g': '200G',
    'int_unused_400g': '400G',
}


def build_speed_counts(post_data, prefix):
    speed_counts = {}
    for field_name, speed_name in INTERFACE_SPEED_FIELD_MAP.items():
        if not field_name.startswith(prefix):
            continue
        value = post_data.get(field_name) or 0
        if value:
            speed_counts[speed_name] = value
    return speed_counts


def sync_interface_utilization_snapshot(post_data, device_serial_num, device_name, snapshot_time):
    if not device_serial_num:
        return
    InterfaceUtilizationSnapshot.objects.update_or_create(
        device_serial_num=str(device_serial_num),
        component_scope=InterfaceUtilizationSnapshot.SCOPE_DEVICE,
        component_key='',
        defaults={
            'manage_ip': post_data.get('host_ip') or '0.0.0.0',
            'device_name': device_name or post_data.get('host') or '',
            'component_name': device_name or post_data.get('host') or '',
            'dominant_speed': post_data.get('host_type') or '',
            'total_ports': post_data.get('int_total') or 0,
            'used_ports': post_data.get('int_used') or 0,
            'unused_ports': post_data.get('int_unused') or 0,
            'utilization_percent': post_data.get('utilization') or 0,
            'used_speed_counts': build_speed_counts(post_data, 'int_used_'),
            'unused_speed_counts': build_speed_counts(post_data, 'int_unused_'),
            'source_execute_time': snapshot_time.strftime('%Y-%m-%d %H:%M:%S'),
        },
    )
