import json
import re
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


def _find_first_mapping_with_any_keys(value, key_names):
    if isinstance(value, dict):
        if any(key in value for key in key_names):
            return value
        for child in value.values():
            found = _find_first_mapping_with_any_keys(child, key_names)
            if isinstance(found, dict):
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_mapping_with_any_keys(item, key_names)
            if isinstance(found, dict):
                return found
    return None


def _collect_values(value, key_name):
    values = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == key_name:
                if isinstance(child, list):
                    values.extend(
                        item for item in child if not isinstance(item, (dict, list))
                    )
                elif not isinstance(child, (dict, list)):
                    values.append(child)
            values.extend(_collect_values(child, key_name))
    elif isinstance(value, list):
        for item in value:
            values.extend(_collect_values(item, key_name))
    return values


def _collect_first_value(value, *key_names):
    for key_name in key_names:
        values = _collect_values(value, key_name)
        for item in values:
            text = str(item or "").strip()
            if text:
                return item
    return ""


def _pick_first(mapping, *key_names, default=""):
    if not isinstance(mapping, dict):
        return default
    for key_name in key_names:
        if key_name not in mapping:
            continue
        value = mapping.get(key_name)
        if isinstance(value, (dict, list)):
            if value:
                return value
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return value
    return default


def _normalize_speed_for_mathintspeed(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        numeric = int(text)
    except (TypeError, ValueError):
        return text
    if numeric >= 1000000:
        numeric = int(numeric / 1000000)
    return str(numeric)


def _infer_huawei_interface_speed(interface: str) -> str:
    text = str(interface or "").strip().upper()
    if not text:
        return ""
    patterns = (
        (r"^400GE", "400000"),
        (r"^200GE", "200000"),
        (r"^100GE", "100000"),
        (r"^50GE", "50000"),
        (r"^40GE", "40000"),
        (r"^25GE", "25000"),
        (r"^10GE", "10000"),
        (r"^XGE", "10000"),
        (r"^GE", "1000"),
        (r"^ETH-TRUNK", "0"),
        (r"^METH", "1000"),
    )
    for pattern, speed in patterns:
        if re.search(pattern, text):
            return speed
    return ""


def _normalize_huawei_interface(interface: str) -> str:
    if not interface:
        return ""
    if "." in interface:
        interface = interface.split(".")[0]
    return InterfaceFormat.huawei_interface_format(interface)


def _normalize_huawei_mac(mac_address: str) -> str:
    return (mac_address or "").lower()


def _normalize_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "up", "registered"}


def _build_huawei_mac_record(entry, *, vlan="", bd_id="", interface="", tunnel_type="", source_ip="", peer_ip="", vn_id=""):
    return dict(
        macaddress=_normalize_huawei_mac(entry.get("macAddress", "")),
        vlan=vlan,
        bd_id=bd_id,
        interface=_normalize_huawei_interface(interface),
        type=entry.get("macType", ""),
        tunnel_type=tunnel_type,
        source_ip=source_ip,
        peer_ip=peer_ip,
        vn_id=vn_id,
    )


def _build_ipv4_location(ip_address: str, ip_mask: str, prefix_length: str = ""):
    if not ip_address or ip_address == "0.0.0.0":
        return None
    if not ip_mask and prefix_length:
        ip_mask = str(IPNetwork(f"{ip_address}/{prefix_length}").netmask)
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


def _collect_netconf_schemas(data):
    if not isinstance(data, dict):
        return []
    records = _find_records(data, {"identifier", "namespace"})
    if records:
        return records
    schemas = ((data.get("netconf-state", {}) or {}).get("schemas", {}) or {}).get("schema")
    return [item for item in _as_list(schemas) if isinstance(item, dict)]


def _backfill_huawei_device_identity(device_ip: str, *, product_version: str = "", patch_version: str = "", model_name: str = ""):
    if not device_ip:
        return
    try:
        device = (
            NetworkDevice.objects.filter(manage_ip=device_ip)
            .select_related("vendor")
            .first()
        )
        if not device:
            return

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
        pass


def _extract_prefix_length(ipv4_entry):
    return _pick_first(ipv4_entry, "prefix-length", "prefixLength", "ip:prefix-length")


def _extract_huawei_ipv4_entries(entry):
    ipv4_entries = []

    ipv4_oper = entry.get("ipv4Oper", {}) or {}
    ipv4_addrs = (ipv4_oper.get("ipv4Addrs", {}) or {}).get("ipv4Addr")
    for addr in _as_list(ipv4_addrs):
        if not isinstance(addr, dict):
            continue
        ipv4_entries.append(
            dict(
                ip=_pick_first(addr, "ifIpAddr", "ip", "ip-address"),
                mask=_pick_first(addr, "subnetMask", "netmask", "mask"),
                prefix_length=_extract_prefix_length(addr),
                ip_type=_pick_first(addr, "addrType", "type", "ip-type", default=""),
            )
        )

    for key_name in ("ip:ipv4", "ipv4", "ietf-ip:ipv4", "urn3:ipv4"):
        ipv4_container = entry.get(key_name)
        if not isinstance(ipv4_container, dict):
            continue
        address = (
            ipv4_container.get("ip:address")
            or ipv4_container.get("address")
            or ipv4_container.get("ip-address")
            or ((ipv4_container.get("addresses") or {}).get("address"))
            or ((((ipv4_container.get("state") or {}).get("addresses")) or {}).get("address"))
        )
        for addr in _as_list(address):
            if not isinstance(addr, dict):
                continue
            ipv4_entries.append(
                dict(
                    ip=_pick_first(addr, "ip:ip", "ip", "ip-addr", "ip-address"),
                    mask=_pick_first(
                        addr,
                        "ip:netmask",
                        "netmask",
                        "mask",
                        "subnet-mask",
                    ),
                    prefix_length=_extract_prefix_length(addr),
                    ip_type=_pick_first(
                        addr,
                        "ip:type",
                        "type",
                        "addrType",
                        "ip-type",
                        default="ipv4",
                    ),
                )
            )

    return ipv4_entries


def _extract_huawei_vlan_mac_records(value, current_vlan=""):
    records = []
    if isinstance(value, dict):
        vlan_id = (
            _pick_first(value, "vlanId", "vlan-id", "vid")
            or current_vlan
        )
        mac_container = value.get("mac-addresss")
        if mac_container is not None:
            mac_items = mac_container
            if isinstance(mac_container, dict):
                mac_items = (
                    mac_container.get("mac-address")
                    or mac_container.get("mac-address-entry")
                    or mac_container.get("item")
                    or []
                )
            for item in _as_list(mac_items):
                if isinstance(item, dict):
                    record = dict(item)
                else:
                    record = {"mac-address": item}
                if vlan_id and not any(record.get(key) for key in ("vlanId", "vlan-id", "vid")):
                    record["vlan-id"] = vlan_id
                records.append(record)

        for child in value.values():
            records.extend(_extract_huawei_vlan_mac_records(child, vlan_id))
    elif isinstance(value, list):
        for item in value:
            records.extend(_extract_huawei_vlan_mac_records(item, current_vlan))
    return records


def _is_established(state: str) -> bool:
    text = str(state or "").strip().lower()
    return text in {"established", "estab", "up"} or "established" in text


