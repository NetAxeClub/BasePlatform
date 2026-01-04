from .base import register_processor

@register_processor(vendor='Huawei', device_type='switch', collection_type='arp', method='netmiko')
def process_huawei_arp_netmiko(data):
    """华为 交换机 ARP 处理 (Netmiko)"""
    return data

@register_processor(vendor='Huawei', device_type='switch', collection_type='mac', method='netmiko')
def process_huawei_mac_netmiko(data):
    """华为 交换机 MAC 处理 (Netmiko)"""
    return data

@register_processor(vendor='Huawei', device_type='switch', collection_type='arp', method='netconf')
def process_huawei_arp_netconf(data):
    """华为 交换机 ARP 处理 (NETCONF)"""
    return data
