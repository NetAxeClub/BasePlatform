from .base import register_processor
from apps.device_api.tools.cisco import CiscoPlan

@register_processor(vendor='Cisco', device_type='', collection_type='arp', method='netmiko')
def process_cisco_arp_netmiko(data):
    """思科 交换机 ARP 处理 (Netmiko)"""
    return CiscoPlan.get_arp(data)

@register_processor(vendor='Cisco', device_type='', collection_type='mac', method='netmiko')
def process_cisco_mac_netmiko(data):
    """思科 交换机 MAC 处理 (Netmiko)"""
    return CiscoPlan.get_mac(data)


@register_processor(vendor='Cisco', device_type='', collection_type='lldp', method='netmiko')
def process_cisco_lldp_netmiko(data):
    """思科 LLDP 处理 (Netmiko)"""
    return CiscoPlan.get_lldp(data)


@register_processor(vendor='Cisco', device_type='', collection_type='interface_brief', method='netmiko')
def process_cisco_interface_brief_netmiko(data):
    """思科接口摘要处理 (Netmiko)"""
    return CiscoPlan.get_interface_brief(data)


@register_processor(vendor='Cisco', device_type='', collection_type='ip_interface', method='netmiko')
def process_cisco_ip_interface_netmiko(data):
    """思科三层接口处理 (Netmiko)"""
    return CiscoPlan.get_ip_interface(data)


@register_processor(vendor='Cisco', device_type='', collection_type='aggre_port', method='netmiko')
def process_cisco_aggre_port_netmiko(data):
    """思科聚合端口处理 (Netmiko)"""
    return CiscoPlan.get_aggre_port(data)
