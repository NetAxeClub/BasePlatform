import re
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

from django.utils import timezone

from apps.asset.models import Model, NetworkDevice, Vendor
from apps.device_api.connection_manager import DeviceConnectionManager
from apps.device_api.contract import build_plan_collection_name
from apps.device_api.fields_mapping import (
    DEFAULT_COLLECTION_TYPES,
    RAW_NETMIKO_COLLECTION_TYPES,
)
from apps.device_api.models import (
    DeviceCollectionPlans,
    DeviceDiscoveryState,
    NetconfXMLTemplate,
    PlatformProfile,
    PlansToDevice,
)
from apps.device_api.services_new import DeviceCollectionService
from utils.db.mongo_ops import MongoOps


TEMPLATE_BASE_DIR = (
    Path(__file__).resolve().parents[2]
    / "utils"
    / "connect_layer"
    / "zetmiko"
    / "templates"
)
PLACEHOLDER_TEMPLATE_MARKERS = ("Placeholder template for P1.5 baseline",)
DEVICE_CATEGORY_ALIASES = {
    "switch": "switch",
    "交换机": "switch",
    "tap交换机": "switch",
    "firewall": "firewall",
    "防火墙": "firewall",
    "router": "router",
    "路由器": "router",
}


def _supported_types(*collection_types: str) -> List[str]:
    ordered = []
    for collection_type in DEFAULT_COLLECTION_TYPES:
        if collection_type in collection_types and collection_type not in ordered:
            ordered.append(collection_type)
    return ordered


BUILTIN_PLATFORM_PROFILES: List[Dict[str, object]] = [
    {
        "code": "Huawei-S",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"^S\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "netconf_capability": ["netconf"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
            "lldp": ["netconf", "netmiko"],
            "interface_brief": ["netconf", "netmiko"],
            "ip_interface": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "fan_status",
            "power_status",
            "temperature_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
        ),
        "default_plan_name": "default-huawei-s-switch",
    },
    {
        "code": "Huawei-CE68xx-netconf",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"^CE68\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netconf"],
            "board_status": ["netconf"],
            "stack_status": ["netconf"],
            "netconf_capability": ["netconf"],
            "arp": ["netconf"],
            "mac": ["netconf"],
            "mac_bd": ["netconf"],
            "mac_vxlan": ["netconf"],
            "mac_vxlan_control": ["netconf"],
            "lldp": ["netconf"],
            "interface_brief": ["netconf"],
            "ip_interface": ["netconf"],
            "aggre_port": ["netconf"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "board_status",
            "stack_status",
            "netconf_capability",
            "arp",
            "mac",
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
        ),
        "default_plan_name": "default-huawei-ce68-netconf-switch",
    },
    {
        "code": "Huawei-CE98xx",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"^CE98\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "netconf_capability": ["netconf"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
            "mac_bd": ["netconf"],
            "mac_vxlan": ["netconf"],
            "mac_vxlan_control": ["netconf"],
            "lldp": ["netconf", "netmiko"],
            "interface_brief": ["netconf", "netmiko"],
            "ip_interface": ["netconf", "netmiko"],
            "route_table": ["netconf", "netmiko"],
            "bgp_neighbors": ["netconf", "netmiko"],
            "bgp_summary": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "route_table": ["netmiko"],
            "bgp_neighbors": ["netmiko"],
            "bgp_summary": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "arp",
            "mac",
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "fan_status",
            "power_status",
            "temperature_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
        ),
        "default_plan_name": "default-huawei-ce98xx-netconf-switch",
    },
    {
        "code": "Huawei-CE88xx",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"^CE88\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "netconf_capability": ["netconf"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
            "mac_bd": ["netconf"],
            "mac_vxlan": ["netconf"],
            "mac_vxlan_control": ["netconf"],
            "lldp": ["netconf", "netmiko"],
            "interface_brief": ["netconf", "netmiko"],
            "ip_interface": ["netconf", "netmiko"],
            "route_table": ["netconf", "netmiko"],
            "bgp_neighbors": ["netconf", "netmiko"],
            "bgp_summary": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "route_table": ["netmiko"],
            "bgp_neighbors": ["netmiko"],
            "bgp_summary": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "arp",
            "mac",
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "fan_status",
            "power_status",
            "temperature_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
        ),
        "default_plan_name": "default-huawei-ce88xx-netconf-switch",
    },
    {
        "code": "Huawei-CE",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"^CE\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
            "mac_bd": ["netconf"],
            "mac_vxlan": ["netconf"],
            "mac_vxlan_control": ["netconf"],
            "lldp": ["netconf", "netmiko"],
            "interface_brief": ["netconf", "netmiko"],
            "ip_interface": ["netconf", "netmiko"],
            "route_table": ["netconf", "netmiko"],
            "bgp_neighbors": ["netconf", "netmiko"],
            "bgp_summary": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "route_table": ["netmiko"],
            "bgp_neighbors": ["netmiko"],
            "bgp_summary": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "mac",
            "mac_bd",
            "mac_vxlan",
            "mac_vxlan_control",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "fan_status",
            "power_status",
            "temperature_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
        ),
        "default_plan_name": "default-huawei-ce-netconf-switch",
    },
    {
        "code": "Huawei-router-cli",
        "vendor_alias": "Huawei",
        "category": "router",
        "series_patterns": [r"^AR\d+", r"^NE\d+", r"路由"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "ospf_neighbors": ["netmiko"],
            "ospf_interfaces": ["netmiko"],
            "isis_neighbors": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "lldp",
            "interface_brief",
            "ip_interface",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
        ),
        "default_plan_name": "default-huawei-router",
    },
    {
        "code": "Huawei-USG",
        "vendor_alias": "Huawei",
        "category": "firewall",
        "series_patterns": [r"^USG\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netconf", "netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netconf"],
            "ip_interface": ["netconf"],
            "aggre_port": ["netconf"],
            "hrp_state": ["netconf"],
            "security_policy": ["netconf"],
            "dnat": ["netconf"],
            "snat": ["netconf"],
            "nat_address": ["netconf"],
            "address_set": ["netconf"],
            "service_set": ["netconf"],
            "slb_info": ["netconf"],
            "vrrp_info": ["netconf"],
        },
        "fallback_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "hrp_state",
            "security_policy",
            "dnat",
            "snat",
            "nat_address",
            "address_set",
            "service_set",
            "slb_info",
            "vrrp_info",
        ),
        "default_plan_name": "default-huawei-usg-firewall",
    },
    {
        "code": "Huawei-YunShan",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [
            r"YunShan",
            r"CloudEngine.*AI",
            r"^CE16800-X\d+",
            r"^CE168\d+",
            r"CHASSIS-X",
        ],
        "os_family": "YunShan OS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netconf", "netmiko"],
            "netconf_capability": ["netconf"],
            "board_status": ["netconf"],
            "arp": ["netconf"],
            "mac": ["netconf", "netmiko"],
            "lldp": ["netconf", "netmiko"],
            "cpu_status": ["telemetry", "restconf"],
            "memory_status": ["telemetry", "restconf"],
            "interface_brief": ["netconf", "restconf", "netmiko"],
            "ip_interface": ["netconf", "restconf", "netmiko"],
            "aggre_port": ["netconf", "netmiko"],
            "route_table": ["netconf"],
            "bgp_neighbors": ["netconf", "netmiko"],
            "bgp_summary": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "device_identity": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "cpu_status": ["netmiko"],
            "memory_status": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "aggre_port": ["netmiko"],
            "bgp_neighbors": ["netmiko"],
            "bgp_summary": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "board_status",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
        ),
        "default_plan_name": "default-huawei-yunshan-switch",
    },
    {
        "code": "H3C-S98xx-cli",
        "vendor_alias": "H3C",
        "category": "switch",
        "series_patterns": [r"^S98\d+", r"^S982", r"^S985", r"^S988"],
        "os_family": "Comware",
        "version_patterns": [r"9\.", r"Release 9", r"Version 9\."],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "netconf_capability": ["netconf"],
            "cli_output_capability": ["netmiko"],
            "board_status": ["netmiko"],
            "arp": ["netmiko"],
            "lldp": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "cli_output_capability",
            "board_status",
            "arp",
            "lldp",
            "ip_interface",
        ),
        "default_plan_name": "default-h3c-s98xx-switch",
    },
    {
        "code": "H3C-legacy-cli",
        "vendor_alias": "H3C",
        "category": "switch",
        "series_patterns": [r"^S\d+", r"^E\d+"],
        "os_family": "Comware",
        "version_patterns": [r"5\.", r"Comware 5"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "netconf_capability": ["netconf"],
            "cli_output_capability": ["netmiko"],
            "board_status": ["netmiko"],
            "irf_status": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "cli_output_capability",
            "board_status",
            "irf_status",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
        ),
        "default_plan_name": "default-h3c-legacy-switch",
    },
    {
        "code": "H3C-modern-cli",
        "vendor_alias": "H3C",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "Comware",
        "version_patterns": [r"7\.", r"Comware 7"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "cli_output_capability": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "aggre_port": ["netmiko"],
            "fan_status": ["netmiko"],
            "power_status": ["netmiko"],
            "clock_status": ["netmiko"],
            "ospf_neighbors": ["netmiko"],
            "ospf_interfaces": ["netmiko"],
            "isis_neighbors": ["netmiko"],
            "board_status": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "cli_output_capability",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "fan_status",
            "power_status",
            "clock_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
        ),
        "default_plan_name": "default-h3c-modern-cli-switch",
    },
    {
        "code": "H3C-modern-netconf",
        "vendor_alias": "H3C",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "Comware",
        "version_patterns": [r"7\.", r"Comware 7"],
        "preferred_methods": {
            "device_identity": ["netconf", "netmiko"],
            "netconf_capability": ["netconf"],
            "cli_output_capability": ["netmiko"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
            "mac_evpn": ["netconf"],
            "lldp": ["netconf", "netmiko"],
            "interface_brief": ["netconf", "netmiko"],
            "ip_interface": ["netconf", "netmiko"],
            "aggre_port": ["netconf", "netmiko"],
            "irf_status": ["netconf"],
            "board_status": ["netconf", "netmiko"],
            "vrrp_info": ["netconf"],
            "route_table": ["netconf", "netmiko"],
            "bgp_neighbors": ["netconf", "netmiko"],
            "bgp_summary": ["netconf", "netmiko"],
        },
        "fallback_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "aggre_port": ["netmiko"],
            "board_status": ["netmiko"],
            "route_table": ["netmiko"],
            "bgp_neighbors": ["netmiko"],
            "bgp_summary": ["netmiko"],
        },
        "supported_collection_types": _supported_types(
            "device_identity",
            "netconf_capability",
            "cli_output_capability",
            "arp",
            "mac",
            "mac_evpn",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "vrrp_info",
            "fan_status",
            "power_status",
            "clock_status",
            "irf_status",
            "ospf_neighbors",
            "ospf_interfaces",
            "isis_neighbors",
            "board_status",
            "route_table",
            "bgp_neighbors",
            "bgp_summary",
        ),
        "default_plan_name": "default-h3c-modern-switch",
    },
    {
        "code": "H3C-router-cli",
        "vendor_alias": "H3C",
        "category": "router",
        "series_patterns": [r"^SR\d+", r"路由"],
        "os_family": "Comware",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "interface_brief",
            "ip_interface",
        ),
        "default_plan_name": "default-h3c-router",
    },
    {
        "code": "H3C-firewall-cli",
        "vendor_alias": "H3C",
        "category": "firewall",
        "series_patterns": [r"SecPath", r"^F\d+"],
        "os_family": "SecPath",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "interface_brief",
            "ip_interface",
        ),
        "default_plan_name": "default-h3c-firewall",
    },
    {
        "code": "Ruijie-switch",
        "vendor_alias": "Ruijie",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "RGOS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "aggre_port": ["netmiko"],
            "stack_status": ["netmiko"],
            "irf_status": ["netmiko"],
            "fan_status": ["netmiko"],
            "power_status": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "mac",
            "lldp",
            "interface_brief",
            "ip_interface",
            "aggre_port",
            "stack_status",
            "irf_status",
            "fan_status",
            "power_status",
        ),
        "default_plan_name": "default-ruijie-switch",
    },
    {
        "code": "Hillstone-firewall",
        "vendor_alias": "Hillstone",
        "category": "firewall",
        "series_patterns": [r".*"],
        "os_family": "StoneOS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
            "zone": ["netmiko"],
            "service_predefined": ["netmiko"],
            "policy_hit_count": ["netmiko"],
            "security_policy": ["netmiko"],
            "dnat": ["netmiko"],
            "snat": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "mac",
            "interface_brief",
            "ip_interface",
            "zone",
            "service_predefined",
            "policy_hit_count",
            "security_policy",
            "dnat",
            "snat",
        ),
        "default_plan_name": "default-hillstone-firewall",
    },
    {
        "code": "Cisco-switch",
        "vendor_alias": "Cisco",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "IOS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "mac",
        ),
        "default_plan_name": "default-cisco-switch",
    },
    {
        "code": "ZTE-switch",
        "vendor_alias": "ZTE",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "ZXR10",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "device_identity",
            "arp",
            "lldp",
        ),
        "default_plan_name": "default-zte-switch",
    },
    {
        "code": "Maipu-switch",
        "vendor_alias": "Maipu",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "MPSOS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "arp",
            "mac",
            "interface_brief",
            "aggre_port",
            "lldp",
        ),
        "default_plan_name": "default-maipu-switch",
    },
    {
        "code": "Mellanox-switch",
        "vendor_alias": "Mellanox",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "Onyx",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "mac",
            "aggre_port",
            "fan_status",
            "power_status",
        ),
        "default_plan_name": "default-mellanox-switch",
    },
    {
        "code": "Centec-switch",
        "vendor_alias": "centec",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "CNOS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netmiko"],
            "mac": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": _supported_types(
            "arp",
            "ip_interface",
        ),
        "default_plan_name": "default-centec-switch",
    },
]

DEVICE_IDENTITY_NETMIKO_COMMANDS = {
    "Huawei": "display version",
    "H3C": "display version",
    "Ruijie": "show version",
    "Hillstone": "show version",
    "Cisco": "show version",
    "ZTE": "show version",
    "Maipu": "show version",
    "Mellanox": "show version",
    "centec": "show version",
}

PROFILE_PLAN_METHOD_DEFAULTS: Dict[str, str] = {
    "Huawei-CE68xx-netconf": DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
    "Huawei-CE98xx": DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
    "Huawei-CE88xx": DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
    "Huawei-CE": DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
    "Huawei-USG": DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
    "Huawei-YunShan": DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
    "H3C-S98xx-cli": DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
    "H3C-legacy-cli": DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
    "H3C-modern-cli": DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
    "H3C-modern-netconf": DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
}

PROFILE_LEGACY_PLAN_NAME_ALIASES: Dict[str, List[str]] = {
    "Huawei-CE": ["default-huawei-ce-switch"],
    "Huawei-CE88xx": ["default-huawei-ce88xx-switch"],
    "Huawei-CE98xx": ["default-huawei-ce98xx-switch"],
    "H3C-modern-netconf": ["default-h3c-netconf-switch"],
}

PROFILE_CAPABILITY_REQUIREMENTS: Dict[str, Dict[str, object]] = {
    "Huawei-CE68xx-netconf": {
        "preferred_successful_probes": ["netconf_capability"],
        "required_protocols": {"netconf": True},
        "preferred_identity_patterns": {
            "model_name": [r"^CE68\d+"],
        },
    },
    "Huawei-CE88xx": {
        "preferred_successful_probes": ["netconf_capability"],
        "required_protocols": {"netconf": True},
        "preferred_identity_patterns": {
            "model_name": [r"^CE88\d+"],
        },
    },
    "Huawei-YunShan": {
        "preferred_successful_probes": ["netconf_capability"],
        "required_protocols": {"netconf": True},
        "preferred_identity_patterns": {
            "platform_name": [r"YunShan"],
            "model_name": [r"^CE168\d+"],
            "product_name": [r"CloudEngine"],
        },
    },
    "H3C-modern-netconf": {
        "preferred_successful_probes": ["netconf_capability"],
        "required_protocols": {"netconf": True},
        "disallowed_failed_probes": ["netconf_capability"],
        "preferred_probe_flags": {
            "netconf_capability": ["has_l2vpn_schema"],
        },
    },
    "H3C-modern-cli": {
        "preferred_successful_probes": ["cli_output_capability"],
        "preferred_failed_probes": ["netconf_capability"],
        "required_protocols": {"ssh": True},
        "preferred_probe_flags": {
            "cli_output_capability": ["supports_irf_cli"],
        },
    },
    "H3C-S98xx-cli": {
        "preferred_successful_probes": ["netconf_capability", "cli_output_capability"],
        "required_protocols": {"ssh": True},
        "preferred_probe_flags": {
            "netconf_capability": ["has_telemetry_schema"],
            "cli_output_capability": ["command_unrecognized"],
        },
        "preferred_probe_min_values": {
            "netconf_capability": {"schema_count": 200},
        },
    },
    "H3C-legacy-cli": {
        "preferred_successful_probes": ["cli_output_capability"],
        "required_protocols": {"ssh": True},
        "preferred_probe_flags": {
            "cli_output_capability": ["supports_irf_cli", "has_irf_members"],
        },
    },
}

