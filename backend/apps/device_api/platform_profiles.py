import re
from typing import Dict, List, Optional

from django.utils import timezone

from apps.asset.models import Category, Model, NetworkDevice, Vendor
from apps.device_api.fields_mapping import DEFAULT_COLLECTION_TYPES
from apps.device_api.models import (
    DeviceCollectionPlans,
    DeviceDiscoveryState,
    PlatformProfile,
    PlansToDevice,
)
from apps.device_api.services_new import DeviceCollectionService


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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-huawei-s-switch",
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-huawei-ce-switch",
    },
    {
        "code": "Huawei-USG",
        "vendor_alias": "Huawei",
        "category": "firewall",
        "series_patterns": [r"^USG\d+"],
        "os_family": "VRP",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["restconf", "netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {
            "arp": ["netmiko"],
        },
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-huawei-usg-firewall",
    },
    {
        "code": "Huawei-YunShan",
        "vendor_alias": "Huawei",
        "category": "switch",
        "series_patterns": [r"YunShan", r"CloudEngine.*AI"],
        "os_family": "YunShan OS",
        "version_patterns": [r".*"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "cpu_status": ["telemetry", "restconf"],
            "memory_status": ["telemetry", "restconf"],
            "interface_brief": ["restconf", "netmiko"],
            "ip_interface": ["restconf", "netmiko"],
        },
        "fallback_methods": {
            "cpu_status": ["netmiko"],
            "memory_status": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-huawei-yunshan-switch",
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
            "arp": ["netmiko"],
            "mac": ["netmiko"],
            "lldp": ["netmiko"],
            "interface_brief": ["netmiko"],
            "ip_interface": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-h3c-legacy-switch",
    },
    {
        "code": "H3C-modern-netconf",
        "vendor_alias": "H3C",
        "category": "switch",
        "series_patterns": [r".*"],
        "os_family": "Comware",
        "version_patterns": [r"7\.", r"Comware 7"],
        "preferred_methods": {
            "device_identity": ["netmiko"],
            "arp": ["netconf", "netmiko"],
            "mac": ["netconf", "netmiko"],
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
        "default_plan_name": "default-h3c-modern-switch",
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
            "fan_status": ["netmiko"],
            "power_status": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
            "session": ["netmiko"],
        },
        "fallback_methods": {},
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "supported_collection_types": DEFAULT_COLLECTION_TYPES,
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
        "device_identity": {"command": "display version", "template": "huawei_vrp_display_version.textfsm"},
        "arp": {"command": "display arp", "template": "huawei_vrp_display_arp.textfsm"},
        "lldp": {"command": "display lldp neighbor", "template": "huawei_usg_display_lldp_neighbor.textfsm"},
        "mac": {"command": "display mac-address", "template": "huawei_usg_display_mac-address.textfsm"},
    },
    "Huawei-YunShan": {
        "device_identity": {"command": "display version", "template": "huawei_vrp_display_version.textfsm"},
        "interface_brief": {"command": "display interface brief", "template": "huawei_vrp_display_interface_brief.textfsm"},
        "ip_interface": {"command": "display interface", "template": "huawei_vrp_display_interface.textfsm"},
    },
    "H3C-legacy-cli": {
        "device_identity": {"command": "display version", "template": "hp_comware_display_version.textfsm"},
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "mac": {"command": "display mac-address", "template": "hp_comware_display_mac-address.textfsm"},
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "interface_brief": {"command": "display interface brief", "template": "hp_comware_display_interface_brief.textfsm"},
        "ip_interface": {"command": "display ip interface", "template": "hp_comware_display_ip_interface.textfsm"},
        "aggre_port": {
            "command": "display link-aggregation verbose",
            "template": "hp_comware_display_link-aggregation_verbose.textfsm",
        },
        "fan_status": {"command": "display fan", "template": "hp_comware_display_fan.textfsm"},
        "power_status": {"command": "display power", "template": "hp_comware_display_power.textfsm"},
        "clock_status": {"command": "display clock", "template": "hp_comware_display_clock.textfsm"},
        "ospf_neighbors": {"command": "display ospf peer verbose", "template": "hp_comware_display_ospf_peer.textfsm"},
        "ospf_interfaces": {"command": "display ospf interface", "template": "hp_comware_display_ospf_interface.textfsm"},
        "isis_neighbors": {"command": "display isis peer verbose", "template": "hp_comware_display_isis_peer_verbose.textfsm"},
        "board_status": {"command": "display device manuinfo", "template": "hp_comware_display_device_manuinfo.textfsm"},
    },
    "H3C-modern-netconf": {
        "device_identity": {"command": "display version", "template": "hp_comware_display_version.textfsm"},
        "arp": {"command": "display arp", "template": "hp_comware_display_arp.textfsm"},
        "mac": {"command": "display mac-address", "template": "hp_comware_display_mac-address.textfsm"},
        "lldp": {
            "command": "display lldp neighbor-information verbose",
            "template": "hp_comware_display_lldp_neighbor-information_verbose.textfsm",
        },
        "interface_brief": {"command": "display interface brief", "template": "hp_comware_display_interface_brief.textfsm"},
        "ip_interface": {"command": "display ip interface", "template": "hp_comware_display_ip_interface.textfsm"},
        "aggre_port": {
            "command": "display link-aggregation verbose",
            "template": "hp_comware_display_link-aggregation_verbose.textfsm",
        },
        "fan_status": {"command": "display fan", "template": "hp_comware_display_fan.textfsm"},
        "power_status": {"command": "display power", "template": "hp_comware_display_power.textfsm"},
        "clock_status": {"command": "display clock", "template": "hp_comware_display_clock.textfsm"},
        "ospf_neighbors": {"command": "display ospf peer verbose", "template": "hp_comware_display_ospf_peer.textfsm"},
        "ospf_interfaces": {"command": "display ospf interface", "template": "hp_comware_display_ospf_interface.textfsm"},
        "isis_neighbors": {"command": "display isis peer verbose", "template": "hp_comware_display_isis_peer_verbose.textfsm"},
        "board_status": {"command": "display device manuinfo", "template": "hp_comware_display_device_manuinfo.textfsm"},
    },
    "Ruijie-switch": {
        "device_identity": {"command": "show version", "template": "ruijie_show_version.textfsm"},
        "fan_status": {"command": "show fan", "template": "ruijie_show_fan.textfsm"},
        "power_status": {"command": "show power", "template": "ruijie_show_power.textfsm"},
        "interface_brief": {"command": "show interfaces status", "template": "ruijie_show_interfaces_status.textfsm"},
        "arp": {"command": "show ip arp", "template": ""},
        "mac": {"command": "show mac", "template": ""},
    },
    "Hillstone-firewall": {
        "device_identity": {"command": "show version", "template": "hillstone_show_version.textfsm"},
        "arp": {"command": "show arp", "template": "hillstone_show_arp.textfsm"},
    },
    "Cisco-switch": {
        "device_identity": {"command": "show version", "template": "cisco_ios_show_version.textfsm"},
        "arp": {"command": "show ip arp", "template": ""},
        "mac": {"command": "show mac-address-table", "template": "cisco_ios_show_mac-address-table.textfsm"},
    },
    "ZTE-switch": {
        "device_identity": {"command": "show version", "template": "zte_zxros_show_version.textfsm"},
        "lldp": {"command": "show lldp entry", "template": "zte_zxros_show_lldp_entry.textfsm"},
        "arp": {"command": "show arp", "template": "zte_zxros_show_arp.textfsm"},
    },
    "Maipu-switch": {
        "arp": {"command": "show arp", "template": "maipu_show_arp.textfsm"},
        "mac": {"command": "show mac-address all", "template": "maipu_show_mac-address_all.textfsm"},
        "interface_brief": {"command": "show interface", "template": "maipu_show_interface.textfsm"},
        "aggre_port": {"command": "show link-aggregation interface", "template": "maipu_show_link-aggregation_interface.textfsm"},
    },
    "Mellanox-switch": {
        "mac": {"command": "show mac-address-table", "template": "mellanox_show_mac-address-table.textfsm"},
        "aggre_port": {"command": "show interface port-channel summary", "template": "mellanox_show_interface_port-channel_summary.textfsm"},
        "fan_status": {"command": "show fan", "template": "mellanox_show_fan.textfsm"},
        "power_status": {"command": "show power", "template": "mellanox_show_power.textfsm"},
    },
    "Centec-switch": {
        "arp": {"command": "show ip arp", "template": "centec_show_ip_arp.textfsm"},
        "ip_interface": {"command": "show ip interface brief", "template": "centec_show_ip_interface_brief.textfsm"},
    },
}


