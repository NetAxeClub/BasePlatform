import re
import math
import json
from netaddr import IPNetwork, IPAddress
from .base import register_processor
from apps.automation.tools.base_connection import InterfaceFormat
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

    TODO: 解析 data['top']['ARP']['ARPTable']['ARPEntry']
          注意：单条记录时 ncclient 返回 dict 而非 list，需做 isinstance 兼容处理
          输出字段：ipaddress, macaddress, vlan, interface, type, aging, vpninstance
    """
    top = data['top']
    ifindex_map = _build_ifindex_map(top)
    arp_entries = top.get('ARP', {}).get('ArpTable', {}).get('ArpEntry', [])
    if isinstance(arp_entries, dict):
        arp_entries = [arp_entries]
    arp_datas = []
    for entry in arp_entries:
        ifindex = str(entry.get('IfIndex', ''))
        interface_name = ifindex_map.get(ifindex, ifindex)
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


@register_processor(vendor='H3C', device_type='', collection_type='mac', method='netconf')
def process_mac_netconf(data):
    """H3C 交换机 MAC 地址表处理 (NETCONF)

    TODO: 解析 H3C MAC 地址表 XML 结构
          输出字段：macaddress（aabb-ccdd-eeff 格式）, vlan, interface, type
    """
    # TODO: 实现 H3C NETCONF MAC 地址表解析
    raise NotImplementedError("H3C NETCONF MAC 地址表处理器待实现")


@register_processor(vendor='H3C', device_type='', collection_type='ip_interface', method='netconf')
def process_ip_interface_netconf(data):
    """H3C 交换机三层接口处理 (NETCONF)

    TODO: 解析三层接口信息，含 IP/掩码提取，调用 IPNetwork 计算 location 字段
          输出字段：interface, line_status, protocol_status, ipaddress, ipmask,
                   ip_type, mtu, location
    """
    # TODO: 实现 H3C NETCONF 三层接口解析
    raise NotImplementedError("H3C NETCONF 三层接口处理器待实现")


@register_processor(vendor='H3C', device_type='', collection_type='lldp', method='netconf')
def process_lldp_netconf(data):
    """H3C 交换机 LLDP 邻居表处理 (NETCONF)

    TODO: 解析 LLDP 邻居信息，保留通过 CMDB 查询补充 neighbor_ip 的逻辑
          输出字段：local_interface, chassis_id, neighbor_port, portdescription,
                   neighborsysname, management_ip, management_type, neighbor_ip
    """
    # TODO: 实现 H3C NETCONF LLDP 邻居解析
    raise NotImplementedError("H3C NETCONF LLDP 邻居处理器待实现")


@register_processor(vendor='H3C', device_type='', collection_type='aggre_port', method='netconf')
def process_aggre_port_netconf(data):
    """H3C 交换机聚合端口处理 (NETCONF)

    TODO: 解析聚合端口及其成员端口列表
          输出字段：aggregroup, memberports（list，接口名已规范化）, status, mode
    """
    # TODO: 实现 H3C NETCONF 聚合端口解析
    raise NotImplementedError("H3C NETCONF 聚合端口处理器待实现")


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
            memberports = [InterfaceFormat.h3c_interface_format(m) for m in memberports]
        result.append(dict(
            aggregroup=i.get('aggname', ''),
            memberports=memberports,
            status=i.get('status', ''),
            mode=i.get('mode', ''),
        ))
    return result
