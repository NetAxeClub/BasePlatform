from .base import register_processor
from apps.device_api.tools.hillstone import HillstonePlan

@register_processor(vendor='Hillstone', device_type='', collection_type='arp', method='netmiko')
def process_hillstone_arp_netmiko(data):
    """山石 防火墙 ARP 处理 (Netmiko)"""
    return HillstonePlan.get_arp(data)


@register_processor(vendor='Hillstone', device_type='', collection_type='mac', method='netmiko')
def process_hillstone_mac_netmiko(data):
    """山石 防火墙 MAC 处理 (Netmiko)"""
    return HillstonePlan.get_mac(data)


@register_processor(vendor='Hillstone', device_type='', collection_type='lldp', method='netmiko')
def process_hillstone_lldp_netmiko(data):
    """山石 防火墙 LLDP 处理 (Netmiko)"""
    return HillstonePlan.get_lldp(data)


@register_processor(vendor='Hillstone', device_type='', collection_type='interface_brief', method='netmiko')
def process_hillstone_interface_brief_netmiko(data):
    """山石 防火墙接口摘要处理 (Netmiko)"""
    return HillstonePlan.get_interface_brief(data)


@register_processor(vendor='Hillstone', device_type='', collection_type='ip_interface', method='netmiko')
def process_hillstone_ip_interface_netmiko(data):
    """山石 防火墙三层接口处理 (Netmiko)"""
    return HillstonePlan.get_ip_interface(data)


@register_processor(vendor='Hillstone', device_type='', collection_type='aggre_port', method='netmiko')
def process_hillstone_aggre_port_netmiko(data):
    """山石 防火墙聚合端口处理 (Netmiko)"""
    return HillstonePlan.get_aggre_port(data)

@register_processor(vendor='Hillstone', device_type='', collection_type='session', method='netmiko')
def process_hillstone_session_netmiko(data):
    """山石 防火墙 会话处理 (Netmiko)"""
    return data