class PlatformProfileService:
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
                    profile.save(
                        update_fields=list(defaults.keys()) + ["updated_at"]
                    )
            profiles.append(profile)
        return profiles

    @staticmethod
    def _string_value(value) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _match_patterns(value: str, patterns: List[str]) -> bool:
        if not patterns:
            return True
        return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in patterns)

    @classmethod
    def match_profile_for_device(
        cls, device: NetworkDevice, profiles: Optional[List[PlatformProfile]] = None
    ) -> Optional[PlatformProfile]:
        profiles = profiles or cls.ensure_builtin_profiles()
        vendor_alias = getattr(getattr(device, "vendor", None), "alias", "") or ""
        category_name = getattr(getattr(device, "category", None), "name", "") or ""
        model_name = getattr(getattr(device, "model", None), "name", "") or ""
        soft_version = cls._string_value(getattr(device, "soft_version", ""))
        device_name = cls._string_value(getattr(device, "name", ""))
        haystack = " ".join(filter(None, [model_name, device_name]))

        for profile in profiles:
            if profile.vendor_alias != vendor_alias:
                continue
            if profile.category and profile.category != category_name:
                continue
            if not cls._match_patterns(haystack, profile.series_patterns):
                continue
            if not cls._match_patterns(soft_version, profile.version_patterns):
                continue
            return profile

        for profile in profiles:
            if profile.vendor_alias == vendor_alias and (
                not profile.category or profile.category == category_name
            ):
                return profile
        return None

    @classmethod
    def ensure_default_plan_for_profile(
        cls, profile: PlatformProfile
    ) -> DeviceCollectionPlans:
        plan, _ = DeviceCollectionPlans.objects.get_or_create(
            name=profile.default_plan_name,
            defaults={
                "vendor": profile.vendor_alias,
                "device_type": profile.category,
                "description": f"系统内置默认方案: {profile.code}",
                "is_active": True,
                "profile_code": profile.code,
                "plan_kind": DeviceCollectionPlans.PLAN_KIND_TEMPLATE,
                "generated_by_system": True,
                "version": 1,
                "is_default": True,
            },
        )

        updated_fields = []
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
        if updated_fields:
            plan.save(update_fields=updated_fields + ["updated_at"])

        DeviceCollectionService.ensure_default_sub_plans(plan)
        cls.apply_profile_defaults(plan, profile)
        return plan

    @staticmethod
    def _get_cli_defaults(profile: PlatformProfile, collection_type: str) -> Dict[str, str]:
        profile_defaults = PROFILE_NETMIKO_SUB_PLAN_DEFAULTS.get(profile.code, {})
        return profile_defaults.get(collection_type, {})

    @classmethod
    def apply_profile_defaults(
        cls, plan: DeviceCollectionPlans, profile: PlatformProfile
    ) -> None:
        identity_command = DEVICE_IDENTITY_NETMIKO_COMMANDS.get(profile.vendor_alias, "")
        for sub_plan in plan.collect_plans.all():
            preferred = (profile.preferred_methods or {}).get(sub_plan.collection_type, [])
            supported = sub_plan.collection_type in (profile.supported_collection_types or [])
            cli_defaults = cls._get_cli_defaults(profile, sub_plan.collection_type)
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

            desired_netmiko_enabled = supported and preferred_uses_netmiko and bool(command)
            if (
                not desired_netmiko_enabled
                and cli_defaults
                and "netmiko" in (profile.fallback_methods or {}).get(sub_plan.collection_type, [])
            ):
                desired_netmiko_enabled = bool(command)

            if sub_plan.netmiko_enabled != desired_netmiko_enabled:
                sub_plan.netmiko_enabled = desired_netmiko_enabled
                updated_fields.append("netmiko_enabled")

            if updated_fields:
                sub_plan.save(update_fields=updated_fields + ["updated_at"])

    @classmethod
    def auto_bind_devices(
        cls, devices, binding_source: str = PlansToDevice.BINDING_SOURCE_AUTO
    ) -> Dict[str, object]:
        profiles = cls.ensure_builtin_profiles()
        created = 0
        updated = 0
        skipped = 0
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

            plan = cls.ensure_default_plan_for_profile(profile)
            defaults = {
                "manage_ip": device.manage_ip,
                "profile_code": profile.code,
                "binding_source": binding_source,
                "is_active": True,
                "use_local": True,
                "execute_node": "",
                "last_bound_at": timezone.now(),
            }
            relation, created_flag = PlansToDevice.objects.get_or_create(
                device_serial_num=device.serial_num,
                plan=plan,
                defaults=defaults,
            )
            if created_flag:
                created += 1
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
                    updated += 1
                else:
                    skipped += 1
                    status = "skipped"

            results.append(
                {
                    "manage_ip": device.manage_ip,
                    "serial_num": device.serial_num,
                    "profile_code": profile.code,
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "status": status,
                }
            )

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "results": results,
        }

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
            PlansToDevice.objects.filter(device_serial_num=device.serial_num, is_active=True)
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
        return {
            "serial_num": device.serial_num,
            "manage_ip": device.manage_ip,
            "profile_code": profile.code,
            "supported_collection_types": profile.supported_collection_types,
            "preferred_methods": profile.preferred_methods,
            "fallback_methods": profile.fallback_methods,
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
    def _ensure_vendor(vendor_alias: str) -> Optional[Vendor]:
        if not vendor_alias:
            return None
        vendor = Vendor.objects.filter(alias=vendor_alias).first()
        if vendor:
            return vendor
        return Vendor.objects.filter(name=vendor_alias).first()

    @staticmethod
    def _ensure_category(category_name: str) -> Optional[Category]:
        if not category_name:
            return None
        category, _ = Category.objects.get_or_create(name=category_name)
        return category

    @classmethod
    def _ensure_model(cls, vendor: Optional[Vendor], model_name: str) -> Optional[Model]:
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
        if collection_type not in ("device_identity", "version"):
            return
        if not processed_data:
            return

        manage_ip = str(device_info.get("manage_ip") or "")
        serial_num = str(device_info.get("serial_num") or "")
        device = None
        if serial_num:
            device = NetworkDevice.objects.filter(serial_num=serial_num).first()
        if device is None and manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
        if device is None:
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

        if profile_code:
            profile = PlatformProfile.objects.filter(code=profile_code).first()
            if profile:
                category = cls._ensure_category(profile.category)
                if category and device.category_id != category.id:
                    device.category = category
                    update_fields.append("category")

        if update_fields:
            device.save(update_fields=list(dict.fromkeys(update_fields)))

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