PROFILE_NETMIKO_SUB_PLAN_DEFAULTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "Huawei-S": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "huawei_vrp_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display interface",
            "template": "huawei_vrp_display_interface.textfsm",
        },
        "aggre_port": {
            "command": "display eth-trunk",
            "template": "huawei_vrp_display_eth-trunk.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "huawei_vrp_display_fan.textfsm",
        },
        "power_status": {
            "command": "display power",
            "template": "huawei_vrp_display_power.textfsm",
        },
        "temperature_status": {
            "command": "display temperature",
            "template": "huawei_vrp_display_temperature.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer brief",
            "template": "huawei_vrp_display_ospf_peer_brief.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "huawei_vrp_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "huawei_vrp_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manufacture-info",
            "template": "huawei_vrp_display_device_manufacture-info.textfsm",
        },
    },
    "Huawei-CE98xx": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "huawei_vrp_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display interface",
            "template": "huawei_vrp_display_interface.textfsm",
        },
        "aggre_port": {
            "command": "display eth-trunk",
            "template": "huawei_vrp_display_eth-trunk.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "huawei_vrp_display_fan.textfsm",
        },
        "power_status": {
            "command": "display device power",
            "template": "huawei_ce_display_device_power.textfsm",
        },
        "temperature_status": {
            "command": "display temperature",
            "template": "huawei_vrp_display_temperature.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer brief",
            "template": "huawei_vrp_display_ospf_peer_brief.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "huawei_vrp_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "huawei_vrp_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manufacture-info",
            "template": "huawei_vrp_display_device_manufacture-info.textfsm",
        },
        "route_table": {
            "command": "display ip routing-table",
            "template": "huawei_vrp_display_ip_routing-table.textfsm",
        },
        "bgp_neighbors": {
            "command": "display bgp peer verbose",
            "template": "huawei_vrp_display_bgp_peer_verbose.textfsm",
        },
        "bgp_summary": {
            "command": "display bgp peer",
            "template": "huawei_vrp_display_bgp_peer.textfsm",
        },
    },
    "Huawei-CE88xx": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "huawei_vrp_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display interface",
            "template": "huawei_vrp_display_interface.textfsm",
        },
        "aggre_port": {
            "command": "display eth-trunk",
            "template": "huawei_vrp_display_eth-trunk.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "huawei_vrp_display_fan.textfsm",
        },
        "power_status": {
            "command": "display device power",
            "template": "huawei_ce_display_device_power.textfsm",
        },
        "temperature_status": {
            "command": "display temperature",
            "template": "huawei_vrp_display_temperature.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer brief",
            "template": "huawei_vrp_display_ospf_peer_brief.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "huawei_vrp_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "huawei_vrp_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manufacture-info",
            "template": "huawei_vrp_display_device_manufacture-info.textfsm",
        },
        "route_table": {
            "command": "display ip routing-table",
            "template": "huawei_vrp_display_ip_routing-table.textfsm",
        },
        "bgp_neighbors": {
            "command": "display bgp peer verbose",
            "template": "huawei_vrp_display_bgp_peer_verbose.textfsm",
        },
        "bgp_summary": {
            "command": "display bgp peer",
            "template": "huawei_vrp_display_bgp_peer.textfsm",
        },
    },
    "Huawei-CE": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "huawei_vrp_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display interface",
            "template": "huawei_vrp_display_interface.textfsm",
        },
        "aggre_port": {
            "command": "display eth-trunk",
            "template": "huawei_vrp_display_eth-trunk.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "huawei_vrp_display_fan.textfsm",
        },
        "power_status": {
            "command": "display device power",
            "template": "huawei_ce_display_device_power.textfsm",
        },
        "temperature_status": {
            "command": "display temperature",
            "template": "huawei_vrp_display_temperature.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer brief",
            "template": "huawei_vrp_display_ospf_peer_brief.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "huawei_vrp_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "huawei_vrp_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manufacture-info",
            "template": "huawei_vrp_display_device_manufacture-info.textfsm",
        },
    },
    "Huawei-USG": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {
            "command": "display arp all",
            "template": "huawei_vrp_display_arp.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_usg_display_lldp_neighbor.textfsm",
        },
        "mac": {
            "command": "display mac-address",
            "template": "huawei_usg_display_mac-address.textfsm",
        },
    },
    "Huawei-router-cli": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface brief",
            "template": "huawei_vrp_display_ip_interface_brief.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer brief",
            "template": "huawei_vrp_display_ospf_peer_brief.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "huawei_vrp_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "huawei_vrp_display_isis_peer_verbose.textfsm",
        },
    },
    "Huawei-YunShan": {
        "device_identity": {
            "command": "display version",
            "template": "huawei_vrp_display_version.textfsm",
        },
        "mac": {
            "command": "display mac-address",
            "template": "huawei_vrp_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor",
            "template": "huawei_vrp_display_lldp_neighbor.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "huawei_vrp_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display interface",
            "template": "huawei_vrp_display_interface.textfsm",
        },
        "aggre_port": {
            "command": "display eth-trunk",
            "template": "huawei_vrp_display_eth-trunk.textfsm",
        },
        "bgp_neighbors": {
            "command": "display bgp peer verbose",
            "template": "huawei_vrp_display_bgp_peer_verbose.textfsm",
        },
        "bgp_summary": {
            "command": "display bgp peer",
            "template": "huawei_vrp_display_bgp_peer.textfsm",
        },
    },
    "H3C-legacy-cli": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "cli_output_capability": {"command": "display irf", "template": ""},
        "board_status": {
            "command": "display device manuinfo",
            "template": "hp_comware_display_device_manuinfo.textfsm",
        },
        "irf_status": {
            "command": "display irf",
            "template": "hp_comware_display_irf.textfsm",
        },
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "hp_comware_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "hp_comware_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
        "aggre_port": {
            "command": "display link-aggregation verbose",
            "template": "hp_comware_display_link-aggregation_verbose.textfsm",
        },
    },
    "H3C-S98xx-cli": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "cli_output_capability": {"command": "display irf", "template": ""},
        "board_status": {
            "command": "display device manuinfo",
            "template": "hp_comware_display_device_manuinfo.textfsm",
        },
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
    },
    "H3C-modern-netconf": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "cli_output_capability": {"command": "display irf", "template": ""},
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "hp_comware_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "hp_comware_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
        "aggre_port": {
            "command": "display link-aggregation verbose",
            "template": "hp_comware_display_link-aggregation_verbose.textfsm",
        },
        "irf_status": {
            "command": "display irf",
            "template": "hp_comware_display_irf.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "hp_comware_display_fan.textfsm",
        },
        "power_status": {
            "command": "display power",
            "template": "hp_comware_display_power.textfsm",
        },
        "clock_status": {
            "command": "display clock",
            "template": "hp_comware_display_clock.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer verbose",
            "template": "hp_comware_display_ospf_peer.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "hp_comware_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "hp_comware_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manuinfo",
            "template": "hp_comware_display_device_manuinfo.textfsm",
        },
    },
    "H3C-modern-cli": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "cli_output_capability": {"command": "display irf", "template": ""},
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "mac": {
            "command": "display mac-address",
            "template": "hp_comware_display_mac-address.textfsm",
        },
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "interface_brief": {
            "command": "display interface brief",
            "template": "hp_comware_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
        "aggre_port": {
            "command": "display link-aggregation verbose",
            "template": "hp_comware_display_link-aggregation_verbose.textfsm",
        },
        "fan_status": {
            "command": "display fan",
            "template": "hp_comware_display_fan.textfsm",
        },
        "power_status": {
            "command": "display power",
            "template": "hp_comware_display_power.textfsm",
        },
        "clock_status": {
            "command": "display clock",
            "template": "hp_comware_display_clock.textfsm",
        },
        "ospf_neighbors": {
            "command": "display ospf peer verbose",
            "template": "hp_comware_display_ospf_peer.textfsm",
        },
        "ospf_interfaces": {
            "command": "display ospf interface",
            "template": "hp_comware_display_ospf_interface.textfsm",
        },
        "isis_neighbors": {
            "command": "display isis peer verbose",
            "template": "hp_comware_display_isis_peer_verbose.textfsm",
        },
        "board_status": {
            "command": "display device manuinfo",
            "template": "hp_comware_display_device_manuinfo.textfsm",
        },
    },
    "H3C-router-cli": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "interface_brief": {
            "command": "display interface brief",
            "template": "hp_comware_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
    },
    "H3C-firewall-cli": {
        "device_identity": {
            "command": "display version",
            "template": "hp_comware_display_version.textfsm",
        },
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "interface_brief": {
            "command": "display interface brief",
            "template": "hp_comware_display_interface_brief.textfsm",
        },
        "ip_interface": {
            "command": "display ip interface",
            "template": "hp_comware_display_ip_interface.textfsm",
        },
    },
    "Ruijie-switch": {
        "device_identity": {
            "command": "show version",
            "template": "ruijie_show_version.textfsm",
        },
        "fan_status": {"command": "show fan", "template": "ruijie_show_fan.textfsm"},
        "power_status": {
            "command": "show power",
            "template": "ruijie_show_power.textfsm",
        },
        "interface_brief": {
            "command": "show interfaces status",
            "template": "ruijie_show_interfaces_status.textfsm",
        },
        "ip_interface": {
            "command": "show ip interface brief",
            "template": "ruijie_show_ip_interface_brief.textfsm",
        },
        "arp": {"command": "show ip arp", "template": "ruijie_show_ip_arp.textfsm"},
        "mac": {"command": "show mac", "template": "ruijie_show_mac.textfsm"},
        "lldp": {
            "command": "show lldp neighbors detail",
            "template": "ruijie_show_lldp_neighbors_detail.textfsm",
        },
        "aggre_port": {
            "command": "show aggregatePort summary",
            "template": "ruijie_show_aggregatePort_summary.textfsm",
        },
        "stack_status": {
            "command": "show switch virtual",
            "template": "ruijie_show_switch_virtual.textfsm",
        },
        "irf_status": {
            "command": "show member",
            "template": "ruijie_show_member.textfsm",
        },
    },
    "Hillstone-firewall": {
        "device_identity": {
            "command": "show version",
            "template": "hillstone_show_version.textfsm",
        },
        "arp": {"command": "show arp", "template": "hillstone_show_arp.textfsm"},
        "mac": {"command": "show mac", "template": "hillstone_show_mac.textfsm"},
        "interface_brief": {
            "command": "show interface",
            "template": "hillstone_show_interface.textfsm",
        },
        "ip_interface": {
            "command": "show interface",
            "template": "hillstone_show_interface.textfsm",
        },
        "zone": {"command": "show zone", "template": "hillstone_show_zone.textfsm"},
        "service_predefined": {
            "command": "show service predefined",
            "template": "hillstone_show_service_predefined.textfsm",
        },
        "policy_hit_count": {
            "command": "show policy hit-count top 50",
            "template": "hillstone_show_policy_hit-count_top_50.textfsm",
        },
        "security_policy": {"command": "show configuration", "template": ""},
        "dnat": {"command": "show configuration", "template": ""},
        "snat": {"command": "show configuration", "template": ""},
    },
    "Cisco-switch": {
        "device_identity": {
            "command": "show version",
            "template": "cisco_ios_show_version.textfsm",
        },
        "arp": {"command": "show ip arp", "template": "cisco_ios_show_ip_arp.textfsm"},
        "mac": {
            "command": "show mac-address-table",
            "template": "cisco_ios_show_mac-address-table.textfsm",
        },
    },
    "ZTE-switch": {
        "device_identity": {
            "command": "show version",
            "template": "zte_zxros_show_version.textfsm",
        },
        "lldp": {
            "command": "show lldp entry",
            "template": "zte_zxros_show_lldp_entry.textfsm",
        },
        "arp": {"command": "show arp", "template": "zte_zxros_show_arp.textfsm"},
    },
    "Maipu-switch": {
        "arp": {"command": "show arp", "template": "maipu_show_arp.textfsm"},
        "mac": {
            "command": "show mac-address all",
            "template": "maipu_show_mac-address_all.textfsm",
        },
        "interface_brief": {
            "command": "show interface",
            "template": "maipu_show_interface.textfsm",
        },
        "aggre_port": {
            "command": "show link-aggregation interface",
            "template": "maipu_show_link-aggregation_interface.textfsm",
        },
    },
    "Mellanox-switch": {
        "mac": {
            "command": "show mac-address-table",
            "template": "mellanox_show_mac-address-table.textfsm",
        },
        "aggre_port": {
            "command": "show interface port-channel summary",
            "template": "mellanox_show_interface_port-channel_summary.textfsm",
        },
        "fan_status": {"command": "show fan", "template": "mellanox_show_fan.textfsm"},
        "power_status": {
            "command": "show power",
            "template": "mellanox_show_power.textfsm",
        },
    },
    "Centec-switch": {
        "arp": {"command": "show ip arp", "template": "centec_show_ip_arp.textfsm"},
        "ip_interface": {
            "command": "show ip interface brief",
            "template": "centec_show_ip_interface_brief.textfsm",
        },
    },
}

PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "H3C-modern-netconf": {
        "device_identity": {
            "collect_method": "get",
            "legacy_method": "collection_device_base",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <Device>
    <Base>
      <HostName></HostName>
      <HostDescription></HostDescription>
      <LocalTime></LocalTime>
    </Base>
    <PhysicalEntities>
      <Entity>
        <PhysicalIndex></PhysicalIndex>
        <Chassis></Chassis>
        <Slot></Slot>
        <Class></Class>
        <Name></Name>
        <Description></Description>
        <SoftwareRev></SoftwareRev>
        <SerialNumber></SerialNumber>
        <Model></Model>
      </Entity>
    </PhysicalEntities>
  </Device>
  <Package>
    <BootLoaderList>
      <BootList>
        <DeviceNode>
          <Chassis></Chassis>
          <Slot></Slot>
          <CPUID></CPUID>
        </DeviceNode>
        <BootType>0</BootType>
        <ImageFiles>
          <FileName></FileName>
        </ImageFiles>
      </BootList>
    </BootLoaderList>
  </Package>
</top>
""".strip(),
            "description": "H3CNetconf.collection_device_base + collection_device_PhysicalEntities + patch_version",
        },
        "netconf_capability": {
            "collect_method": "get",
            "legacy_method": "collection_yang_info",
            "xml_template": """
<netconf-state xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">
  <schemas/>
</netconf-state>
""".strip(),
            "description": "H3CNetconf.collection_yang_info",
        },
        "board_status": {
            "collect_method": "get",
            "legacy_method": "collection_device_PhysicalEntities",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <Device>
    <PhysicalEntities>
      <Entity>
        <PhysicalIndex></PhysicalIndex>
        <Chassis></Chassis>
        <Slot></Slot>
        <SubSlot></SubSlot>
        <Class></Class>
        <Description></Description>
        <Name></Name>
        <HardwareRev></HardwareRev>
        <FirmwareRev></FirmwareRev>
        <SoftwareRev></SoftwareRev>
        <SerialNumber></SerialNumber>
        <Model></Model>
      </Entity>
    </PhysicalEntities>
  </Device>
</top>
""".strip(),
            "description": "H3CNetconf.collection_device_PhysicalEntities",
        },
        "arp": {
            "collect_method": "get",
            "legacy_method": "colleciton_arp_list",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <ARP>
    <ArpTable>
      <ArpEntry>
        <IfIndex></IfIndex>
        <Ipv4Address></Ipv4Address>
        <MacAddress></MacAddress>
        <VLANID></VLANID>
        <PortIndex></PortIndex>
        <VrfIndex></VrfIndex>
        <ArpType></ArpType>
      </ArpEntry>
    </ArpTable>
  </ARP>
  <L2VPN>
    <LocalMACs>
      <MAC>
        <VsiName></VsiName>
        <MacAddr></MacAddr>
        <IfIndex></IfIndex>
        <SrvID></SrvID>
        <Type></Type>
      </MAC>
    </LocalMACs>
  </L2VPN>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <PortIndex></PortIndex>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.colleciton_arp_list + collection_arp_over_evpn",
        },
        "mac": {
            "collect_method": "get",
            "legacy_method": "collection_mac_unicasttable",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <MAC>
    <MacUnicastTable>
      <Unicast>
        <VLANID></VLANID>
        <MacAddress></MacAddress>
        <PortIndex></PortIndex>
        <NickName></NickName>
        <Status></Status>
        <Aging></Aging>
      </Unicast>
    </MacUnicastTable>
  </MAC>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <PortIndex></PortIndex>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.collection_mac_unicasttable",
        },
        "mac_evpn": {
            "collect_method": "get",
            "legacy_method": "collection_mac_over_evpn",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <L2VPN>
    <LocalMACs>
      <MAC>
        <VsiName></VsiName>
        <MacAddr></MacAddr>
        <IfIndex></IfIndex>
        <SrvID></SrvID>
        <Type></Type>
      </MAC>
    </LocalMACs>
  </L2VPN>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <PortIndex></PortIndex>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.collection_mac_over_evpn",
        },
        "lldp": {
            "collect_method": "get",
            "legacy_method": "collection_lldp_info",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <LLDP>
    <LLDPNeighbors>
      <LLDPNeighbor>
        <TimeMark></TimeMark>
        <IfIndex></IfIndex>
        <NeighborIndex></NeighborIndex>
        <SystemName></SystemName>
        <ChassisId></ChassisId>
        <PortId></PortId>
      </LLDPNeighbor>
    </LLDPNeighbors>
    <NbManageAddresses>
      <ManageAddress>
        <TimeMark></TimeMark>
        <IfIndex></IfIndex>
        <AgentID></AgentID>
        <NeighborIndex></NeighborIndex>
        <SubType></SubType>
        <Address></Address>
        <InterfaceType></InterfaceType>
        <InterfaceID></InterfaceID>
      </ManageAddress>
    </NbManageAddresses>
  </LLDP>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <PortIndex></PortIndex>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.collection_lldp_info",
        },
        "interface_brief": {
            "collect_method": "get",
            "legacy_method": "colleciton_interface_list",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <AbbreviatedName></AbbreviatedName>
        <PortIndex></PortIndex>
        <ifTypeExt></ifTypeExt>
        <ifType></ifType>
        <Description></Description>
        <AdminStatus></AdminStatus>
        <OperStatus></OperStatus>
        <ConfigSpeed></ConfigSpeed>
        <ActualSpeed></ActualSpeed>
        <ConfigDuplex></ConfigDuplex>
        <ActualDuplex></ActualDuplex>
        <LinkType></LinkType>
        <PVID></PVID>
        <InetAddressIPV4></InetAddressIPV4>
        <InetAddressIPV4Mask></InetAddressIPV4Mask>
        <PhysicalIndex></PhysicalIndex>
        <MAC></MAC>
        <PortLayer></PortLayer>
        <ForwardingAttributes></ForwardingAttributes>
        <Loopback></Loopback>
        <MDI></MDI>
        <ConfigMTU></ConfigMTU>
        <ActualMTU></ActualMTU>
        <ConfigBandwidth></ConfigBandwidth>
        <ActualBandwidth></ActualBandwidth>
        <SubPort></SubPort>
        <ForceUP></ForceUP>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.colleciton_interface_list",
        },
        "ip_interface": {
            "collect_method": "get",
            "legacy_method": "collection_ipv4address_list",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <IPV4ADDRESS>
    <Ipv4Addresses>
      <Ipv4Address>
        <IfIndex></IfIndex>
        <Ipv4Address></Ipv4Address>
        <Ipv4Mask></Ipv4Mask>
        <AddressOrigin></AddressOrigin>
      </Ipv4Address>
    </Ipv4Addresses>
  </IPV4ADDRESS>
  <IPV6ADDRESS>
    <Ipv6Addresses>
      <AddressEntry>
        <IfIndex></IfIndex>
        <Ipv6Address></Ipv6Address>
        <AddressOrigin></AddressOrigin>
        <Ipv6PrefixLength></Ipv6PrefixLength>
        <AnycastFlag></AnycastFlag>
      </AddressEntry>
    </Ipv6Addresses>
  </IPV6ADDRESS>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.collection_ipv4address_list + collection_ipv6address_list",
        },
        "aggre_port": {
            "collect_method": "get",
            "legacy_method": "colleciton_lagg_list",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <LAGG>
    <LAGGGroups>
      <LAGGGroup>
        <GroupId></GroupId>
        <LinkMode></LinkMode>
        <IfIndex></IfIndex>
      </LAGGGroup>
    </LAGGGroups>
    <LAGGMembers>
      <LAGGMember>
        <IfIndex></IfIndex>
        <GroupId></GroupId>
        <SelectedStatus></SelectedStatus>
        <UnSelectedReason></UnSelectedReason>
        <LacpEnable></LacpEnable>
        <LacpMode></LacpMode>
      </LAGGMember>
    </LAGGMembers>
  </LAGG>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.colleciton_lagg_list",
        },
        "irf_status": {
            "collect_method": "get",
            "legacy_method": "collection_irf_info",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <IRF>
    <Members>
      <Member>
        <MemberID></MemberID>
        <NewMemberID></NewMemberID>
        <Description></Description>
        <Priority></Priority>
        <CPUMac></CPUMac>
        <Board>
          <Chassis></Chassis>
          <Slot></Slot>
          <Role></Role>
        </Board>
      </Member>
    </Members>
  </IRF>
</top>
""".strip(),
            "description": "H3CNetconf.collection_irf_info",
        },
        "vrrp_info": {
            "collect_method": "get",
            "legacy_method": "collection_vrrp_info",
            "xml_template": """
<top xmlns="http://www.h3c.com/netconf/data:1.0">
  <VRRP>
    <VRRPOper>
      <Operation>
        <AddressType></AddressType>
        <IfIndex></IfIndex>
        <VrID></VrID>
        <OperState></OperState>
        <PriorityConfig></PriorityConfig>
        <PriorityRun></PriorityRun>
        <IpAddressCount></IpAddressCount>
        <MasterIpAddress></MasterIpAddress>
        <AuthTypeConfig></AuthTypeConfig>
        <AuthTypeRun></AuthTypeRun>
        <AdverInterval></AdverInterval>
        <PreemptMode></PreemptMode>
        <PreemptDelay></PreemptDelay>
      </Operation>
    </VRRPOper>
    <VRRPAssoIpAddress>
      <AssoIpAddr>
        <AddressType></AddressType>
        <IfIndex></IfIndex>
        <VrID></VrID>
        <IpAddress></IpAddress>
        <LinkLocal></LinkLocal>
      </AssoIpAddr>
    </VRRPAssoIpAddress>
  </VRRP>
  <Ifmgr>
    <Interfaces>
      <Interface>
        <IfIndex></IfIndex>
        <Name></Name>
        <PortIndex></PortIndex>
      </Interface>
    </Interfaces>
  </Ifmgr>
</top>
""".strip(),
            "description": "H3CNetconf.collection_vrrp_info",
        },
    },
    "Huawei-CE68xx-netconf": {
        "device_identity": {
            "collect_method": "get",
            "legacy_method": "collection_system_info",
            "xml_template": """
<system xmlns="http://www.huawei.com/netconf/vrp/huawei-system">
  <systemInfo>
  </systemInfo>
</system>
""".strip(),
            "description": "HuaweiCollection.collection_system_info",
        },
        "board_status": {
            "collect_method": "get",
            "legacy_method": "collection_moduleinfo",
            "xml_template": """
<devm xmlns="http://www.huawei.com/netconf/vrp/huawei-devm">
  <rUModuleInfos>
    <rUModuleInfo>
      <entClass>mpuModule</entClass>
      <position></position>
      <entSerialNo></entSerialNo>
      <entSerialNum></entSerialNum>
    </rUModuleInfo>
  </rUModuleInfos>
</devm>
""".strip(),
            "description": "HuaweiCollection.collection_moduleinfo",
        },
        "stack_status": {
            "collect_method": "get",
            "legacy_method": "collection_stack",
            "xml_template": """
<stack xmlns="http://www.huawei.com/netconf/vrp/huawei-stack">
  <stackMemberInfos>
    <stackMemberInfo>
      <memberID></memberID>
      <nextMemberID></nextMemberID>
      <deviceType></deviceType>
      <sysoid></sysoid>
      <role></role>
      <mac></mac>
      <priority></priority>
      <nextPriority></nextPriority>
      <domain></domain>
      <nextDomain></nextDomain>
      <stackPort1State></stackPort1State>
    </stackMemberInfo>
  </stackMemberInfos>
</stack>
""".strip(),
            "description": "HuaweiCollection.collection_stack",
        },
        "vxlan_capability": {
            "collect_method": "get_config",
            "legacy_method": "collection_vxlan_capability",
            "xml_template": """
<filter type="subtree">
<feil3bd xmlns="http://www.huawei.com/netconf/vrp/huawei-feil3bd">
</feil3bd>
<vxlan xmlns="http://www.huawei.com/netconf/vrp/huawei-vxlan">
</vxlan>
<bgp xmlns="http://www.huawei.com/netconf/vrp/huawei-bgp">
  <bgpcomm>
    <bgpVrfs>
      <bgpVrf>
        <vrfName></vrfName>
        <bgpVrfAFs>
          <bgpVrfAF>
            <afType></afType>
          </bgpVrfAF>
        </bgpVrfAFs>
      </bgpVrf>
    </bgpVrfs>
  </bgpcomm>
</bgp>
</filter>
""".strip(),
            "description": "Huawei CE VXLAN/BD/EVPN capability probe via get_config",
        },
        "arp": {
            "collect_method": "get",
            "legacy_method": "collection_arp_list",
            "xml_template": """
<arp xmlns="http://www.huawei.com/netconf/vrp/huawei-arp">
  <arpTables>
    <arpTable>
      <vrfName></vrfName>
      <ipAddr></ipAddr>
      <macAddr></macAddr>
      <styleType></styleType>
      <ifName></ifName>
      <expireTime></expireTime>
      <peVid></peVid>
      <ceVid></ceVid>
      <pvc></pvc>
      <peerAddr></peerAddr>
    </arpTable>
  </arpTables>
</arp>
""".strip(),
            "description": "HuaweiCollection.collection_arp_list",
        },
        "mac": {
            "collect_method": "get",
            "legacy_method": "collection_mac_table",
            "xml_template": """
<mac xmlns="http://www.huawei.com/netconf/vrp/huawei-mac">
  <vlanFdbDynamics>
    <vlanFdbDynamic>
      <slotId></slotId>
      <vlanId></vlanId>
      <macAddress></macAddress>
      <macType></macType>
      <outIfName></outIfName>
    </vlanFdbDynamic>
  </vlanFdbDynamics>
  <vlanFdbs>
    <vlanFdb>
      <slotId></slotId>
      <vlanId></vlanId>
      <macAddress></macAddress>
      <macType></macType>
      <outIfName></outIfName>
    </vlanFdb>
  </vlanFdbs>
</mac>
""".strip(),
            "description": "HuaweiCollection.collection_mac_table",
        },
        "mac_bd": {
            "collect_method": "get",
            "legacy_method": "collection_mac_bd",
            "xml_template": """
<mac xmlns="http://www.huawei.com/netconf/vrp/huawei-mac">
  <bdFdbs>
    <bdFdb>
      <slotId></slotId>
      <macAddress></macAddress>
      <macType></macType>
      <outIfName></outIfName>
      <bdId></bdId>
      <vid></vid>
    </bdFdb>
  </bdFdbs>
</mac>
""".strip(),
            "description": "HuaweiCollection.collection_mac_bd",
        },
        "mac_vxlan": {
            "collect_method": "get",
            "legacy_method": "collection_mac_vxlan",
            "xml_template": """
<mac xmlns="http://www.huawei.com/netconf/vrp/huawei-mac">
  <vxlanFdbs>
    <vxlanFdb>
      <slotId></slotId>
      <macAddress></macAddress>
      <bdId></bdId>
      <macType></macType>
      <sourceIP></sourceIP>
      <peerIP></peerIP>
      <vnId></vnId>
      <tunnelType></tunnelType>
    </vxlanFdb>
  </vxlanFdbs>
</mac>
""".strip(),
            "description": "HuaweiCollection.collection_mac_vxlan",
        },
        "mac_vxlan_control": {
            "collect_method": "get",
            "legacy_method": "collection_mac_vxlan_control",
            "xml_template": """
<mac xmlns="http://www.huawei.com/netconf/vrp/huawei-mac">
  <vxlanControls>
    <vxlanControl>
      <slotId></slotId>
      <macAddress></macAddress>
      <bdId></bdId>
      <macType></macType>
      <tunnelType></tunnelType>
      <sourceIpv6></sourceIpv6>
      <peerIpv6></peerIpv6>
      <vnId></vnId>
    </vxlanControl>
  </vxlanControls>
</mac>
""".strip(),
            "description": "HuaweiCollection.collection_mac_vxlan_control",
        },
        "lldp": {
            "collect_method": "get",
            "legacy_method": "collection_lldp_ip",
            "xml_template": """
<lldp xmlns="http://www.huawei.com/netconf/vrp/huawei-lldp">
  <lldpInterfaces>
    <lldpInterface>
      <ifName></ifName>
      <lldpNeighbors>
        <lldpNeighbor>
          <nbIndex></nbIndex>
          <managementAddresss>
            <managementAddress>
              <manAddrSubtype></manAddrSubtype>
              <manAddr></manAddr>
              <manAddrLen></manAddrLen>
            </managementAddress>
          </managementAddresss>
          <chassisIdSubtype></chassisIdSubtype>
          <chassisId></chassisId>
          <portIdSubtype></portIdSubtype>
          <portId></portId>
          <portDescription></portDescription>
          <systemName></systemName>
        </lldpNeighbor>
      </lldpNeighbors>
    </lldpInterface>
  </lldpInterfaces>
</lldp>
""".strip(),
            "description": "HuaweiCollection.collection_lldp_ip",
        },
        "interface_brief": {
            "collect_method": "get",
            "legacy_method": "collection_intf_ipv4v6",
            "xml_template": """
<ifm xmlns="http://www.huawei.com/netconf/vrp/huawei-ifm">
  <interfaces>
    <interface>
      <ifName></ifName>
      <ipv6Oper>
        <ipv6Addrs>
          <ipv6Addr>
            <ifIp6Addr></ifIp6Addr>
            <addrType6></addrType6>
          </ipv6Addr>
        </ipv6Addrs>
      </ipv6Oper>
      <ipv4Oper>
        <ipv4Addrs>
          <ipv4Addr>
            <ifIpAddr/>
            <subnetMask/>
            <addrType/>
          </ipv4Addr>
        </ipv4Addrs>
      </ipv4Oper>
      <ifDynamicInfo>
        <ifOperStatus></ifOperStatus>
        <ifPhyStatus></ifPhyStatus>
        <ifLinkStatus></ifLinkStatus>
        <ifOpertMTU></ifOpertMTU>
        <ifOperSpeed></ifOperSpeed>
        <ifV4State></ifV4State>
        <ifV6State></ifV6State>
        <ifCtrlFlapDamp></ifCtrlFlapDamp>
        <ifOperMac></ifOperMac>
      </ifDynamicInfo>
    </interface>
  </interfaces>
</ifm>
""".strip(),
            "description": "HuaweiCollection.collection_intf_ipv4v6 shared with ip_interface",
        },
        "ip_interface": {
            "collect_method": "get",
            "legacy_method": "collection_intf_ipv4v6",
            "xml_template": """
<ifm xmlns="http://www.huawei.com/netconf/vrp/huawei-ifm">
  <interfaces>
    <interface>
      <ifName></ifName>
      <ipv6Oper>
        <ipv6Addrs>
          <ipv6Addr>
            <ifIp6Addr></ifIp6Addr>
            <addrType6></addrType6>
          </ipv6Addr>
        </ipv6Addrs>
      </ipv6Oper>
      <ipv4Oper>
        <ipv4Addrs>
          <ipv4Addr>
            <ifIpAddr/>
            <subnetMask/>
            <addrType/>
          </ipv4Addr>
        </ipv4Addrs>
      </ipv4Oper>
      <ifDynamicInfo>
        <ifOperStatus></ifOperStatus>
        <ifPhyStatus></ifPhyStatus>
        <ifLinkStatus></ifLinkStatus>
        <ifOpertMTU></ifOpertMTU>
        <ifOperSpeed></ifOperSpeed>
        <ifV4State></ifV4State>
        <ifV6State></ifV6State>
        <ifCtrlFlapDamp></ifCtrlFlapDamp>
        <ifOperMac></ifOperMac>
      </ifDynamicInfo>
    </interface>
  </interfaces>
</ifm>
""".strip(),
            "description": "HuaweiCollection.collection_intf_ipv4v6 shared with interface_brief",
        },
        "aggre_port": {
            "collect_method": "get",
            "legacy_method": "collection_trunk_lacp",
            "xml_template": """
<ifmtrunk xmlns="http://www.huawei.com/netconf/vrp/huawei-ifmtrunk">
  <TrunkIfs>
    <TrunkIf>
      <ifName></ifName>
      <TrunkMemberIfs>
        <TrunkMemberIf>
          <memberIfName></memberIfName>
          <weight></weight>
          <memberIfState></memberIfState>
        </TrunkMemberIf>
      </TrunkMemberIfs>
    </TrunkIf>
  </TrunkIfs>
</ifmtrunk>
""".strip(),
            "description": "HuaweiCollection.collection_trunk_lacp; placeholder for collection_aggregation",
        },
    },
}

PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS["Huawei-USG"] = {
    "device_identity": {
        "collect_method": "get",
        "legacy_method": "get_system_info",
        "xml_template": """
<device-state xmlns="urn:huawei:params:xml:ns:yang:huawei-device">
</device-state>
""".strip(),
        "description": "HuaweiUSG.get_system_info",
    },
    "hrp_state": {
        "collect_method": "get",
        "legacy_method": "get_hrp_state",
        "xml_template": """
<hrp-state xmlns="urn:huawei:params:xml:ns:yang:huawei-hrp">
</hrp-state>
""".strip(),
        "description": "HuaweiUSG.get_hrp_state",
    },
    "interface_brief": {
        "collect_method": "get_config",
        "legacy_method": "get_interface_list",
        "xml_template": """
<filter type="subtree">
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"
      xmlns:ip="urn:ietf:params:xml:ns:yang:ietf-ip"
      xmlns:hw-if="urn:huawei:params:xml:ns:yang:huawei-interface"
      xmlns:hw-zone="urn:huawei:params:xml:ns:yang:huawei-security-zone"
      xmlns:hw-trunk="urn:huawei:params:xml:ns:yang:huawei-eth-trunk">
  </interfaces>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_interface_list shared with ip_interface",
    },
    "ip_interface": {
        "collect_method": "get_config",
        "legacy_method": "get_interface_list",
        "xml_template": """
<filter type="subtree">
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"
      xmlns:ip="urn:ietf:params:xml:ns:yang:ietf-ip"
      xmlns:hw-if="urn:huawei:params:xml:ns:yang:huawei-interface"
      xmlns:hw-zone="urn:huawei:params:xml:ns:yang:huawei-security-zone"
      xmlns:hw-trunk="urn:huawei:params:xml:ns:yang:huawei-eth-trunk">
  </interfaces>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_interface_list shared with interface_brief",
    },
    "aggre_port": {
        "collect_method": "get_config",
        "legacy_method": "get_trunk_lacp",
        "xml_template": """
<filter type="subtree">
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces"
      xmlns:hw-trunk="urn:huawei:params:xml:ns:yang:huawei-eth-trunk">
  </interfaces>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_trunk_lacp",
    },
    "security_policy": {
        "collect_method": "get_config",
        "legacy_method": "get_sec_policy",
        "xml_template": """
<filter type="subtree">
  <sec-policy xmlns="urn:huawei:params:xml:ns:yang:huawei-security-policy">
  </sec-policy>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_sec_policy",
    },
    "snat": {
        "collect_method": "get_config",
        "legacy_method": "get_nat_policy",
        "xml_template": """
<filter type="subtree">
  <nat-policy xmlns="urn:huawei:params:xml:ns:yang:huawei-nat-policy">
  </nat-policy>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_nat_policy",
    },
    "dnat": {
        "collect_method": "get_config",
        "legacy_method": "get_nat_server",
        "xml_template": """
<filter type="subtree">
  <nat-server xmlns="urn:huawei:params:xml:ns:yang:huawei-nat-server">
  </nat-server>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_nat_server",
    },
    "nat_address": {
        "collect_method": "get_config",
        "legacy_method": "get_nat_address",
        "xml_template": """
<filter type="subtree">
  <nat-address-group xmlns="urn:huawei:params:xml:ns:yang:huawei-nat-address-group">
  </nat-address-group>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_nat_address",
    },
    "address_set": {
        "collect_method": "get_config",
        "legacy_method": "get_address_set",
        "xml_template": """
<filter type="subtree">
  <address-set xmlns="urn:huawei:params:xml:ns:yang:huawei-address-set">
  </address-set>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_address_set",
    },
    "service_set": {
        "collect_method": "get_config",
        "legacy_method": "get_service_set",
        "xml_template": """
<filter type="subtree">
  <service-set xmlns="urn:huawei:params:xml:ns:yang:huawei-service-set">
  </service-set>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_service_set",
    },
    "slb_info": {
        "collect_method": "get_config",
        "legacy_method": "get_slb_info",
        "xml_template": """
<filter type="subtree">
  <slb xmlns="urn:huawei:params:xml:ns:yang:huawei-slb">
  </slb>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_slb_info",
    },
    "vrrp_info": {
        "collect_method": "get_config",
        "legacy_method": "get_vrrp_info",
        "xml_template": """
<filter type="subtree">
  <vrrp xmlns="urn:huawei:params:xml:ns:yang:huawei-vrrp">
  </vrrp>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_vrrp_info",
    },
    "route_table": {
        "collect_method": "get_config",
        "legacy_method": "get_device_route",
        "xml_template": """
<filter type="subtree">
  <routing xmlns="urn:ietf:params:xml:ns:yang:ietf-routing">
  </routing>
</filter>
""".strip(),
        "description": "HuaweiUSG.get_device_route",
    },
}

PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS["Huawei-YunShan"] = {
    "device_identity": {
        "collect_method": "get",
        "legacy_method": "collection_system_info",
        "xml_template": """
<system xmlns="urn:huawei:yang:huawei-system">
  <system-info/>
</system>
""".strip(),
        "description": "Huawei YunShan system-info via huawei-system YANG",
    },
    "netconf_capability": {
        "collect_method": "get",
        "legacy_method": "collection_yang_info",
        "xml_template": """
<netconf-state xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">
  <schemas/>
</netconf-state>
""".strip(),
        "description": "Huawei YunShan NETCONF schema probe via ietf-netconf-monitoring",
    },
    "board_status": {
        "collect_method": "get",
        "legacy_method": "collection_moduleinfo",
        "xml_template": """
<devm xmlns="urn:huawei:yang:huawei-devm">
  <mpu-boards/>
  <lpu-boards/>
  <sfu-boards/>
  <device-info/>
</devm>
""".strip(),
        "description": "Huawei YunShan board inventory via huawei-devm",
    },
    "arp": {
        "collect_method": "get",
        "legacy_method": "collection_arp_list",
        "xml_template": """
<arp:arp xmlns:arp="urn:huawei:yang:huawei-arp">
  <arp:query-entries>
    <arp:query-entry>
      <arp:ip-addr/>
      <arp:if-name/>
      <arp:mac-addr/>
    </arp:query-entry>
  </arp:query-entries>
</arp:arp>
""".strip(),
        "description": "HuaweiYunShanCollection.collection_arp_list",
    },
    "mac": {
        "collect_method": "get",
        "legacy_method": "collection_mac_table",
        "xml_template": """
<mac:mac xmlns:mac="urn:huawei:yang:huawei-mac">
  <mac:vlan-dynamic-macs>
    <mac:vlan-dynamic-mac>
      <mac:slot-id/>
      <mac:vlan-id/>
      <mac:address/>
      <mac:type/>
      <mac:out-interface-name/>
      <mac:last-change-time/>
    </mac:vlan-dynamic-mac>
  </mac:vlan-dynamic-macs>
</mac:mac>
""".strip(),
        "description": "Huawei YunShan VLAN dynamic MAC state path from huawei-mac schema",
    },
    "lldp": {
        "collect_method": "get",
        "legacy_method": "collection_lldp_ip",
        "xml_template": """
<ifm:ifm xmlns:ifm="urn:huawei:yang:huawei-ifm" xmlns:lldp="urn:huawei:yang:huawei-lldp">
  <ifm:interfaces>
    <ifm:interface>
      <ifm:name/>
      <lldp:lldp>
        <lldp:session>
          <lldp:neighbors/>
        </lldp:session>
      </lldp:lldp>
    </ifm:interface>
  </ifm:interfaces>
</ifm:ifm>
""".strip(),
        "description": "Huawei YunShan LLDP neighbors via huawei-lldp augment on huawei-ifm",
    },
    "interface_brief": {
        "collect_method": "get",
        "legacy_method": "collection_arp_list_test",
        "xml_template": """
<ifm:ifm xmlns:ifm="urn:huawei:yang:huawei-ifm" xmlns:ip="urn:huawei:yang:huawei-ip">
  <ifm:interfaces>
    <ifm:interface>
      <ifm:name/>
      <ifm:admin-status/>
      <ifm:oper-status/>
      <ifm:speed/>
      <ifm:description/>
      <ip:ipv4/>
    </ifm:interface>
  </ifm:interfaces>
</ifm:ifm>
""".strip(),
        "description": "HuaweiYunShanCollection.collection_arp_list_test shared with ip_interface",
    },
    "ip_interface": {
        "collect_method": "get",
        "legacy_method": "collection_arp_list_test",
        "xml_template": """
<ifm:ifm xmlns:ifm="urn:huawei:yang:huawei-ifm" xmlns:ip="urn:huawei:yang:huawei-ip">
  <ifm:interfaces>
    <ifm:interface>
      <ifm:name/>
      <ifm:admin-status/>
      <ifm:oper-status/>
      <ifm:speed/>
      <ifm:description/>
      <ip:ipv4/>
    </ifm:interface>
  </ifm:interfaces>
</ifm:ifm>
""".strip(),
        "description": "HuaweiYunShanCollection.collection_arp_list_test shared with interface_brief",
    },
    "aggre_port": {
        "collect_method": "get",
        "legacy_method": "collection_trunk_lacp",
        "xml_template": """
<ifm:ifm xmlns:ifm="urn:huawei:yang:huawei-ifm" xmlns:trunk="urn:huawei:yang:huawei-ifm-trunk">
  <ifm:interfaces>
    <ifm:interface>
      <ifm:name/>
      <ifm:type/>
      <trunk:trunk>
        <trunk:work-mode/>
        <trunk:members/>
      </trunk:trunk>
    </ifm:interface>
  </ifm:interfaces>
</ifm:ifm>
""".strip(),
        "description": "Huawei YunShan trunk members via huawei-ifm-trunk augment on huawei-ifm",
    },
    "route_table": {
        "collect_method": "get",
        "legacy_method": "collection_route_table",
        "xml_template": """
<network-instance xmlns="urn:huawei:yang:huawei-network-instance" xmlns:l3vpn="urn:huawei:yang:huawei-l3vpn" xmlns:rt="urn:huawei:yang:huawei-routing">
  <instances>
    <instance>
      <name/>
      <l3vpn:afs>
        <l3vpn:af>
          <l3vpn:type/>
          <rt:routing>
            <rt:routing-manage>
              <rt:topologys>
                <rt:topology>
                  <rt:name/>
                  <rt:routes>
                    <rt:ipv4-unicast-routes/>
                  </rt:routes>
                </rt:topology>
              </rt:topologys>
            </rt:routing-manage>
          </rt:routing>
        </l3vpn:af>
      </l3vpn:afs>
    </instance>
  </instances>
</network-instance>
""".strip(),
        "description": "Huawei YunShan IPv4 unicast routes via huawei-network-instance + huawei-routing",
    },
    "bgp_neighbors": {
        "collect_method": "get",
        "legacy_method": "collection_bgp_peer",
        "xml_template": """
<network-instance xmlns="urn:huawei:yang:huawei-network-instance" xmlns:bgp="urn:huawei:yang:huawei-bgp">
  <instances>
    <instance>
      <name/>
      <bgp:bgp>
        <bgp:base-process>
          <bgp:peer-states>
            <bgp:peer-state>
              <bgp:address/>
              <bgp:af-type/>
              <bgp:establish-mode/>
              <bgp:remote-as/>
              <bgp:peer-state/>
              <bgp:remote-router-id/>
              <bgp:group-name/>
            </bgp:peer-state>
          </bgp:peer-states>
          <bgp:peer-total-numbers>
            <bgp:peer-total-number>
              <bgp:af-type/>
              <bgp:static-peer-number/>
              <bgp:static-peer-established-number/>
              <bgp:dynamic-peer-number/>
            </bgp:peer-total-number>
          </bgp:peer-total-numbers>
          <bgp:peers>
            <bgp:peer>
              <bgp:address/>
              <bgp:remote-as/>
              <bgp:group-name/>
              <bgp:description/>
            </bgp:peer>
          </bgp:peers>
        </bgp:base-process>
      </bgp:bgp>
    </instance>
  </instances>
</network-instance>
""".strip(),
        "description": "Huawei YunShan BGP peers via huawei-network-instance + huawei-bgp (peer-states if present, peers config fallback)",
    },
    "bgp_summary": {
        "collect_method": "get",
        "legacy_method": "collection_bgp_peer",
        "xml_template": """
<network-instance xmlns="urn:huawei:yang:huawei-network-instance" xmlns:bgp="urn:huawei:yang:huawei-bgp">
  <instances>
    <instance>
      <name/>
      <bgp:bgp>
        <bgp:base-process>
          <bgp:peer-total-numbers>
            <bgp:peer-total-number>
              <bgp:af-type/>
              <bgp:static-peer-number/>
              <bgp:static-peer-established-number/>
              <bgp:dynamic-peer-number/>
            </bgp:peer-total-number>
          </bgp:peer-total-numbers>
        </bgp:base-process>
      </bgp:bgp>
    </instance>
  </instances>
</network-instance>
""".strip(),
        "description": "Huawei YunShan BGP peer totals via huawei-network-instance + huawei-bgp",
    },
}

for _h3c_cli_cap_profile_code in ("H3C-S98xx-cli", "H3C-legacy-cli"):
    PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS[_h3c_cli_cap_profile_code] = {
        "netconf_capability": dict(
            PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS["H3C-modern-netconf"][
                "netconf_capability"
            ]
        )
    }

for _huawei_netconf_profile_code in ("Huawei-CE98xx", "Huawei-CE88xx", "Huawei-CE"):
    PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS[_huawei_netconf_profile_code] = {
        key: dict(value)
        for key, value in PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS[
            "Huawei-CE68xx-netconf"
        ].items()
    }

for _huawei_vxlan_no_bd_profile_code in ("Huawei-CE98xx", "Huawei-CE"):
    PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS[_huawei_vxlan_no_bd_profile_code][
        "vxlan_capability"
    ] = {
        "collect_method": "get_config",
        "legacy_method": "collection_vxlan_capability",
        "xml_template": """
<filter type="subtree">
<vxlan xmlns="http://www.huawei.com/netconf/vrp/huawei-vxlan">
</vxlan>
<bgp xmlns="http://www.huawei.com/netconf/vrp/huawei-bgp">
  <bgpcomm>
    <bgpVrfs>
      <bgpVrf>
        <vrfName></vrfName>
        <bgpVrfAFs>
          <bgpVrfAF>
            <afType></afType>
          </bgpVrfAF>
        </bgpVrfAFs>
      </bgpVrf>
    </bgpVrfs>
  </bgpcomm>
</bgp>
</filter>
""".strip(),
        "description": "Huawei CE VXLAN/EVPN capability probe via get_config (no feil3bd support)",
    }


