from .base import register_processor

@register_processor(vendor='Ruijie', device_type='switch', collection_type='arp', method='netmiko')
def process_ruijie_arp_netmiko(data):
    """锐捷 交换机 ARP 处理 (Netmiko)"""
    return data

@register_processor(vendor='Ruijie', device_type='switch', collection_type='mac', method='netmiko')
def process_ruijie_mac_netmiko(data):
    """锐捷 交换机 MAC 处理 (Netmiko)"""
    return data
