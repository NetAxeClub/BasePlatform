import re
import math
import json
from netaddr import IPNetwork, IPAddress
from .base import register_processor
from apps.device_api.common import InterfaceFormat
from django.core.cache import cache
from apps.asset.models import NetworkDevice


# 专门处理交换机端口速率的版本
def format_switch_port_speed(speed_str):
    """
    针对交换机端口速率的格式化
    输入: '10000000' -> 输出: '10G'
    """
    try:
        speed = int(speed_str)

        # 常见交换机端口速率映射
        speed_mapping = {
            10: "10M",
            100: "100M",
            1000: "1G",
            10000: "10G",
            25000: "25G",
            40000: "40G",
            100000: "100G",
            200000: "200G",
            400000: "400G"
        }

        # 尝试直接匹配常见速率
        if speed in speed_mapping:
            return speed_mapping[speed]

        # 如果不是标准速率，按千进制计算
        if speed >= 1000000:  # 1G以上
            g_speed = speed / 1000000
            if g_speed.is_integer():
                return f"{int(g_speed)}G"
            else:
                return f"{g_speed}G"
        elif speed >= 1000:  # 1M以上
            m_speed = speed / 1000
            if m_speed.is_integer():
                return f"{int(m_speed)}M"
            else:
                return f"{m_speed}M"
        else:
            return f"{speed}bps"

    except (ValueError, TypeError):
        return "N/A"


def h3c_speed_format(interface):
    if re.search(r'^(GE)', interface) or re.search(
            r'^(GigabitEthernet)', interface):
        return '1G'

    elif re.search(r'^(XGE)', interface) or re.search(r'^(Ten-GigabitEthernet)', interface):
        return '10G'

    elif re.search(r'^(FGE)', interface) or re.search(r'^(FortyGigE)', interface):
        return '40G'

    elif re.search(r'^(Twenty-FiveGigE)', interface):
        return '25G'

    elif re.search(r'^(TwentyGigE)', interface):
        return '20G'

    elif re.search(r'^(TwoHundredGigE)', interface):
        return '200G'

    elif re.search(r'^(FourHundredGigE)', interface):
        return '400G'

    elif re.search(r'^(HGE)', interface):
        return '100G'

    elif re.search(r'^(MGE)', interface) or re.search(r'^(MEth)', interface):
        return '1G'

    elif re.search(r'^(M-GE)', interface):
        return '1G'
    return interface


def _normalize_mac(mac_str):
    """将 H3C MAC 地址统一为 aabb-ccdd-eeff 格式（小写）。

    H3C NETCONF 可能返回 aa-bb-cc-dd-ee-ff（6组2位）或 aabb-ccdd-eeff（3组4位）。
    """
    if not mac_str:
        return mac_str
    parts = mac_str.lower().split('-')
    if len(parts) == 6:
        # aa-bb-cc-dd-ee-ff → aabb-ccdd-eeff
        return f"{parts[0]}{parts[1]}-{parts[2]}{parts[3]}-{parts[4]}{parts[5]}"
    # 已经是 3 组 4 位，直接返回小写
    return mac_str.lower()


def _normalize_h3c_model_name(model_name: str) -> str:
    text = str(model_name or "").strip()
    return re.sub(r"^H3C\s+", "", text, flags=re.IGNORECASE)


def _build_ifindex_map(top):
    """从 Ifmgr.Interfaces.Interface 构建 IfIndex → 接口名 映射。"""
    ifindex_map = {}
    try:
        interfaces = top.get('Ifmgr', {}).get('Interfaces', {}).get('Interface', [])
        if isinstance(interfaces, dict):
            interfaces = [interfaces]
        for iface in interfaces:
            idx = str(iface.get('IfIndex', ''))
            name = iface.get('Name', '')
            if idx and name:
                ifindex_map[idx] = name
    except Exception:
        pass
    return ifindex_map


def _build_portindex_map(top):
    portindex_map = {}
    try:
        interfaces = top.get('Ifmgr', {}).get('Interfaces', {}).get('Interface', [])
        if isinstance(interfaces, dict):
            interfaces = [interfaces]
        for iface in interfaces:
            port_index = str(iface.get('PortIndex', '') or '')
            name = iface.get('Name', '')
            if port_index and name:
                portindex_map[port_index] = name
    except Exception:
        pass
    return portindex_map


def _collect_h3c_schemas(value):
    if isinstance(value, dict):
        schemas = value.get('netconf-state', {}).get('schemas', {}).get('schema')
        if schemas is not None:
            return schemas if isinstance(schemas, list) else [schemas]
        results = []
        for child in value.values():
            results.extend(_collect_h3c_schemas(child))
        return results
    if isinstance(value, list):
        results = []
        for item in value:
            results.extend(_collect_h3c_schemas(item))
        return results
    return []


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_records(value, required_keys):
    """递归查找包含 required_keys 的 dict 记录。"""
    records = []
    if isinstance(value, dict):
        if required_keys.issubset(set(value.keys())):
            records.append(value)
        for child in value.values():
            records.extend(_find_records(child, required_keys))
    elif isinstance(value, list):
        for item in value:
            records.extend(_find_records(item, required_keys))
    return records


def _normalize_h3c_interface(name: str) -> str:
    if not name:
        return ""
    return InterfaceFormat.h3c_interface_format(name)


def _strip_irf_reference_suffix(name: str) -> str:
    return re.sub(r"\(R\)$", "", str(name or "").strip())


def _build_ipv4_location(ip_address: str, ip_mask: str):
    if not ip_address or ip_address == "0.0.0.0":
        return None
    if ip_mask:
        network = IPNetwork(f"{ip_address}/{ip_mask}")
        return dict(
            ipaddress=network.ip.format(),
            ipmask=network.netmask.format(),
            location=[dict(start=network.first, end=network.last)],
        )
    host = IPAddress(ip_address)
    return dict(
        ipaddress=host.format(),
        ipmask="255.255.255.255",
        location=[dict(start=host.value, end=host.value)],
    )