class PlatformProfileService:
    _template_placeholder_cache: Dict[str, bool] = {}
    _capability_collection_cache: Dict[str, MongoOps] = {}
    CAPABILITY_DISCOVERY_COLLECTION_TYPES = (
        "netconf_capability",
        "cli_output_capability",
        "vxlan_capability",
    )

    @classmethod
    def _normalize_requested_capability_types(
        cls,
        *,
        vendor_alias: str = "",
        collection_type: str = "",
        collection_types: Optional[List[str]] = None,
    ) -> List[str]:
        requested = []
        for item in [collection_type, *(collection_types or [])]:
            text = str(item or "").strip()
            if text and text not in requested:
                requested.append(text)

        if not requested:
            requested = ["netconf_capability"]
            if vendor_alias == "H3C":
                requested.append("cli_output_capability")

        invalid_types = [
            item
            for item in requested
            if item not in cls.CAPABILITY_DISCOVERY_COLLECTION_TYPES
        ]
        if invalid_types:
            raise ValueError(
                "collection_type 仅支持: "
                + ", ".join(cls.CAPABILITY_DISCOVERY_COLLECTION_TYPES)
            )

        return requested

    @staticmethod
    def _normalize_vendor_alias(device: NetworkDevice) -> str:
        vendor_alias = getattr(getattr(device, "vendor", None), "alias", "")
        return str(vendor_alias or "").strip() or "UNKNOWN"

    @classmethod
    def build_discovery_connection_policy(cls, device: NetworkDevice) -> Dict[str, int]:
        policy = {
            "netconf_timeout_seconds": 8,
            "netconf_retry_times": 0,
            "netmiko_timeout_seconds": 8,
            "netmiko_session_timeout_seconds": 15,
            "netmiko_retry_times": 0,
        }
        vendor_alias = cls._normalize_vendor_alias(device)
        model_name = str(
            getattr(getattr(device, "model", None), "name", "") or ""
        ).upper()
        if vendor_alias == "H3C" and model_name.startswith("S5130"):
            policy["netconf_timeout_seconds"] = 5
        return policy

    @staticmethod
    def _build_category_hint_device(device: NetworkDevice, category_name: str):
        normalized_category_name = str(category_name or "").strip()
        if not normalized_category_name:
            return device
        current_category_name = (
            getattr(getattr(device, "category", None), "name", "") or ""
        )
        if current_category_name:
            return device
        return SimpleNamespace(
            serial_num=getattr(device, "serial_num", ""),
            manage_ip=getattr(device, "manage_ip", ""),
            vendor=getattr(device, "vendor", None),
            category=SimpleNamespace(name=normalized_category_name),
            model=getattr(device, "model", None),
            soft_version=getattr(device, "soft_version", ""),
            name=getattr(device, "name", ""),
            ssh_account=getattr(device, "ssh_account", None),
            ssh_account_id=getattr(device, "ssh_account_id", None),
            netconf_account=getattr(device, "netconf_account", None),
            netconf_account_id=getattr(device, "netconf_account_id", None),
        )

    @staticmethod
    def _resolve_effective_category_name(
        device: NetworkDevice, category_name: str
    ) -> str:
        requested_name = str(category_name or "").strip()
        if requested_name:
            return requested_name
        return str(getattr(getattr(device, "category", None), "name", "") or "").strip()

    @staticmethod
    def _resolve_probe_skip_reason(device: NetworkDevice, collection_type: str) -> str:
        if collection_type in {"netconf_capability", "vxlan_capability"}:
            if not (device.netconf_enable == "account" and device.netconf_account):
                return "missing_netconf_account"
        if collection_type == "cli_output_capability":
            if not (device.ssh_enable == "account" and device.ssh_account):
                return "missing_ssh_account"
        return ""

    @classmethod
    def discover_device_capabilities(
        cls,
        device: NetworkDevice,
        *,
        category_name: str = "",
        collection_type: str = "",
        collection_types: Optional[List[str]] = None,
        rebind: bool = True,
    ) -> Dict[str, object]:
        device_for_matching = cls._build_category_hint_device(device, category_name)
        initial_capabilities = cls.build_capabilities(device_for_matching)
        profile = cls.match_profile_for_device(device_for_matching)
        requested_types = cls._normalize_requested_capability_types(
            vendor_alias=getattr(
                profile,
                "vendor_alias",
                cls._normalize_vendor_alias(device_for_matching),
            ),
            collection_type=collection_type,
            collection_types=collection_types,
        )

        response = {
            "manage_ip": getattr(device, "manage_ip", ""),
            "serial_num": getattr(device, "serial_num", ""),
            "requested_collection_types": requested_types,
            "matched_profile_before": initial_capabilities.get("profile_code", ""),
            "matched_profile_after": initial_capabilities.get("profile_code", ""),
            "probe_summary": {
                "total": len(requested_types),
                "success": 0,
                "failed": 0,
                "skipped": 0,
            },
            "probes": [],
            "auto_bind_result": None,
            "capabilities": initial_capabilities,
        }

        if not profile:
            response["status"] = "skipped"
            response["reason"] = "profile_not_matched"
            return response

        plan = cls.ensure_default_plan_for_profile(profile)
        connection_policy = cls.build_discovery_connection_policy(device)

        for current_type in requested_types:
            sub_plan = plan.collect_plans.filter(collection_type=current_type).first()
            if not sub_plan:
                response["probe_summary"]["skipped"] += 1
                response["probes"].append(
                    {
                        "collection_type": current_type,
                        "status": "skipped",
                        "reason": "sub_plan_not_configured",
                    }
                )
                continue

            skip_reason = cls._resolve_probe_skip_reason(device, current_type)
            if skip_reason:
                response["probe_summary"]["skipped"] += 1
                response["probes"].append(
                    {
                        "collection_type": current_type,
                        "status": "skipped",
                        "reason": skip_reason,
                    }
                )
                continue

            result = DeviceCollectionService.execute_both_collection_local(
                sub_plan,
                device,
                connection_policy=connection_policy,
            )
            if result.get("success"):
                response["probe_summary"]["success"] += 1
                response["probes"].append(
                    {
                        "collection_type": current_type,
                        "status": "success",
                        "message": result.get("message", ""),
                        "execute_time": result.get("execute_time", ""),
                    }
                )
                continue

            response["probe_summary"]["failed"] += 1
            cls.record_capability_probe_failure(
                device_info={
                    "manage_ip": getattr(device, "manage_ip", ""),
                    "serial_num": getattr(device, "serial_num", ""),
                },
                collection_type=current_type,
                error=result.get("error", ""),
                rebind_on_failure=False,
            )
            response["probes"].append(
                {
                    "collection_type": current_type,
                    "status": "failed",
                    "error": result.get("error", ""),
                }
            )

        if rebind:
            response["auto_bind_result"] = cls.auto_bind_devices([device])

        refreshed_capabilities = cls.build_capabilities(device_for_matching)
        response["matched_profile_after"] = refreshed_capabilities.get(
            "profile_code", ""
        )
        response["capabilities"] = refreshed_capabilities
        response["status"] = "finished"
        return response

    @classmethod
    def _record_connectivity_probe_success(
        cls,
        *,
        device: NetworkDevice,
        collection_type: str,
        method: str,
    ) -> None:
        now = timezone.now().isoformat()
        cls.update_capability_facts(
            device_info={
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
                "vendor__alias": getattr(getattr(device, "vendor", None), "alias", ""),
            },
            capability_facts={
                "protocols": {
                    "netconf": bool(
                        getattr(device, "netconf_account_id", None)
                        or getattr(device, "netconf_account", None)
                    ),
                    "ssh": bool(
                        getattr(device, "ssh_account_id", None)
                        or getattr(device, "ssh_account", None)
                    ),
                },
                "probes": {
                    collection_type: {
                        "ran_success": True,
                        "probe_mode": "connectivity",
                        "connection_verified": True,
                        "verified_at": now,
                        "verified_method": method,
                    }
                },
            },
            resolve_profile=False,
        )

    @classmethod
    def _probe_device_connectivity(
        cls,
        device: NetworkDevice,
        *,
        collection_type: str,
        connection_policy: Optional[Dict[str, int]] = None,
    ) -> Dict[str, str]:
        skip_reason = cls._resolve_probe_skip_reason(device, collection_type)
        if skip_reason:
            return {
                "collection_type": collection_type,
                "status": "skipped",
                "reason": skip_reason,
                "probe_mode": "connectivity",
            }

        device_info = DeviceCollectionService._build_device_info_for_local(
            device,
            connection_policy=connection_policy or {},
        )
        probe_method = (
            "netconf" if collection_type == "netconf_capability" else "netmiko"
        )
        try:
            with DeviceConnectionManager(
                device.manage_ip, device_info
            ) as connection_manager:
                if collection_type == "netconf_capability":
                    connection_manager.get_netconf_connection()
                    success_message = "NETCONF连接验证成功"
                elif collection_type == "cli_output_capability":
                    connection_manager.get_netmiko_connection()
                    success_message = "SSH连接验证成功"
                else:
                    raise ValueError(f"不支持的连通性探测类型: {collection_type}")
            cls._record_connectivity_probe_success(
                device=device,
                collection_type=collection_type,
                method=probe_method,
            )
            return {
                "collection_type": collection_type,
                "status": "success",
                "message": success_message,
                "probe_mode": "connectivity",
            }
        except Exception as exc:
            cls.record_capability_probe_failure(
                device_info={
                    "manage_ip": getattr(device, "manage_ip", ""),
                    "serial_num": getattr(device, "serial_num", ""),
                },
                collection_type=collection_type,
                error=str(exc),
                rebind_on_failure=False,
            )
            return {
                "collection_type": collection_type,
                "status": "failed",
                "error": str(exc),
                "probe_mode": "connectivity",
            }

    @classmethod
    def _list_candidate_plans_for_device(
        cls,
        device: NetworkDevice,
        *,
        category_name: str,
    ) -> List[DeviceCollectionPlans]:
        vendor_value = (
            getattr(getattr(device, "vendor", None), "alias", "")
            or getattr(getattr(device, "vendor", None), "name", "")
            or ""
        )
        vendor_variants = DeviceCollectionPlans.resolve_vendor_variants(vendor_value)
        device_type_variants = DeviceCollectionPlans.resolve_device_type_variants(
            category_name
        )
        if not vendor_variants or not device_type_variants:
            return []
        return list(
            DeviceCollectionPlans.objects.filter(
                is_active=True,
                vendor__in=vendor_variants,
                device_type__in=device_type_variants,
            ).order_by("-is_default", "-generated_by_system", "name", "id")
        )

    @staticmethod
    def _plan_protocol_match_score(
        plan: DeviceCollectionPlans, protocol_hint: str
    ) -> tuple:
        profile_text = str(getattr(plan, "profile_code", "") or "").lower()
        name_text = str(getattr(plan, "name", "") or "").lower()
        description_text = str(getattr(plan, "description", "") or "").lower()
        haystack = " ".join(filter(None, [profile_text, name_text, description_text]))
        builtin_profile_codes = {
            str(profile.code or "").strip()
            for profile in PlatformProfileService.ensure_builtin_profiles()
        }
        has_builtin_profile = (
            str(getattr(plan, "profile_code", "") or "").strip()
            in builtin_profile_codes
        )
        if protocol_hint == "netconf":
            keywords = ("netconf",)
            method_order = {
                DeviceCollectionPlans.COLLECTION_METHOD_NETCONF: 2,
                DeviceCollectionPlans.COLLECTION_METHOD_BOTH: 1,
                DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO: 0,
            }
        else:
            keywords = ("cli", "netmiko")
            method_order = {
                DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO: 2,
                DeviceCollectionPlans.COLLECTION_METHOD_BOTH: 1,
                DeviceCollectionPlans.COLLECTION_METHOD_NETCONF: 0,
            }
        method_value = str(getattr(plan, "collection_method", "") or "").lower()
        return (
            1 if has_builtin_profile else 0,
            1 if any(keyword in profile_text for keyword in keywords) else 0,
            1 if any(keyword in name_text for keyword in keywords) else 0,
            1 if any(keyword in haystack for keyword in keywords) else 0,
            method_order.get(method_value, -1),
            1 if getattr(plan, "is_default", False) else 0,
            1 if getattr(plan, "generated_by_system", False) else 0,
            (
                1
                if getattr(plan, "plan_kind", "")
                == DeviceCollectionPlans.PLAN_KIND_TEMPLATE
                else 0
            ),
            -(getattr(plan, "id", 0) or 0),
        )

    @classmethod
    def _select_plan_for_protocol(
        cls,
        candidate_plans: List[DeviceCollectionPlans],
        *,
        protocol_hint: str,
    ) -> Optional[DeviceCollectionPlans]:
        if not candidate_plans:
            return None
        return sorted(
            candidate_plans,
            key=lambda item: cls._plan_protocol_match_score(item, protocol_hint),
            reverse=True,
        )[0]

    @classmethod
    def _filter_candidate_plans_by_protocol(
        cls,
        candidate_plans: List[DeviceCollectionPlans],
        *,
        protocol_hint: str,
    ) -> List[DeviceCollectionPlans]:
        filtered = []
        for plan in candidate_plans:
            method_value = str(getattr(plan, "collection_method", "") or "").lower()
            profile_text = str(getattr(plan, "profile_code", "") or "").lower()
            name_text = str(getattr(plan, "name", "") or "").lower()
            description_text = str(getattr(plan, "description", "") or "").lower()
            haystack = " ".join(
                filter(None, [profile_text, name_text, description_text])
            )
            if protocol_hint == "netconf":
                if (
                    method_value
                    in {
                        DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
                        DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
                    }
                    or "netconf" in haystack
                ):
                    filtered.append(plan)
            elif protocol_hint == "cli":
                if method_value in {
                    DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
                    DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
                } or any(keyword in haystack for keyword in ("cli", "netmiko")):
                    filtered.append(plan)
        return filtered

    @staticmethod
    def _plan_supports_collection_type(
        plan: DeviceCollectionPlans,
        *,
        collection_type: str,
    ) -> bool:
        enabled_types = list(getattr(plan, "enabled_collection_types", []) or [])
        if collection_type and collection_type not in enabled_types:
            return False
        sub_plan = plan.collect_plans.filter(collection_type=collection_type).first()
        if sub_plan is None:
            return False
        if collection_type == "netconf_capability":
            if not getattr(sub_plan, "netconf_enabled", False):
                return False
            if (
                hasattr(sub_plan, "xml_templates")
                and not sub_plan.xml_templates.exists()
            ):
                return False
        if collection_type == "cli_output_capability":
            if not getattr(sub_plan, "netmiko_enabled", False):
                return False
            if not getattr(sub_plan, "netmiko_method", ""):
                return False
        return True

    @classmethod
    def _probe_capability_with_plan(
        cls,
        device: NetworkDevice,
        *,
        plan: DeviceCollectionPlans,
        collection_type: str,
        connection_policy: Optional[Dict[str, int]] = None,
    ) -> Dict[str, str]:
        sub_plan = plan.collect_plans.filter(collection_type=collection_type).first()
        if not sub_plan:
            return {
                "collection_type": collection_type,
                "status": "skipped",
                "reason": "sub_plan_not_configured",
                "probe_mode": "capability",
                "plan_id": getattr(plan, "id", None),
                "plan_name": getattr(plan, "name", ""),
            }

        skip_reason = cls._resolve_probe_skip_reason(device, collection_type)
        if skip_reason:
            return {
                "collection_type": collection_type,
                "status": "skipped",
                "reason": skip_reason,
                "probe_mode": "capability",
                "plan_id": getattr(plan, "id", None),
                "plan_name": getattr(plan, "name", ""),
            }

        result = DeviceCollectionService.execute_both_collection_local(
            sub_plan,
            device,
            connection_policy=connection_policy or {},
        )
        if result.get("success"):
            return {
                "collection_type": collection_type,
                "status": "success",
                "message": result.get("message", ""),
                "execute_time": result.get("execute_time", ""),
                "probe_mode": "capability",
                "plan_id": getattr(plan, "id", None),
                "plan_name": getattr(plan, "name", ""),
            }

        cls.record_capability_probe_failure(
            device_info={
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
            },
            collection_type=collection_type,
            error=result.get("error", ""),
            rebind_on_failure=False,
        )
        return {
            "collection_type": collection_type,
            "status": "failed",
            "error": result.get("error", ""),
            "probe_mode": "capability",
            "plan_id": getattr(plan, "id", None),
            "plan_name": getattr(plan, "name", ""),
        }

    @classmethod
    def _resolve_profiles_for_plans(
        cls,
        candidate_plans: List[DeviceCollectionPlans],
    ) -> List[PlatformProfile]:
        profiles_by_code = {
            profile.code: profile for profile in cls.ensure_builtin_profiles()
        }
        resolved = []
        for plan in candidate_plans:
            profile_code = str(getattr(plan, "profile_code", "") or "").strip()
            profile = profiles_by_code.get(profile_code)
            if profile and profile not in resolved:
                resolved.append(profile)
        return resolved

    @classmethod
    def _select_plan_for_profile_code(
        cls,
        candidate_plans: List[DeviceCollectionPlans],
        *,
        profile_code: str,
        protocol_hint: str,
    ) -> Optional[DeviceCollectionPlans]:
        filtered = [
            plan
            for plan in candidate_plans
            if str(getattr(plan, "profile_code", "") or "").strip()
            == str(profile_code or "").strip()
        ]
        if not filtered:
            return None
        return cls._select_plan_for_protocol(
            filtered,
            protocol_hint=protocol_hint,
        )

    @classmethod
    def _sync_discovery_state_profile_code(
        cls,
        *,
        device: NetworkDevice,
        profile_code: str,
    ) -> None:
        if not getattr(device, "serial_num", ""):
            return
        existing_state = DeviceDiscoveryState.objects.filter(
            device_serial_num=device.serial_num
        ).first()
        capability_facts = getattr(existing_state, "capability_facts", {}) or {}
        DeviceDiscoveryState.objects.update_or_create(
            device_serial_num=device.serial_num,
            defaults={
                "manage_ip": device.manage_ip,
                "profile_code": profile_code,
                "capability_facts": capability_facts,
                "last_discovered_at": timezone.now(),
                "last_discovery_status": "success",
                "last_discovery_error": "",
            },
        )

    @classmethod
    def _retire_stale_auto_bindings(
        cls,
        device: NetworkDevice,
        target_plan: DeviceCollectionPlans,
    ) -> int:
        queryset = PlansToDevice.objects.filter(
            binding_source=PlansToDevice.BINDING_SOURCE_AUTO,
            is_active=True,
        ).exclude(plan=target_plan)

        if getattr(device, "serial_num", ""):
            queryset = queryset.filter(device_serial_num=device.serial_num)
        else:
            queryset = queryset.filter(manage_ip=device.manage_ip)

        return queryset.update(is_active=False)

    @staticmethod
    def template_exists(template_name: str) -> bool:
        if not template_name:
            return False
        return (TEMPLATE_BASE_DIR / template_name).exists()

    @classmethod
    def template_is_placeholder(cls, template_name: str) -> bool:
        if not template_name:
            return False
        if template_name in cls._template_placeholder_cache:
            return cls._template_placeholder_cache[template_name]
        template_path = TEMPLATE_BASE_DIR / template_name
        if not template_path.exists():
            cls._template_placeholder_cache[template_name] = False
            return False
        try:
            content = template_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            cls._template_placeholder_cache[template_name] = False
            return False
        is_placeholder = any(
            marker in content for marker in PLACEHOLDER_TEMPLATE_MARKERS
        )
        cls._template_placeholder_cache[template_name] = is_placeholder
        return is_placeholder

    @staticmethod
    def resolve_plan_collection_method(profile: PlatformProfile) -> str:
        return PROFILE_PLAN_METHOD_DEFAULTS.get(
            profile.code,
            DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
        )

    @staticmethod
    def ensure_builtin_profiles() -> List[PlatformProfile]:
        profiles = []
        for item in BUILTIN_PLATFORM_PROFILES:
            defaults = {
                "vendor_alias": item["vendor_alias"],
                "category": item["category"],
                "series_patterns": item["series_patterns"],
                "os_family": item["os_family"],
                "version_patterns": item["version_patterns"],
                "preferred_methods": item["preferred_methods"],
                "fallback_methods": item["fallback_methods"],
                "supported_collection_types": item["supported_collection_types"],
                "default_plan_name": item["default_plan_name"],
                "is_active": True,
            }
            profile, created = PlatformProfile.objects.get_or_create(
                code=item["code"],
                defaults=defaults,
            )
            if not created:
                changed = False
                for key, value in defaults.items():
                    if getattr(profile, key) != value:
                        setattr(profile, key, value)
                        changed = True
                if changed:
                    profile.save(update_fields=list(defaults.keys()) + ["updated_at"])
            profiles.append(profile)
        return profiles

    @staticmethod
    def _string_value(value) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def normalize_device_category(value: str) -> str:
        text = (value or "").strip()
        return DEVICE_CATEGORY_ALIASES.get(text.lower(), text.lower())

    @classmethod
    def _get_capability_collection(cls, collection_type: str) -> MongoOps:
        if collection_type not in cls._capability_collection_cache:
            cls._capability_collection_cache[collection_type] = MongoOps(
                db="Automation",
                coll=build_plan_collection_name(collection_type),
            )
        return cls._capability_collection_cache[collection_type]

    @classmethod
    def load_device_capability_facts(cls, device: NetworkDevice) -> Dict[str, object]:
        state = None
        if getattr(device, "serial_num", ""):
            state = DeviceDiscoveryState.objects.filter(
                device_serial_num=device.serial_num
            ).first()
        if state is None and getattr(device, "manage_ip", ""):
            state = DeviceDiscoveryState.objects.filter(
                manage_ip=device.manage_ip
            ).first()

        if (
            state
            and isinstance(getattr(state, "capability_facts", None), dict)
            and state.capability_facts
        ):
            return state.capability_facts

        protocol_facts = {
            "netconf": bool(
                getattr(device, "netconf_account_id", None)
                or getattr(device, "netconf_account", None)
            ),
            "ssh": bool(
                getattr(device, "ssh_account_id", None)
                or getattr(device, "ssh_account", None)
            ),
        }
        probes: Dict[str, Dict[str, object]] = {}

        try:
            vxlan_row = (
                cls._get_capability_collection("vxlan_capability").coll.find_one(
                    {"hostip": getattr(device, "manage_ip", "")},
                    sort=[("execute_time", -1)],
                )
            ) or {}
        except Exception:
            vxlan_row = {}

        if vxlan_row:
            probes["vxlan_capability"] = {
                "ran_success": True,
                "has_bd": bool(vxlan_row.get("has_bd")),
                "has_vxlan_vni": bool(vxlan_row.get("has_vxlan_vni")),
                "has_nve": bool(vxlan_row.get("has_nve")),
                "has_evpn_bgp": bool(vxlan_row.get("has_evpn_bgp")),
                "evidence": list(vxlan_row.get("evidence") or []),
                "vrfs": list(vxlan_row.get("vrfs") or []),
                "execute_time": vxlan_row.get("execute_time", ""),
            }

        try:
            netconf_row = (
                cls._get_capability_collection("netconf_capability").coll.find_one(
                    {"hostip": getattr(device, "manage_ip", "")},
                    sort=[("execute_time", -1)],
                )
            ) or {}
        except Exception:
            netconf_row = {}

        if netconf_row:
            probes["netconf_capability"] = {
                "ran_success": True,
                "schema_count": int(netconf_row.get("schema_count") or 0),
                "openconfig_schema_count": int(
                    netconf_row.get("openconfig_schema_count") or 0
                ),
                "has_bgp_schema": bool(netconf_row.get("has_bgp_schema")),
                "has_l2vpn_schema": bool(netconf_row.get("has_l2vpn_schema")),
                "has_ifmgr_schema": bool(netconf_row.get("has_ifmgr_schema")),
                "has_telemetry_schema": bool(netconf_row.get("has_telemetry_schema")),
                "schema_samples": list(netconf_row.get("schema_samples") or []),
                "execute_time": netconf_row.get("execute_time", ""),
            }

        try:
            cli_row = (
                cls._get_capability_collection("cli_output_capability").coll.find_one(
                    {"hostip": getattr(device, "manage_ip", "")},
                    sort=[("execute_time", -1)],
                )
            ) or {}
        except Exception:
            cli_row = {}

        if cli_row:
            probes["cli_output_capability"] = {
                "ran_success": True,
                "supports_irf_cli": bool(cli_row.get("supports_irf_cli")),
                "command_unrecognized": bool(cli_row.get("command_unrecognized")),
                "has_irf_members": bool(cli_row.get("has_irf_members")),
                "evidence": list(cli_row.get("evidence") or []),
                "execute_time": cli_row.get("execute_time", ""),
            }

        facts = {
            "protocols": protocol_facts,
            "probes": probes,
        }
        cls.update_capability_facts(
            device_info={
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
                "vendor__alias": getattr(getattr(device, "vendor", None), "alias", ""),
            },
            capability_facts=facts,
            resolve_profile=False,
        )
        return facts

    @classmethod
    def _normalize_capability_record(
        cls, record: Dict[str, object]
    ) -> Dict[str, object]:
        normalized = {}
        for key, value in (record or {}).items():
            if key in {"_id"}:
                continue
            if hasattr(value, "isoformat"):
                normalized[key] = value.isoformat()
            else:
                normalized[key] = value
        return normalized

    @classmethod
    def update_capability_facts(
        cls,
        device_info: Dict[str, object],
        collection_type: str = "",
        processed_data: Optional[List[Dict[str, object]]] = None,
        capability_facts: Optional[Dict[str, object]] = None,
        resolve_profile: bool = True,
    ) -> None:
        manage_ip = str(device_info.get("manage_ip") or "")
        serial_num = str(device_info.get("serial_num") or "")
        device = None
        if serial_num:
            device = NetworkDevice.objects.filter(serial_num=serial_num).first()
        if device is None and manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
        if device is None:
            return

        if capability_facts is None:
            if collection_type not in {
                "vxlan_capability",
                "netconf_capability",
                "cli_output_capability",
            }:
                return
            record = cls._normalize_capability_record((processed_data or [{}])[0] or {})
            capability_facts = {
                "protocols": {
                    "netconf": bool(
                        getattr(device, "netconf_account_id", None)
                        or getattr(device, "netconf_account", None)
                    ),
                    "ssh": bool(
                        getattr(device, "ssh_account_id", None)
                        or getattr(device, "ssh_account", None)
                    ),
                },
                "probes": {
                    collection_type: {
                        "ran_success": True,
                        **record,
                    }
                },
            }
        else:
            capability_facts = dict(capability_facts or {})

        existing_state = None
        if device.serial_num:
            existing_state = DeviceDiscoveryState.objects.filter(
                device_serial_num=device.serial_num
            ).first()
        if existing_state is None and device.manage_ip:
            existing_state = DeviceDiscoveryState.objects.filter(
                manage_ip=device.manage_ip
            ).first()

        capability_facts = cls._merge_capability_facts(
            getattr(existing_state, "capability_facts", {}) or {},
            capability_facts,
        )

        profile_code = getattr(existing_state, "profile_code", "") or str(
            device_info.get("platform_profile_code") or ""
        )
        if not profile_code and resolve_profile:
            profile = cls.match_profile_for_device(device)
            profile_code = profile.code if profile else ""

        state_defaults = {
            "manage_ip": device.manage_ip,
            "profile_code": profile_code,
            "capability_facts": capability_facts,
            "last_discovered_at": timezone.now(),
            "last_discovery_status": "success",
            "last_discovery_error": "",
        }
        if device.serial_num:
            DeviceDiscoveryState.objects.update_or_create(
                device_serial_num=device.serial_num,
                defaults=state_defaults,
            )

    @staticmethod
    def _merge_capability_facts(
        existing_facts: Optional[Dict[str, object]],
        incoming_facts: Optional[Dict[str, object]],
    ) -> Dict[str, object]:
        merged = dict(existing_facts or {})
        for top_level_key, top_level_value in (incoming_facts or {}).items():
            if isinstance(top_level_value, dict) and isinstance(
                merged.get(top_level_key), dict
            ):
                section = dict(merged.get(top_level_key) or {})
                for nested_key, nested_value in top_level_value.items():
                    if isinstance(nested_value, dict) and isinstance(
                        section.get(nested_key), dict
                    ):
                        nested_section = dict(section.get(nested_key) or {})
                        nested_section.update(nested_value)
                        section[nested_key] = nested_section
                    else:
                        section[nested_key] = nested_value
                merged[top_level_key] = section
            else:
                merged[top_level_key] = top_level_value
        return merged

    @classmethod
    def _score_profile_by_capabilities(
        cls,
        profile: PlatformProfile,
        capability_facts: Dict[str, object],
    ) -> tuple:
        requirements = PROFILE_CAPABILITY_REQUIREMENTS.get(profile.code, {})
        protocol_facts = (capability_facts or {}).get("protocols", {}) or {}
        probes = (capability_facts or {}).get("probes", {}) or {}
        required_protocols = requirements.get("required_protocols", {}) or {}
        preferred_probes = requirements.get("preferred_successful_probes", []) or []
        preferred_failed_probes = requirements.get("preferred_failed_probes", []) or []
        disallowed_failed_probes = (
            requirements.get("disallowed_failed_probes", []) or []
        )
        preferred_probe_flags = requirements.get("preferred_probe_flags", {}) or {}
        preferred_probe_min_values = (
            requirements.get("preferred_probe_min_values", {}) or {}
        )
        preferred_identity_patterns = (
            requirements.get("preferred_identity_patterns", {}) or {}
        )
        identity_facts = (capability_facts or {}).get("identity", {}) or {}
        protocol_match_count = sum(
            1
            for key, required in required_protocols.items()
            if bool(protocol_facts.get(key)) == bool(required)
        )
        successful_probe_count = 0
        failed_probe_count = 0
        disallowed_failed_probe_count = 0
        feature_hit_count = 0
        threshold_hit_count = 0
        identity_hit_count = 0

        for probe_name in preferred_probes:
            probe_payload = probes.get(probe_name, {}) or {}
            if probe_payload.get("ran_success"):
                successful_probe_count += 1
                feature_hit_count += sum(
                    1
                    for key in preferred_probe_flags.get(probe_name, [])
                    if probe_payload.get(key)
                )
                threshold_hit_count += sum(
                    1
                    for key, min_value in preferred_probe_min_values.get(
                        probe_name, {}
                    ).items()
                    if float(probe_payload.get(key) or 0) >= float(min_value)
                )

        for probe_name in preferred_failed_probes:
            probe_payload = probes.get(probe_name, {}) or {}
            if probe_payload and probe_payload.get("ran_success") is False:
                failed_probe_count += 1

        for probe_name in disallowed_failed_probes:
            probe_payload = probes.get(probe_name, {}) or {}
            if probe_payload and probe_payload.get("ran_success") is False:
                disallowed_failed_probe_count += 1

        for identity_key, patterns in preferred_identity_patterns.items():
            if cls._match_patterns(
                str(identity_facts.get(identity_key) or ""), patterns
            ):
                identity_hit_count += 1

        return (
            protocol_match_count,
            1 if successful_probe_count else 0,
            successful_probe_count,
            identity_hit_count,
            feature_hit_count,
            threshold_hit_count,
            failed_probe_count,
            -disallowed_failed_probe_count,
        )

    @staticmethod
    def _match_patterns(value: str, patterns: List[str]) -> bool:
        if not patterns:
            return True
        return any(
            re.search(pattern, value or "", re.IGNORECASE) for pattern in patterns
        )

    @classmethod
    def match_profile_for_device(
        cls, device: NetworkDevice, profiles: Optional[List[PlatformProfile]] = None
    ) -> Optional[PlatformProfile]:
        profiles = profiles or cls.ensure_builtin_profiles()
        vendor_alias = getattr(getattr(device, "vendor", None), "alias", "") or ""
        category_name = cls.normalize_device_category(
            getattr(getattr(device, "category", None), "name", "") or ""
        )
        model_name = getattr(getattr(device, "model", None), "name", "") or ""
        soft_version = cls._string_value(getattr(device, "soft_version", ""))
        device_name = cls._string_value(getattr(device, "name", ""))
        haystack = " ".join(filter(None, [model_name, device_name]))
        capability_facts = cls.load_device_capability_facts(device)
        candidates = []
        for index, profile in enumerate(profiles):
            if profile.vendor_alias != vendor_alias:
                continue
            if (
                profile.category
                and cls.normalize_device_category(profile.category) != category_name
            ):
                continue
            series_match = cls._match_patterns(haystack, profile.series_patterns)
            version_match = cls._match_patterns(soft_version, profile.version_patterns)
            capability_score = cls._score_profile_by_capabilities(
                profile, capability_facts
            )
            score = (
                1 if series_match and version_match else 0,
                1 if series_match else 0,
                1 if version_match else 0,
                capability_score[0],
                capability_score[1],
                capability_score[2],
                capability_score[3],
                capability_score[4],
                capability_score[5],
                capability_score[6],
                capability_score[7],
                -index,
            )
            candidates.append((score, profile))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    @classmethod
    def ensure_default_plan_for_profile(
        cls, profile: PlatformProfile
    ) -> DeviceCollectionPlans:
        expected_collection_method = cls.resolve_plan_collection_method(profile)
        normalized_vendor = DeviceCollectionPlans.normalize_vendor_value(
            profile.vendor_alias
        )
        normalized_device_type = DeviceCollectionPlans.normalize_device_type_value(
            profile.category
        )
        cls._adopt_legacy_default_plan_alias(profile)
        plan, _ = DeviceCollectionPlans.objects.get_or_create(
            name=profile.default_plan_name,
            defaults={
                "vendor": normalized_vendor,
                "device_type": normalized_device_type,
                "description": f"系统内置默认方案: {profile.code}",
                "is_active": True,
                "profile_code": profile.code,
                "plan_kind": DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
                "generated_by_system": True,
                "version": 1,
                "is_default": True,
                "enabled_collection_types": profile.supported_collection_types or [],
                "collection_method": expected_collection_method,
            },
        )

        updated_fields = []
        if plan.vendor != normalized_vendor:
            plan.vendor = normalized_vendor
            updated_fields.append("vendor")
        if plan.device_type != normalized_device_type:
            plan.device_type = normalized_device_type
            updated_fields.append("device_type")
        if plan.profile_code != profile.code:
            plan.profile_code = profile.code
            updated_fields.append("profile_code")
        if plan.plan_kind != DeviceCollectionPlans.PLAN_KIND_TEMPLATE:
            plan.plan_kind = DeviceCollectionPlans.PLAN_KIND_TEMPLATE
            updated_fields.append("plan_kind")
        if not plan.generated_by_system:
            plan.generated_by_system = True
            updated_fields.append("generated_by_system")
        if not plan.is_default:
            plan.is_default = True
            updated_fields.append("is_default")
        expected_enabled_types = profile.supported_collection_types or []
        if plan.enabled_collection_types != expected_enabled_types:
            plan.enabled_collection_types = expected_enabled_types
            updated_fields.append("enabled_collection_types")
        if plan.collection_method != expected_collection_method:
            plan.collection_method = expected_collection_method
            updated_fields.append("collection_method")
        if updated_fields:
            plan.save(update_fields=updated_fields + ["updated_at"])

        DeviceCollectionService.ensure_default_sub_plans(plan)
        cls.apply_profile_defaults(plan, profile)
        cls._retire_legacy_default_plan_aliases(profile, plan)
        return plan

    @classmethod
    def bind_device_to_plan(
        cls,
        *,
        device: NetworkDevice,
        plan: DeviceCollectionPlans,
        profile_code: str = "",
        binding_source: str = PlansToDevice.BINDING_SOURCE_AUTO,
    ) -> Dict[str, object]:
        now = timezone.now()
        resolved_profile_code = str(
            profile_code or getattr(plan, "profile_code", "") or ""
        )
        defaults = {
            "manage_ip": device.manage_ip,
            "profile_code": resolved_profile_code,
            "binding_source": binding_source,
            "is_active": True,
            "use_local": True,
            "execute_node": "",
            "last_bound_at": now,
        }
        if getattr(device, "serial_num", ""):
            relation = PlansToDevice.objects.filter(
                device_serial_num=device.serial_num,
                plan=plan,
            ).first()
        else:
            relation = PlansToDevice.objects.filter(
                device_serial_num="",
                manage_ip=device.manage_ip,
                plan=plan,
            ).first()

        created_flag = False
        if relation is None:
            relation = PlansToDevice.objects.create(
                device_serial_num=getattr(device, "serial_num", "") or "",
                plan=plan,
                **defaults,
            )
            created_flag = True

        if created_flag:
            status = "created"
        else:
            status = "updated"
            changed = False
            for key, value in defaults.items():
                if getattr(relation, key) != value:
                    setattr(relation, key, value)
                    changed = True
            if relation.manage_ip != device.manage_ip:
                relation.manage_ip = device.manage_ip
                changed = True
            if changed:
                relation.save()
            else:
                status = "skipped"

        retired_count = 0
        if binding_source == PlansToDevice.BINDING_SOURCE_AUTO:
            retired_count = cls._retire_stale_auto_bindings(
                device=device,
                target_plan=plan,
            )

        return {
            "manage_ip": device.manage_ip,
            "serial_num": device.serial_num,
            "profile_code": resolved_profile_code,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "status": status,
            "retired_auto_bindings": retired_count,
        }

    @classmethod
    def _adopt_legacy_default_plan_alias(
        cls, profile: PlatformProfile
    ) -> Optional[DeviceCollectionPlans]:
        alias_names = PROFILE_LEGACY_PLAN_NAME_ALIASES.get(profile.code, [])
        if not alias_names:
            return None

        if DeviceCollectionPlans.objects.filter(
            name=profile.default_plan_name
        ).exists():
            return None

        alias_plan = (
            DeviceCollectionPlans.objects.filter(name__in=alias_names)
            .order_by("id")
            .first()
        )
        if alias_plan is None:
            return None

        alias_plan.name = profile.default_plan_name
        alias_plan.save(update_fields=["name", "updated_at"])
        return alias_plan

    @classmethod
    def _retire_legacy_default_plan_aliases(
        cls, profile: PlatformProfile, active_plan: DeviceCollectionPlans
    ) -> None:
        alias_names = PROFILE_LEGACY_PLAN_NAME_ALIASES.get(profile.code, [])
        if not alias_names:
            return

        alias_plans = DeviceCollectionPlans.objects.filter(
            name__in=alias_names
        ).exclude(id=getattr(active_plan, "id", None))
        for alias_plan in alias_plans:
            if PlansToDevice.objects.filter(plan=alias_plan, is_active=True).exists():
                continue

            updated_fields = []
            if alias_plan.is_active:
                alias_plan.is_active = False
                updated_fields.append("is_active")
            if alias_plan.is_default:
                alias_plan.is_default = False
                updated_fields.append("is_default")
            if updated_fields:
                alias_plan.save(update_fields=updated_fields + ["updated_at"])

    @staticmethod
    def audit_plan_readiness(plan: DeviceCollectionPlans) -> List[Dict[str, str]]:
        blockers = []
        enabled_sub_plans = []
        for sub_plan in plan.collect_plans.all():
            if any(
                bool(getattr(sub_plan, field_name, False))
                for field_name in (
                    "netmiko_enabled",
                    "netconf_enabled",
                    "snmp_enabled",
                    "restconf_enabled",
                    "telemetry_enabled",
                )
            ):
                enabled_sub_plans.append(sub_plan)

        if not enabled_sub_plans:
            blockers.append(
                {
                    "code": "missing_enabled_sub_plans",
                    "message": "默认方案没有任何启用中的子方案",
                }
            )
            return blockers

        for sub_plan in enabled_sub_plans:
            collection_type = getattr(sub_plan, "collection_type", "")
            if getattr(sub_plan, "netmiko_enabled", False) and not getattr(
                sub_plan, "netmiko_method", ""
            ):
                blockers.append(
                    {
                        "code": "missing_netmiko_command",
                        "collection_type": collection_type,
                        "message": "Netmiko 子方案缺少执行命令",
                    }
                )
            if getattr(sub_plan, "netmiko_enabled", False):
                template_name = getattr(sub_plan, "textfsm_template", "")
                if sub_plan.collection_type in RAW_NETMIKO_COLLECTION_TYPES:
                    template_name = template_name or "__raw_netmiko__"
                if not template_name:
                    blockers.append(
                        {
                            "code": "missing_textfsm_template",
                            "collection_type": collection_type,
                            "message": "Netmiko 子方案缺少 TextFSM 模板",
                        }
                    )
                elif not PlatformProfileService.template_exists(template_name):
                    blockers.append(
                        {
                            "code": "missing_textfsm_template_file",
                            "collection_type": collection_type,
                            "message": f"TextFSM 模板文件不存在: {template_name}",
                        }
                    )
                elif PlatformProfileService.template_is_placeholder(template_name):
                    blockers.append(
                        {
                            "code": "placeholder_textfsm_template",
                            "collection_type": collection_type,
                            "message": f"TextFSM 模板仍为占位版本，解析能力未就绪: {template_name}",
                        }
                    )
            if getattr(sub_plan, "netconf_enabled", False):
                templates = []
                if hasattr(sub_plan, "xml_templates"):
                    templates = list(sub_plan.xml_templates.all())
                if not templates:
                    blockers.append(
                        {
                            "code": "missing_netconf_template",
                            "collection_type": collection_type,
                            "message": "NETCONF 子方案缺少 XML 模板",
                        }
                    )
            if getattr(sub_plan, "snmp_enabled", False) and not getattr(
                sub_plan, "snmp_oids", []
            ):
                blockers.append(
                    {
                        "code": "missing_snmp_oids",
                        "collection_type": collection_type,
                        "message": "SNMP 子方案缺少 OID 配置",
                    }
                )
            if getattr(sub_plan, "restconf_enabled", False) and not getattr(
                sub_plan, "restconf_endpoint", ""
            ):
                blockers.append(
                    {
                        "code": "missing_restconf_endpoint",
                        "collection_type": collection_type,
                        "message": "RESTCONF 子方案缺少端点配置",
                    }
                )
            if getattr(sub_plan, "telemetry_enabled", False) and not getattr(
                sub_plan, "telemetry_subscription_path", ""
            ):
                blockers.append(
                    {
                        "code": "missing_telemetry_path",
                        "collection_type": collection_type,
                        "message": "Telemetry 子方案缺少订阅路径",
                    }
                )
        return blockers

    @classmethod
    def audit_legacy_default_plan_aliases(
        cls,
        *,
        profile_codes: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        builtin_profiles = {
            str(profile.code or "").strip(): profile
            for profile in cls.ensure_builtin_profiles()
        }
        scoped_profile_codes = [
            profile_code
            for profile_code in PROFILE_LEGACY_PLAN_NAME_ALIASES.keys()
            if not profile_codes or profile_code in profile_codes
        ]
        summary = {
            "profiles_scanned": len(scoped_profile_codes),
            "alias_names_declared": sum(
                len(PROFILE_LEGACY_PLAN_NAME_ALIASES.get(profile_code, []))
                for profile_code in scoped_profile_codes
            ),
            "alias_plans_found": 0,
            "adoptable": 0,
            "retirable": 0,
            "blocked_by_active_bindings": 0,
            "readiness_blocked": 0,
            "non_builtin_profile_code": 0,
            "runtime_plan_kind": 0,
            "non_system_generated": 0,
            "inactive_alias": 0,
        }
        results = []

        for profile_code in scoped_profile_codes:
            profile = builtin_profiles.get(profile_code)
            alias_names = PROFILE_LEGACY_PLAN_NAME_ALIASES.get(profile_code, [])
            canonical_plan = None
            if profile is not None:
                canonical_plan = DeviceCollectionPlans.objects.filter(
                    name=profile.default_plan_name
                ).first()

            alias_plans = list(
                DeviceCollectionPlans.objects.filter(name__in=alias_names)
                .order_by("id")
                .prefetch_related("collect_plans__xml_templates")
            )
            for alias_plan in alias_plans:
                summary["alias_plans_found"] += 1
                readiness_blockers = cls.audit_plan_readiness(alias_plan)
                active_bindings = PlansToDevice.objects.filter(
                    plan=alias_plan, is_active=True
                ).count()
                total_bindings = PlansToDevice.objects.filter(plan=alias_plan).count()
                issue_codes = []
                if getattr(alias_plan, "profile_code", "") != profile_code:
                    issue_codes.append("legacy_profile_code_mismatch")
                    summary["non_builtin_profile_code"] += 1
                if (
                    getattr(alias_plan, "plan_kind", "")
                    != DeviceCollectionPlans.PLAN_KIND_TEMPLATE
                ):
                    issue_codes.append("legacy_runtime_plan_kind")
                    summary["runtime_plan_kind"] += 1
                if not getattr(alias_plan, "generated_by_system", False):
                    issue_codes.append("legacy_not_generated_by_system")
                    summary["non_system_generated"] += 1
                if not getattr(alias_plan, "is_active", False):
                    issue_codes.append("legacy_alias_inactive")
                    summary["inactive_alias"] += 1
                if readiness_blockers:
                    issue_codes.append("legacy_alias_not_ready")
                    summary["readiness_blocked"] += 1

                if canonical_plan is None:
                    recommended_action = "adopt_alias"
                    summary["adoptable"] += 1
                elif active_bindings:
                    recommended_action = "keep_alias_with_active_bindings"
                    summary["blocked_by_active_bindings"] += 1
                else:
                    recommended_action = "retire_alias"
                    summary["retirable"] += 1

                results.append(
                    {
                        "profile_code": profile_code,
                        "default_plan_name": getattr(profile, "default_plan_name", ""),
                        "alias_plan_id": getattr(alias_plan, "id", None),
                        "alias_plan_name": getattr(alias_plan, "name", ""),
                        "alias_plan_profile_code": getattr(
                            alias_plan, "profile_code", ""
                        ),
                        "alias_plan_kind": getattr(alias_plan, "plan_kind", ""),
                        "alias_generated_by_system": bool(
                            getattr(alias_plan, "generated_by_system", False)
                        ),
                        "alias_is_default": bool(
                            getattr(alias_plan, "is_default", False)
                        ),
                        "alias_is_active": bool(
                            getattr(alias_plan, "is_active", False)
                        ),
                        "canonical_plan_exists": canonical_plan is not None,
                        "canonical_plan_id": getattr(canonical_plan, "id", None),
                        "canonical_plan_name": getattr(canonical_plan, "name", ""),
                        "active_bindings": active_bindings,
                        "total_bindings": total_bindings,
                        "recommended_action": recommended_action,
                        "issues": issue_codes,
                        "readiness_blockers": readiness_blockers,
                    }
                )

        return {
            "summary": summary,
            "results": results,
        }

    @classmethod
    def audit_device_coverage(cls, devices) -> Dict[str, object]:
        profiles = cls.ensure_builtin_profiles()
        summary = {
            "total": 0,
            "ready": 0,
            "blocked": 0,
            "profile_not_matched": 0,
            "missing_default_plan": 0,
            "missing_binding": 0,
        }
        results = []

        for device in devices:
            summary["total"] += 1
            vendor_alias = getattr(getattr(device, "vendor", None), "alias", "") or ""
            model_name = getattr(getattr(device, "model", None), "name", "") or ""
            profile = cls.match_profile_for_device(device, profiles=profiles)
            item = {
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
                "vendor_alias": vendor_alias,
                "model_name": model_name,
                "profile_code": "",
                "plan_id": None,
                "plan_name": "",
                "binding_id": None,
                "use_local": None,
                "execute_node": "",
                "blockers": [],
            }
            if not profile:
                summary["blocked"] += 1
                summary["profile_not_matched"] += 1
                item["blockers"].append(
                    {"code": "profile_not_matched", "message": "设备未匹配到平台画像"}
                )
                results.append(item)
                continue

            item["profile_code"] = profile.code
            plan = (
                DeviceCollectionPlans.objects.filter(name=profile.default_plan_name)
                .prefetch_related("collect_plans", "collect_plans__xml_templates")
                .first()
            )
            if not plan:
                summary["blocked"] += 1
                summary["missing_default_plan"] += 1
                item["blockers"].append(
                    {"code": "missing_default_plan", "message": "画像默认方案不存在"}
                )
                results.append(item)
                continue

            item["plan_id"] = getattr(plan, "id", None)
            item["plan_name"] = getattr(plan, "name", "")

            bindings = list(
                PlansToDevice.objects.select_related("plan").filter(
                    device_serial_num=getattr(device, "serial_num", ""), is_active=True
                )
            )
            if not bindings and getattr(device, "manage_ip", ""):
                bindings = list(
                    PlansToDevice.objects.select_related("plan").filter(
                        manage_ip=getattr(device, "manage_ip", ""), is_active=True
                    )
                )

            binding = next(
                (
                    relation
                    for relation in bindings
                    if getattr(relation, "plan_id", None) == getattr(plan, "id", None)
                ),
                bindings[0] if bindings else None,
            )
            if binding is None:
                summary["blocked"] += 1
                summary["missing_binding"] += 1
                item["blockers"].append(
                    {"code": "missing_binding", "message": "设备未绑定到 PlansToDevice"}
                )
                item["blockers"].extend(cls.audit_plan_readiness(plan))
                results.append(item)
                continue

            item["binding_id"] = getattr(binding, "id", None)
            item["use_local"] = getattr(binding, "use_local", None)
            item["execute_node"] = getattr(binding, "execute_node", "") or ""
            if getattr(binding, "plan_id", None) != getattr(plan, "id", None):
                item["blockers"].append(
                    {
                        "code": "binding_plan_mismatch",
                        "message": "设备已绑定方案与画像默认方案不一致",
                    }
                )

            if getattr(binding, "use_local", True):
                plan_blockers = cls.audit_plan_readiness(plan)
                item["blockers"].extend(plan_blockers)
                if any(
                    bool(getattr(sub_plan, "netmiko_enabled", False))
                    for sub_plan in plan.collect_plans.all()
                ):
                    if getattr(device, "ssh_enable", "") != "account" or not getattr(
                        device, "ssh_account", None
                    ):
                        item["blockers"].append(
                            {
                                "code": "missing_ssh_account",
                                "message": "本地 Netmiko 采集缺少 SSH 账号绑定",
                            }
                        )
                if any(
                    bool(getattr(sub_plan, "netconf_enabled", False))
                    for sub_plan in plan.collect_plans.all()
                ):
                    if getattr(
                        device, "netconf_enable", ""
                    ) != "account" or not getattr(device, "netconf_account", None):
                        item["blockers"].append(
                            {
                                "code": "missing_netconf_account",
                                "message": "本地 NETCONF 采集缺少 NETCONF 账号绑定",
                            }
                        )
            elif not item["execute_node"]:
                item["blockers"].append(
                    {
                        "code": "missing_execute_node",
                        "message": "南向驱动采集缺少执行节点",
                    }
                )

            if item["blockers"]:
                summary["blocked"] += 1
            else:
                summary["ready"] += 1
            results.append(item)

        return {"summary": summary, "results": results}

    @staticmethod
    def _get_cli_defaults(
        profile: PlatformProfile, collection_type: str
    ) -> Dict[str, str]:
        profile_defaults = PROFILE_NETMIKO_SUB_PLAN_DEFAULTS.get(profile.code, {})
        return profile_defaults.get(collection_type, {})

    @staticmethod
    def _get_netconf_defaults(
        profile: PlatformProfile, collection_type: str
    ) -> Dict[str, str]:
        profile_defaults = PROFILE_NETCONF_XML_TEMPLATE_DEFAULTS.get(profile.code, {})
        return profile_defaults.get(collection_type, {})

    @classmethod
    def apply_profile_defaults(
        cls, plan: DeviceCollectionPlans, profile: PlatformProfile
    ) -> None:
        identity_command = DEVICE_IDENTITY_NETMIKO_COMMANDS.get(
            profile.vendor_alias, ""
        )
        enabled_collection_types = set(
            DeviceCollectionService.get_enabled_collection_types(plan)
        )
        plan_method = getattr(
            plan, "collection_method", DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO
        )
        plan_allows_netmiko = plan_method in {
            DeviceCollectionPlans.COLLECTION_METHOD_NETMIKO,
            DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
        }
        plan_allows_netconf = plan_method in {
            DeviceCollectionPlans.COLLECTION_METHOD_NETCONF,
            DeviceCollectionPlans.COLLECTION_METHOD_BOTH,
        }
        for sub_plan in plan.collect_plans.all():
            preferred = (profile.preferred_methods or {}).get(
                sub_plan.collection_type, []
            )
            supported = sub_plan.collection_type in (
                profile.supported_collection_types or []
            )
            cli_defaults = cls._get_cli_defaults(profile, sub_plan.collection_type)
            netconf_defaults = cls._get_netconf_defaults(
                profile, sub_plan.collection_type
            )
            updated_fields = []
            profile_summary = (
                f"profile={profile.code}; supported={supported}; "
                f"preferred={','.join(preferred) if preferred else 'none'}"
            )
            if profile_summary not in (sub_plan.description or ""):
                sub_plan.description = profile_summary
                updated_fields.append("description")

            command = cli_defaults.get("command")
            template = cli_defaults.get("template", "")
            preferred_uses_netmiko = "netmiko" in preferred or not preferred

            if sub_plan.collection_type == "device_identity" and not command:
                command = identity_command

            if command and sub_plan.netmiko_method != command:
                sub_plan.netmiko_method = command
                updated_fields.append("netmiko_method")

            if template and sub_plan.textfsm_template != template:
                sub_plan.textfsm_template = template
                updated_fields.append("textfsm_template")

            desired_netmiko_enabled = (
                supported and preferred_uses_netmiko and bool(command)
            )
            if (
                not desired_netmiko_enabled
                and cli_defaults
                and "netmiko"
                in (profile.fallback_methods or {}).get(sub_plan.collection_type, [])
            ):
                desired_netmiko_enabled = bool(command)
            if (
                sub_plan.collection_type not in enabled_collection_types
                or not plan_allows_netmiko
            ):
                desired_netmiko_enabled = False

            if sub_plan.netmiko_enabled != desired_netmiko_enabled:
                sub_plan.netmiko_enabled = desired_netmiko_enabled
                updated_fields.append("netmiko_enabled")

            desired_netconf_enabled = (
                supported
                and "netconf" in preferred
                and bool(netconf_defaults.get("xml_template"))
            )
            if (
                sub_plan.collection_type not in enabled_collection_types
                or not plan_allows_netconf
            ):
                desired_netconf_enabled = False

            if sub_plan.netconf_enabled != desired_netconf_enabled:
                sub_plan.netconf_enabled = desired_netconf_enabled
                updated_fields.append("netconf_enabled")

            legacy_method = netconf_defaults.get("legacy_method", "")
            if legacy_method and sub_plan.netconf_path != legacy_method:
                sub_plan.netconf_path = legacy_method
                updated_fields.append("netconf_path")

            if updated_fields:
                sub_plan.save(update_fields=updated_fields + ["updated_at"])

            if desired_netconf_enabled and netconf_defaults:
                collect_method = netconf_defaults.get("collect_method", "get")
                xml_template = netconf_defaults.get("xml_template", "")
                description = netconf_defaults.get("description", "")
                if xml_template:
                    template_obj = sub_plan.xml_templates.filter(
                        collect_method=collect_method
                    ).first()
                    if template_obj is None:
                        NetconfXMLTemplate.objects.create(
                            collect_method=collect_method,
                            xml_template=xml_template,
                            description=description,
                            collection_plan=sub_plan,
                        )
                    else:
                        template_updates = []
                        if template_obj.xml_template != xml_template:
                            template_obj.xml_template = xml_template
                            template_updates.append("xml_template")
                        if template_obj.description != description:
                            template_obj.description = description
                            template_updates.append("description")
                        if template_updates:
                            template_obj.save(
                                update_fields=template_updates + ["updated_at"]
                            )

    @classmethod
    def auto_bind_devices(
        cls, devices, binding_source: str = PlansToDevice.BINDING_SOURCE_AUTO
    ) -> Dict[str, object]:
        profiles = cls.ensure_builtin_profiles()
        plan_cache: Dict[str, DeviceCollectionPlans] = {}
        created = 0
        updated = 0
        skipped = 0
        retired = 0
        results = []

        for device in devices:
            profile = cls.match_profile_for_device(device, profiles=profiles)
            if not profile:
                skipped += 1
                results.append(
                    {
                        "manage_ip": device.manage_ip,
                        "serial_num": device.serial_num,
                        "status": "skipped",
                        "reason": "profile_not_matched",
                    }
                )
                continue

            if profile.code not in plan_cache:
                plan_cache[profile.code] = cls.ensure_default_plan_for_profile(profile)
            plan = plan_cache[profile.code]
            bind_result = cls.bind_device_to_plan(
                device=device,
                plan=plan,
                profile_code=profile.code,
                binding_source=binding_source,
            )
            if bind_result["status"] == "created":
                created += 1
            elif bind_result["status"] == "updated":
                updated += 1
            else:
                skipped += 1
            retired += int(bind_result.get("retired_auto_bindings") or 0)
            results.append(bind_result)

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "retired": retired,
            "results": results,
        }

    @classmethod
    def auto_bind_device_by_connection_priority(
        cls,
        device: NetworkDevice,
        *,
        category_name: str = "",
    ) -> Dict[str, object]:
        device_for_matching = cls._build_category_hint_device(device, category_name)
        effective_category_name = cls._resolve_effective_category_name(
            device_for_matching, category_name
        )
        if not effective_category_name:
            raise ValueError("缺少必要参数: category_name")

        initial_capabilities = cls.build_capabilities(device_for_matching)
        candidate_plans = cls._list_candidate_plans_for_device(
            device,
            category_name=effective_category_name,
        )
        connection_policy = cls.build_discovery_connection_policy(device)
        requested_types = []
        if getattr(device, "netconf_enable", "") == "account" and getattr(
            device, "netconf_account", None
        ):
            requested_types.append("netconf_capability")
        if getattr(device, "ssh_enable", "") == "account" and getattr(
            device, "ssh_account", None
        ):
            requested_types.append("cli_output_capability")

        response = {
            "manage_ip": getattr(device, "manage_ip", ""),
            "serial_num": getattr(device, "serial_num", ""),
            "category_name": effective_category_name,
            "requested_collection_types": requested_types,
            "matched_profile_before": initial_capabilities.get("profile_code", ""),
            "matched_profile_after": initial_capabilities.get("profile_code", ""),
            "probe_summary": {
                "total": len(requested_types),
                "success": 0,
                "failed": 0,
                "skipped": 0,
            },
            "probes": [],
            "candidate_plans": [
                {
                    "id": plan.id,
                    "name": plan.name,
                    "profile_code": plan.profile_code,
                    "collection_method": plan.collection_method,
                }
                for plan in candidate_plans
            ],
            "selected_plan": None,
            "auto_bind_result": None,
            "capabilities": initial_capabilities,
        }

        if not requested_types:
            response["status"] = "skipped"
            response["reason"] = "missing_access_account"
            return response

        desired_protocol = ""
        capability_selected_profile_code = ""
        candidate_plans_for_netconf = cls._filter_candidate_plans_by_protocol(
            candidate_plans,
            protocol_hint="netconf",
        )
        if "netconf_capability" in requested_types:
            netconf_probe = cls._probe_device_connectivity(
                device,
                collection_type="netconf_capability",
                connection_policy=connection_policy,
            )
            response["probes"].append(netconf_probe)
            if netconf_probe["status"] == "success":
                response["probe_summary"]["success"] += 1
                capability_probe_candidates = [
                    plan
                    for plan in candidate_plans_for_netconf
                    if cls._plan_supports_collection_type(
                        plan, collection_type="netconf_capability"
                    )
                ]
                capability_probe_plan = cls._select_plan_for_protocol(
                    capability_probe_candidates or candidate_plans_for_netconf,
                    protocol_hint="netconf",
                )
                if capability_probe_plan is None:
                    response["probe_summary"]["skipped"] += 1
                    response["probes"].append(
                        {
                            "collection_type": "netconf_capability",
                            "status": "skipped",
                            "reason": (
                                "netconf_capability_plan_not_found"
                                if candidate_plans_for_netconf
                                else "candidate_plan_not_found"
                            ),
                            "probe_mode": "capability",
                        }
                    )
                else:
                    capability_probe = cls._probe_capability_with_plan(
                        device,
                        plan=capability_probe_plan,
                        collection_type="netconf_capability",
                        connection_policy=connection_policy,
                    )
                    response["probes"].append(capability_probe)
                    if capability_probe["status"] == "success":
                        response["probe_summary"]["success"] += 1
                        desired_protocol = "netconf"
                        candidate_profiles = cls._resolve_profiles_for_plans(
                            candidate_plans_for_netconf
                        )
                        if candidate_profiles:
                            matched_profile = cls.match_profile_for_device(
                                device_for_matching,
                                profiles=candidate_profiles,
                            )
                            if matched_profile:
                                capability_selected_profile_code = matched_profile.code
                    elif capability_probe["status"] == "failed":
                        response["probe_summary"]["failed"] += 1
                    else:
                        response["probe_summary"]["skipped"] += 1
            elif netconf_probe["status"] == "failed":
                response["probe_summary"]["failed"] += 1
            else:
                response["probe_summary"]["skipped"] += 1

        if desired_protocol == "netconf" and "cli_output_capability" in requested_types:
            response["probe_summary"]["skipped"] += 1
            response["probes"].append(
                {
                    "collection_type": "cli_output_capability",
                    "status": "skipped",
                    "reason": "netconf_preferred_plan_selected",
                    "probe_mode": "connectivity",
                }
            )
        elif "cli_output_capability" in requested_types:
            cli_probe = cls._probe_device_connectivity(
                device,
                collection_type="cli_output_capability",
                connection_policy=connection_policy,
            )
            response["probes"].append(cli_probe)
            if cli_probe["status"] == "success":
                response["probe_summary"]["success"] += 1
                desired_protocol = "cli"
            elif cli_probe["status"] == "failed":
                response["probe_summary"]["failed"] += 1
            else:
                response["probe_summary"]["skipped"] += 1

        if not desired_protocol:
            refreshed_capabilities = cls.build_capabilities(device_for_matching)
            response["matched_profile_after"] = refreshed_capabilities.get(
                "profile_code", ""
            )
            response["capabilities"] = refreshed_capabilities
            response["status"] = "skipped"
            response["reason"] = "no_protocol_connectivity"
            return response

        candidate_plans_for_protocol = cls._filter_candidate_plans_by_protocol(
            candidate_plans,
            protocol_hint=desired_protocol,
        )

        selected_plan = None
        if capability_selected_profile_code:
            selected_plan = cls._select_plan_for_profile_code(
                candidate_plans_for_protocol,
                profile_code=capability_selected_profile_code,
                protocol_hint=desired_protocol,
            )
        if selected_plan is None:
            selected_plan = cls._select_plan_for_protocol(
                candidate_plans_for_protocol,
                protocol_hint=desired_protocol,
            )
        if selected_plan is None:
            refreshed_capabilities = cls.build_capabilities(device_for_matching)
            response["matched_profile_after"] = refreshed_capabilities.get(
                "profile_code", ""
            )
            response["capabilities"] = refreshed_capabilities
            response["status"] = "skipped"
            response["reason"] = "candidate_plan_not_found"
            return response

        bind_result = cls.bind_device_to_plan(
            device=device,
            plan=selected_plan,
            profile_code=getattr(selected_plan, "profile_code", ""),
            binding_source=PlansToDevice.BINDING_SOURCE_AUTO,
        )
        cls._sync_discovery_state_profile_code(
            device=device,
            profile_code=str(getattr(selected_plan, "profile_code", "") or ""),
        )

        response["selected_plan"] = {
            "id": selected_plan.id,
            "name": selected_plan.name,
            "profile_code": selected_plan.profile_code,
            "collection_method": selected_plan.collection_method,
            "selection_reason": (
                f"capability_scored_{desired_protocol}_plan"
                if capability_selected_profile_code
                else f"preferred_{desired_protocol}_plan"
            ),
        }
        response["auto_bind_result"] = {
            "created": 1 if bind_result["status"] == "created" else 0,
            "updated": 1 if bind_result["status"] == "updated" else 0,
            "skipped": 1 if bind_result["status"] == "skipped" else 0,
            "retired": int(bind_result.get("retired_auto_bindings") or 0),
            "results": [bind_result],
        }
        refreshed_capabilities = cls.build_capabilities(device_for_matching)
        response["matched_profile_after"] = str(
            getattr(selected_plan, "profile_code", "") or ""
        )
        response["capabilities"] = refreshed_capabilities
        response["status"] = "finished"
        return response

    @classmethod
    def record_capability_probe_failure(
        cls,
        *,
        device_info: Dict[str, object],
        collection_type: str,
        error: str,
        rebind_on_failure: bool = False,
    ) -> Optional[Dict[str, object]]:
        if collection_type not in {
            "netconf_capability",
            "cli_output_capability",
            "vxlan_capability",
        }:
            return None

        manage_ip = str(device_info.get("manage_ip") or "")
        serial_num = str(device_info.get("serial_num") or "")
        device = None
        if serial_num:
            device = (
                NetworkDevice.objects.filter(serial_num=serial_num)
                .select_related(
                    "vendor", "category", "model", "ssh_account", "netconf_account"
                )
                .first()
            )
        if device is None and manage_ip:
            device = (
                NetworkDevice.objects.filter(manage_ip=manage_ip)
                .select_related(
                    "vendor", "category", "model", "ssh_account", "netconf_account"
                )
                .first()
            )
        if device is None:
            return None

        now = timezone.now()
        failure_facts = {
            "protocols": {
                "netconf": bool(
                    getattr(device, "netconf_account_id", None)
                    or getattr(device, "netconf_account", None)
                ),
                "ssh": bool(
                    getattr(device, "ssh_account_id", None)
                    or getattr(device, "ssh_account", None)
                ),
            },
            "probes": {
                collection_type: {
                    "ran_success": False,
                    "last_error": str(error or "")[:1000],
                    "failed_at": now.isoformat(),
                }
            },
        }

        existing_state = None
        if device.serial_num:
            existing_state = DeviceDiscoveryState.objects.filter(
                device_serial_num=device.serial_num
            ).first()
        if existing_state is None and device.manage_ip:
            existing_state = DeviceDiscoveryState.objects.filter(
                manage_ip=device.manage_ip
            ).first()

        existing_probe = (
            (getattr(existing_state, "capability_facts", {}) or {}).get("probes", {})
            or {}
        ).get(collection_type, {}) or {}
        preserved_probe_state = {
            "ran_success": bool(existing_probe.get("ran_success")),
            "connection_verified": bool(existing_probe.get("connection_verified")),
            "verified_at": str(existing_probe.get("verified_at") or ""),
            "verified_method": str(existing_probe.get("verified_method") or ""),
            "probe_mode": str(existing_probe.get("probe_mode") or ""),
        }

        capability_facts = cls._merge_capability_facts(
            getattr(existing_state, "capability_facts", {}) or {},
            failure_facts,
        )
        probe_state = (capability_facts.get("probes") or {}).get(collection_type) or {}
        if preserved_probe_state["ran_success"]:
            probe_state["ran_success"] = True
        if preserved_probe_state["connection_verified"]:
            probe_state["connection_verified"] = True
        if preserved_probe_state["verified_at"]:
            probe_state["verified_at"] = preserved_probe_state["verified_at"]
        if preserved_probe_state["verified_method"]:
            probe_state["verified_method"] = preserved_probe_state["verified_method"]
        if preserved_probe_state["probe_mode"]:
            probe_state["probe_mode"] = preserved_probe_state["probe_mode"]
        state_defaults = {
            "manage_ip": device.manage_ip,
            "profile_code": str(getattr(existing_state, "profile_code", "") or ""),
            "capability_facts": capability_facts,
            "last_discovered_at": now,
            "last_discovery_status": "failed",
            "last_discovery_error": str(error or "")[:1000],
        }
        DeviceDiscoveryState.objects.update_or_create(
            device_serial_num=device.serial_num,
            defaults=state_defaults,
        )

        if rebind_on_failure:
            return cls.auto_bind_devices([device])
        return None

    @classmethod
    def build_capabilities(cls, device: NetworkDevice) -> Dict[str, object]:
        profile = cls.match_profile_for_device(device)
        if not profile:
            return {
                "serial_num": device.serial_num,
                "manage_ip": device.manage_ip,
                "profile_code": "",
                "supported_collection_types": [],
                "preferred_methods": {},
                "fallback_methods": {},
                "bindings": [],
            }

        bindings = list(
            PlansToDevice.objects.filter(
                device_serial_num=device.serial_num, is_active=True
            )
            .select_related("plan")
            .values(
                "id",
                "plan_id",
                "plan__name",
                "use_local",
                "execute_node",
                "binding_source",
                "profile_code",
            )
        )
        capability_facts = cls.load_device_capability_facts(device)
        return {
            "serial_num": device.serial_num,
            "manage_ip": device.manage_ip,
            "profile_code": profile.code,
            "supported_collection_types": profile.supported_collection_types,
            "preferred_methods": profile.preferred_methods,
            "fallback_methods": profile.fallback_methods,
            "capability_facts": capability_facts,
            "bindings": [
                {
                    "id": item["id"],
                    "plan_id": item["plan_id"],
                    "plan_name": item["plan__name"],
                    "use_local": item["use_local"],
                    "execute_node": item["execute_node"],
                    "binding_source": item["binding_source"],
                    "profile_code": item["profile_code"],
                }
                for item in bindings
            ],
        }


