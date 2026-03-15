import json
from netaddr import IPAddress, IPNetwork
from .base import register_processor
from apps.device_api.common import InterfaceFormat
from django.core.cache import cache
from apps.asset.models import NetworkDevice, Model


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _lookup_neighbor_ip(neighborsysname: str) -> str:
    """通过设备名查询 CMDB 管理 IP，先查 cache，再查 DB。"""
    if not neighborsysname:
        return ""
    try:
        cached = cache.get("cmdb_" + neighborsysname)
        if cached:
            return json.loads(cached)[0]["manage_ip"]
        row = (
            NetworkDevice.objects.filter(name=neighborsysname)
            .values("manage_ip")
            .first()
        )
        return row["manage_ip"] if row else ""
    except Exception:
        return ""


def _safe_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_records(value, required_keys):
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


def _normalize_huawei_interface(interface: str) -> str:
    if not interface:
        return ""
    if "." in interface:
        interface = interface.split(".")[0]
    return InterfaceFormat.huawei_interface_format(interface)


def _normalize_huawei_mac(mac_address: str) -> str:
    return (mac_address or "").lower()


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


def _is_established(state: str) -> bool:
    text = str(state or "").strip().lower()
    return text in {"established", "estab", "up"} or "established" in text


# ────────────────────────────────────────────────────────────
# Netmiko (TextFSM) 处理器
# 注册时省略 device_type，通过 base.py 的兜底逻辑对所有设备类型生效
# ────────────────────────────────────────────────────────────