def _h3c_protocol_name(protocol: dict) -> str:
    protocol_id = str(protocol.get('ProtocolID', ''))
    sub_protocol_id = str(protocol.get('SubProtocolID', ''))
    mapping = {
        ('1', ''): 'direct',
        ('2', ''): 'static',
        ('8', ''): 'rip',
        ('16', ''): 'ospf',
        ('32', ''): 'isis',
        ('64', ''): 'bgp',
    }
    return mapping.get((protocol_id, sub_protocol_id), protocol_id or sub_protocol_id or 'unknown')


def _index_by(items, key_name):
    result = {}
    for item in _as_list(items):
        key = item.get(key_name)
        if key:
            result[str(key)] = item
    return result


def _extract_h3c_patch_version(top):
    package = top.get('Package', {}) or {}
    boot_lists = _as_list((package.get('BootLoaderList', {}) or {}).get('BootList'))
    pattern = re.compile(r"(R\d+H\w?\d+)", re.IGNORECASE)
    for boot in boot_lists:
        image_files = (boot.get('ImageFiles', {}) or {}).get('FileName', [])
        for file_name in _as_list(image_files):
            match = pattern.search(str(file_name or ''))
            if match:
                return match.group(1)
    return ''


def _extract_h3c_physical_entities(top):
    entities = top.get('Device', {}).get('PhysicalEntities', {}).get('Entity', [])
    return _as_list(entities)


def _pick_h3c_identity_entity(entities):
    if not entities:
        return {}

    def _rank(entity):
        class_rank = {'3': 0, '9': 1}.get(str(entity.get('Class') or '').strip(), 2)
        slot_rank = 0 if str(entity.get('Slot') or '').strip() in {'', '0'} else 1
        missing_serial = 0 if entity.get('SerialNumber') else 1
        missing_model = 0 if entity.get('Model') else 1
        missing_software = 0 if entity.get('SoftwareRev') else 1
        return (class_rank, slot_rank, missing_serial, missing_model, missing_software)

    return sorted(entities, key=_rank)[0]


def _is_established(state: str) -> bool:
    text = str(state or '').strip().lower()
    return text in {'established', 'estab', 'up'} or 'established' in text


@register_processor(vendor='H3C', device_type='', collection_type='version', method='netmiko')
def process_version_netmiko(data):
    """H3C display version 处理 (Netmiko/TextFSM)。"""
    rows = _as_list(data)
    if not rows:
        return []

    model_name = ''
    soft_version = ''
    patch_version = ''

    for row in rows:
        if not isinstance(row, dict):
            continue
        if not model_name:
            model_name = str(row.get('BOARD_TYPE') or row.get('board_type') or '').strip()
        if not soft_version:
            soft_version = str(
                row.get('Version')
                or row.get('version')
                or row.get('Release_Ver')
                or row.get('release_ver')
                or ''
            ).strip().replace(', ', ' ')
        if not patch_version:
            patch_version = str(row.get('Patch_Ver') or row.get('patch_ver') or '').strip()

    if not any([model_name, soft_version, patch_version]):
        return []

    return [
        dict(
            vendor_alias='H3C',
            model_name=model_name,
            soft_version=soft_version,
            patch_version=patch_version,
        )
    ]


@register_processor(vendor='H3C', device_type='', collection_type='version', method='netconf')
def process_version_netconf(data):
    top = data.get('top', {}) if isinstance(data, dict) else {}
    base = top.get('Device', {}).get('Base', {}) or {}
    entity = _pick_h3c_identity_entity(_extract_h3c_physical_entities(top))

    model_name = _normalize_h3c_model_name(
        entity.get('Model') or entity.get('Name') or entity.get('Description') or ''
    )
    soft_version = str(entity.get('SoftwareRev') or '').strip()
    patch_version = _extract_h3c_patch_version(top)
    serial_num = str(entity.get('SerialNumber') or '').strip()
    hostname = str(base.get('HostName') or '').strip()

    if not any([hostname, model_name, soft_version, patch_version, serial_num]):
        return []

    return [
        dict(
            vendor_alias='H3C',
            hostname=hostname,
            serial_num=serial_num,
            model_name=model_name,
            soft_version=soft_version,
            patch_version=patch_version,
        )
    ]


@register_processor(vendor='H3C', device_type='', collection_type='board_status', method='netmiko')
def process_board_status_netmiko(data):
    """H3C display device manuinfo 处理 (Netmiko/TextFSM)。"""
    rows = []
    for item in _as_list(data):
        if not isinstance(item, dict):
            continue
        slot_type = str(item.get('SLOT_TYPE') or item.get('slot_type') or '').strip()
        slot_id = str(item.get('SLOT_ID') or item.get('slot_id') or '').strip()
        serial_num = str(
            item.get('DEVICE_SERIAL_NUMBER') or item.get('device_serial_number') or ''
        ).strip()
        if serial_num.upper() == 'NONE':
            serial_num = ''
        device_name = str(item.get('DEVICE_NAME') or item.get('device_name') or '').strip()
        chassis_id = str(item.get('CHASSIS_ID') or item.get('chassis_id') or '').strip()
        rows.append(
            dict(
                slot='' if slot_id == 'self' else slot_id,
                board_name=device_name,
                board_model=device_name,
                serial_num=serial_num,
                status=slot_type,
                slot_type=slot_type.lower(),
                chassis_id=chassis_id,
            )
        )
    return rows