def _normalize_vrf_name(vrf_name: str) -> str:
    value = str(vrf_name or "").strip()
    return "" if value == "_public_" else value


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        return default


def _collect_yunshan_bgp_instance_views(data):
    network_instance = data.get("network-instance", {}) or {}
    instances = _safe_list((network_instance.get("instances", {}) or {}).get("instance"))
    result = []
    for instance in instances:
        if not isinstance(instance, dict):
            continue
        bgp = instance.get("bgp", {}) or {}
        base_process = (bgp.get("base-process", {}) or {}) if isinstance(bgp, dict) else {}
        result.append(
            {
                "name": _pick_first(instance, "name"),
                "vrf": _normalize_vrf_name(_pick_first(instance, "name")),
                "base_process": base_process if isinstance(base_process, dict) else {},
            }
        )
    return result


def _collect_yunshan_bgp_summary_rows(data):
    rows = []
    for instance_view in _collect_yunshan_bgp_instance_views(data):
        base_process = instance_view["base_process"]
        peer_totals = _safe_list((base_process.get("peer-total-numbers", {}) or {}).get("peer-total-number"))
        for item in peer_totals:
            if not isinstance(item, dict):
                continue
            static_peer_number = _safe_int(_pick_first(item, "static-peer-number"))
            static_peer_established_number = _safe_int(
                _pick_first(item, "static-peer-established-number")
            )
            dynamic_peer_number = _safe_int(_pick_first(item, "dynamic-peer-number"))
            rows.append(
                {
                    "instance_name": instance_view["name"],
                    "vrf": instance_view["vrf"],
                    "af_type": _pick_first(item, "af-type"),
                    "static_peer_number": static_peer_number,
                    "static_peer_established_number": static_peer_established_number,
                    "dynamic_peer_number": dynamic_peer_number,
                    "total_peers": static_peer_number + dynamic_peer_number,
                    "established_peers": static_peer_established_number,
                }
            )
    return rows


def _dedupe_strings(values):
    ordered = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered


def _usg_port_range_dict(protocol: str, port_value) -> dict:
    text = str(port_value or "").strip()
    if not text:
        return {}
    normalized = text.replace(" to ", "-").replace(" ", "")
    parts = [part for part in normalized.split("-") if part]
    start = parts[0] if parts else text
    end = parts[-1] if len(parts) > 1 else start
    try:
        start_int = int(start)
        end_int = int(end)
    except (TypeError, ValueError):
        start_int = 0
        end_int = 0
    return {
        "start": start_int,
        "end": end_int,
        "protocol": protocol,
        "result": text,
    }


def _usg_address_items(container):
    items = []
    if not isinstance(container, dict):
        return items

    for value in _safe_list(container.get("address-ipv4")):
        if value:
            items.append({"ip": value})

    for value in _safe_list(container.get("address-set")):
        if value:
            items.append({"object": value})

    for range_item in _safe_list(container.get("address-ipv4-range")):
        if not isinstance(range_item, dict):
            continue
        start_ip = _pick_first(range_item, "start-ipv4")
        end_ip = _pick_first(range_item, "end-ipv4")
        if start_ip or end_ip:
            items.append({"range": f"{start_ip}-{end_ip}".strip("-")})

    for value in _safe_list(container.get("address-ipv4-exclude")):
        if value:
            items.append({"exclude_ip": value})

    for value in _safe_list(container.get("address-set-exclude")):
        if value:
            items.append({"exclude_object": value})

    for range_item in _safe_list(container.get("address-ipv4-range-exclude")):
        if not isinstance(range_item, dict):
            continue
        start_ip = _pick_first(range_item, "start-ipv4")
        end_ip = _pick_first(range_item, "end-ipv4")
        if start_ip or end_ip:
            items.append({"exclude_range": f"{start_ip}-{end_ip}".strip("-")})

    return items


def _usg_service_items(container):
    items = []
    if not isinstance(container, dict):
        return items

    for value in _safe_list(container.get("service-object")):
        if value:
            items.append({"object": value})

    service_items = container.get("service-items") or container.get("items") or {}
    if not isinstance(service_items, dict):
        return items

    for protocol in ("tcp", "udp"):
        for item in _safe_list(service_items.get(protocol)):
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "protocol": protocol,
                    "source_port": str(_pick_first(item, "source-port")),
                    "dest_port": str(_pick_first(item, "dest-port")),
                }
            )

    for item in _safe_list(service_items.get("icmp-item")):
        if isinstance(item, dict):
            items.append(
                {
                    "protocol": "icmp",
                    "icmp_type": _pick_first(item, "type"),
                    "icmp_code": _pick_first(item, "code"),
                }
            )
        else:
            items.append({"protocol": "icmp"})

    return items


def _usg_flatten_address_object_items(entry):
    elements = _safe_list(entry.get("elements"))
    items = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        items.extend(_usg_address_items(element))
    return items


def _usg_flatten_nat_address_sections(entry):
    sections = _safe_list(entry.get("section"))
    items = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        start_ip = _pick_first(section, "start-ip")
        end_ip = _pick_first(section, "end-ip")
        if start_ip or end_ip:
            items.append(f"{start_ip}-{end_ip}".strip("-"))
    return items


def _usg_make_ip_entry(value):
    value = str(value or "").strip()
    if not value:
        return dict(start="", end="", result="")
    try:
        if "/" in value:
            ip_net = IPNetwork(value)
            return dict(
                start=value,
                end=value,
                start_int=ip_net.first if ip_net.version == 4 else 0,
                end_int=ip_net.last if ip_net.version == 4 else 0,
                result=value,
            )
        ip_addr = IPAddress(value)
        return dict(
            start=value,
            end=value,
            start_int=ip_addr.value if len(str(ip_addr.value)) < 12 else 0,
            end_int=ip_addr.value if len(str(ip_addr.value)) < 12 else 0,
            result=value,
        )
    except Exception:
        return dict(start=value, end=value, result=value)


def _usg_make_range_entry(start, end):
    start = str(start or "").strip()
    end = str(end or "").strip()
    if not start or not end:
        return dict(start=start, end=end, result=f"{start}-{end}".strip("-"))
    try:
        return dict(
            start=start,
            end=end,
            start_int=IPAddress(start).value,
            end_int=IPAddress(end).value,
            result=f"{start}-{end}",
        )
    except Exception:
        return dict(start=start, end=end, result=f"{start}-{end}")