class DeviceFactService:
    @staticmethod
    def _resolve_device(device_info: Dict[str, object]) -> Optional[NetworkDevice]:
        manage_ip = str(device_info.get("manage_ip") or "")
        serial_num = str(device_info.get("serial_num") or "")
        device = None
        if serial_num:
            device = NetworkDevice.objects.filter(serial_num=serial_num).first()
        if device is None and manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
        return device

    @staticmethod
    def _normalize_positive_int(value) -> Optional[int]:
        try:
            text = str(value).strip()
            if not text:
                return None
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ensure_vendor(vendor_alias: str) -> Optional[Vendor]:
        if not vendor_alias:
            return None
        vendor = Vendor.objects.filter(alias=vendor_alias).first()
        if vendor:
            return vendor
        return Vendor.objects.filter(name=vendor_alias).first()

    @classmethod
    def _ensure_model(
        cls, vendor: Optional[Vendor], model_name: str
    ) -> Optional[Model]:
        if not vendor or not model_name:
            return None
        model, _ = Model.objects.get_or_create(name=model_name, vendor=vendor)
        return model

    @classmethod
    def update_from_processed_data(
        cls,
        collection_type: str,
        device_info: Dict[str, object],
        processed_data: List[Dict[str, object]],
    ) -> None:
        if collection_type not in (
            "device_identity",
            "version",
            "board_status",
            "irf_status",
            "stack_status",
        ):
            return
        if not processed_data:
            return

        device = cls._resolve_device(device_info)
        if device is None:
            return

        if collection_type == "board_status":
            update_fields = []
            preferred_record = None
            for slot_type in ("slot", "chassis"):
                preferred_record = next(
                    (
                        item
                        for item in processed_data
                        if str(item.get("slot_type") or "").lower() == slot_type
                    ),
                    None,
                )
                if preferred_record:
                    break
            preferred_record = preferred_record or (processed_data[0] or {})

            serial_num = str(preferred_record.get("serial_num") or "").strip()
            slot_num = cls._normalize_positive_int(preferred_record.get("slot"))

            if serial_num and device.serial_num != serial_num:
                device.serial_num = serial_num
                update_fields.append("serial_num")
            if slot_num is not None and device.slot != slot_num:
                device.slot = slot_num
                update_fields.append("slot")

            if update_fields:
                device.save(update_fields=list(dict.fromkeys(update_fields)))
            return

        if collection_type in ("irf_status", "stack_status"):
            records = processed_data or []
            desired_ha_status = None
            if len(records) <= 1:
                desired_ha_status = 0
            else:
                current_slot = cls._normalize_positive_int(device.slot)
                current_chassis = cls._normalize_positive_int(device.chassis)
                match = None
                if current_slot is not None:
                    match = next(
                        (
                            item
                            for item in records
                            if cls._normalize_positive_int(item.get("member_id"))
                            == current_slot
                        ),
                        None,
                    )
                if match is None and current_chassis is not None:
                    match = next(
                        (
                            item
                            for item in records
                            if cls._normalize_positive_int(item.get("chassis_id"))
                            == current_chassis
                        ),
                        None,
                    )
                if match:
                    role = str(match.get("role") or "").strip().lower()
                    if role == "master":
                        desired_ha_status = 1
                    elif role in ("standby", "slave"):
                        desired_ha_status = 2

            if desired_ha_status is not None and device.ha_status != desired_ha_status:
                device.ha_status = desired_ha_status
                device.save(update_fields=["ha_status"])
            return

        record = processed_data[0] or {}
        update_fields = []

        discovered_name = (
            record.get("hostname")
            or record.get("device_name")
            or record.get("name")
            or device_info.get("name")
        )
        if discovered_name and device.name != discovered_name:
            device.name = discovered_name
            update_fields.append("name")

        vendor_alias = (
            record.get("vendor_alias")
            or device_info.get("vendor__alias")
            or getattr(getattr(device, "vendor", None), "alias", "")
        )
        vendor = cls._ensure_vendor(vendor_alias)
        if vendor and device.vendor_id != vendor.id:
            device.vendor = vendor
            update_fields.append("vendor")

        model_name = record.get("model_name") or record.get("model") or ""
        model = cls._ensure_model(vendor or device.vendor, model_name)
        if model and device.model_id != model.id:
            device.model = model
            update_fields.append("model")

        soft_version = record.get("soft_version") or record.get("version") or ""
        if soft_version and device.soft_version != soft_version:
            device.soft_version = soft_version
            update_fields.append("soft_version")

        patch_version = record.get("patch_version") or ""
        if patch_version and device.patch_version != patch_version:
            device.patch_version = patch_version
            update_fields.append("patch_version")

        if not device.serial_num and record.get("serial_num"):
            device.serial_num = record["serial_num"]
            update_fields.append("serial_num")

        profile_code = str(device_info.get("platform_profile_code") or "")
        if not profile_code:
            profile = PlatformProfileService.match_profile_for_device(device)
            profile_code = profile.code if profile else ""

        if update_fields:
            device.save(update_fields=list(dict.fromkeys(update_fields)))

        identity_facts = {
            "hostname": str(discovered_name or "").strip(),
            "platform_name": str(
                record.get("platform_name") or record.get("platform-name") or ""
            ).strip(),
            "product_name": str(
                record.get("product_name") or record.get("product-name") or ""
            ).strip(),
            "model_name": str(
                model_name or getattr(getattr(device, "model", None), "name", "") or ""
            ).strip(),
            "soft_version": str(
                soft_version or getattr(device, "soft_version", "") or ""
            ).strip(),
            "patch_version": str(
                patch_version or getattr(device, "patch_version", "") or ""
            ).strip(),
        }
        identity_facts = {key: value for key, value in identity_facts.items() if value}
        if identity_facts:
            PlatformProfileService.update_capability_facts(
                device_info={
                    "manage_ip": device.manage_ip,
                    "serial_num": device.serial_num,
                    "vendor__alias": getattr(
                        getattr(device, "vendor", None), "alias", ""
                    ),
                    "platform_profile_code": profile_code,
                },
                capability_facts={"identity": identity_facts},
                resolve_profile=False,
            )

        now = timezone.now()
        DeviceDiscoveryState.objects.update_or_create(
            device_serial_num=device.serial_num,
            defaults={
                "manage_ip": device.manage_ip,
                "profile_code": profile_code,
                "last_discovered_at": now,
                "last_discovery_status": "success",
                "last_discovery_error": "",
            },
        )

    @staticmethod
    def mark_discovery_failure(device_info: Dict[str, object], error: str) -> None:
        manage_ip = str(device_info.get("manage_ip") or "")
        serial_num = str(device_info.get("serial_num") or "")
        device = None
        if serial_num:
            device = NetworkDevice.objects.filter(serial_num=serial_num).first()
        if device is None and manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
        if device is None:
            return

        DeviceDiscoveryState.objects.update_or_create(
            device_serial_num=device.serial_num,
            defaults={
                "manage_ip": device.manage_ip,
                "profile_code": "",
                "last_discovered_at": timezone.now(),
                "last_discovery_status": "failed",
                "last_discovery_error": error or "",
            },
        )
