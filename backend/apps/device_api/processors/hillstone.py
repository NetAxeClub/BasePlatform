from .base import register_processor

@register_processor(vendor='Hillstone', device_type='firewall', collection_type='arp', method='netmiko')
def process_hillstone_arp_netmiko(data):
    """山石 防火墙 ARP 处理 (Netmiko)"""
    return data

@register_processor(vendor='Hillstone', device_type='firewall', collection_type='session', method='netmiko')
def process_hillstone_session_netmiko(data):
    """山石 防火墙 会话处理 (Netmiko)"""
    return data