def _usg_build_address_object(entry, object_type):
    record = dict(
        vsys=_pick_first(entry, "vsys"),
        name=_pick_first(entry, "name"),
        description=_pick_first(entry, "desc", "description"),
        object_type=object_type,
        ip=[],
        range=[],
        exclude_ip=[],
        exclude_range=[],
        member=[],
        resolved=[],
        items=[],
    )
    containers = _safe_list(entry.get("elements")) or [entry]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for value in _safe_list(container.get("address-ipv4")):
            if value:
                record["ip"].append({"ip": value})
                record["items"].append({"ip": value})
        for value in _safe_list(container.get("address-set")):
            if value:
                record["member"].append({"name": value})
                record["items"].append({"object": value})
        for range_item in _safe_list(container.get("address-ipv4-range")):
            if not isinstance(range_item, dict):
                continue
            start_ip = _pick_first(range_item, "start-ipv4")
            end_ip = _pick_first(range_item, "end-ipv4")
            if start_ip or end_ip:
                record["range"].append({"start": start_ip, "end": end_ip})
                record["items"].append({"range": f"{start_ip}-{end_ip}".strip("-")})
        for value in _safe_list(container.get("address-ipv4-exclude")):
            if value:
                record["exclude_ip"].append({"ip": value})
                record["items"].append({"exclude_ip": value})
        for value in _safe_list(container.get("address-set-exclude")):
            if value:
                record["exclude_range"].append({"start": value, "end": value})
                record["items"].append({"exclude_object": value})
        for range_item in _safe_list(container.get("address-ipv4-range-exclude")):
            if not isinstance(range_item, dict):
                continue
            start_ip = _pick_first(range_item, "start-ipv4")
            end_ip = _pick_first(range_item, "end-ipv4")
            if start_ip or end_ip:
                record["exclude_range"].append({"start": start_ip, "end": end_ip})
                record["items"].append({"exclude_range": f"{start_ip}-{end_ip}".strip("-")})
    return record


def _usg_address_object_to_entries(address_obj, address_map, seen=None):
    seen = seen or set()
    name = address_obj.get("name", "")
    if name in seen:
        return []
    seen = set(seen)
    if name:
        seen.add(name)
    results = []
    for item in address_obj.get("ip", []):
        ip_value = item.get("ip", "")
        if ip_value:
            results.append(_usg_make_ip_entry(ip_value))
    for item in address_obj.get("range", []):
        start = item.get("start", "")
        end = item.get("end", "")
        if start or end:
            results.append(_usg_make_range_entry(start, end))
    for item in address_obj.get("member", []):
        member_name = item.get("name", "")
        member_obj = address_map.get(member_name)
        if member_obj:
            results.extend(_usg_address_object_to_entries(member_obj, address_map, seen=seen))
    return results


def _usg_resolve_policy_address_items(container, address_map=None):
    address_map = address_map or {}
    resolved = []
    for item in _usg_address_items(container):
        if not isinstance(item, dict):
            continue
        if item.get("object"):
            name = str(item.get("object") or "")
            address_obj = address_map.get(name)
            if address_obj:
                resolved.append(
                    dict(
                        name=name,
                        ip=list(address_obj.get("ip", [])),
                        range=list(address_obj.get("range", [])),
                        exclude_ip=list(address_obj.get("exclude_ip", [])),
                        exclude_range=list(address_obj.get("exclude_range", [])),
                        member=list(address_obj.get("member", [])),
                        resolved=_usg_address_object_to_entries(address_obj, address_map),
                    )
                )
            else:
                resolved.append(dict(name=name, raw=name, resolved=[dict(start=name, end=name, result=name)]))
        elif item.get("ip"):
            ip_value = str(item.get("ip") or "")
            resolved.append(dict(name="", raw=ip_value, resolved=[_usg_make_ip_entry(ip_value)]))
        elif item.get("range"):
            range_value = str(item.get("range") or "")
            start, _, end = range_value.partition("-")
            resolved.append(dict(name="", raw=range_value, resolved=[_usg_make_range_entry(start, end)]))
        elif item.get("exclude_ip"):
            ip_value = str(item.get("exclude_ip") or "")
            resolved.append(dict(name="", raw=ip_value, resolved=[_usg_make_ip_entry(ip_value)]))
        elif item.get("exclude_range"):
            range_value = str(item.get("exclude_range") or "")
            start, _, end = range_value.partition("-")
            resolved.append(dict(name="", raw=range_value, resolved=[_usg_make_range_entry(start, end)]))
    return resolved


def _usg_normalize_service_items(container):
    normalized = []
    service_items = (container.get("service-items") or container.get("items") or {}) if isinstance(container, dict) else {}
    if not isinstance(service_items, dict):
        return normalized
    for protocol in ("tcp", "udp"):
        for item in _safe_list(service_items.get(protocol)):
            if not isinstance(item, dict):
                continue
            service_item = {"protocol": protocol}
            source_port = str(_pick_first(item, "source-port") or "")
            dest_port = str(_pick_first(item, "dest-port") or "")
            if source_port:
                source_range = _usg_port_range_dict(protocol, source_port)
                service_item["src-port-min"] = source_range.get("start", 0)
                service_item["src-port-max"] = source_range.get("end", 0)
            if dest_port:
                dest_range = _usg_port_range_dict(protocol, dest_port)
                service_item["dst-port-min"] = dest_range.get("start", 0)
                service_item["dst-port-max"] = dest_range.get("end", 0)
            normalized.append(service_item)
    for item in _safe_list(service_items.get("icmp-item")):
        if isinstance(item, dict):
            normalized.append(
                {
                    "protocol": "icmp",
                    "type": _pick_first(item, "type"),
                    "code": _pick_first(item, "code"),
                }
            )
        else:
            normalized.append({"protocol": "icmp"})
    return normalized


def _usg_resolve_policy_service_items(container):
    resolved = []
    if not isinstance(container, dict):
        return resolved
    for value in _safe_list(container.get("service-object")):
        if value:
            token = str(value)
            resolved.append(
                {
                    "name": token,
                    "items": [{"start": token, "end": token, "protocol": token.lower(), "result": token}],
                }
            )
    for item in _usg_normalize_service_items(container):
        protocol = str(item.get("protocol") or "any").lower()
        if "dst-port-min" in item:
            start = item.get("dst-port-min", 0)
            end = item.get("dst-port-max", start)
            resolved.append(
                {
                    "name": "",
                    "items": [
                        {
                            "start": start,
                            "end": end,
                            "protocol": protocol,
                            "result": f"{start}-{end}" if start != end else str(start),
                        }
                    ],
                }
            )
        elif "type" in item:
            type_value = str(item.get("type") or "")
            code_value = str(item.get("code") or "").strip()
            result = f"type:{type_value}" if type_value else "Any"
            if code_value:
                result = f"{result} code:{code_value}"
            resolved.append(
                {
                    "name": "",
                    "items": [{"start": 0, "end": 65535, "protocol": protocol, "result": result}],
                }
            )
        else:
            resolved.append(
                {"name": "", "items": [{"start": 0, "end": 65535, "protocol": protocol, "result": "Any"}]}
            )
    return resolved


def _usg_service_summary(service_items):
    protocol = ""
    src_port_min = ""
    src_port_max = ""
    dst_port_min = ""
    dst_port_max = ""
    for item in service_items:
        if not isinstance(item, dict):
            continue
        protocol = protocol or str(item.get("protocol") or "")
        if "src-port-min" in item:
            src_port_min = src_port_min or item.get("src-port-min", "")
            src_port_max = src_port_max or item.get("src-port-max", "")
        if "dst-port-min" in item:
            dst_port_min = dst_port_min or item.get("dst-port-min", "")
            dst_port_max = dst_port_max or item.get("dst-port-max", "")
    return protocol, src_port_min, src_port_max, dst_port_min, dst_port_max


def _extract_usg_security_policy_rules(data):
    sec_policy = data.get("sec-policy", {}) or {}
    vsys_items = _safe_list(sec_policy.get("vsys"))
    rules = []
    for vsys in vsys_items:
        if not isinstance(vsys, dict):
            continue
        static_policy = vsys.get("static-policy", {}) or {}
        for rule in _safe_list(static_policy.get("rule")):
            if isinstance(rule, dict):
                rules.append((vsys, rule))
    return rules


