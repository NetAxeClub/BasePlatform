from .base import register_processor

@register_processor(vendor='Cisco', device_type='switch', collection_type='arp', method='netmiko')
def process_cisco_arp_netmiko(data):
    """思科 交换机 ARP 处理 (Netmiko)"""
    return data

@register_processor(vendor='Cisco', device_type='switch', collection_type='mac', method='netmiko')
def process_cisco_mac_netmiko(data):
    """思科 交换机 MAC 处理 (Netmiko)"""
    return data
