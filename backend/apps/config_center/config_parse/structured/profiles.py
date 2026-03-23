from __future__ import annotations

import re
from typing import Any, Dict, List

from apps.config_center.config_parse.structured.base import (
    StructuredConfigProfile,
    compact_dict,
    ensure_list,
    normalize_bool,
)


COMWARE_TTP_TEMPLATE = r"""
<group name="system">
 version {{ version | re(".*") }}
 sysname {{ hostname }}
 clock timezone {{ timezone | re(".*") }}
 clock protocol {{ clock_protocol }}
 ip unreachables enable {{ ip_unreachables | set(True) }}
 ip ttl-expires enable {{ ip_ttl_expires | set(True) }}
 lldp global enable {{ lldp_enabled | set(True) }}
 stp global enable {{ stp_enabled | set(True) }}
 ssh server enable {{ ssh_enabled | set(True) }}
 netconf ssh server enable {{ netconf_ssh_enabled | set(True) }}
</group>
<group name="routing_instances*">
ip vpn-instance {{ name }}
 description {{ description | ORPHRASE }}
</group>
<group name="vlans*">
vlan {{ vlan_id }}
</group>
<group name="ntp_servers*">
 ntp-service unicast-server {{ address }} vpn-instance {{ vrf }}
 ntp-service unicast-server {{ address }} vpn-instance {{ vrf }} source {{ source_interface }}
</group>
<group name="log_hosts*">
 info-center loghost vpn-instance {{ vrf }} {{ address }}
</group>
<group name="interfaces*">
interface {{ name | _start_ }}
 description {{ description | ORPHRASE }}
 port link-type {{ link_type }}
 port trunk permit vlan {{ trunk_vlans | re(".*") }}
 port access vlan {{ access_vlan | to_int }}
 stp edged-port {{ edge_port | set(True) }}
 port link-aggregation group {{ aggregation_group | to_int }}
 ip address {{ ip_address }} {{ ip_mask }}
 ip binding vpn-instance {{ vrf }}
 shutdown {{ enabled | set(False) }}
# {{ _end_ }}
</group>
"""


HUAWEI_TTP_TEMPLATE = r"""
<group name="system">
 sysname {{ hostname }}
 clock timezone {{ timezone | re(".*") }}
 stelnet server enable {{ ssh_enabled | set(True) }}
 telnet server disable {{ telnet_disabled | set(True) }}
 stp mode {{ stp_mode }}
 stp v-stp enable {{ stp_enabled | set(True) }}
 stp bpdu-protection {{ stp_bpdu_protection | set(True) }}
</group>
<group name="routing_instances*">
ip vpn-instance {{ name }}
 description {{ description | ORPHRASE }}
</group>
<group name="vlans*">
vlan batch {{ vlan_batch | re(".*") }}
vlan {{ vlan_id }}
</group>
<group name="ntp_servers*">
 ntp unicast-server {{ address }} vpn-instance {{ vrf }} {{ preferred | re("preferred") }}
</group>
<group name="log_hosts*">
 info-center loghost {{ address }} vpn-instance {{ vrf }}
 info-center loghost {{ address }} vpn-instance {{ vrf }} source-ip {{ source_ip }} channel {{ channel }} port {{ port }}
</group>
<group name="access_lists*">
acl number {{ name | _start_ }}
 description {{ description | ORPHRASE }}
 <group name="rules*">
  rule {{ sequence }} {{ action }} vpn-instance {{ vrf }} source {{ source | re(".*") }}
 </group>
# {{ _end_ }}
</group>
<group name="interfaces*">
interface {{ name | _start_ }}
 description {{ description | ORPHRASE }}
 port link-type {{ link_type }}
 port trunk permit vlan {{ trunk_vlans | re(".*") }}
 port access vlan {{ access_vlan | to_int }}
 stp edged-port {{ edge_port | set(True) }}
 port link-aggregation group {{ aggregation_group | to_int }}
 ip address {{ ip_address }} {{ ip_mask }}
 ip binding vpn-instance {{ vrf }}
 shutdown {{ enabled | set(False) }}
# {{ _end_ }}
</group>
"""