@register_processor(vendor='H3C', device_type='', collection_type='board_status', method='netconf')
def process_board_status_netconf(data):
    top = data.get('top', {}) if isinstance(data, dict) else {}
    rows = []
    for entity in _extract_h3c_physical_entities(top):
        slot = str(entity.get('Slot') or '').strip()
        chassis_id = str(entity.get('Chassis') or '').strip()
        board_model = _normalize_h3c_model_name(
            entity.get('Model') or entity.get('Name') or entity.get('Description') or ''
        )
        board_name = str(entity.get('Name') or entity.get('Description') or board_model).strip()
        serial_num = str(entity.get('SerialNumber') or '').strip()
        if not any([slot, chassis_id, board_name, board_model, serial_num]):
            continue
        slot_type = "slot" if slot and slot != "0" else "chassis" if chassis_id else "module"
        rows.append(
            dict(
                slot=slot,
                board_name=board_name,
                board_model=board_model,
                serial_num=serial_num,
                status=str(entity.get('SoftwareRev') or entity.get('Description') or '').strip(),
                slot_type=slot_type,
                chassis_id=chassis_id,
            )
        )
    return rows


@register_processor(vendor='H3C', device_type='', collection_type='irf_status', method='netmiko')
def process_irf_status_netmiko(data):
    """H3C display irf 处理 (Netmiko/TextFSM)。"""
    rows = []
    for item in _as_list(data):
        if not isinstance(item, dict):
            continue
        member_id = str(item.get('MemberID') or item.get('memberid') or item.get('member_id') or '').strip()
        chassis_id = str(item.get('ChassisID') or item.get('chassisid') or item.get('chassis_id') or '').strip()
        rows.append(
            dict(
                chassis_id=chassis_id,
                member_id=member_id,
                slot=member_id,
                role=str(item.get('Role') or item.get('role') or '').strip(),
                priority=str(item.get('Priority') or item.get('priority') or '').strip(),
                mac=str(item.get('Mac') or item.get('mac') or '').strip(),
            )
        )
    return rows


@register_processor(vendor='H3C', device_type='', collection_type='irf_status', method='netconf')
def process_irf_status_netconf(data):
    top = data.get('top', {}) if isinstance(data, dict) else {}
    members = _as_list((top.get('IRF', {}) or {}).get('Members', {}).get('Member'))
    role_map = {'1': 'Master', '2': 'Standby', '3': 'Loading', '4': 'Other'}
    rows = []
    for member in members:
        boards = _as_list(member.get('Board'))
        if not boards:
            boards = [{}]
        for board in boards:
            slot = str(board.get('Slot') or '').strip()
            member_id = slot or str(member.get('MemberID') or '').strip()
            role = str(board.get('Role') or '').strip()
            rows.append(
                dict(
                    chassis_id=str(board.get('Chassis') or '').strip(),
                    member_id=member_id,
                    slot=slot or member_id,
                    role=role_map.get(role, role),
                    priority=str(member.get('Priority') or '').strip(),
                    mac=str(member.get('CPUMac') or '').strip(),
                    irf_member_id=str(member.get('MemberID') or '').strip(),
                )
            )
    return rows


@register_processor(vendor='H3C', device_type='', collection_type='interface_brief', method='netconf')
def process_interface_brief_netconf(data):
    """H3C 交换机二层接口处理 (NETCONF)"""
    data = data['top']['Ifmgr']['Interfaces']['Interface']
    layer2datas = []
    for i in data:
        # 正常物理接口都会带speed和duplex的key，不带则是逻辑接口
        if 'ActualSpeed' in i.keys() and 'ActualDuplex' in i.keys():
            if i['Name'].startswith('M-'):
                continue
            elif i['Name'].startswith('Bridge-Aggregation'):
                continue
            elif i['Name'].startswith('Vlan-interface'):
                continue
            elif i['Name'].startswith('InLoopBack'):
                continue
            elif i['Name'].startswith('NULL'):
                continue
            if i['ActualSpeed'] == '0':
                i['ActualSpeed'] = h3c_speed_format(
                    i['Name'])
            if format_switch_port_speed(i['ActualSpeed']) == '830G':
                i['ActualSpeed'] = h3c_speed_format(i['Name'])
            layer2datas.append(dict(
                        interface=i['Name'],
                        status=i['OperStatus'],
                        speed=format_switch_port_speed(
                            i['ActualSpeed']),
                        duplex=i['ActualDuplex'],
                        description=i['Description']))
    return layer2datas


@register_processor(vendor='H3C', device_type='', collection_type='arp', method='netconf')
def process_arp_netconf(data):
    """H3C 交换机 ARP 表处理 (NETCONF)
    """
    top = data['top']
    ifindex_map = _build_ifindex_map(top)
    portindex_map = _build_portindex_map(top)
    evpn_ifindex_map = {}
    for mac_entry in _as_list((top.get('L2VPN', {}) or {}).get('LocalMACs', {}).get('MAC')):
        mac_address = _normalize_mac(mac_entry.get('MacAddr', ''))
        if mac_address and mac_entry.get('IfIndex'):
            evpn_ifindex_map[mac_address] = str(mac_entry.get('IfIndex'))
    arp_entries = top.get('ARP', {}).get('ArpTable', {}).get('ArpEntry', [])
    if isinstance(arp_entries, dict):
        arp_entries = [arp_entries]
    arp_datas = []
    for entry in arp_entries:
        ifindex = str(entry.get('IfIndex', ''))
        normalized_mac = _normalize_mac(entry.get('MacAddress', ''))
        if not ifindex and normalized_mac:
            ifindex = evpn_ifindex_map.get(normalized_mac, '')
        interface_name = (
            ifindex_map.get(ifindex)
            or portindex_map.get(str(entry.get('PortIndex', '')))
            or ifindex
        )
        if not interface_name:
            continue
        arp_datas.append(dict(
            ipaddress=entry.get('Ipv4Address', ''),
            macaddress=_normalize_mac(entry.get('MacAddress', '')),
            vlan=entry.get('VrfIndex', ''),
            interface=interface_name,
            type=entry.get('ArpType'),
            aging=entry.get('aging'),
        ))
    return arp_datas


