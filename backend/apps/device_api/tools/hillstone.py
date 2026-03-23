import io
import re
from pathlib import Path

import textfsm
from netaddr import IPAddress, IPNetwork, valid_ipv4

from apps.asset.models import Model, NetworkDevice, Vendor
from apps.device_api import (
    ip_interface_mongo,
    policy_hit_count_mongo,
    service_predefined_mongo,
)


TEMPLATE_BASE_DIR = (
    Path(__file__).resolve().parents[3] / "utils" / "connect_layer" / "zetmiko" / "templates"
)


class HillstonePlan:
    @staticmethod
    def get_version(data_list):
        results = []
        for item in data_list or []:
            soft_version = (item.get("version") or "").strip()
            model_name = (item.get("product") or "").strip()
            serial_num = (item.get("sn") or "").strip()
            results.append(
                dict(
                    serial_num=serial_num,
                    vendor_alias="Hillstone",
                    model_name=model_name,
                    soft_version=soft_version,
                    patch_version="",
                )
            )

        device_ip = ""
        if data_list and isinstance(data_list[0], dict):
            device_ip = data_list[0].get("_resolve_device_ip", "")
        if device_ip and results:
            HillstonePlan._sync_device_identity(device_ip, results[0])
        return results

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        for item in data_list or []:
            arp_datas.append(
                dict(
                    hostip=item.get("hostip", ""),
                    hostname=item.get("hostname", ""),
                    idc_name=item.get("idc_name", ""),
                    ipaddress=item.get("ipaddress", ""),
                    macaddress=HillstonePlan._normalize_mac(item.get("macaddress", "")),
                    aging=item.get("age", ""),
                    type=item.get("typeflag", ""),
                    vlan="",
                    interface=item.get("interface", ""),
                    vpninstance="",
                    log_time=item.get("log_time", ""),
                )
            )
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        mac_data = []
        for item in data_list or []:
            mac_data.append(
                dict(
                    hostip=item.get("hostip", ""),
                    hostname=item.get("hostname", ""),
                    idc_name=item.get("idc_name", ""),
                    macaddress=HillstonePlan._normalize_mac(item.get("macaddress", "")),
                    vlan=item.get("switch", ""),
                    interface=item.get("interface", ""),
                    type=item.get("type", ""),
                    log_time=item.get("log_time", ""),
                )
            )
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        return data_list

    @staticmethod
    def get_ip_interface(data_list):
        layer3datas = []
        for item in data_list or []:
            ipaddr = (item.get("ipaddr") or "").strip()
            if not ipaddr or ipaddr in {"-", "--", "N/A"}:
                continue
            try:
                ip_net = IPNetwork(ipaddr)
            except Exception:
                continue

            halp = HillstonePlan._parse_halp(item.get("halp", ""))
            location = []
            if ipaddr != "0.0.0.0/0":
                location = [dict(start=ip_net.first, end=ip_net.last)]

            layer3datas.append(
                dict(
                    hostip=item.get("hostip", ""),
                    interface=item.get("interface", ""),
                    line_status=halp.get("line_status", ""),
                    protocol_status=halp.get("protocol_status", ""),
                    ipaddress=ip_net.ip.format(),
                    ipmask=ip_net.netmask.format(),
                    ip_type="",
                    location=location,
                    mtu="",
                    log_time=item.get("log_time", ""),
                )
            )
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        layer2datas = []
        int_regex = re.compile(r"(ethernet|xethernet|cethernet|xxvethernet)", re.I)
        for item in data_list or []:
            interface = item.get("interface", "")
            if not int_regex.search(interface):
                continue
            halp = HillstonePlan._parse_halp(item.get("halp", ""))
            layer2datas.append(
                dict(
                    hostip=item.get("hostip", ""),
                    interface=interface,
                    status=halp.get("physical_status", ""),
                    speed=HillstonePlan._hillstone_speed_format(interface),
                    duplex="",
                    description=item.get("description", ""),
                    log_time=item.get("log_time", ""),
                )
            )
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        return data_list

    @staticmethod
    def get_zone(data_list):
        results = []
        for item in data_list or []:
            results.append(
                dict(
                    hostip=item.get("hostip", ""),
                    hostname=item.get("hostname", ""),
                    idc_name=item.get("idc_name", ""),
                    name=HillstonePlan._strip_quotes(item.get("name", "")),
                    type=item.get("type", ""),
                    vswitch=item.get("vswitch", ""),
                    ifcount=item.get("ifcount", ""),
                    shared=item.get("shared", ""),
                    log_time=item.get("log_time", ""),
                )
            )
        return results

    @staticmethod
    def get_service_predefined(data_list):
        results = []
        for item in data_list or []:
            name = HillstonePlan._strip_quotes(item.get("name", ""))
            protocol = (item.get("protocol") or "").strip().lower()
            dst_port_min, dst_port_max = HillstonePlan._parse_port_range(item.get("dstport", ""))
            src_port_min, src_port_max = HillstonePlan._parse_port_range(item.get("srcport", ""))
            results.append(
                dict(
                    hostip=item.get("hostip", ""),
                    hostname=item.get("hostname", ""),
                    idc_name=item.get("idc_name", ""),
                    name=name,
                    protocol=protocol,
                    dst_port_min=dst_port_min,
                    dst_port_max=dst_port_max,
                    src_port_min=src_port_min,
                    src_port_max=src_port_max,
                    timeout=item.get("timeout", ""),
                    raw_dst_port=item.get("dstport", ""),
                    raw_src_port=item.get("srcport", ""),
                    log_time=item.get("log_time", ""),
                )
            )
        return results

    @staticmethod
    def get_policy_hit_count(data_list):
        results = []
        for item in data_list or []:
            results.append(
                dict(
                    hostip=item.get("hostip", ""),
                    hostname=item.get("hostname", ""),
                    idc_name=item.get("idc_name", ""),
                    id=str(item.get("id", "")).strip(),
                    name=HillstonePlan._strip_quotes(item.get("name", "")),
                    count=HillstonePlan._safe_int(item.get("count", 0), 0),
                    log_time=item.get("log_time", ""),
                )
            )
        return results

    @staticmethod
    def get_security_policy(data):
        raw_text, device_ip = HillstonePlan._extract_raw_payload(data)
        if not raw_text:
            return []

        address_map = HillstonePlan._parse_address_objects(raw_text)
        service_map = HillstonePlan._parse_service_objects(raw_text)
        servgroup_map = HillstonePlan._parse_service_groups(raw_text)
        predefined_map = HillstonePlan._load_service_predefined_map(device_ip)
        hit_count_map = HillstonePlan._load_policy_hit_count_map(device_ip)

        results = []
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_security_policy.textfsm"
        ):
            rule_id = str(item.get("id", "")).strip()
            if not rule_id or not (
                item.get("action")
                or item.get("src_zone")
                or item.get("dst_zone")
                or item.get("description")
                or item.get("src_object")
                or item.get("dst_object")
                or item.get("service_object")
            ):
                continue
            src_tokens = (
                HillstonePlan._as_list(item.get("src_ip"))
                + HillstonePlan._as_list(item.get("src_range"))
                + HillstonePlan._as_list(item.get("src_object"))
            )
            dst_tokens = (
                HillstonePlan._as_list(item.get("dst_ip"))
                + HillstonePlan._as_list(item.get("dst_range"))
                + HillstonePlan._as_list(item.get("dst_object"))
            )
            service_tokens = HillstonePlan._as_list(item.get("service_object"))
            results.append(
                dict(
                    hostip="",
                    hostname="",
                    idc_name="",
                    rule_id=rule_id,
                    name=(item.get("description") or f"rule-{rule_id}").strip(),
                    action=(item.get("action") or "").strip().lower(),
                    src_zone=HillstonePlan._strip_quotes(item.get("src_zone", "")),
                    dst_zone=HillstonePlan._strip_quotes(item.get("dst_zone", "")),
                    src_addr=[
                        HillstonePlan._resolve_address_for_policy(token, address_map)
                        for token in src_tokens
                        if str(token).strip()
                    ],
                    dst_addr=[
                        HillstonePlan._resolve_address_for_policy(token, address_map)
                        for token in dst_tokens
                        if str(token).strip()
                    ],
                    service=[
                        HillstonePlan._resolve_service_for_policy(
                            token,
                            service_map,
                            servgroup_map,
                            predefined_map,
                        )
                        for token in service_tokens
                        if str(token).strip()
                    ],
                    logs=HillstonePlan._as_list(item.get("log")),
                    description=(item.get("description") or "").strip(),
                    count=hit_count_map.get(rule_id, ""),
                    disabled=bool(str(item.get("disabled", "")).strip()),
                )
            )
        return results

    @staticmethod
    def get_dnat(data):
        raw_text, device_ip = HillstonePlan._extract_raw_payload(data)
        if not raw_text:
            return []

        address_map = HillstonePlan._parse_address_objects(raw_text)
        service_map = HillstonePlan._parse_service_objects(raw_text)
        servgroup_map = HillstonePlan._parse_service_groups(raw_text)
        slb_map = HillstonePlan._parse_slb_pools(raw_text)
        predefined_map = HillstonePlan._load_service_predefined_map(device_ip)

        results = []
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_dnat.textfsm"
        ):
            if not str(item.get("id", "")).strip():
                continue
            global_ip = HillstonePlan._resolve_address_entries(
                item.get("to", "") or item.get("to_ip", ""),
                address_map,
            )
            global_port = HillstonePlan._resolve_service_entries(
                item.get("service", ""),
                service_map,
                servgroup_map,
                predefined_map,
            )
            local_ip = HillstonePlan._resolve_dnat_local_ip(item, address_map, slb_map)
            local_port = HillstonePlan._resolve_dnat_local_port(item, global_port, service_map)
            track = HillstonePlan._format_track(item)
            results.append(
                dict(
                    hostip="",
                    hostname="",
                    idc_name="",
                    rule_id=str(item.get("id", "")).strip(),
                    global_ip=global_ip,
                    global_port=global_port,
                    local_ip=local_ip,
                    local_port=local_port,
                    ingress_interface=HillstonePlan._strip_quotes(item.get("ingress_interface", "")),
                    from_zone=HillstonePlan._strip_quotes(item.get("from_zone", "")),
                    to_zone=HillstonePlan._strip_quotes(item.get("to_zone", "")),
                    description=(item.get("desc") or "").strip(),
                    disabled=bool(str(item.get("disabled", "") or item.get("rulestate", "")).strip()),
                    track=track,
                )
            )
        return results

    @staticmethod
    def get_snat(data):
        raw_text, device_ip = HillstonePlan._extract_raw_payload(data)
        if not raw_text:
            return []

        address_map = HillstonePlan._parse_address_objects(raw_text)
        service_map = HillstonePlan._parse_service_objects(raw_text)
        servgroup_map = HillstonePlan._parse_service_groups(raw_text)
        predefined_map = HillstonePlan._load_service_predefined_map(device_ip)

        results = []
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_snat.textfsm"
        ):
            if not str(item.get("id", "")).strip():
                continue
            local_ip, local_exclude_ip = HillstonePlan._resolve_snat_local_ip(item, address_map)
            destination_ip = HillstonePlan._resolve_address_entries(
                item.get("to", "") or item.get("to_ip", ""),
                address_map,
                allow_any=True,
            )
            destination_port = HillstonePlan._resolve_service_entries(
                item.get("service", ""),
                service_map,
                servgroup_map,
                predefined_map,
            )
            trans_ip = HillstonePlan._resolve_snat_trans_ip(item, address_map, device_ip)
            track = HillstonePlan._format_track(item)
            results.append(
                dict(
                    hostip="",
                    hostname="",
                    idc_name="",
                    rule_id=str(item.get("id", "")).strip(),
                    trans_ip=trans_ip,
                    local_ip=local_ip,
                    local_exclude_ip=local_exclude_ip,
                    destination_ip=destination_ip,
                    destination_port=destination_port,
                    mode=(item.get("mode") or "").strip(),
                    source_zone=HillstonePlan._strip_quotes(item.get("fromzone", "")),
                    destination_zone=HillstonePlan._strip_quotes(item.get("tozone", "")),
                    egress_interface=HillstonePlan._strip_quotes(item.get("egress_interface", "")),
                    description=(item.get("desc") or "").strip(),
                    disabled=bool(str(item.get("disable", "")).strip()),
                    track=track,
                )
            )
        return results

    @staticmethod
    def _sync_device_identity(device_ip, record):
        try:
            device = (
                NetworkDevice.objects.filter(manage_ip=device_ip)
                .select_related("vendor")
                .first()
            )
            if not device:
                return
            update_fields = []
            soft_version = record.get("soft_version", "")
            model_name = record.get("model_name", "")
            serial_num = record.get("serial_num", "")
            if soft_version and device.soft_version != soft_version:
                device.soft_version = soft_version
                update_fields.append("soft_version")
            if serial_num and device.serial_num != serial_num:
                device.serial_num = serial_num
                update_fields.append("serial_num")
            if model_name:
                vendor = device.vendor
                if vendor is None:
                    vendor = Vendor.objects.filter(alias="Hillstone").first()
                if vendor:
                    model_obj, _ = Model.objects.get_or_create(
                        name=model_name,
                        vendor=vendor,
                        defaults={"vendor": vendor},
                    )
                    if device.model_id != model_obj.id:
                        device.model = model_obj
                        update_fields.append("model")
            if update_fields:
                device.save(update_fields=update_fields)
        except Exception:
            return

    @staticmethod
    def _extract_raw_payload(data):
        if isinstance(data, dict):
            return str(data.get("raw_output", "") or ""), data.get("_resolve_device_ip", "")
        return str(data or ""), ""

    @staticmethod
    def _parse_halp(value):
        parts = str(value or "").split()
        mapping = {"U": "up", "D": "down", "K": "ha"}
        return {
            "physical_status": mapping.get(parts[0], "") if len(parts) > 0 else "",
            "line_status": mapping.get(parts[2], "") if len(parts) > 2 else "",
            "protocol_status": mapping.get(parts[3], "") if len(parts) > 3 else "",
        }

    @staticmethod
    def _normalize_mac(value):
        return (value or "").replace(".", "-").lower()

    @staticmethod
    def _strip_quotes(value):
        text = str(value or "").strip()
        if len(text) >= 2 and text[0] == text[-1] == '"':
            return text[1:-1]
        return text

    @staticmethod
    def _safe_int(value, default=""):
        if value in ("", None):
            return default
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_list(value):
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _parse_textfsm_output(raw_text, template_name):
        template_path = TEMPLATE_BASE_DIR / template_name
        if not raw_text or not template_path.exists():
            return []
        try:
            with template_path.open(encoding="utf-8") as handle:
                fsm = textfsm.TextFSM(handle)
            parsed_rows = fsm.ParseText(raw_text)
        except Exception:
            return []
        headers = [header.lower() for header in fsm.header]
        return [dict(zip(headers, row)) for row in parsed_rows]

    @staticmethod
    def _parse_port_range(value):
        text = str(value or "").strip()
        if not text or text in {"-", "Any"} or "type" in text or "code" in text:
            return 0, 65535
        if "-" in text:
            left, right = text.split("-", 1)
            return HillstonePlan._safe_int(left, 0), HillstonePlan._safe_int(right, 65535)
        port = HillstonePlan._safe_int(text, "")
        if port == "":
            return "", ""
        return port, port

    @staticmethod
    def _hillstone_speed_format(interface):
        if re.search(r"^(ethernet)", interface, re.I):
            return "1G"
        if re.search(r"^(xethernet)", interface, re.I):
            return "10G"
        if re.search(r"^(cethernet)", interface, re.I):
            return "100G"
        if re.search(r"^(xxvethernet)", interface, re.I):
            return "25G"
        return "auto"

    @staticmethod
    def _parse_address_objects(raw_text):
        address_map = {}
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_address.textfsm"
        ):
            name = HillstonePlan._strip_quotes(item.get("name", ""))
            if not name:
                continue
            bucket = address_map.setdefault(
                name,
                {
                    "name": name,
                    "description": item.get("description", ""),
                    "ip": [],
                    "range": [],
                    "exclude_ip": [],
                    "exclude_range": [],
                    "member": [],
                    "host": [],
                    "wildcard": [],
                    "country": [],
                },
            )
            entry_type = (item.get("entry_type") or "").strip().lower()
            value1 = HillstonePlan._strip_quotes(item.get("value1", ""))
            value2 = HillstonePlan._strip_quotes(item.get("value2", ""))
            if entry_type == "ip" and value1:
                bucket["ip"].append({"ip": value1})
            elif entry_type == "range" and value1 and value2:
                bucket["range"].append({"start": value1, "end": value2})
            elif entry_type == "exclude ip" and value1:
                bucket["exclude_ip"].append({"ip": value1})
            elif entry_type == "exclude range" and value1 and value2:
                bucket["exclude_range"].append({"start": value1, "end": value2})
            elif entry_type == "member" and value1:
                bucket["member"].append({"name": value1})
            elif entry_type == "host" and value1:
                if HillstonePlan._looks_like_ip(value1):
                    bucket["ip"].append({"ip": value1 if "/" in value1 else f"{value1}/32"})
                else:
                    bucket["host"].append({"host": value1})
            elif entry_type == "wildcard" and value1:
                bucket["wildcard"].append({"value": value1, "mask": value2})
            elif entry_type == "country" and value1:
                bucket["country"].append({"value": value1})
        return address_map

    @staticmethod
    def _parse_service_objects(raw_text):
        service_map = {}
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_service.textfsm"
        ):
            name = HillstonePlan._strip_quotes(item.get("name", ""))
            if not name:
                continue
            bucket = service_map.setdefault(name, [])
            protocol = (item.get("protocol") or "").strip().lower()
            service_item = {"protocol": protocol}
            if item.get("dst_port_min"):
                service_item["dst-port-min"] = HillstonePlan._safe_int(item.get("dst_port_min"), 0)
                service_item["dst-port-max"] = HillstonePlan._safe_int(
                    item.get("dst_port_max"), service_item["dst-port-min"]
                )
            if item.get("src_port_min"):
                service_item["src-port-min"] = HillstonePlan._safe_int(item.get("src_port_min"), 0)
                service_item["src-port-max"] = HillstonePlan._safe_int(
                    item.get("src_port_max"), service_item["src-port-min"]
                )
            if item.get("icmp_type"):
                service_item["type"] = item.get("icmp_type")
            if item.get("icmp_code"):
                service_item["code"] = item.get("icmp_code")
            if service_item not in bucket:
                bucket.append(service_item)
        return service_map

    @staticmethod
    def _parse_service_groups(raw_text):
        group_map = {}
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_servgroup.textfsm"
        ):
            group_name = HillstonePlan._strip_quotes(item.get("servgroup", ""))
            service_name = HillstonePlan._strip_quotes(item.get("service", ""))
            if not group_name or not service_name:
                continue
            group_map.setdefault(group_name, []).append({"service": service_name})
        return group_map

    @staticmethod
    def _parse_slb_pools(raw_text):
        pool_map = {}
        for item in HillstonePlan._parse_textfsm_output(
            raw_text, "hillstone_show_configuration_slb-server-pool.textfsm"
        ):
            pool_name = HillstonePlan._strip_quotes(item.get("poolname", ""))
            if not pool_name:
                continue
            pool_map.setdefault(pool_name, []).append(item)
        return pool_map

    @staticmethod
    def _resolve_address_entries(token, address_map, allow_any=False, seen=None):
        token = HillstonePlan._strip_quotes(token)
        if not token:
            return []
        if allow_any and token == "Any":
            return [dict(start="", end="", result="Any")]
        if token in address_map:
            return HillstonePlan._address_object_to_entries(address_map[token], address_map, seen=seen)
        if HillstonePlan._looks_like_ip(token):
            return [HillstonePlan._make_ip_entry(token)]
        return [dict(start=token, end=token, result=token)]

    @staticmethod
    def _address_object_to_entries(address_obj, address_map, seen=None):
        seen = seen or set()
        name = address_obj.get("name", "")
        if name in seen:
            return []
        seen = set(seen)
        seen.add(name)
        results = []
        for item in address_obj.get("ip", []):
            ip_value = item.get("ip", "")
            if ip_value:
                results.append(HillstonePlan._make_ip_entry(ip_value))
        for item in address_obj.get("range", []):
            start = item.get("start", "")
            end = item.get("end", "")
            if start and end:
                results.append(HillstonePlan._make_range_entry(start, end))
        for item in address_obj.get("member", []):
            member_name = item.get("name", "")
            member_obj = address_map.get(member_name)
            if member_obj:
                results.extend(HillstonePlan._address_object_to_entries(member_obj, address_map, seen=seen))
        return results

    @staticmethod
    def _resolve_address_for_policy(token, address_map):
        token = HillstonePlan._strip_quotes(token)
        if token in address_map:
            address_obj = address_map[token]
            return dict(
                name=token,
                ip=list(address_obj.get("ip", [])),
                range=list(address_obj.get("range", [])),
                exclude_ip=list(address_obj.get("exclude_ip", [])),
                exclude_range=list(address_obj.get("exclude_range", [])),
                member=list(address_obj.get("member", [])),
                resolved=HillstonePlan._address_object_to_entries(address_obj, address_map),
            )
        if HillstonePlan._looks_like_ip(token):
            return dict(name="", raw=token, resolved=[HillstonePlan._make_ip_entry(token)])
        if token == "Any":
            return dict(name="Any", raw="Any", resolved=[dict(start="", end="", result="Any")])
        return dict(name=token, raw=token, resolved=[dict(start=token, end=token, result=token)])

    @staticmethod
    def _resolve_service_entries(token, service_map, servgroup_map, predefined_map, seen=None):
        token = HillstonePlan._strip_quotes(token)
        seen = seen or set()
        if not token:
            return [dict(start=0, end=65535, protocol="any", result="Any")]
        if token == "Any":
            return [dict(start=0, end=65535, protocol="any", result="Any")]
        if token in seen:
            return []
        seen = set(seen)
        seen.add(token)

        if token in predefined_map:
            return list(predefined_map[token])
        if token in servgroup_map:
            results = []
            for item in servgroup_map[token]:
                results.extend(
                    HillstonePlan._resolve_service_entries(
                        item.get("service", ""),
                        service_map,
                        servgroup_map,
                        predefined_map,
                        seen=seen,
                    )
                )
            return results
        if token in service_map:
            return [HillstonePlan._service_item_to_entry(item) for item in service_map[token]]
        inline = HillstonePlan._parse_inline_service_token(token)
        if inline:
            return inline
        return [dict(start=token, end=token, protocol=token.lower(), result=token)]

    @staticmethod
    def _resolve_service_for_policy(token, service_map, servgroup_map, predefined_map):
        token = HillstonePlan._strip_quotes(token)
        return dict(
            name=token,
            items=HillstonePlan._resolve_service_entries(
                token,
                service_map,
                servgroup_map,
                predefined_map,
            ),
        )

    @staticmethod
    def _service_item_to_entry(item):
        protocol = str(item.get("protocol", "")).lower() or "any"
        if "dst-port-min" in item:
            start = HillstonePlan._safe_int(item.get("dst-port-min"), 0)
            end = HillstonePlan._safe_int(item.get("dst-port-max"), start)
            return dict(start=start, end=end, protocol=protocol, result=f"{start}-{end}" if start != end else str(start))
        if "type" in item:
            type_value = str(item.get("type", ""))
            code_value = str(item.get("code", "")).strip()
            result = f"type:{type_value}"
            if code_value:
                result = f"{result} code:{code_value}"
            return dict(start=0, end=65535, protocol=protocol, result=result)
        return dict(start=0, end=65535, protocol=protocol, result="Any")

    @staticmethod
    def _parse_inline_service_token(token):
        match = re.match(r"^(tcp|udp)\s+(\d+)(?:\s+(\d+))?$", token, re.I)
        if match:
            protocol = match.group(1).lower()
            start = int(match.group(2))
            end = int(match.group(3) or match.group(2))
            return [dict(start=start, end=end, protocol=protocol, result=f"{start}-{end}" if start != end else str(start))]
        if token.lower() in {"icmp", "ping", "ndp"}:
            return [dict(start=0, end=65535, protocol=token.lower(), result=token)]
        if re.match(r"^\d+(?:-\d+)?$", token):
            start, end = HillstonePlan._parse_port_range(token)
            return [dict(start=start, end=end, protocol="tcp", result=token)]
        return []

    @staticmethod
    def _resolve_dnat_local_ip(item, address_map, slb_map):
        trans_to_ip = item.get("transto_ip", "")
        trans_to_name = item.get("transto", "")
        pool_name = item.get("poolname", "")
        if trans_to_ip:
            return [HillstonePlan._make_ip_entry(trans_to_ip)]
        if trans_to_name:
            return HillstonePlan._resolve_address_entries(trans_to_name, address_map)
        if pool_name and pool_name in slb_map:
            results = []
            for entry in slb_map[pool_name]:
                server_ip = entry.get("serverip", "")
                if not server_ip:
                    continue
                if entry.get("addrtype") == "ip-range" and " " in server_ip:
                    start, end = server_ip.split(None, 1)
                    results.append(HillstonePlan._make_range_entry(start, end))
                else:
                    results.append(HillstonePlan._make_ip_entry(server_ip))
            return results
        return []

    @staticmethod
    def _resolve_dnat_local_port(item, global_port, service_map):
        port = str(item.get("port", "")).strip()
        if not port:
            return list(global_port)
        if port in service_map:
            return [HillstonePlan._service_item_to_entry(obj) for obj in service_map[port]]
        if re.match(r"^\d+$", port):
            protocol = global_port[0]["protocol"] if global_port else "tcp"
            return [dict(start=int(port), end=int(port), protocol=protocol, result=port)]
        return [dict(start=port, end=port, protocol=port.lower(), result=port)]

    @staticmethod
    def _resolve_snat_local_ip(item, address_map):
        local_ip = []
        exclude_ip = []
        from_ip = item.get("from_ip", "")
        from_name = item.get("from", "")
        if from_ip:
            local_ip.append(HillstonePlan._make_ip_entry(from_ip))
        if from_name == "Any":
            local_ip.append(dict(start="", end="", result="Any"))
        elif from_name in address_map:
            address_obj = address_map[from_name]
            local_ip.extend(HillstonePlan._address_object_to_entries(address_obj, address_map))
            for entry in address_obj.get("exclude_ip", []):
                exclude_ip.append(HillstonePlan._make_ip_entry(entry.get("ip", "")))
            for entry in address_obj.get("exclude_range", []):
                exclude_ip.append(HillstonePlan._make_range_entry(entry.get("start", ""), entry.get("end", "")))
        return local_ip, exclude_ip

    @staticmethod
    def _resolve_snat_trans_ip(item, address_map, device_ip):
        trans_to_ip = item.get("transto_ip", "")
        trans_to_name = item.get("transto", "")
        if trans_to_ip:
            return [HillstonePlan._make_ip_entry(trans_to_ip)]
        if trans_to_name:
            return HillstonePlan._resolve_address_entries(trans_to_name, address_map)
        if item.get("transto_eip"):
            interface_name = HillstonePlan._strip_quotes(item.get("egress_interface", ""))
            for interface in HillstonePlan._load_latest_ip_interface_rows(device_ip):
                if interface.get("interface") == interface_name and interface.get("ipaddress"):
                    cidr = f"{interface['ipaddress']}/{interface['ipmask']}"
                    return [HillstonePlan._make_ip_entry(cidr)]
        return []

    @staticmethod
    def _format_track(item):
        track_tokens = []
        for key in ("track_tcp", "track_ping", "track"):
            value = str(item.get(key, "")).strip()
            if value:
                track_tokens.append(value)
        return " ".join(track_tokens)

    @staticmethod
    def _make_ip_entry(value):
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

    @staticmethod
    def _make_range_entry(start, end):
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

    @staticmethod
    def _looks_like_ip(value):
        text = str(value or "").strip()
        if not text:
            return False
        if "/" in text:
            try:
                IPNetwork(text)
                return True
            except Exception:
                return False
        try:
            return valid_ipv4(text, flags=1)
        except Exception:
            return False

    @staticmethod
    def _load_latest_rows(mongo, device_ip):
        if not device_ip:
            return []
        try:
            rows = list(
                mongo.coll.find({"hostip": device_ip}, {"_id": 0}).sort(
                    [("execute_time", -1), ("log_time", -1)]
                )
            )
        except Exception:
            return []
        if not rows:
            return []
        latest_execute_time = rows[0].get("execute_time")
        if latest_execute_time:
            return [row for row in rows if row.get("execute_time") == latest_execute_time]
        return rows

    @staticmethod
    def _load_service_predefined_map(device_ip):
        result = {}
        for row in HillstonePlan._load_latest_rows(service_predefined_mongo, device_ip):
            name = row.get("name", "")
            if not name:
                continue
            result.setdefault(name, []).append(
                dict(
                    start=HillstonePlan._safe_int(row.get("dst_port_min"), 0),
                    end=HillstonePlan._safe_int(row.get("dst_port_max"), 65535),
                    protocol=(row.get("protocol") or "").lower() or "any",
                    result=row.get("raw_dst_port") or "Any",
                )
            )
        return result

    @staticmethod
    def _load_policy_hit_count_map(device_ip):
        result = {}
        for row in HillstonePlan._load_latest_rows(policy_hit_count_mongo, device_ip):
            rule_id = str(row.get("id", "")).strip()
            if rule_id:
                result[rule_id] = row.get("count", "")
        return result

    @staticmethod
    def _load_latest_ip_interface_rows(device_ip):
        return HillstonePlan._load_latest_rows(ip_interface_mongo, device_ip)
