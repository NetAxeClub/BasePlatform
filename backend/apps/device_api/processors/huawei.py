import json
from netaddr import IPNetwork
from .base import register_processor
from apps.automation.tools.base_connection import InterfaceFormat
from django.core.cache import cache
from apps.asset.models import NetworkDevice, Model


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
