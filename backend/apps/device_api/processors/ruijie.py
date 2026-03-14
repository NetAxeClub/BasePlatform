from .base import register_processor

@register_processor(vendor='Ruijie', device_type='', collection_type='arp', method='netmiko')
def process_ruijie_arp_netmiko(data):
    """锐捷 交换机 ARP 处理 (Netmiko)"""
    return data

@register_processor(vendor='Ruijie', device_type='', collection_type='mac', method='netmiko')
def process_ruijie_mac_netmiko(data):
    """锐捷 交换机 MAC 处理 (Netmiko)"""
    return data


@register_processor(vendor='Ruijie', device_type='', collection_type='fan_status', method='netmiko')
def process_ruijie_fan_status_netmiko(data):
    """锐捷 风扇状态处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        fan_name = item.get('Name', '') or item.get('name', '')
        result.append(
            dict(
                chassis='',
                slot=item.get('Slot', '') or item.get('slot', ''),
                fan_id=item.get('Item', '') or item.get('item', ''),
                fan_name=fan_name,
                present='',
                register_state='',
                status=item.get('Status', '') or item.get('status', ''),
                speed=item.get('Speed', '') or item.get('speed', ''),
                mode=item.get('Level', '') or item.get('level', ''),
                airflow_direction='',
                prefer_airflow_direction='',
            )
        )
    return result


@register_processor(vendor='Ruijie', device_type='', collection_type='power_status', method='netmiko')
def process_ruijie_power_status_netmiko(data):
    """锐捷 电源状态处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        power_name = item.get('Name', '') or item.get('Type', '') or item.get('name', '')
        result.append(
            dict(
                chassis='',
                slot=item.get('Slot', '') or item.get('slot', ''),
                power_id=item.get('Item', '') or item.get('item', ''),
                power_name=power_name,
                present='',
                status=item.get('Status', '') or item.get('status', ''),
                mode=item.get('Type', '') or item.get('type', ''),
                current='',
                voltage=item.get('Vol', '') or item.get('vol', ''),
                output_power=item.get('OutPower', '') or item.get('outpower', ''),
            )
        )
    return result