HILLSTONE_TTP_TEMPLATE = r"""
<group name="system">
Version {{ version }}
</group>
<group name="routing_instances*">
ip vrouter "{{ name }}"
</group>
<group name="zones*">
zone "{{ name }}" {{ zone_mode | ORPHRASE }}
</group>
<group name="interfaces*">
interface {{ name }}
</group>
<group name="services*">
service "{{ name }}"
</group>
<group name="aaa_servers*">
aaa-server "{{ name }}" type {{ aaa_type }}
</group>
"""


RUIJIE_TTP_TEMPLATE = r"""
<group name="system">
version {{ version | re(".*") }}
hostname {{ hostname }}
clock timezone {{ timezone | re(".*") }}
enable service ssh-server {{ ssh_enabled | set(True) }}
no enable service telnet-server {{ telnet_disabled | set(True) }}
spanning-tree {{ stp_enabled | set(True) }}
</group>
<group name="vlans*">
vlan {{ vlan_id }}
</group>
<group name="log_hosts*">
logging server {{ address }}
</group>
<group name="access_lists*">
ip access-list {{ acl_type }} {{ name | _start_ }}
 <group name="rules*">
  {{ sequence }} {{ action }} {{ match | re(".*") }}
 </group>
! {{ _end_ }}
</group>
<group name="interfaces*">
interface {{ name | _start_ }}
 description {{ description | ORPHRASE }}
 switchport access vlan {{ access_vlan | to_int }}
 spanning-tree portfast {{ edge_port | set(True) }}
 shutdown {{ enabled | set(False) }}
! {{ _end_ }}
</group>
"""


CISCO_IOS_TTP_TEMPLATE = r"""
<group name="system">
hostname {{ hostname }}
service http disable {{ http_disabled | set(True) }}
service https enable {{ https_enabled | set(True) }}
aaa new-model {{ aaa_new_model | set(True) }}
</group>
<group name="log_hosts*">
logging server address mgmt-if {{ address }}
</group>
<group name="aaa_servers*">
tacacs-server host mgmt-if {{ address }} key {{ key | ORPHRASE }}
</group>
<group name="ntp_servers*">
ntp server mgmt-if {{ address }}
</group>
<group name="access_lists*">
ip access-list {{ acl_type }} {{ name | _start_ }}
 <group name="rules*">
  sequence-num {{ sequence }} {{ action }} {{ match | re(".*") }}
 </group>
 exit {{ _end_ }}
</group>
<group name="interfaces*">
interface {{ name | _start_ }}
 description {{ description | ORPHRASE }}
 static-channel-group {{ aggregation_group | to_int }}
 shutdown {{ enabled | set(False) }}
! {{ _end_ }}
</group>
"""