@register_processor(vendor='H3C', device_type='', collection_type='arp_evpn', method='netconf')
def process_arp_evpn_netconf(data):
    """H3C 交换机 ARP EVPN 表处理 (NETCONF)。

    由于不同固件/模板可能使用不同 XML 容器名称（如 ArpTable / EvpnArpTable 等），
    这里对候选路径做了兼容提取；若仍无法定位到表数据，则返回空列表。
    """
    top = data.get('top', {}) if isinstance(data, dict) else {}
    ifindex_map = _build_ifindex_map(top)
    portindex_map = _build_portindex_map(top)

    # EVPN 场景下 IfIndex 可能缺失，尝试用 LocalMACs.MAC -> IfIndex 回填接口名
    evpn_ifindex_map = {}
    l2vpn = (top.get('L2VPN', {}) or {})
    for mac_entry in _as_list((l2vpn.get('LocalMACs', {}) or {}).get('MAC', None)):
        if not isinstance(mac_entry, dict):
            continue
        raw_mac = (
            mac_entry.get('MacAddr')
            or mac_entry.get('MacAddress')
            or mac_entry.get('mac')
            or mac_entry.get('mac-address')
            or ''
        )
        mac_address = _normalize_mac(raw_mac)
        if not mac_address:
            continue
        idx = str(mac_entry.get('IfIndex') or mac_entry.get('Ifindex') or '').strip()
        if idx:
            evpn_ifindex_map[mac_address] = idx

    # 候选路径：优先在 L2VPN 下查找；找不到则回退到 ARP
    candidate_paths = [
        ('ArpTable', 'ArpEntry'),
        ('EvpnArpTable', 'EvpnArpEntry'),
        ('EvpnArpTable', 'ArpEntry'),
        ('EVPNArpTable', 'ArpEntry'),
    ]
    arp_entries = None
    for table_name, entry_name in candidate_paths:
        container = (l2vpn.get(table_name, {}) or {})
        entries = container.get(entry_name)
        if entries:
            arp_entries = entries
            break
    if arp_entries is None:
        arp_entries = top.get('ARP', {}).get('ArpTable', {}).get('ArpEntry', [])

    if isinstance(arp_entries, dict):
        arp_entries = [arp_entries]

    results = []
    for entry in arp_entries or []:
        if not isinstance(entry, dict):
            continue

        ipaddress = (
            entry.get('Ipv4Address')
            or entry.get('IpAddress')
            or entry.get('ipaddress')
            or entry.get('Ip')
            or ''
        )
        mac_raw = entry.get('MacAddress') or entry.get('MacAddr') or entry.get('mac') or ''
        macaddress = _normalize_mac(mac_raw)

        if not ipaddress and not macaddress:
            continue

        ifindex = str(entry.get('IfIndex') or entry.get('Ifindex') or '').strip()
        if not ifindex and macaddress:
            ifindex = evpn_ifindex_map.get(macaddress, '')

        port_index = str(entry.get('PortIndex') or entry.get('PortIndexId') or '').strip()
        interface_name = (
            ifindex_map.get(ifindex)
            or portindex_map.get(port_index)
            or ifindex
        )

        vlan = (
            entry.get('VrfIndex')
            or entry.get('VrfId')
            or entry.get('VlanID')
            or entry.get('VlanId')
            or ''
        )

        results.append(dict(
            ipaddress=ipaddress,
            macaddress=macaddress,
            vlan=vlan,
            vpninstance=str(vlan),
            interface=interface_name,
            type=entry.get('ArpType') or entry.get('Type') or '',
            aging=entry.get('aging') or entry.get('Aging') or '',
        ))

    return results


@register_processor(vendor='H3C', device_type='', collection_type='mac', method='netconf')
def process_mac_netconf(data):
    """H3C 交换机 MAC 地址表处理 (NETCONF)

    优先兼容旧 H3C NETCONF `mac_unicasttable` 结构，并允许通过 IfIndex 回填接口名。
    """
    top = data.get('top', {}) if isinstance(data, dict) else {}
    ifindex_map = _build_ifindex_map(top)
    status_map = {
        '0': 'Other',
        '1': 'Security',
        '2': 'Learned',
        '3': 'Static',
        '4': 'Blackhole',
    }

    entries = _find_records(data, {'MacAddress'})
    mac_datas = []
    for entry in entries:
        if not any(
            entry.get(key)
            for key in ('PortName', 'VLANID', 'VlanID', 'Status')
        ):
            continue
        interface_name = (
            entry.get('PortName')
            or ifindex_map.get(str(entry.get('IfIndex', '')))
            or entry.get('Name')
            or ""
        )
        if not interface_name:
            continue
        status = str(entry.get('Status', ''))
        mac_datas.append(
            dict(
                macaddress=_normalize_mac(entry.get('MacAddress', '')),
                vlan=entry.get('VLANID', '') or entry.get('VlanID', ''),
                interface=_normalize_h3c_interface(interface_name),
                type=status_map.get(status, entry.get('Type', '') or status),
            )
        )
    return mac_datas


