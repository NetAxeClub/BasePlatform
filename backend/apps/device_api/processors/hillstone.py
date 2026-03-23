from .base import register_processor
from apps.device_api.tools.hillstone import HillstonePlan


@register_processor(vendor="Hillstone", device_type="", collection_type="version", method="netmiko")
def process_hillstone_version_netmiko(data):
    """山石防火墙设备标识处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_version(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="arp", method="netmiko")
def process_hillstone_arp_netmiko(data):
    """山石防火墙 ARP 处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_arp(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="mac", method="netmiko")
def process_hillstone_mac_netmiko(data):
    """山石防火墙 MAC 处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_mac(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="lldp", method="netmiko")
def process_hillstone_lldp_netmiko(data):
    """山石防火墙 LLDP 处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_lldp(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="interface_brief", method="netmiko")
def process_hillstone_interface_brief_netmiko(data):
    """山石防火墙接口摘要处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_interface_brief(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="ip_interface", method="netmiko")
def process_hillstone_ip_interface_netmiko(data):
    """山石防火墙三层接口处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_ip_interface(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="aggre_port", method="netmiko")
def process_hillstone_aggre_port_netmiko(data):
    """山石防火墙聚合端口处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_aggre_port(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="zone", method="netmiko")
def process_hillstone_zone_netmiko(data):
    """山石防火墙安全域处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_zone(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="service_predefined", method="netmiko")
def process_hillstone_service_predefined_netmiko(data):
    """山石防火墙预定义服务处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_service_predefined(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="policy_hit_count", method="netmiko")
def process_hillstone_policy_hit_count_netmiko(data):
    """山石防火墙策略命中统计处理 (Netmiko/TextFSM)"""
    return HillstonePlan.get_policy_hit_count(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="security_policy", method="netmiko")
def process_hillstone_security_policy_netmiko(data):
    """山石防火墙安全策略处理 (Netmiko/RAW + TextFSM)"""
    return HillstonePlan.get_security_policy(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="dnat", method="netmiko")
def process_hillstone_dnat_netmiko(data):
    """山石防火墙 DNAT 处理 (Netmiko/RAW + TextFSM)"""
    return HillstonePlan.get_dnat(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="snat", method="netmiko")
def process_hillstone_snat_netmiko(data):
    """山石防火墙 SNAT 处理 (Netmiko/RAW + TextFSM)"""
    return HillstonePlan.get_snat(data)


@register_processor(vendor="Hillstone", device_type="", collection_type="session", method="netmiko")
def process_hillstone_session_netmiko(data):
    """保留兼容的会话采集占位处理器"""
    return data