def _normalize_vlans(vlans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in vlans:
        vlan_id = item.get('vlan_id')
        if vlan_id is None and item.get('vlan_batch'):
            batch_value = str(item['vlan_batch']).strip()
            parts = re.split(r'\s+', batch_value)
            for part in parts:
                if part.isdigit():
                    normalized.append({'vlan_id': int(part)})
            continue
        if str(vlan_id).isdigit():
            normalized.append({'vlan_id': int(vlan_id)})
    deduplicated = {}
    for item in normalized:
        deduplicated[item['vlan_id']] = item
    return [deduplicated[key] for key in sorted(deduplicated.keys())]


def _normalize_interfaces(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    interfaces = []
    for item in items:
        ip_address = item.get('ip_address')
        ip_addresses = []
        if ip_address:
            ip_addresses.append(compact_dict({
                'address': ip_address,
                'mask': item.get('ip_mask'),
            }))
        interfaces.append(compact_dict({
            'name': item.get('name'),
            'description': item.get('description'),
            'enabled': item.get('enabled') if item.get('enabled') is False else True,
            'link_type': item.get('link_type'),
            'access_vlan': item.get('access_vlan'),
            'trunk_vlans': item.get('trunk_vlans'),
            'edge_port': normalize_bool(item.get('edge_port')),
            'aggregation_group': item.get('aggregation_group'),
            'vrf': item.get('vrf'),
            'ip_addresses': ip_addresses,
        }))
    return [item for item in interfaces if item.get('name')]


def _normalize_log_hosts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        normalized.append(compact_dict({
            'address': item.get('address'),
            'vrf': item.get('vrf'),
            'source_ip': item.get('source_ip'),
            'channel': item.get('channel'),
            'port': int(item['port']) if str(item.get('port', '')).isdigit() else item.get('port'),
        }))
    return [item for item in normalized if item.get('address')]


def _normalize_ntp_servers(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        normalized.append(compact_dict({
            'address': item.get('address'),
            'vrf': item.get('vrf'),
            'source_interface': item.get('source_interface'),
            'preferred': normalize_bool(item.get('preferred')),
        }))
    return [item for item in normalized if item.get('address')]


def _regex_single(pattern: str, text: str, flags: int = re.MULTILINE) -> str:
    match = re.search(pattern, text, flags=flags)
    if not match:
        return ''
    return (match.group(1) or '').strip()


def _parse_regex_ntp_servers(
    text: str,
    pattern: str,
    address_group: str = 'address',
    vrf_group: str = 'vrf',
    source_group: str = 'source_interface',
    preferred_group: str = 'preferred',
) -> List[Dict[str, Any]]:
    servers = []
    for match in re.finditer(pattern, text, flags=re.MULTILINE):
        servers.append(compact_dict({
            'address': match.groupdict().get(address_group),
            'vrf': match.groupdict().get(vrf_group),
            'source_interface': match.groupdict().get(source_group),
            'preferred': bool(match.groupdict().get(preferred_group)),
        }))
    return [item for item in servers if item.get('address')]


def _parse_regex_log_hosts(
    text: str,
    pattern: str,
    address_group: str = 'address',
    vrf_group: str = 'vrf',
    source_ip_group: str = 'source_ip',
    channel_group: str = 'channel',
    port_group: str = 'port',
) -> List[Dict[str, Any]]:
    log_hosts = []
    for match in re.finditer(pattern, text, flags=re.MULTILINE):
        port = match.groupdict().get(port_group)
        log_hosts.append(compact_dict({
            'address': match.groupdict().get(address_group),
            'vrf': match.groupdict().get(vrf_group),
            'source_ip': match.groupdict().get(source_ip_group),
            'channel': match.groupdict().get(channel_group),
            'port': int(port) if port and str(port).isdigit() else port,
        }))
    return [item for item in log_hosts if item.get('address')]


def _normalize_access_lists(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        rules = []
        for rule in ensure_list(item.get('rules')):
            rules.append(compact_dict({
                'sequence': rule.get('sequence'),
                'action': rule.get('action'),
                'vrf': rule.get('vrf'),
                'match': rule.get('match') or rule.get('source'),
            }))
        normalized.append(compact_dict({
            'name': item.get('name'),
            'type': item.get('acl_type'),
            'description': item.get('description'),
            'rules': [rule for rule in rules if rule],
        }))
    return [item for item in normalized if item.get('name')]


def _parse_regex_vlans(text: str, pattern: str = r'^\s*vlan\s+(\d+)') -> List[Dict[str, Any]]:
    vlans = []
    for match in re.finditer(pattern, text, flags=re.MULTILINE):
        if match.group(1).isdigit():
            vlans.append({'vlan_id': int(match.group(1))})
    deduplicated = {}
    for item in vlans:
        deduplicated[item['vlan_id']] = item
    return [deduplicated[key] for key in sorted(deduplicated.keys())]


def _normalize_routing_instances(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items:
        normalized.append(compact_dict({
            'name': item.get('name'),
            'description': item.get('description'),
        }))
    return [item for item in normalized if item.get('name')]


def _parse_regex_routing_instances(text: str, pattern: str = r'^\s*ip vpn-instance\s+(\S+)') -> List[Dict[str, Any]]:
    names = []
    for match in re.finditer(pattern, text, flags=re.MULTILINE):
        names.append({'name': match.group(1)})
    deduplicated = {}
    for item in names:
        deduplicated[item['name']] = item
    return list(deduplicated.values())


def _parse_hillstone_services(text: str) -> List[Dict[str, Any]]:
    services = []
    pattern = re.compile(
        r'service\s+"(?P<name>[^"]+)"\n(?P<body>.*?)(?:^exit$)',
        flags=re.MULTILINE | re.DOTALL,
    )
    port_pattern = re.compile(
        r'^\s*(?P<protocol>tcp|udp)\s+dst-port\s+(?P<start>\d+)(?:\s+(?P<end>\d+))?\s*$',
        flags=re.MULTILINE | re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        ports = []
        for port_match in port_pattern.finditer(match.group('body')):
            start_port = int(port_match.group('start'))
            end_port = int(port_match.group('end') or start_port)
            ports.append({
                'protocol': port_match.group('protocol').lower(),
                'start_port': start_port,
                'end_port': end_port,
            })
        services.append(compact_dict({
            'name': match.group('name'),
            'ports': ports,
        }))
    if services:
        return services
    fallback = []
    for item in re.finditer(r'^service\s+"(?P<name>[^"]+)"$', text, flags=re.MULTILINE):
        fallback.append({'name': item.group('name')})
    return fallback


def _parse_hillstone_zones(text: str) -> List[Dict[str, Any]]:
    zones = []
    for match in re.finditer(r'^zone\s+"(?P<name>[^"]+)"(?:\s+(?P<mode>\S+))?$', text, flags=re.MULTILINE):
        zones.append(compact_dict({
            'name': match.group('name'),
            'mode': match.group('mode') or 'l3',
        }))
    return zones


def _parse_cisco_like_interfaces(text: str) -> List[Dict[str, Any]]:
    interfaces = []
    pattern = re.compile(
        r'^interface (?P<name>[^\n]+)\n(?P<body>.*?)(?=^!$|^interface |\Z)',
        flags=re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        body = match.group('body')
        description = _regex_single(r'^\s*description\s+(.+)$', body)
        access_vlan = _regex_single(
            r'^\s*(?:switchport access vlan|port access vlan)\s+(\d+)', body)
        trunk_vlans = _regex_single(
            r'^\s*(?:switchport trunk allowed vlan|port trunk permit vlan)\s+(.+)$', body)
        aggregation_group = _regex_single(
            r'^\s*(?:port-group|static-channel-group)\s+(\d+)', body)
        interfaces.append(compact_dict({
            'name': match.group('name').strip(),
            'description': description,
            'enabled': False if re.search(r'^\s*shutdown\b', body, flags=re.MULTILINE) else True,
            'access_vlan': int(access_vlan) if access_vlan.isdigit() else None,
            'trunk_vlans': trunk_vlans,
            'edge_port': True if re.search(r'^\s*(?:spanning-tree portfast|stp edged-port)\b', body, flags=re.MULTILINE) else None,
            'aggregation_group': int(aggregation_group) if aggregation_group.isdigit() else None,
            'ip_addresses': [],
        }))
    return [item for item in interfaces if item.get('name')]


def _parse_cisco_like_access_lists(text: str) -> List[Dict[str, Any]]:
    access_lists = []
    pattern = re.compile(
        r'^ip access-list (?P<acl_type>\S+) (?P<name>[^\n]+)\n(?P<body>.*?)(?=^\s*exit$|\Z)',
        flags=re.MULTILINE | re.DOTALL,
    )
    rule_pattern = re.compile(
        r'^\s*(?:sequence-num\s+)?(?P<sequence>\d+)\s+(?P<action>\S+)\s+(?P<match>.+)$', flags=re.MULTILINE)
    for match in pattern.finditer(text):
        rules = []
        for rule_match in rule_pattern.finditer(match.group('body')):
            rules.append(compact_dict({
                'sequence': rule_match.group('sequence'),
                'action': rule_match.group('action'),
                'match': rule_match.group('match').strip(),
            }))
        access_lists.append(compact_dict({
            'name': match.group('name').strip(),
            'type': match.group('acl_type').strip(),
            'rules': rules,
        }))
    return [item for item in access_lists if item.get('name')]


class H3CStructuredProfile(StructuredConfigProfile):
    aliases = ('H3C', 'hp_comware')
    vendor_family = 'h3c_comware'
    os_family = 'Comware'
    profile_name = 'h3c_comware'
    template = COMWARE_TTP_TEMPLATE

    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = parsed.get('system') or {}
        features = self.default_features()
        features.update({
            'ssh_enabled': normalize_bool(system.get('ssh_enabled') or system.get('netconf_ssh_enabled')),
            'stp_enabled': normalize_bool(system.get('stp_enabled')),
            'lldp_enabled': normalize_bool(system.get('lldp_enabled')),
        })
        telnet_disabled = re.search(
            r'^\s*undo\s+telnet\s+server\s+enable\b', text, flags=re.MULTILINE)
        if telnet_disabled:
            features['telnet_enabled'] = False
        routing_instances = _normalize_routing_instances(
            ensure_list(parsed.get('routing_instances')))
        if not routing_instances:
            routing_instances = _parse_regex_routing_instances(text)
        ntp_servers = _normalize_ntp_servers(
            ensure_list(parsed.get('ntp_servers')))
        if not ntp_servers:
            ntp_servers = _parse_regex_ntp_servers(
                text,
                r'^\s*ntp-service unicast-server (?P<address>\S+)(?: vpn-instance (?P<vrf>\S+))?(?: source (?P<source_interface>\S+))?',
            )
        log_hosts = _normalize_log_hosts(ensure_list(parsed.get('log_hosts')))
        if not log_hosts:
            log_hosts = _parse_regex_log_hosts(
                text,
                r'^\s*info-center loghost(?: vpn-instance (?P<vrf>\S+))? (?P<address>\S+)',
            )
        vlans = _normalize_vlans(ensure_list(parsed.get('vlans')))
        if not vlans:
            vlans = _parse_regex_vlans(text)
        return {
            'system': compact_dict({
                'hostname': system.get('hostname'),
                'version': system.get('version'),
                'timezone': system.get('timezone'),
                'clock_protocol': system.get('clock_protocol'),
                'os_family': self.os_family,
            }),
            'features': features,
            'routing_instances': routing_instances,
            'vlans': vlans,
            'zones': [],
            'services': [],
            'ntp_servers': ntp_servers,
            'log_hosts': log_hosts,
            'aaa_servers': [],
            'interfaces': _normalize_interfaces(ensure_list(parsed.get('interfaces'))),
            'access_lists': [],
            'snmp': {
                'enabled': bool(re.search(r'^\s*snmp-agent\b', text, flags=re.MULTILINE)),
            },
            'vendor_specific': {
                'unreachables_enabled': normalize_bool(system.get('ip_unreachables')),
                'ttl_expires_enabled': normalize_bool(system.get('ip_ttl_expires')),
            },
        }


class HuaweiStructuredProfile(StructuredConfigProfile):
    aliases = ('Huawei', 'HUAWEI', 'huawei')
    vendor_family = 'huawei_vrp'
    os_family = 'VRP'
    profile_name = 'huawei_vrp'
    template = HUAWEI_TTP_TEMPLATE

    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = parsed.get('system') or {}
        features = self.default_features()
        hostname = system.get('hostname') or _regex_single(
            r'^\s*sysname\s+(\S+)', text)
        timezone = system.get('timezone') or _regex_single(
            r'^\s*clock timezone\s+(.*)$', text)
        stp_mode = system.get('stp_mode') or _regex_single(
            r'^\s*stp mode\s+(\S+)', text)
        features.update({
            'ssh_enabled': True if system.get('ssh_enabled') or re.search(r'^\s*stelnet server enable\b', text, flags=re.MULTILINE) else None,
            'telnet_enabled': False if system.get('telnet_disabled') or re.search(r'^\s*telnet server disable\b', text, flags=re.MULTILINE) else None,
            'stp_enabled': True if stp_mode or system.get('stp_enabled') or re.search(r'^\s*stp v-stp enable\b', text, flags=re.MULTILINE) else None,
        })
        snmp_enabled = bool(
            re.search(r'^\s*snmp-agent\b', text, flags=re.MULTILINE))
        if snmp_enabled:
            features['snmp_enabled'] = True
        ntp_servers = _normalize_ntp_servers(
            ensure_list(parsed.get('ntp_servers')))
        if not ntp_servers:
            ntp_servers = _parse_regex_ntp_servers(
                text,
                r'^\s*ntp unicast-server (?P<address>\S+)(?: vpn-instance (?P<vrf>\S+))?(?: (?P<preferred>preferred))?',
            )
        log_hosts = _normalize_log_hosts(ensure_list(parsed.get('log_hosts')))
        if not log_hosts:
            log_hosts = _parse_regex_log_hosts(
                text,
                r'^\s*info-center loghost (?P<address>\S+)(?: vpn-instance (?P<vrf>\S+))?(?: source-ip (?P<source_ip>\S+) channel (?P<channel>\S+) port (?P<port>\S+))?',
            )
        return {
            'system': compact_dict({
                'hostname': hostname,
                'timezone': timezone,
                'stp_mode': stp_mode,
                'os_family': self.os_family,
            }),
            'features': features,
            'routing_instances': _normalize_routing_instances(ensure_list(parsed.get('routing_instances'))),
            'vlans': _normalize_vlans(ensure_list(parsed.get('vlans'))),
            'zones': [],
            'services': [],
            'ntp_servers': ntp_servers,
            'log_hosts': log_hosts,
            'aaa_servers': [],
            'interfaces': _normalize_interfaces(ensure_list(parsed.get('interfaces'))),
            'access_lists': _normalize_access_lists(ensure_list(parsed.get('access_lists'))),
            'snmp': {
                'enabled': snmp_enabled,
                'version': next(
                    (match.group(1) for match in re.finditer(
                        r'^\s*snmp-agent.*\b(v[123]c?)\b', text, flags=re.MULTILINE)),
                    '',
                ),
            },
            'vendor_specific': {},
        }


class HillstoneStructuredProfile(StructuredConfigProfile):
    aliases = ('Hillstone',)
    vendor_family = 'hillstone_sg'
    os_family = 'StoneOS'
    profile_name = 'hillstone_stoneos'
    template = HILLSTONE_TTP_TEMPLATE

    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = parsed.get('system') or {}
        features = self.default_features()
        return {
            'system': compact_dict({
                'version': system.get('version'),
                'os_family': self.os_family,
            }),
            'features': features,
            'routing_instances': _normalize_routing_instances(ensure_list(parsed.get('routing_instances'))),
            'vlans': [],
            'zones': _parse_hillstone_zones(text),
            'services': _parse_hillstone_services(text),
            'ntp_servers': [],
            'log_hosts': [],
            'aaa_servers': [
                compact_dict({
                    'name': item.get('name'),
                    'type': item.get('aaa_type'),
                })
                for item in ensure_list(parsed.get('aaa_servers'))
                if item.get('name')
            ],
            'interfaces': [
                {'name': item.get('name'), 'enabled': True}
                for item in ensure_list(parsed.get('interfaces'))
                if item.get('name')
            ],
            'access_lists': [],
            'snmp': {
                'enabled': bool(re.search(r'^\s*snmp\b', text, flags=re.MULTILINE)),
            },
            'vendor_specific': {
                'zone_count_from_text': len(_parse_hillstone_zones(text)),
            },
        }


class RuijieStructuredProfile(StructuredConfigProfile):
    aliases = ('Ruijie', 'ruijie_os', 'ruijie_os_telnet')
    vendor_family = 'ruijie_rgos'
    os_family = 'RGOS'
    profile_name = 'ruijie_rgos'
    template = RUIJIE_TTP_TEMPLATE

    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = parsed.get('system') or {}
        features = self.default_features()
        features.update({
            'ssh_enabled': True if system.get('ssh_enabled') or re.search(r'^\s*ip ssh version \d+', text, flags=re.MULTILINE) else None,
            'telnet_enabled': False if system.get('telnet_disabled') else None,
            'stp_enabled': normalize_bool(system.get('stp_enabled')),
        })
        return {
            'system': compact_dict({
                'hostname': system.get('hostname'),
                'version': system.get('version'),
                'timezone': system.get('timezone'),
                'os_family': self.os_family,
            }),
            'features': features,
            'routing_instances': [],
            'vlans': _normalize_vlans(ensure_list(parsed.get('vlans'))),
            'zones': [],
            'services': [],
            'ntp_servers': [],
            'log_hosts': _normalize_log_hosts(ensure_list(parsed.get('log_hosts'))),
            'aaa_servers': [],
            'interfaces': _normalize_interfaces(ensure_list(parsed.get('interfaces'))) or _parse_cisco_like_interfaces(text),
            'access_lists': _normalize_access_lists(ensure_list(parsed.get('access_lists'))),
            'snmp': {
                'enabled': bool(re.search(r'^\s*snmp-server\b', text, flags=re.MULTILINE)),
            },
            'vendor_specific': {},
        }


class CiscoIOSStructuredProfile(StructuredConfigProfile):
    aliases = ('Cisco_ios', 'cisco_ios', 'Cisco')
    vendor_family = 'cisco_ios'
    os_family = 'IOS'
    profile_name = 'cisco_ios'
    template = CISCO_IOS_TTP_TEMPLATE

    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        system = parsed.get('system') or {}
        features = self.default_features()
        features.update({
            'http_enabled': False if system.get('http_disabled') else None,
            'https_enabled': normalize_bool(system.get('https_enabled')),
            'snmp_enabled': True if re.search(r'^\s*snmp-server enable\b', text, flags=re.MULTILINE) else None,
        })
        return {
            'system': compact_dict({
                'hostname': system.get('hostname'),
                'os_family': self.os_family,
            }),
            'features': features,
            'routing_instances': [],
            'vlans': [],
            'zones': [],
            'services': [],
            'ntp_servers': _normalize_ntp_servers(ensure_list(parsed.get('ntp_servers'))),
            'log_hosts': _normalize_log_hosts(ensure_list(parsed.get('log_hosts'))),
            'aaa_servers': [
                compact_dict({
                    'address': item.get('address'),
                    'key': item.get('key'),
                    'type': 'tacacs',
                })
                for item in ensure_list(parsed.get('aaa_servers'))
                if item.get('address')
            ],
            'interfaces': _normalize_interfaces(ensure_list(parsed.get('interfaces'))) or _parse_cisco_like_interfaces(text),
            'access_lists': _normalize_access_lists(ensure_list(parsed.get('access_lists'))) or _parse_cisco_like_access_lists(text),
            'snmp': {
                'enabled': bool(re.search(r'^\s*snmp-server enable\b', text, flags=re.MULTILINE)),
                'version': next(
                    (match.group(1) for match in re.finditer(
                        r'^\s*snmp-server version\s+(\S+)', text, flags=re.MULTILINE)),
                    '',
                ),
            },
            'vendor_specific': {
                'aaa_new_model': normalize_bool(system.get('aaa_new_model')),
            },
        }


DEFAULT_PROFILES = [
    H3CStructuredProfile(),
    HuaweiStructuredProfile(),
    HillstoneStructuredProfile(),
    RuijieStructuredProfile(),
    CiscoIOSStructuredProfile(),
]