@register_processor(vendor='H3C', device_type='', collection_type='ip_interface', method='netconf')
def process_ip_interface_netconf(data):
    """H3C 交换机三层接口处理 (NETCONF)

    优先兼容旧 H3C NETCONF `ipv4address` 结构。
    """
    entries = _find_records(data, {'Name', 'Ipv4Address'})
    results = []
    for entry in entries:
        location_payload = _build_ipv4_location(
            entry.get('Ipv4Address', ''),
            entry.get('Ipv4Mask', ''),
        )
        if not location_payload:
            continue
        results.append(
            dict(
                interface=_normalize_h3c_interface(entry.get('Name', '')),
                line_status=entry.get('LineStatus', '') or entry.get('line_status', ''),
                protocol_status=entry.get('ProtocolStatus', '') or entry.get('protocol_status', ''),
                ipaddress=location_payload['ipaddress'],
                ipmask=location_payload['ipmask'],
                ip_type=entry.get('type', '') or entry.get('IpType', ''),
                mtu=entry.get('MTU', '') or entry.get('mtu', ''),
                location=location_payload['location'],
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='lldp', method='netconf')
def process_lldp_netconf(data):
    """H3C 交换机 LLDP 邻居表处理 (NETCONF)

    优先兼容旧 H3C NETCONF `lldp` 结构。
    """
    entries = _find_records(data, {'LocalPort', 'PortId', 'SystemName'})
    results = []
    for entry in entries:
        neighborsysname = entry.get('SystemName', '')
        results.append(
            dict(
                local_interface=_normalize_h3c_interface(entry.get('LocalPort', '')),
                chassis_id=entry.get('ChassisId', ''),
                neighbor_port=entry.get('PortId', ''),
                portdescription=entry.get('PortDescription', ''),
                neighborsysname=neighborsysname,
                management_ip=entry.get('Address', '') or entry.get('ManagementIp', ''),
                management_type=entry.get('SubType', '') or entry.get('ManagementType', ''),
                neighbor_ip=_lookup_neighbor_ip(neighborsysname),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='aggre_port', method='netconf')
def process_aggre_port_netconf(data):
    """H3C 交换机聚合端口处理 (NETCONF)

    优先兼容旧 H3C NETCONF `lagg_list` 结构。
    """
    entries = []
    for record in _find_records(data, {'Name'}):
        name = str(record.get('Name', ''))
        attr = str(record.get('attr', '') or '')
        if (
            record.get('GroupId')
            or record.get('Memberlist') is not None
            or 'aggregation' in attr.lower()
            or name.startswith('Bridge-Aggregation')
            or name.startswith('Route-Aggregation')
        ):
            entries.append(record)

    results = []
    for entry in entries:
        member_items = _as_list(entry.get('Memberlist'))
        memberports = []
        member_statuses = []
        for member in member_items:
            member_name = member.get('Name', '')
            if member_name:
                memberports.append(_normalize_h3c_interface(member_name))
            selected_status = member.get('SelectedStatus')
            if selected_status:
                member_statuses.append(selected_status)

        results.append(
            dict(
                aggregroup=entry.get('Name', ''),
                memberports=memberports,
                status=','.join(member_statuses),
                mode=entry.get('LinkMode', '') or entry.get('Mode', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='mac_evpn', method='netconf')
def process_mac_evpn_netconf(data):
    """H3C 交换机 MAC EVPN 处理 (NETCONF)

    XML 模板需同时查询 L2VPN.LocalMACs.MAC 和 Ifmgr.Interfaces.Interface，
    通过 IfIndex 将接口索引映射为接口名称。
    """
    top = data['top']
    ifindex_map = _build_ifindex_map(top)

    mac_entries = top.get('L2VPN', {}).get('LocalMACs', {}).get('MAC', [])
    if isinstance(mac_entries, dict):
        mac_entries = [mac_entries]

    mac_datas = []
    for entry in mac_entries:
        ifindex = str(entry.get('IfIndex', ''))
        interface_name = ifindex_map.get(ifindex, ifindex)
        if not interface_name:
            continue

        mac_datas.append(dict(
            macaddress=_normalize_mac(entry.get('MacAddr', '')),
            vlan=entry.get('SrvID', ''),
            interface=interface_name,
            type=entry.get('Type', 'evpn'),
        ))

    return mac_datas


@register_processor(vendor='H3C', device_type='', collection_type='vrrp_info', method='netconf')
def process_vrrp_info_netconf(data):
    top = data.get('top', {}) if isinstance(data, dict) else {}
    operations = _as_list((top.get('VRRP', {}) or {}).get('VRRPOper', {}).get('Operation'))
    assoc_entries = _as_list((top.get('VRRP', {}) or {}).get('VRRPAssoIpAddress', {}).get('AssoIpAddr'))
    assoc_map = {
        (str(item.get('IfIndex') or ''), str(item.get('VrID') or '')): item
        for item in assoc_entries
    }
    ifindex_map = _build_ifindex_map(top)
    state_map = {
        "0": "Inactive",
        "1": "Initialize",
        "2": "Backup",
        "3": "Master",
    }

    results = []
    for operation in operations:
        if_index = str(operation.get('IfIndex') or '')
        vrid = str(operation.get('VrID') or '')
        assoc = assoc_map.get((if_index, vrid), {})
        interface_name = _normalize_h3c_interface(ifindex_map.get(if_index, if_index))
        if not interface_name:
            continue
        virtual_ip = str(assoc.get('IpAddress') or '').strip()
        results.append(
            dict(
                interface=interface_name,
                vrid=vrid,
                virtual_ip=virtual_ip,
                ipmask='255.255.255.255' if virtual_ip else '',
                priority=str(operation.get('PriorityRun') or operation.get('PriorityConfig') or '').strip(),
                preempt_mode=str(operation.get('PreemptMode') or '').strip(),
                admin_state=state_map.get(str(operation.get('OperState') or ''), str(operation.get('OperState') or '')),
                config_state=str(operation.get('AuthTypeRun') or operation.get('AuthTypeConfig') or '').strip(),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='route_table', method='netconf')
def process_route_table_netconf(data):
    """H3C 路由表处理 (NETCONF)

    解析 `Route.Ipv4Routes.RouteEntry` 结果，输出归一化路由记录。
    当前优先处理 IPv4 路由表。
    """
    top = data.get('top', {})
    route_entries = (
        top.get('Route', {})
        .get('Ipv4Routes', {})
        .get('RouteEntry', [])
    )
    ifindex_map = _build_ifindex_map(top)

    results = []
    for entry in _as_list(route_entries):
        ipv4 = entry.get('Ipv4', {}) or {}
        addr = ipv4.get('Ipv4Address', '')
        prefix_len = ipv4.get('Ipv4PrefixLength', '')
        prefix = f"{addr}/{prefix_len}" if addr and prefix_len != '' else addr
        protocol = entry.get('Protocol', {}) or {}
        if_index = str(entry.get('IfIndex', ''))

        results.append(
            dict(
                prefix=prefix,
                next_hop=entry.get('Nexthop', ''),
                interface=ifindex_map.get(if_index, if_index),
                protocol=_h3c_protocol_name(protocol),
                protocol_id=protocol.get('ProtocolID', ''),
                sub_protocol_id=protocol.get('SubProtocolID', ''),
                process_id=entry.get('ProcessID', ''),
                preference=entry.get('Preference', ''),
                metric=entry.get('Metric', ''),
                vrf=entry.get('VRF', ''),
                topology=entry.get('Topology', ''),
                neighbor=entry.get('Neighbor', ''),
                age=entry.get('Age', ''),
                origin_as=(entry.get('ASNumber', {}) or {}).get('OriginAS', ''),
                last_as=(entry.get('ASNumber', {}) or {}).get('LastAS', ''),
            )
        )

    return results


@register_processor(vendor='H3C', device_type='', collection_type='netconf_capability', method='netconf')
def process_netconf_capability_netconf(data):
    schemas = _collect_h3c_schemas(data)
    identifiers = [str(item.get('identifier') or '') for item in schemas if isinstance(item, dict)]
    namespaces = [str(item.get('namespace') or '') for item in schemas if isinstance(item, dict)]
    combined = identifiers + namespaces
    return [
        dict(
            schema_count=len(schemas),
            openconfig_schema_count=sum(1 for item in identifiers if item.startswith('openconfig-')),
            has_bgp_schema=any('bgp' in item.lower() for item in combined),
            has_l2vpn_schema=any(any(keyword in item.lower() for keyword in ('l2vpn', 'vsi', 'evpn')) for item in combined),
            has_ifmgr_schema=any(any(keyword in item.lower() for keyword in ('ifmgr', 'interface')) for item in combined),
            has_telemetry_schema=any('telemetry' in item.lower() for item in combined),
            schema_samples=[item for item in identifiers[:10] if item],
        )
    ]


@register_processor(vendor='H3C', device_type='', collection_type='cli_output_capability', method='netmiko')
def process_cli_output_capability_netmiko(data):
    raw_text = str(data or "")
    lowered = raw_text.lower()
    command_unrecognized = "unrecognized command" in lowered
    supports_irf_cli = not command_unrecognized
    has_irf_members = any(keyword in raw_text for keyword in ("Master", "Standby", "MemberID", "IRF Port"))
    evidence = []
    if command_unrecognized:
        evidence.append("irf-command-unrecognized")
    if has_irf_members:
        evidence.append("irf-members-visible")
    return [
        dict(
            supports_irf_cli=supports_irf_cli,
            command_unrecognized=command_unrecognized,
            has_irf_members=has_irf_members,
            evidence=evidence,
        )
    ]


@register_processor(vendor='H3C', device_type='', collection_type='bgp_neighbors', method='netconf')
def process_bgp_neighbors_netconf(data):
    """H3C BGP 邻居处理 (NETCONF)

    优先解析 `BGP.Sessions.Session` 的运行状态，并尝试用
    `BGP.CfgSessions.CfgSession` 补充邻居组、连接接口等配置侧信息。
    """
    top = data.get('top', {})
    bgp = top.get('BGP', {}) or {}
    sessions = _as_list((bgp.get('Sessions', {}) or {}).get('Session'))
    cfg_sessions = _index_by((bgp.get('CfgSessions', {}) or {}).get('CfgSession'), 'IpAddress')

    results = []
    for session in sessions:
        peer_ip = session.get('IpAddress', '')
        cfg = cfg_sessions.get(str(peer_ip), {})
        results.append(
            dict(
                peer_ip=peer_ip,
                address_family=session.get('AF', ''),
                vrf=session.get('VRF', ''),
                remote_as=session.get('ASNumber', '') or cfg.get('ASNumber', ''),
                state=session.get('State', ''),
                peer_group=cfg.get('GroupName', ''),
                remote_router_id='',
                peer_type='',
                connect_interface=cfg.get('ConnectInterface', ''),
                update_interval=cfg.get('UpdateInterval', ''),
                ebgp_max_hop=cfg.get('EbgpMaxHop', ''),
            )
        )

    return results


@register_processor(vendor='H3C', device_type='', collection_type='bgp_summary', method='netconf')
def process_bgp_summary_netconf(data):
    """H3C BGP 汇总处理 (NETCONF)

    基于 `Sessions.Session` 按 `VRF + AF` 聚合 BGP 邻居状态。
    """
    top = data.get('top', {})
    bgp = top.get('BGP', {}) or {}
    sessions = _as_list((bgp.get('Sessions', {}) or {}).get('Session'))

    grouped = {}
    for session in sessions:
        af = session.get('AF', '')
        vrf = session.get('VRF', '')
        key = (vrf, af)
        state = session.get('State', '')
        item = grouped.setdefault(
            key,
            {
                'address_family': af,
                'vrf': vrf,
                'total_peers': 0,
                'established_peers': 0,
                'non_established_peers': 0,
                'states': {},
            },
        )
        item['total_peers'] += 1
        if _is_established(state):
            item['established_peers'] += 1
        else:
            item['non_established_peers'] += 1
        item['states'][state] = item['states'].get(state, 0) + 1

    results = []
    for item in grouped.values():
        dominant_state = ''
        if item['states']:
            dominant_state = sorted(item['states'].items(), key=lambda kv: kv[1], reverse=True)[0][0]
        results.append(
            dict(
                address_family=item['address_family'],
                vrf=item['vrf'],
                total_peers=item['total_peers'],
                established_peers=item['established_peers'],
                non_established_peers=item['non_established_peers'],
                dominant_state=dominant_state,
            )
        )

    return results


@register_processor(vendor='H3C', device_type='', collection_type='ospf_neighbors', method='netmiko')
def process_ospf_neighbors_netmiko(data):
    """H3C OSPF 邻居处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        results.append(
            dict(
                area=item.get('area', ''),
                local_interface=item.get('interface', ''),
                neighbor_router_id=item.get('router_id', ''),
                neighbor_ip=item.get('address', ''),
                state=item.get('state', ''),
                priority=item.get('priority', ''),
                dead_time=item.get('dead_time', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='ospf_interfaces', method='netmiko')
def process_ospf_interfaces_netmiko(data):
    """H3C OSPF 接口处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        results.append(
            dict(
                area=item.get('area', ''),
                local_interface=item.get('interface', ''),
                interface_ip=item.get('interface_ip', ''),
                network_type=item.get('network_type', ''),
                state=item.get('state', ''),
                cost=item.get('cost', ''),
                priority=item.get('priority', ''),
                dr=item.get('dr', ''),
                bdr=item.get('bdr', ''),
                hello_interval=item.get('hello_interval', ''),
                dead_interval=item.get('dead_interval', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='isis_neighbors', method='netmiko')
def process_isis_neighbors_netmiko(data):
    """H3C ISIS 邻居处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        peer_ip_raw = item.get('peer_ip', '')
        peer_ip = str(peer_ip_raw).split()[0] if peer_ip_raw else ''
        results.append(
            dict(
                system_id=item.get('system_id', ''),
                local_interface=item.get('local_interface', ''),
                circuit_id=item.get('circuit_id', ''),
                state=item.get('state', ''),
                hold_time=item.get('hold_time', ''),
                neighbor_type=item.get('neighbor_type', ''),
                priority=item.get('priority', ''),
                area=item.get('area', ''),
                peer_ip=peer_ip,
                uptime=item.get('uptime', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='fan_status', method='netmiko')
def process_fan_status_netmiko(data):
    """H3C 风扇状态处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        fan_id = item.get('FanID', '') or item.get('fan_id', '')
        results.append(
            dict(
                chassis='',
                slot=item.get('Slot', '') or item.get('slot', ''),
                fan_id=fan_id,
                fan_name=f"Fan{fan_id}" if fan_id else '',
                present='',
                register_state='',
                status=item.get('State', '') or item.get('state', ''),
                speed='',
                mode='',
                airflow_direction=item.get('AirflowDirection', '') or item.get('airflowdirection', ''),
                prefer_airflow_direction=item.get('PreferAirflowDirection', '') or item.get('preferairflowdirection', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='power_status', method='netmiko')
def process_power_status_netmiko(data):
    """H3C 电源状态处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        power_id = item.get('PowerID', '') or item.get('power_id', '')
        results.append(
            dict(
                chassis='',
                slot=item.get('Slot', '') or item.get('slot', ''),
                power_id=power_id,
                power_name=f"Power{power_id}" if power_id else '',
                present='',
                status=item.get('State', '') or item.get('state', ''),
                mode=item.get('Mode', '') or item.get('mode', ''),
                current=item.get('Current', '') or item.get('current', ''),
                voltage=item.get('Voltage', '') or item.get('voltage', ''),
                output_power=item.get('Power', '') or item.get('power', ''),
            )
        )
    return results


@register_processor(vendor='H3C', device_type='', collection_type='clock_status', method='netmiko')
def process_clock_status_netmiko(data):
    """H3C 时钟状态处理 (Netmiko/TextFSM)"""
    results = []
    for item in data:
        month = str(item.get('MONTH', '') or item.get('month', '')).zfill(2)
        day = str(item.get('DAY', '') or item.get('day', '')).zfill(2)
        year = str(item.get('YEAR', '') or item.get('year', ''))
        device_time = item.get('TIME', '') or item.get('time', '')
        device_date = f"{year}-{month}-{day}" if year and month and day else ''
        device_datetime = f"{device_date} {device_time}" if device_date and device_time else ''
        results.append(
            dict(
                device_time=device_time,
                timezone=item.get('TIMEZONE', '') or item.get('timezone', ''),
                weekday=item.get('DAYWEEK', '') or item.get('dayweek', ''),
                device_date=device_date,
                device_datetime=device_datetime,
            )
        )
    return results


# ────────────────────────────────────────────────────────────
# Netmiko (TextFSM) 处理器
# 入参为 TextFSM 解析后的 list[dict]，字段名由 TextFSM 模板决定
# 注册时省略 device_type，通过 base.py 的兜底逻辑对所有设备类型生效
# ────────────────────────────────────────────────────────────

def _lookup_neighbor_ip(neighborsysname: str) -> str:
    """通过设备名查询 CMDB 管理 IP，先查 cache，再查 DB。"""
    if not neighborsysname:
        return ''
    try:
        cached = cache.get('cmdb_' + neighborsysname)
        if cached:
            return json.loads(cached)[0]['manage_ip']
        row = NetworkDevice.objects.filter(name=neighborsysname).values('manage_ip').first()
        return row['manage_ip'] if row else ''
    except Exception:
        return ''


@register_processor(vendor='H3C', device_type='', collection_type='arp', method='netmiko')
def process_arp_netmiko(data):
    """H3C ARP 表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：ipaddress, macaddress, aging, type, vlan, interface, vpninstance
    """
    result = []
    for i in data:
        result.append(dict(
            ipaddress=i.get('ipaddress', ''),
            macaddress=i.get('macaddress', ''),
            aging=i.get('aging', ''),
            type=i.get('type', ''),
            vlan=i.get('vlan', ''),
            interface=InterfaceFormat.h3c_interface_format(i.get('interface', '')),
            vpninstance=i.get('vpninstance', ''),
        ))
    return result


@register_processor(vendor='H3C', device_type='', collection_type='mac', method='netmiko')
def process_mac_netmiko(data):
    """H3C MAC 地址表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：macaddress, vlan, interface, type/state
    """
    result = []
    for i in data:
        result.append(dict(
            macaddress=i.get('macaddress', ''),
            vlan=i.get('vlan', ''),
            interface=InterfaceFormat.h3c_interface_format(i.get('interface', '')),
            type=i.get('type', '') or i.get('state', ''),
        ))
    return result


@register_processor(vendor='H3C', device_type='', collection_type='lldp', method='netmiko')
def process_lldp_netmiko(data):
    """H3C LLDP 邻居表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：local_interface, chassis_id, neighbor_port, portdescription,
                     neighborsysname, management_ip, management_type
    通过 CMDB 补充 neighbor_ip。
    """
    result = []
    for i in data:
        neighborsysname = i.get('neighborsysname', '')
        result.append(dict(
            local_interface=i.get('local_interface', ''),
            chassis_id=i.get('chassis_id', ''),
            neighbor_port=i.get('neighbor_port', ''),
            portdescription=i.get('portdescription', ''),
            neighborsysname=neighborsysname,
            management_ip=i.get('management_ip', ''),
            management_type=i.get('management_type', ''),
            neighbor_ip=_lookup_neighbor_ip(neighborsysname),
        ))
    return result


@register_processor(vendor='H3C', device_type='', collection_type='ip_interface', method='netmiko')
def process_ip_interface_netmiko(data):
    """H3C 三层接口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：intf, line_status, protocol_status, ipaddr（可为 list）,
                     ip_type（可为 list），mtu
    支持 CIDR（x.x.x.x/prefix）和纯 IP 两种格式，IP 可为列表（多地址接口）。
    """
    result = []
    for i in data:
        ipaddr = i.get('ipaddr', '')
        if isinstance(ipaddr, list):
            ip_type_list = i.get('ip_type', [])
            for idx, ip in enumerate(ipaddr):
                if not ip:
                    continue
                ip_type = ip_type_list[idx] if idx < len(ip_type_list) else ''
                if '/' in str(ip):
                    net = IPNetwork(ip)
                    location = [dict(start=net.first, end=net.last)]
                    result.append(dict(
                        interface=InterfaceFormat.h3c_interface_format(i.get('intf', '')),
                        line_status=i.get('line_status', ''),
                        protocol_status=i.get('protocol_status', ''),
                        ipaddress=net.ip.format(),
                        ipmask=net.netmask.format(),
                        ip_type=ip_type,
                        location=location,
                        mtu=i.get('mtu', ''),
                    ))
                else:
                    addr = IPAddress(ip)
                    location = [dict(start=addr.value, end=addr.value)]
                    result.append(dict(
                        interface=InterfaceFormat.h3c_interface_format(i.get('intf', '')),
                        line_status=i.get('line_status', ''),
                        protocol_status=i.get('protocol_status', ''),
                        ipaddress=addr.format(),
                        ipmask='255.255.255.255',
                        ip_type=ip_type,
                        location=location,
                        mtu=i.get('mtu', ''),
                    ))
        else:
            if not ipaddr:
                continue
            if '/' in str(ipaddr):
                net = IPNetwork(ipaddr)
                location = [dict(start=net.first, end=net.last)]
                result.append(dict(
                    interface=InterfaceFormat.h3c_interface_format(i.get('intf', '')),
                    line_status=i.get('line_status', ''),
                    protocol_status=i.get('protocol_status', ''),
                    ipaddress=net.ip.format(),
                    ipmask=net.netmask.format(),
                    ip_type=i.get('ip_type', ''),
                    location=location,
                    mtu=i.get('mtu', ''),
                ))
            else:
                addr = IPAddress(ipaddr)
                location = [dict(start=addr.value, end=addr.value)]
                result.append(dict(
                    interface=InterfaceFormat.h3c_interface_format(i.get('intf', '')),
                    line_status=i.get('line_status', ''),
                    protocol_status=i.get('protocol_status', ''),
                    ipaddress=addr.format(),
                    ipmask='255.255.255.255',
                    ip_type=i.get('ip_type', ''),
                    location=location,
                    mtu=i.get('mtu', ''),
                ))
    return result


@register_processor(vendor='H3C', device_type='', collection_type='interface_brief', method='netmiko')
def process_interface_brief_netmiko(data):
    """H3C 二层接口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：interface, status, speed, duplex, description
    过滤聚合口、Vlan 接口、Loopback 等逻辑接口，并规范化速率/双工字段。
    """
    result = []
    for i in data:
        interface = i.get('interface', '')
        if (interface.startswith('BAGG') or interface.startswith('RAGG')
                or interface.startswith('Vlan') or interface.startswith('Loop')
                or interface.startswith('InLoop')):
            continue

        speed = i.get('speed', '')
        duplex = i.get('duplex', '')

        if isinstance(speed, str):
            if '-' in speed:
                speed = 'IRF'
            elif '(' in speed:
                speed = speed.split('(')[0]

        if isinstance(duplex, str) and '-' in duplex:
            duplex = 'IRF'

        if speed == 'auto':
            speed = h3c_speed_format(interface)
        elif speed == 'UP':
            speed = h3c_speed_format(interface)
            duplex = '--'

        if speed:
            speed = InterfaceFormat.mathintspeed(speed)

        result.append(dict(
            interface=InterfaceFormat.h3c_interface_format(interface),
            status=i.get('status', ''),
            speed=speed,
            duplex=duplex,
            description=i.get('description', ''),
        ))
    return result


@register_processor(vendor='H3C', device_type='', collection_type='aggre_port', method='netmiko')
def process_aggre_port_netmiko(data):
    """H3C 聚合端口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：aggname, memberports（list）, status, mode
    """
    result = []
    for i in data:
        memberports = i.get('memberports', '')
        if isinstance(memberports, list):
            memberports = [
                InterfaceFormat.h3c_interface_format(_strip_irf_reference_suffix(m))
                for m in memberports
            ]
        result.append(dict(
            aggregroup=i.get('aggname', ''),
            memberports=memberports,
            status=i.get('status', ''),
            mode=i.get('mode', ''),
        ))
    return result