def _extract_usg_nat_policy_rules(data):
    nat_policy = data.get("nat-policy", {}) or {}
    vsys_items = _safe_list(nat_policy.get("vsys"))
    rules = []
    for vsys in vsys_items:
        if not isinstance(vsys, dict):
            continue
        for rule in _safe_list(vsys.get("rule")):
            if isinstance(rule, dict):
                rules.append((vsys, rule))
    return rules


def _extract_usg_nat_server_rules(data):
    nat_server = data.get("nat-server", {}) or {}
    return [item for item in _safe_list(nat_server.get("server-mapping")) if isinstance(item, dict)]


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

    _backfill_huawei_device_identity(
        device_ip,
        product_version=product_version,
        patch_version=patch_version,
        model_name=model_name,
    )

    return data


@register_processor(
    vendor="Huawei", device_type="", collection_type="version", method="netconf"
)
def process_version_netconf(data):
    """Huawei collection_system_info 处理 (NETCONF)。"""
    device_ip = ""
    if isinstance(data, dict):
        device_ip = str(data.get("_resolve_device_ip", "") or "")
    records = _find_records(data, {"sysName", "platformVer", "productName"})
    if records:
        record = records[0]
    else:
        candidate = _find_first_mapping_with_any_keys(
            data,
            {
                "sysName",
                "host-name",
                "hostname",
                "productName",
                "product-name",
                "model",
                "platformVer",
                "software-version",
                "version",
                "esn",
                "serial-number",
            },
        )
        if not isinstance(candidate, dict):
            return []
        record = candidate

    hostname = _pick_first(record, "sysName", "host-name", "hostname", "hostName")
    if not hostname:
        hostname = _pick_first(record, "sys-name")
    platform_name = _pick_first(
        record,
        "platform-name",
        "platformName",
    ) or _collect_first_value(
        data,
        "platform-name",
        "platformName",
    )
    product_name = _pick_first(
        record,
        "product-name",
        "productName",
    ) or _collect_first_value(
        data,
        "product-name",
        "productName",
    )
    model_name = _pick_first(
        record,
        "hardware-model",
        "productName",
        "product-name",
        "productModel",
        "product-model",
        "model",
        "device-model",
        "deviceType",
        "device-type",
    ) or _collect_first_value(
        data,
        "hardware-model",
        "productName",
        "product-name",
        "productModel",
        "product-model",
        "model",
        "device-model",
        "deviceType",
        "device-type",
    )
    soft_version = _pick_first(
        record,
        "product-version",
        "productVersion",
        "platformVer",
        "platform-version",
        "software-version",
        "softwareVersion",
        "softVersion",
        "version",
    ) or _collect_first_value(
        data,
        "product-version",
        "productVersion",
        "platformVer",
        "platform-version",
        "software-version",
        "softwareVersion",
        "softVersion",
        "version",
    )
    patch_version = _pick_first(
        record,
        "patchVer",
        "patch-version",
        "patchVersion",
    ) or _collect_first_value(data, "patchVer", "patch-version", "patchVersion")
    serial_num = _pick_first(
        record,
        "esn",
        "serial-number",
        "serialNumber",
        "serialNum",
    ) or _collect_first_value(data, "esn", "serial-number", "serialNumber", "serialNum")

    if not any((hostname, model_name, soft_version, serial_num)):
        return []
    _backfill_huawei_device_identity(
        device_ip,
        product_version=soft_version,
        patch_version=patch_version,
        model_name=model_name,
    )
    return [
        dict(
            hostname=hostname,
            vendor_alias="Huawei",
            platform_name=platform_name,
            product_name=product_name,
            model_name=model_name,
            soft_version=soft_version,
            patch_version=patch_version,
            serial_num=serial_num,
        )
    ]


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
    vendor="Huawei", device_type="", collection_type="board_status", method="netconf"
)
def process_board_status_netconf(data):
    """Huawei collection_moduleinfo 处理 (NETCONF)。"""
    results = []
    entries = _find_records(data, {"position", "entSerialNum"})
    for entry in entries:
        ent_class = str(entry.get("entClass", "")).strip()
        results.append(
            dict(
                slot=entry.get("position", ""),
                board_name=ent_class or "module",
                board_model=ent_class or "module",
                serial_num=entry.get("entSerialNum", ""),
                status=ent_class,
                slot_type=ent_class.lower(),
            )
        )

    devm = data.get("devm", {}) if isinstance(data, dict) else {}
    yunshan_board_sets = (
        ("mpu-boards", "mpu-board", "mpu"),
        ("lpu-boards", "lpu-board", "lpu"),
        ("sfu-boards", "sfu-board", "sfu"),
    )
    for container_name, list_name, slot_type in yunshan_board_sets:
        boards = ((devm.get(container_name, {}) or {}).get(list_name))
        for entry in _as_list(boards):
            if not isinstance(entry, dict):
                continue
            board_type = _pick_first(entry, "board-type", "service-type", default=slot_type.upper())
            status = "registered" if _normalize_truthy(entry.get("is-register")) else ""
            results.append(
                dict(
                    slot=_pick_first(entry, "position"),
                    board_name=board_type,
                    board_model=board_type,
                    serial_num=_pick_first(entry, "serial-number", "serialNumber"),
                    status=status,
                    slot_type=slot_type,
                )
            )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="stack_status", method="netconf"
)
def process_stack_status_netconf(data):
    """Huawei collection_stack 处理 (NETCONF)。"""
    entries = _find_records(data, {"memberID", "role"})
    results = []
    for entry in entries:
        results.append(
            dict(
                member_id=entry.get("memberID", ""),
                slot=entry.get("memberID", ""),
                role=entry.get("role", ""),
                priority=entry.get("priority", ""),
                mac=entry.get("mac", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="route_table", method="netconf"
)
def process_route_table_netconf(data):
    """Huawei 路由表处理 (NETCONF)

    当前优先解析 IETF routing 视图下的静态 IPv4 路由。
    若设备仅返回静态路由，也照常输出为 route_table 的一部分。
    """
    result = []

    routing = data.get("routing", {}) or {}
    instances = _as_list(routing.get("routing-instance"))
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

    network_instance = data.get("network-instance", {}) or {}
    yunshan_instances = _as_list(((network_instance.get("instances", {}) or {}).get("instance")))
    for instance in yunshan_instances:
        instance_name = _pick_first(instance, "name")
        afs = _as_list(((instance.get("afs", {}) or {}).get("af")))
        for af in afs:
            af_type = _pick_first(af, "type")
            if af_type not in {"ipv4-unicast", ""}:
                continue
            routing = af.get("routing", {}) or {}
            topologies_container = ((routing.get("routing-manage", {}) or {}).get("topologys", {}) or {})
            topologies = _as_list(topologies_container.get("topology"))
            for topology in topologies:
                topology_name = _pick_first(topology, "name")
                routes_container = ((topology.get("routes", {}) or {}).get("ipv4-unicast-routes", {}) or {})
                routes = _as_list(routes_container.get("ipv4-unicast-route"))
                for route in routes:
                    prefix = _pick_first(route, "prefix")
                    mask_length = _pick_first(route, "mask-length")
                    route_prefix = f"{prefix}/{mask_length}" if prefix and mask_length != "" else prefix
                    result.append(
                        dict(
                            prefix=route_prefix,
                            next_hop=_pick_first(route, "nexthop", "direct-nexthop"),
                            interface=_normalize_huawei_interface(
                                _pick_first(route, "nexthop-interface-name", "interface-name")
                            ),
                            protocol=_pick_first(route, "protocol-type"),
                            protocol_id=_pick_first(route, "protocol-type"),
                            sub_protocol_id=_pick_first(route, "sub-protocol-type"),
                            process_id=_pick_first(route, "process-id"),
                            preference=_pick_first(route, "preference"),
                            metric=_pick_first(route, "cost", default="0"),
                            vrf="" if instance_name == "_public_" else instance_name,
                            topology=topology_name,
                            neighbor=_pick_first(route, "neighbour", "neighbor"),
                            age=_pick_first(route, "age"),
                            origin_as="",
                            last_as="",
                        )
                    )

    return result


@register_processor(
    vendor="Huawei", device_type="", collection_type="netconf_capability", method="netconf"
)
def process_netconf_capability_netconf(data):
    schemas = _collect_netconf_schemas(data)
    identifiers = [str(item.get("identifier") or "") for item in schemas if isinstance(item, dict)]
    namespaces = [str(item.get("namespace") or "") for item in schemas if isinstance(item, dict)]
    combined = identifiers + namespaces
    return [
        dict(
            schema_count=len(schemas),
            openconfig_schema_count=sum(1 for item in identifiers if item.startswith("openconfig-")),
            has_bgp_schema=any("bgp" in item.lower() for item in combined),
            has_l2vpn_schema=any(any(keyword in item.lower() for keyword in ("l2vpn", "vsi", "evpn")) for item in combined),
            has_ifmgr_schema=any(any(keyword in item.lower() for keyword in ("ifm", "interface")) for item in combined),
            has_telemetry_schema=any("telemetry" in item.lower() for item in combined),
            schema_samples=[item for item in identifiers[:10] if item],
        )
    ]


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

    if result:
        return result

    summary_rows = _collect_yunshan_bgp_summary_rows(data)
    summary_by_instance = {}
    for row in summary_rows:
        summary_by_instance.setdefault(row["instance_name"], []).append(row)

    for instance_view in _collect_yunshan_bgp_instance_views(data):
        base_process = instance_view["base_process"]
        peer_states = _safe_list((base_process.get("peer-states", {}) or {}).get("peer-state"))
        if peer_states:
            for peer in peer_states:
                if not isinstance(peer, dict):
                    continue
                result.append(
                    dict(
                        peer_ip=_pick_first(peer, "address"),
                        address_family=_pick_first(peer, "af-type"),
                        vrf=instance_view["vrf"],
                        remote_as=_pick_first(peer, "remote-as"),
                        state=_pick_first(peer, "peer-state", "connection-state", "session-state", "state"),
                        peer_group=_pick_first(peer, "group-name"),
                        remote_router_id=_pick_first(peer, "remote-router-id"),
                        peer_type=_pick_first(peer, "establish-mode"),
                        connect_interface="",
                        update_interval="",
                        ebgp_max_hop="",
                    )
                )
            continue

        peers = _safe_list((base_process.get("peers", {}) or {}).get("peer"))
        if not peers:
            continue

        instance_summaries = summary_by_instance.get(instance_view["name"], [])
        inferred_af = ""
        inferred_state = ""
        if len(instance_summaries) == 1:
            summary = instance_summaries[0]
            inferred_af = summary["af_type"]
            if summary["static_peer_number"] > 0 and summary["static_peer_number"] == summary["static_peer_established_number"]:
                inferred_state = "Established"

        for peer in peers:
            if not isinstance(peer, dict):
                continue
            result.append(
                dict(
                    peer_ip=_pick_first(peer, "address"),
                    address_family=inferred_af,
                    vrf=instance_view["vrf"],
                    remote_as=_pick_first(peer, "remote-as"),
                    state=inferred_state,
                    peer_group=_pick_first(peer, "group-name"),
                    remote_router_id="",
                    peer_type="static",
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

    if not grouped:
        for row in _collect_yunshan_bgp_summary_rows(data):
            key = (row["vrf"], row["af_type"])
            item = grouped.setdefault(
                key,
                {
                    "address_family": row["af_type"],
                    "vrf": row["vrf"],
                    "total_peers": 0,
                    "established_peers": 0,
                    "non_established_peers": 0,
                    "states": {},
                },
            )
            total_peers = row["total_peers"]
            established_peers = min(row["established_peers"], total_peers)
            non_established_peers = max(total_peers - established_peers, 0)
            item["total_peers"] += total_peers
            item["established_peers"] += established_peers
            item["non_established_peers"] += non_established_peers
            if total_peers:
                if non_established_peers == 0:
                    dominant_state = "Established"
                elif established_peers == 0:
                    dominant_state = "NonEstablished"
                else:
                    dominant_state = "Mixed"
                item["states"][dominant_state] = item["states"].get(dominant_state, 0) + total_peers

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
    entries.extend(_find_records(data, {"ip-addr", "if-name"}))
    results = []
    for entry in entries:
        results.append(
            dict(
                ipaddress=_pick_first(entry, "ipAddr", "ip-addr", "ipaddress"),
                macaddress=_normalize_huawei_mac(
                    _pick_first(entry, "macAddr", "mac-addr", "macAddress")
                ),
                vlan=_pick_first(entry, "peVid", "vlanId", "vlan-id"),
                interface=_normalize_huawei_interface(
                    _pick_first(entry, "ifName", "if-name", "outIfName", "out-if-name")
                ),
                type=_pick_first(entry, "styleType", "style-type", "type"),
                aging=_pick_first(entry, "expireTime", "age"),
                vpninstance=_pick_first(entry, "vrfName", "vrf-name", "ni-name"),
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
    entries.extend(_find_records(data, {"mac-address"}))
    entries.extend(_find_records(data, {"address", "vlan-id"}))
    entries.extend(_extract_huawei_vlan_mac_records(data))
    results = []
    seen = {}
    for entry in entries:
        if _pick_first(entry, "vnId", "vn-id"):
            continue
        vlan = _pick_first(entry, "vlanId", "vlan-id", "vid")
        interface = _pick_first(
            entry,
            "outIfName",
            "out-if-name",
            "out-interface-name",
            "ifName",
            "if-name",
        )
        mac_type = _pick_first(entry, "macType", "mac-type", "type")
        mac_address = _pick_first(entry, "macAddress", "mac-address", "address")
        if isinstance(vlan, (list, dict)):
            vlan = _collect_first_value(entry, "vlanId", "vlan-id", "vid")
        if isinstance(interface, (list, dict)):
            interface = _collect_first_value(
                entry,
                "outIfName",
                "out-if-name",
                "out-interface-name",
                "ifName",
                "if-name",
            )
        if isinstance(mac_type, (list, dict)):
            mac_type = _collect_first_value(entry, "macType", "mac-type", "type")
        if isinstance(mac_address, (list, dict)):
            mac_address = _collect_first_value(entry, "macAddress", "mac-address", "address")
        if not mac_address or not any((vlan, interface, mac_type)):
            continue
        record = _build_huawei_mac_record(
            {
                "macAddress": mac_address,
                "macType": mac_type,
            },
            vlan=vlan or "-",
            interface=interface,
        )
        dedupe_key = (
            record["macaddress"],
            record["interface"],
            record["type"],
            record["bd_id"],
            record["vn_id"],
            record["source_ip"],
            record["peer_ip"],
        )
        existing_index = seen.get(dedupe_key)
        if existing_index is None:
            seen[dedupe_key] = len(results)
            results.append(record)
            continue
        existing_record = results[existing_index]
        if existing_record.get("vlan") in {"", "-"} and record.get("vlan") not in {"", "-"}:
            results[existing_index] = record
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac_bd", method="netconf"
)
def process_mac_bd_netconf(data):
    """Huawei BD MAC 地址表处理 (NETCONF)。"""
    entries = _find_records(data, {"macAddress", "bdId"})
    results = []
    for entry in entries:
        if entry.get("vnId"):
            continue
        if not any(entry.get(key) for key in ("bdId", "outIfName", "macType", "vid")):
            continue
        results.append(
            _build_huawei_mac_record(
                entry,
                vlan=entry.get("vid", "") or "-",
                bd_id=entry.get("bdId", ""),
                interface=entry.get("outIfName", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac_vxlan", method="netconf"
)
def process_mac_vxlan_netconf(data):
    """Huawei VXLAN 数据面 MAC 地址表处理 (NETCONF)。"""
    entries = _find_records(data, {"macAddress", "bdId", "vnId"})
    results = []
    for entry in entries:
        if not any(entry.get(key) for key in ("sourceIP", "peerIP", "vnId", "tunnelType")):
            continue
        results.append(
            _build_huawei_mac_record(
                entry,
                bd_id=entry.get("bdId", ""),
                tunnel_type=entry.get("tunnelType", ""),
                source_ip=entry.get("sourceIP", ""),
                peer_ip=entry.get("peerIP", ""),
                vn_id=entry.get("vnId", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="mac_vxlan_control", method="netconf"
)
def process_mac_vxlan_control_netconf(data):
    """Huawei VXLAN 控制面 MAC 地址表处理 (NETCONF)。"""
    entries = _find_records(data, {"macAddress", "bdId", "vnId"})
    results = []
    for entry in entries:
        if not any(entry.get(key) for key in ("sourceIpv6", "peerIpv6", "vnId", "tunnelType")):
            continue
        results.append(
            _build_huawei_mac_record(
                entry,
                bd_id=entry.get("bdId", ""),
                tunnel_type=entry.get("tunnelType", ""),
                source_ip=entry.get("sourceIpv6", "") or entry.get("sourceIP", ""),
                peer_ip=entry.get("peerIpv6", "") or entry.get("peerIP", ""),
                vn_id=entry.get("vnId", ""),
            )
        )
    return results


@register_processor(
    vendor="Huawei", device_type="", collection_type="vxlan_capability", method="netconf"
)
def process_vxlan_capability_netconf(data):
    """Huawei VXLAN/BD/EVPN 配置能力探测 (NETCONF get_config)。"""
    bd_ids = _dedupe_strings(_collect_values(data, "bdId"))
    if not bd_ids and isinstance(data, dict):
        feil3bd = data.get("feil3bd", {}) or {}
        bd_ids = _dedupe_strings(_collect_values(feil3bd, "bdId") + _collect_values(feil3bd, "id"))
    vnis = [
        item
        for item in _dedupe_strings(
            _collect_values(data, "vni") + _collect_values(data, "vnId") + _collect_values(data, "vniId")
        )
        if item not in {"0"}
    ]
    vxlan_section = data.get("vxlan", {}) if isinstance(data, dict) else {}
    nve_ids = [
        item
        for item in _dedupe_strings(_collect_values(vxlan_section, "nveIfName") + _collect_values(vxlan_section, "ifName"))
        if item.upper() != "NULL0"
    ]
    af_types = _dedupe_strings(_collect_values(data, "afType"))
    evpn_afs = [item for item in af_types if "evpn" in item.lower()]
    vrfs = _dedupe_strings(_collect_values(data, "vrfName"))

    evidence = []
    if bd_ids:
        evidence.append("bridge-domain")
    if vnis:
        evidence.append("vxlan-vni")
    if nve_ids:
        evidence.append("nve")
    if evpn_afs:
        evidence.append("bgp-evpn")

    return [
        dict(
            has_bd=bool(bd_ids),
            bd_count=len(bd_ids),
            bd_ids=bd_ids,
            has_vxlan_vni=bool(vnis),
            vni_count=len(vnis),
            vnis=vnis,
            has_nve=bool(nve_ids),
            nve_ids=nve_ids,
            has_evpn_bgp=bool(evpn_afs),
            evpn_af_count=len(evpn_afs),
            vrfs=vrfs,
            evidence=evidence,
        )
    ]


@register_processor(
    vendor="Huawei", device_type="", collection_type="ip_interface", method="netconf"
)
def process_ip_interface_netconf(data):
    """Huawei 三层接口处理 (NETCONF)

    兼容 `intf_ipv4v6` 和 USG `ip:ipv4` 两类旧 Huawei NETCONF 结构。
    """
    interface_entries = _find_records(data, {"ifName"})
    interface_entries.extend(_find_records(data, {"name", "ip:ipv4"}))
    interface_entries.extend(_find_records(data, {"name", "ipv4"}))
    interface_entries.extend(_find_records(data, {"name", "ietf-ip:ipv4"}))
    interface_entries.extend(_find_records(data, {"name", "urn3:ipv4"}))

    results = []
    for entry in interface_entries:
        interface_name = _pick_first(entry, "ifName", "name", "if-name")
        if not interface_name:
            continue
        dynamic = entry.get("ifDynamicInfo", {}) or {}
        line_status = _pick_first(
            dynamic,
            "ifLinkStatus",
            "ifOperStatus",
            default=_pick_first(entry, "oper-status", "admin-status"),
        )
        protocol_status = _pick_first(
            dynamic,
            "ifV4State",
            "ifOperStatus",
            default=_pick_first(entry, "admin-status", "oper-status"),
        )
        mtu = _pick_first(dynamic, "ifOpertMTU", default=_pick_first(entry, "mtu", "ip-mtu"))

        ipv4_entries = _extract_huawei_ipv4_entries(entry)
        for ipv4_entry in ipv4_entries:
            location_payload = _build_ipv4_location(
                ipv4_entry.get("ip", ""),
                ipv4_entry.get("mask", ""),
                ipv4_entry.get("prefix_length", ""),
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
    vendor="Huawei", device_type="", collection_type="interface_brief", method="netconf"
)
def process_interface_brief_netconf(data):
    """Huawei collection_intf_ipv4v6 处理二层接口 (NETCONF)。"""
    interface_entries = _find_records(data, {"ifName"})
    interface_entries.extend(_find_records(data, {"name"}))
    results = []
    seen = set()
    for entry in interface_entries:
        if_name = _pick_first(entry, "ifName", "name", "if-name")
        if not if_name or if_name in seen:
            continue
        seen.add(if_name)
        if (
            if_name.startswith("Tunnel")
            or if_name.startswith("Stack-Port")
            or if_name.startswith("MEth")
            or if_name.startswith("Vbdif")
            or if_name.startswith("Vlanif")
            or if_name.startswith("Eth-Trunk")
        ):
            continue
        dynamic = entry.get("ifDynamicInfo", {}) or {}
        speed = _pick_first(dynamic, "ifOperSpeed", default=_pick_first(entry, "speed", "if-speed", "bandwidth"))
        if not speed:
            speed = _infer_huawei_interface_speed(if_name)
        if not speed:
            continue
        results.append(
            dict(
                interface=_normalize_huawei_interface(if_name),
                status=_pick_first(dynamic, "ifOperStatus", "ifLinkStatus", default=_pick_first(entry, "oper-status", "admin-status")),
                speed=InterfaceFormat.mathintspeed(_normalize_speed_for_mathintspeed(speed)),
                duplex=_pick_first(entry, "duplex"),
                description=_pick_first(entry, "description", "desc"),
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
    entries.extend(_find_records(data, {"name", "lldp"}))
    results = []
    for entry in entries:
        local_interface = _pick_first(entry, "ifName", "name")
        neighbor_items = []

        legacy_neighbors = entry.get("lldpNeighbors", {})
        legacy_neighbor = (legacy_neighbors or {}).get("lldpNeighbor")
        neighbor_items.extend([item for item in _as_list(legacy_neighbor) if isinstance(item, dict)])

        session_neighbors = (((entry.get("lldp", {}) or {}).get("session", {}) or {}).get("neighbors", {}) or {}).get("neighbor")
        neighbor_items.extend([item for item in _as_list(session_neighbors) if isinstance(item, dict)])

        for neighbor in neighbor_items:
            port_id_sub_type = _pick_first(neighbor, "portIdSubtype", "port-id-sub-type")
            if str(port_id_sub_type).lower() == "macaddress":
                continue

            management_ip = ""
            management_type = ""
            management_addresses = ((neighbor.get("managementAddresss", {}) or {}).get("managementAddress"))
            for address in _as_list(management_addresses):
                if not isinstance(address, dict):
                    continue
                address_type = _pick_first(address, "manAddrSubtype", "type")
                address_value = _pick_first(address, "manAddr", "value")
                if address_type == "ipv4" or not management_ip:
                    management_ip = address_value
                    management_type = address_type
                    if management_type == "ipv4":
                        break

            neighborsysname = _pick_first(neighbor, "systemName", "system-name")
            results.append(
                dict(
                    local_interface=_normalize_huawei_interface(local_interface),
                    chassis_id=_pick_first(neighbor, "chassisId", "chassis-id"),
                    neighbor_port=_pick_first(neighbor, "portId", "port-id"),
                    portdescription=_pick_first(neighbor, "portDescription", "port-description"),
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
    entries.extend(_find_records(data, {"name", "trunk"}))
    results = []
    for entry in entries:
        memberports = []
        memberstatus = []
        aggregroup = _pick_first(entry, "ifName", "name")
        mode = _pick_first(entry, "workMode", "mode")

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

        trunk = entry.get("trunk", {}) or {}
        mode = mode or _pick_first(trunk, "work-mode")
        if isinstance(trunk, dict):
            members = ((trunk.get("members", {}) or {}).get("member"))
            for member in _as_list(members):
                if not isinstance(member, dict):
                    continue
                member_name = _pick_first(member, "name")
                if member_name:
                    memberports.append(_normalize_huawei_interface(member_name))
                state = _pick_first(member, "status")
                if state:
                    memberstatus.append(state)

        if not (
            str(aggregroup).startswith("Eth-Trunk")
            or entry.get("TrunkMemberIfs") is not None
            or isinstance(entry.get("trunk"), dict)
        ):
            continue

        results.append(
            dict(
                aggregroup=aggregroup,
                memberports=_dedupe_strings(memberports),
                status=",".join(_dedupe_strings(memberstatus)),
                mode=mode,
            )
        )
    return results


@register_processor(vendor="Huawei", device_type="", collection_type="hrp_state", method="netconf")
def process_hrp_state_netconf(data):
    hrp_state = data.get("hrp-state", {}) or {}
    if not isinstance(hrp_state, dict) or not hrp_state:
        return []
    switch_info = hrp_state.get("hrp-switch-info", {}) or {}
    return [
        dict(
            ha_state=_pick_first(hrp_state, "hrp-status"),
            peer_status=_pick_first(hrp_state, "peer-status"),
            heartbeat_status=_pick_first(hrp_state, "heartbeat-status"),
            config_master=_pick_first(hrp_state, "config-master"),
            switch_id=_pick_first(switch_info, "id"),
            switch_time=_pick_first(switch_info, "time"),
            switch_reason=_pick_first(switch_info, "reason", "description"),
        )
    ]


@register_processor(vendor="Huawei", device_type="", collection_type="address_set", method="netconf")
def process_address_set_netconf(data):
    address_set = data.get("address-set", {}) or {}
    records = []
    address_map = {}
    for key_name, object_type in (("addr-object", "address_object"), ("addr-group", "address_group")):
        for entry in _safe_list(address_set.get(key_name)):
            if not isinstance(entry, dict):
                continue
            record = _usg_build_address_object(entry, object_type)
            address_map[record.get("name")] = record
            records.append(record)
    for record in records:
        record["resolved"] = _usg_address_object_to_entries(record, address_map)
        record["element_count"] = len(record["resolved"])
    return records


@register_processor(vendor="Huawei", device_type="", collection_type="nat_address", method="netconf")
def process_nat_address_netconf(data):
    nat_address_group = data.get("nat-address-group", {}) or {}
    records = []
    for entry in _safe_list(nat_address_group.get("nat-address-group")):
        if not isinstance(entry, dict):
            continue
        items = _usg_flatten_nat_address_sections(entry)
        records.append(
            dict(
                name=_pick_first(entry, "name"),
                vsys=_pick_first(entry, "vsys"),
                address_type=_pick_first(entry, "address-type", "type"),
                section_count=len(items),
                items=items,
            )
        )
    return records


@register_processor(vendor="Huawei", device_type="", collection_type="service_set", method="netconf")
def process_service_set_netconf(data):
    service_set = data.get("service-set", {}) or {}
    records = []
    for key_name in ("service-object", "pre-defined-service"):
        for entry in _safe_list(service_set.get(key_name)):
            if not isinstance(entry, dict):
                continue
            items = _usg_normalize_service_items(entry)
            protocol, src_port_min, src_port_max, dst_port_min, dst_port_max = _usg_service_summary(items)
            records.append(
                dict(
                    vsys=_pick_first(entry, "vsys"),
                    name=_pick_first(entry, "name"),
                    description=_pick_first(entry, "desc", "description"),
                    protocol=protocol,
                    src_port_min=src_port_min,
                    src_port_max=src_port_max,
                    dst_port_min=dst_port_min,
                    dst_port_max=dst_port_max,
                    items=items,
                )
            )
    return records


@register_processor(vendor="Huawei", device_type="", collection_type="slb_info", method="netconf")
def process_slb_info_netconf(data):
    slb = data.get("slb", {}) or {}
    records = []
    for entry in _safe_list(slb.get("slb-pool")):
        if not isinstance(entry, dict):
            continue
        members = []
        for member in _safe_list(entry.get("real-server")):
            if isinstance(member, dict):
                members.append(_pick_first(member, "name", "ip", "address"))
        records.append(
            dict(
                name=_pick_first(entry, "name"),
                slb_type="pool",
                vip="",
                protocol=_pick_first(entry, "protocol"),
                port=_pick_first(entry, "port"),
                description=_pick_first(entry, "desc", "description"),
                items=_dedupe_strings(members),
            )
        )

    for entry in _safe_list(slb.get("slb-loadbalancer")):
        if not isinstance(entry, dict):
            continue
        refs = []
        for ref in _safe_list(entry.get("bind-pool")):
            if isinstance(ref, dict):
                refs.append(_pick_first(ref, "name"))
            elif ref:
                refs.append(str(ref))
        records.append(
            dict(
                name=_pick_first(entry, "name"),
                slb_type="virtual_server",
                vip=_pick_first(entry, "virtual-ip", "ip", "address"),
                protocol=_pick_first(entry, "protocol"),
                port=_pick_first(entry, "port"),
                description=_pick_first(entry, "desc", "description"),
                items=_dedupe_strings(refs),
            )
        )
    return records


@register_processor(vendor="Huawei", device_type="", collection_type="vrrp_info", method="netconf")
def process_vrrp_info_netconf(data):
    vrrp = data.get("vrrp", {}) or {}
    result = []
    for entry in _safe_list(vrrp.get("vrrp-instance")):
        if not isinstance(entry, dict):
            continue
        vrrp4 = entry.get("vrrp4", {}) or {}
        virtual_ip_raw = _pick_first(vrrp4, "virtual-ip")
        virtual_ip = virtual_ip_raw
        ipmask = "255.255.255.255"
        if isinstance(virtual_ip_raw, str) and " " in virtual_ip_raw:
            parts = [part for part in virtual_ip_raw.split() if part]
            virtual_ip = parts[0]
            if len(parts) > 1:
                ipmask = parts[1]
        result.append(
            dict(
                interface=_normalize_huawei_interface(_pick_first(entry, "interface-name")),
                vrid=_pick_first(entry, "vrid", "id"),
                virtual_ip=virtual_ip,
                ipmask=ipmask,
                priority=_pick_first(vrrp4, "priority"),
                preempt_mode=_pick_first(vrrp4, "preempt-mode"),
                admin_state=_pick_first(vrrp4, "admin-state"),
                config_state=_pick_first(vrrp4, "config-state"),
            )
        )
    return result


@register_processor(vendor="Huawei", device_type="", collection_type="security_policy", method="netconf")
def process_security_policy_netconf(data):
    result = []
    for _vsys, rule in _extract_usg_security_policy_rules(data):
        source_items = _usg_resolve_policy_address_items(rule.get("source-ip", {}) or {})
        destination_items = _usg_resolve_policy_address_items(rule.get("destination-ip", {}) or {})
        service_items = _usg_resolve_policy_service_items(rule.get("service", {}) or {})
        result.append(
            dict(
                rule_id=_pick_first(rule, "name", "id"),
                name=_pick_first(rule, "name"),
                action="permit" if _normalize_truthy(_pick_first(rule, "action")) else "deny",
                src_zone=_pick_first(rule, "source-zone"),
                dst_zone=_pick_first(rule, "destination-zone"),
                src_addr=source_items,
                dst_addr=destination_items,
                service=service_items,
                logs=_dedupe_strings(
                    [
                        _pick_first(rule, "log", "log-flag"),
                        _pick_first(rule, "session-log"),
                    ]
                ),
                description=_pick_first(rule, "desc", "description"),
                count=_pick_first(rule, "hit-times"),
                disabled=not _normalize_truthy(_pick_first(rule, "enable", default="true")),
            )
        )
    return result


@register_processor(vendor="Huawei", device_type="", collection_type="snat", method="netconf")
def process_snat_netconf(data):
    result = []
    for _vsys, rule in _extract_usg_nat_policy_rules(data):
        trans_ip = []
        nat_group = _pick_first(rule, "nat-address-group")
        if nat_group:
            trans_ip.append({"object": nat_group})
        if _pick_first(rule, "action") == "easyip":
            trans_ip.append({"object": "easyip"})

        destination_port = []
        for item in _usg_service_items(rule.get("service", {}) or {}):
            if not isinstance(item, dict):
                continue
            protocol = str(item.get("protocol") or item.get("object") or "")
            if item.get("dest_port"):
                destination_port.append(_usg_port_range_dict(protocol or "tcp", item["dest_port"]))
            elif item.get("object"):
                destination_port.append({"start": 0, "end": 0, "protocol": protocol, "result": item["object"]})

        result.append(
            dict(
                rule_id=_pick_first(rule, "name", "id"),
                trans_ip=trans_ip,
                local_ip=_usg_address_items(rule.get("source-ip", {}) or {}),
                local_exclude_ip=[],
                destination_ip=_usg_address_items(rule.get("destination-ip", {}) or {}),
                destination_port=[item for item in destination_port if item],
                mode=_pick_first(rule, "action"),
                source_zone=_pick_first(rule, "source-zone"),
                destination_zone=_pick_first(rule, "destination-zone"),
                egress_interface=_pick_first(rule, "egress-interface"),
                description=_pick_first(rule, "description", "desc"),
                disabled=not _normalize_truthy(_pick_first(rule, "enable", default="true")),
                track=_pick_first(rule, "no-reverse"),
            )
        )
    return result


@register_processor(vendor="Huawei", device_type="", collection_type="dnat", method="netconf")
def process_dnat_netconf(data):
    protocol_map = {
        "1": "icmp",
        "6": "tcp",
        "17": "udp",
    }
    result = []
    for rule in _extract_usg_nat_server_rules(data):
        protocol = protocol_map.get(str(_pick_first(rule, "protocol")), str(_pick_first(rule, "protocol") or "any"))
        global_info = rule.get("global", {}) or {}
        inside_info = rule.get("inside", {}) or {}
        global_ip = _pick_first(global_info, "start-ip")
        local_ip = _pick_first(inside_info, "start-ip")
        global_port = _pick_first(rule.get("global-port", {}) or {}, "start-port")
        local_port = _pick_first(rule.get("inside-port", {}) or {}, "start-port")
        global_port_item = (
            _usg_port_range_dict(protocol, global_port)
            if global_port
            else {"start": 0, "end": 65535, "protocol": protocol, "result": "0-65535"}
        )
        local_port_item = (
            _usg_port_range_dict(protocol, local_port)
            if local_port
            else {"start": 0, "end": 65535, "protocol": protocol, "result": "0-65535"}
        )
        result.append(
            dict(
                rule_id=_pick_first(rule, "name", "id"),
                global_ip=[{"start": global_ip, "end": global_ip, "result": global_ip}] if global_ip else [],
                global_port=[global_port_item],
                local_ip=[{"start": local_ip, "end": local_ip, "result": local_ip}] if local_ip else [],
                local_port=[local_port_item],
                ingress_interface=_pick_first(global_info, "if-type", "interface-name"),
                from_zone="",
                to_zone="",
                description=_pick_first(rule, "description", "desc"),
                disabled=not _normalize_truthy(_pick_first(rule, "enable", default="true")),
                track=_pick_first(rule, "no-reverse"),
            )
        )
    return result
