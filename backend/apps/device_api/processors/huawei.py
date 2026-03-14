import json
from netaddr import IPNetwork
from .base import register_processor
from apps.automation.tools.base_connection import InterfaceFormat
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

    TODO: 解析 Huawei yang 模型的 ARP XML 结构
          输出字段：ipaddress, macaddress, vlan, interface, type, aging, vpninstance
    """
    raise NotImplementedError("Huawei NETCONF ARP 处理器待实现")


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac", method="netconf"
)
def process_mac_netconf(data):
    """Huawei MAC 地址表处理 (NETCONF)

    TODO: 解析 Huawei yang 模型的 MAC XML 结构
          输出字段：macaddress（统一格式）, vlan, interface, type
    """
    raise NotImplementedError("Huawei NETCONF MAC 地址表处理器待实现")


@register_processor(
    vendor="Huawei", device_type="", collection_type="ip_interface", method="netconf"
)
def process_ip_interface_netconf(data):
    """Huawei 三层接口处理 (NETCONF)

    TODO: 解析 Huawei yang 模型的三层接口 XML 结构，含 IP/掩码提取
          输出字段：interface, line_status, protocol_status, ipaddress, ipmask, ip_type, mtu, location
    """
    raise NotImplementedError("Huawei NETCONF 三层接口处理器待实现")


@register_processor(
    vendor="Huawei", device_type="", collection_type="lldp", method="netconf"
)
def process_lldp_netconf(data):
    """Huawei LLDP 邻居表处理 (NETCONF)

    TODO: 解析 Huawei yang 模型的 LLDP XML 结构，保留 CMDB 查询 neighbor_ip 逻辑
          输出字段：local_interface, chassis_id, neighbor_port, portdescription,
                   neighborsysname, management_ip, management_type, neighbor_ip
    """
    raise NotImplementedError("Huawei NETCONF LLDP 邻居处理器待实现")


@register_processor(
    vendor="Huawei", device_type="", collection_type="aggre_port", method="netconf"
)
def process_aggre_port_netconf(data):
    """Huawei 聚合端口处理 (NETCONF)

    TODO: 解析 Huawei yang 模型的聚合端口 XML 结构
          输出字段：aggregroup, memberports（list）, status, mode
    """
    raise NotImplementedError("Huawei NETCONF 聚合端口处理器待实现")