@register_processor(
    vendor="Huawei", device_type="", collection_type="arp", method="netmiko"
)
def process_arp_netmiko(data):
    """Huawei ARP 表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：ipaddress, macaddress, aging, type, vlan, interface, vpninstance
    """
    result = []
    for i in data:
        interface = i.get("interface", "")
        # 去掉子接口编号（如 GE0/0/0.1 → GE0/0/0）
        if "." in interface:
            interface = interface.split(".")[0]
        result.append(
            dict(
                ipaddress=i.get("ipaddress", ""),
                macaddress=i.get("macaddress", ""),
                aging=i.get("aging", ""),
                type=i.get("type", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.huawei_interface_format(interface),
                vpninstance=i.get("vpninstance", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="version", method="netmiko"
)
def process_version_netmiko(data):
    """Huawei display version 表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：vrp_version, product_version, patch_version, model, uptime
    将 product_version 回填 NetworkDevice.soft_version，patch_version 回填 patch_version，
    model 在 Model 表中查询或新建后回填 NetworkDevice.model。
    调用方会在首条记录注入 _resolve_device_ip 用于定位设备。
    """
    if not data or not isinstance(data, list):
        return data or []
    record = data[0] if isinstance(data[0], dict) else {}
    device_ip = record.pop("_resolve_device_ip", None)
    product_version = (record.get("product_version") or "").strip()
    patch_version = (record.get("patch_version") or "").strip()
    model_name = (record.get("model") or "").strip()

    if device_ip:
        try:
            device = (
                NetworkDevice.objects.filter(manage_ip=device_ip)
                .select_related("vendor")
                .first()
            )
            if device:
                update_fields = []
                if product_version:
                    device.soft_version = product_version
                    update_fields.append("soft_version")
                if patch_version:
                    device.patch_version = patch_version
                    update_fields.append("patch_version")
                if model_name:
                    vendor = device.vendor
                    model_obj, _ = Model.objects.get_or_create(
                        name=model_name, vendor=vendor, defaults={"vendor": vendor}
                    )
                    device.model = model_obj
                    update_fields.append("model")
                if update_fields:
                    device.save(update_fields=update_fields)
        except Exception:
            pass  # 回填失败不影响采集结果返回

    return data


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac", method="netmiko"
)
def process_mac_netmiko(data):
    """Huawei MAC 地址表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：macaddress, vlan, interface, type
    """
    result = []
    for i in data:
        result.append(
            dict(
                macaddress=i.get("macaddress", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.huawei_interface_format(
                    i.get("interface", "")
                ),
                type=i.get("type", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="lldp", method="netmiko"
)
def process_lldp_netmiko(data):
    """Huawei LLDP 邻居表处理 (Netmiko/TextFSM)

    TextFSM 输出字段：local_interface, chassis_id, neighbor_port, portdescription,
                     neighborsysname, management_ip, management_type
    通过 CMDB 补充 neighbor_ip。
    """
    result = []
    for i in data:
        neighborsysname = i.get("neighborsysname", "")
        result.append(
            dict(
                local_interface=i.get("local_interface", ""),
                chassis_id=i.get("chassis_id", ""),
                neighbor_port=i.get("neighbor_port", ""),
                portdescription=i.get("portdescription", ""),
                neighborsysname=neighborsysname,
                management_ip=i.get("management_ip", ""),
                management_type=i.get("management_type", ""),
                neighbor_ip=_lookup_neighbor_ip(neighborsysname),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="ip_interface", method="netmiko"
)
def process_ip_interface_netmiko(data):
    """Huawei 三层接口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：interface, line_status, protocol_status, internet_address（CIDR 格式）
    """
    result = []
    for i in data:
        internet_address = i.get("internet_address", "")
        if not internet_address:
            continue
        net = IPNetwork(internet_address)
        location = [dict(start=net.first, end=net.last)]
        result.append(
            dict(
                interface=i.get("interface", ""),
                line_status=i.get("line_status", ""),
                protocol_status=i.get("protocol_status", ""),
                ipaddress=net.ip.format(),
                ipmask=net.netmask.format(),
                ip_type="Primary",
                location=location,
                mtu="",
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="interface_brief", method="netmiko"
)
def process_interface_brief_netmiko(data):
    """Huawei 二层接口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：interface, status, speed, duplex, description
    过滤 LoopBack、NULL、Vlanif、Ethernet0/0/0 等管理/逻辑接口。
    """
    result = []
    for i in data:
        interface = i.get("interface", "")
        if (
            interface.startswith("LoopBack")
            or interface.startswith("NULL")
            or interface.startswith("Vlanif")
            or interface.startswith("Ethernet0/0/0")
        ):
            continue
        result.append(
            dict(
                interface=interface,
                status=i.get("status", ""),
                speed=InterfaceFormat.mathintspeed(i.get("speed", "")),
                duplex=i.get("duplex", ""),
                description=i.get("description", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="aggre_port", method="netmiko"
)
def process_aggre_port_netmiko(data):
    """Huawei 聚合端口处理 (Netmiko/TextFSM)

    TextFSM 输出字段：aggregroup/trunk_num, portname/memberports（list）, status/portstatus, mode
    """
    result = []
    for i in data:
        if isinstance(i.get("portname"), list):
            memberports = list(i["portname"])
        else:
            memberports = i.get("memberports", [])
        result.append(
            dict(
                aggregroup=i.get("aggregroup", "") or i.get("trunk_num", ""),
                memberports=memberports,
                status=i.get("status", "") or i.get("portstatus", ""),
                mode=i.get("mode", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="fan_status", method="netmiko"
)
def process_fan_status_netmiko(data):
    """Huawei 风扇状态处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        fan_id = item.get("FanID", "") or item.get("fan_id", "")
        result.append(
            dict(
                chassis=item.get("Chassis", "") or item.get("chassis", ""),
                slot=item.get("Slot", "") or item.get("slot", ""),
                fan_id=fan_id,
                fan_name=item.get("FanNUM", "") or item.get("fan_num", "") or f"FAN{fan_id}",
                present=item.get("Present", "") or item.get("present", ""),
                register_state=item.get("Register", "") or item.get("register", ""),
                status=item.get("Present", "") or item.get("present", ""),
                speed=item.get("Speed", "") or item.get("speed", ""),
                mode=item.get("Mode", "") or item.get("mode", ""),
                airflow_direction="",
                prefer_airflow_direction="",
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="power_status", method="netmiko"
)
def process_power_status_netmiko(data):
    """Huawei 电源状态处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        result.append(
            dict(
                chassis=item.get("Chassis", "") or item.get("chassis", ""),
                slot=item.get("Slot", "") or item.get("slot", ""),
                power_id=item.get("PowerNo", "") or item.get("power_no", ""),
                power_name=item.get("PowerNo", "") or item.get("power_no", ""),
                present=item.get("Present", "") or item.get("present", ""),
                status=item.get("State", "") or item.get("state", ""),
                mode=item.get("Mode", "") or item.get("mode", ""),
                current=item.get("Current", "") or item.get("current", ""),
                voltage=item.get("Voltage", "") or item.get("voltage", ""),
                output_power=item.get("RealPwr", "") or item.get("real_pwr", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="temperature_status", method="netmiko"
)
def process_temperature_status_netmiko(data):
    """Huawei 温度状态处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        result.append(
            dict(
                chassis="",
                slot=item.get("SLOTID", "") or item.get("slotid", ""),
                sensor=item.get("PCB", "") or item.get("pcb", ""),
                status=item.get("STATUS", "") or item.get("status", ""),
                temperature=item.get("TEMPERATURE", "") or item.get("temperature", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="route_table", method="netconf"
)
def process_route_table_netconf(data):
    """Huawei 路由表处理 (NETCONF)

    当前优先解析 IETF routing 视图下的静态 IPv4 路由。
    若设备仅返回静态路由，也照常输出为 route_table 的一部分。
    """
    routing = data.get("routing", {}) or {}
    instances = _as_list(routing.get("routing-instance"))
    result = []

    for instance in instances:
        instance_name = instance.get("name", "")
        protocols = instance.get("routing-protocols", {}) or {}
        routing_protocols = _as_list(protocols.get("routing-protocol"))
        for protocol in routing_protocols:
            static_routes = protocol.get("static-routes", {}) or {}
            ipv4_container = static_routes.get("v4ur:ipv4", {}) or {}
            routes = _as_list(ipv4_container.get("v4ur:route"))
            for route in routes:
                next_hop = (
                    (route.get("v4ur:next-hop", {}) or {}).get("v4ur:next-hop-address", "")
                )
                result.append(
                    dict(
                        prefix=route.get("v4ur:destination-prefix", ""),
                        next_hop=next_hop,
                        interface="",
                        protocol="static",
                        protocol_id="static",
                        sub_protocol_id="",
                        process_id="",
                        preference=route.get("hw-v4sr:preference", ""),
                        metric="0",
                        vrf="" if instance_name == "_public_" else instance_name,
                        topology="",
                        neighbor="",
                        age="",
                        origin_as="",
                        last_as="",
                    )
                )

    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="bgp_neighbors", method="netconf"
)
def process_bgp_neighbors_netconf(data):
    """Huawei BGP 邻居处理 (NETCONF)

    解析 `bgp.bgpcomm.bgpVrfs.bgpVrf.bgpVrfAFs.bgpVrfAF.peerAFs.peerAF`
    的运行状态信息。
    """
    bgp = data.get("bgp", {}) or {}
    bgpcomm = bgp.get("bgpcomm", {}) or {}
    vrfs = _safe_list((bgpcomm.get("bgpVrfs", {}) or {}).get("bgpVrf"))

    result = []
    for vrf in vrfs:
        vrf_name = vrf.get("vrfName", "")
        afs = _safe_list((vrf.get("bgpVrfAFs", {}) or {}).get("bgpVrfAF"))
        for af in afs:
            af_type = af.get("afType", "")
            peers = _safe_list((af.get("peerAFs", {}) or {}).get("peerAF"))
            for peer in peers:
                peer_info = peer.get("peerInfo", {}) or {}
                result.append(
                    dict(
                        peer_ip=peer.get("remoteAddress", ""),
                        address_family=af_type,
                        vrf="" if vrf_name == "_public_" else vrf_name,
                        remote_as="",
                        state=peer_info.get("bgpCurState", ""),
                        peer_group="",
                        remote_router_id=peer_info.get("remoteRouterId", ""),
                        peer_type=peer_info.get("peerType", ""),
                        connect_interface="",
                        update_interval="",
                        ebgp_max_hop="",
                    )
                )

    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="bgp_summary", method="netconf"
)
def process_bgp_summary_netconf(data):
    """Huawei BGP 汇总处理 (NETCONF)

    基于 `bgpVrfAF.peerAFs.peerAF` 按 `vrf + afType` 聚合邻居状态。
    """
    bgp = data.get("bgp", {}) or {}
    bgpcomm = bgp.get("bgpcomm", {}) or {}
    vrfs = _safe_list((bgpcomm.get("bgpVrfs", {}) or {}).get("bgpVrf"))

    grouped = {}
    for vrf in vrfs:
        vrf_name = "" if vrf.get("vrfName", "") == "_public_" else vrf.get("vrfName", "")
        afs = _safe_list((vrf.get("bgpVrfAFs", {}) or {}).get("bgpVrfAF"))
        for af in afs:
            af_type = af.get("afType", "")
            key = (vrf_name, af_type)
            item = grouped.setdefault(
                key,
                {
                    "address_family": af_type,
                    "vrf": vrf_name,
                    "total_peers": 0,
                    "established_peers": 0,
                    "non_established_peers": 0,
                    "states": {},
                },
            )
            peers = _safe_list((af.get("peerAFs", {}) or {}).get("peerAF"))
            for peer in peers:
                peer_info = peer.get("peerInfo", {}) or {}
                state = peer_info.get("bgpCurState", "")
                item["total_peers"] += 1
                if _is_established(state):
                    item["established_peers"] += 1
                else:
                    item["non_established_peers"] += 1
                item["states"][state] = item["states"].get(state, 0) + 1

    result = []
    for item in grouped.values():
        dominant_state = ""
        if item["states"]:
            dominant_state = sorted(item["states"].items(), key=lambda kv: kv[1], reverse=True)[0][0]
        result.append(
            dict(
                address_family=item["address_family"],
                vrf=item["vrf"],
                total_peers=item["total_peers"],
                established_peers=item["established_peers"],
                non_established_peers=item["non_established_peers"],
                dominant_state=dominant_state,
            )
        )

    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="ospf_neighbors", method="netmiko"
)
def process_ospf_neighbors_netmiko(data):
    """Huawei OSPF 邻居处理 (Netmiko/TextFSM)

    当前基于 `display ospf peer brief` 的简表输出。
    """
    result = []
    for item in data:
        result.append(
            dict(
                area=item.get("area_id", ""),
                local_interface=item.get("interface", ""),
                neighbor_router_id=item.get("neighbor_id", ""),
                neighbor_ip=item.get("neighbor_ip", ""),
                state=item.get("state", ""),
                priority=item.get("priority", ""),
                dead_time=item.get("dead_time", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="ospf_interfaces", method="netmiko"
)
def process_ospf_interfaces_netmiko(data):
    """Huawei OSPF 接口处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        result.append(
            dict(
                area=item.get("area", ""),
                local_interface=item.get("interface", ""),
                interface_ip=item.get("interface_ip", ""),
                network_type=item.get("network_type", ""),
                state=item.get("state", ""),
                cost=item.get("cost", ""),
                priority=item.get("priority", ""),
                dr=item.get("dr", ""),
                bdr=item.get("bdr", ""),
                hello_interval=item.get("hello_interval", ""),
                dead_interval=item.get("dead_interval", ""),
            )
        )
    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="isis_neighbors", method="netmiko"
)
def process_isis_neighbors_netmiko(data):
    """Huawei ISIS 邻居处理 (Netmiko/TextFSM)"""
    result = []
    for item in data:
        peer_ip_raw = item.get("peer_ip", "")
        peer_ip = str(peer_ip_raw).split()[0] if peer_ip_raw else ""
        result.append(
            dict(
                system_id=item.get("system_id", ""),
                local_interface=item.get("local_interface", ""),
                circuit_id=item.get("circuit_id", ""),
                state=item.get("state", ""),
                hold_time=item.get("hold_time", ""),
                neighbor_type=item.get("neighbor_type", ""),
                priority=item.get("priority", ""),
                area=item.get("area", ""),
                peer_ip=peer_ip,
                uptime=item.get("uptime", ""),
            )
        )
    return result


# ────────────────────────────────────────────────────────────
# NETCONF 处理器（待实现）
# ────────────────────────────────────────────────────────────


@register_processor(
    vendor="Huawei", device_type="", collection_type="arp", method="netconf"
)
def process_arp_netconf(data):
    """Huawei ARP 表处理 (NETCONF)

    优先兼容旧 Huawei NETCONF `arp_list` 结构。
    """
    entries = _find_records(data, {"ipAddr", "ifName"})
    results = []
    for entry in entries:
        results.append(
            dict(
                ipaddress=entry.get("ipAddr", ""),
                macaddress=_normalize_huawei_mac(entry.get("macAddr", "")),
                vlan=entry.get("peVid", ""),
                interface=_normalize_huawei_interface(entry.get("ifName", "")),
                type=entry.get("styleType", ""),
                aging=entry.get("expireTime", ""),
                vpninstance=entry.get("vrfName", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac", method="netconf"
)
def process_mac_netconf(data):
    """Huawei MAC 地址表处理 (NETCONF)

    兼容 `mac_table` 和 `mac_bd` 两类旧 Huawei NETCONF 结构。
    """
    entries = _find_records(data, {"macAddress"})
    results = []
    for entry in entries:
        if not any(entry.get(key) for key in ("vlanId", "bdId", "outIfName", "macType")):
            continue
        results.append(
            dict(
                macaddress=_normalize_huawei_mac(entry.get("macAddress", "")),
                vlan=entry.get("vlanId", "") or entry.get("bdId", "") or "-",
                interface=_normalize_huawei_interface(entry.get("outIfName", "")),
                type=entry.get("macType", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="ip_interface", method="netconf"
)
def process_ip_interface_netconf(data):
    """Huawei 三层接口处理 (NETCONF)

    兼容 `intf_ipv4v6` 和 USG `ip:ipv4` 两类旧 Huawei NETCONF 结构。
    """
    interface_entries = _find_records(data, {"ifName"})
    interface_entries.extend(_find_records(data, {"name", "ip:ipv4"}))

    results = []
    for entry in interface_entries:
        interface_name = entry.get("ifName", "") or entry.get("name", "")
        line_status = ((entry.get("ifDynamicInfo", {}) or {}).get("ifLinkStatus", ""))
        protocol_status = ((entry.get("ifDynamicInfo", {}) or {}).get("ifV4State", ""))
        mtu = ((entry.get("ifDynamicInfo", {}) or {}).get("ifOpertMTU", ""))

        ipv4_entries = []
        ipv4_oper = entry.get("ipv4Oper", {}) or {}
        ipv4_addrs = (ipv4_oper.get("ipv4Addrs", {}) or {}).get("ipv4Addr")
        for addr in _as_list(ipv4_addrs):
            if not isinstance(addr, dict):
                continue
            ipv4_entries.append(
                dict(
                    ip=addr.get("ifIpAddr", ""),
                    mask=addr.get("subnetMask", ""),
                    ip_type=addr.get("addrType", ""),
                )
            )

        if not ipv4_entries and entry.get("ip:ipv4"):
            address = ((entry.get("ip:ipv4", {}) or {}).get("ip:address", {}))
            for addr in _as_list(address):
                if not isinstance(addr, dict):
                    continue
                ipv4_entries.append(
                    dict(
                        ip=addr.get("ip:ip", ""),
                        mask=addr.get("ip:netmask", ""),
                        ip_type="ipv4",
                    )
                )

        for ipv4_entry in ipv4_entries:
            location_payload = _build_ipv4_location(
                ipv4_entry.get("ip", ""),
                ipv4_entry.get("mask", ""),
            )
            if not location_payload:
                continue
            results.append(
                dict(
                    interface=_normalize_huawei_interface(interface_name),
                    line_status=line_status,
                    protocol_status=protocol_status,
                    ipaddress=location_payload["ipaddress"],
                    ipmask=location_payload["ipmask"],
                    ip_type=ipv4_entry.get("ip_type", ""),
                    mtu=mtu,
                    location=location_payload["location"],
                )
            )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="lldp", method="netconf"
)
def process_lldp_netconf(data):
    """Huawei LLDP 邻居表处理 (NETCONF)

    优先兼容旧 Huawei NETCONF `lldp` 结构。
    """
    entries = _find_records(data, {"ifName"})
    results = []
    for entry in entries:
        neighbors = entry.get("lldpNeighbors", {})
        neighbor = (neighbors or {}).get("lldpNeighbor")
        if not isinstance(neighbor, dict):
            continue
        if neighbor.get("portIdSubtype") == "macAddress":
            continue

        management_ip = ""
        management_type = ""
        management_addresses = ((neighbor.get("managementAddresss", {}) or {}).get("managementAddress"))
        for address in _as_list(management_addresses):
            if not isinstance(address, dict):
                continue
            if address.get("manAddrSubtype") == "ipv4" or not management_ip:
                management_ip = address.get("manAddr", "")
                management_type = address.get("manAddrSubtype", "")
                if management_type == "ipv4":
                    break

        neighborsysname = neighbor.get("systemName", "")
        results.append(
            dict(
                local_interface=_normalize_huawei_interface(entry.get("ifName", "")),
                chassis_id=neighbor.get("chassisId", ""),
                neighbor_port=neighbor.get("portId", ""),
                portdescription=neighbor.get("portDescription", ""),
                neighborsysname=neighborsysname,
                management_ip=management_ip,
                management_type=management_type,
                neighbor_ip=_lookup_neighbor_ip(neighborsysname),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="aggre_port", method="netconf"
)
def process_aggre_port_netconf(data):
    """Huawei 聚合端口处理 (NETCONF)

    兼容旧 Huawei NETCONF `trunk_lacp` / `aggregation` 结构。
    """
    entries = _find_records(data, {"ifName"})
    results = []
    for entry in entries:
        if not (
            str(entry.get("ifName", "")).startswith("Eth-Trunk")
            or entry.get("TrunkMemberIfs") is not None
        ):
            continue

        memberports = []
        memberstatus = []
        trunk_members = ((entry.get("TrunkMemberIfs", {}) or {}).get("TrunkMemberIf"))
        for member in _as_list(trunk_members):
            if not isinstance(member, dict):
                continue
            member_name = member.get("memberIfName", "")
            if member_name:
                memberports.append(_normalize_huawei_interface(member_name))
            state = member.get("memberIfState", "")
            if state:
                memberstatus.append(state)

        results.append(
            dict(
                aggregroup=entry.get("ifName", ""),
                memberports=memberports,
                status=",".join(memberstatus),
                mode=entry.get("workMode", "") or entry.get("mode", ""),
            )
        )
    return results
