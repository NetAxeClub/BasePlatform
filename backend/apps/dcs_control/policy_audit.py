from __future__ import annotations

from typing import Any, Dict, Iterable, List

from apps.dcs_control.constants import Vendor


HIGH_RISK_PORTS = {20, 21, 22, 23, 445, 1433, 1521, 3306, 3389, 5432, 6379}

VENDOR_STORAGE_ALIASES = {
    Vendor.H3C.value: {"H3C", "h3c_secpath"},
    Vendor.HUAWEI.value: {"Huawei", "huawei_usg"},
    Vendor.HILLSTONE.value: {"Hillstone", "hillstone"},
}

VENDOR_DISPLAY_MAP = {
    "h3c_secpath": Vendor.H3C.value,
    "huawei_usg": Vendor.HUAWEI.value,
    "hillstone": Vendor.HILLSTONE.value,
}


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "on", "permit"}


def _normalize_vendor_name(raw_vendor: str) -> str:
    return VENDOR_DISPLAY_MAP.get(raw_vendor, raw_vendor)


def get_vendor_aliases(vendor: str | None) -> set[str]:
    if not vendor:
        return set()
    normalized = Vendor.normalize(vendor)
    return VENDOR_STORAGE_ALIASES.get(normalized, {normalized})


def _normalize_zone_value(value: Any) -> List[str]:
    items = _ensure_list(value)
    zones: List[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("value")
            if name:
                zones.append(str(name))
        elif item not in (None, ""):
            zones.append(str(item))
    return zones or ["Any"]


def _normalize_address_entries(value: Any) -> List[Dict[str, str]]:
    items = _ensure_list(value)
    entries: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            for field_name in ("object", "ip", "range", "addr"):
                if item.get(field_name):
                    entries.append({"type": field_name, "value": str(item[field_name])})
                    break
        elif item not in (None, ""):
            entries.append({"type": "literal", "value": str(item)})
    return entries or [{"type": "any", "value": "Any"}]


def _service_display(protocol: str, start_port: str, end_port: str) -> str:
    if not protocol:
        return "Any"
    if start_port and end_port and start_port != end_port:
        return f"{protocol}/{start_port}-{end_port}"
    if start_port:
        return f"{protocol}/{start_port}"
    return protocol


def _parse_service_entry(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        is_any = item.strip().lower() == "any"
        return {
            "kind": "any" if is_any else "literal",
            "name": item,
            "protocol": "",
            "start_port": "",
            "end_port": "",
            "display": item,
            "is_any": is_any,
            "is_high_risk": False,
        }

    if not isinstance(item, dict):
        return {
            "kind": "literal",
            "name": str(item),
            "protocol": "",
            "start_port": "",
            "end_port": "",
            "display": str(item),
            "is_any": False,
            "is_high_risk": False,
        }

    if item.get("object"):
        name = str(item["object"])
        is_any = name.strip().lower() == "any"
        return {
            "kind": "object",
            "name": name,
            "protocol": "",
            "start_port": "",
            "end_port": "",
            "display": name,
            "is_any": is_any,
            "is_high_risk": False,
        }

    if item.get("service"):
        name = str(item["service"])
        is_any = name.strip().lower() == "any"
        return {
            "kind": "object",
            "name": name,
            "protocol": "",
            "start_port": "",
            "end_port": "",
            "display": name,
            "is_any": is_any,
            "is_high_risk": False,
        }

    raw_item = item.get("item", item)
    protocol = str(raw_item.get("Type", "")).lower()
    start_port = str(
        raw_item.get("StartDestPort")
        or raw_item.get("dst_port_start")
        or raw_item.get("start_port")
        or ""
    )
    end_port = str(
        raw_item.get("EndDestPort")
        or raw_item.get("dst_port_end")
        or raw_item.get("end_port")
        or start_port
    )

    risk_ports = set()
    if start_port.isdigit() and end_port.isdigit():
        for port in range(int(start_port), int(end_port) + 1):
            if port in HIGH_RISK_PORTS:
                risk_ports.add(port)
    elif start_port.isdigit() and int(start_port) in HIGH_RISK_PORTS:
        risk_ports.add(int(start_port))

    return {
        "kind": "inline",
        "name": "",
        "protocol": protocol,
        "start_port": start_port,
        "end_port": end_port,
        "display": _service_display(protocol, start_port, end_port),
        "is_any": False,
        "is_high_risk": bool(risk_ports),
        "risk_ports": sorted(risk_ports),
    }


def _normalize_service_entries(value: Any) -> List[Dict[str, Any]]:
    items = _ensure_list(value)
    entries = [_parse_service_entry(item) for item in items if item not in (None, "")]
    return entries or [
        {
            "kind": "any",
            "name": "Any",
            "protocol": "",
            "start_port": "",
            "end_port": "",
            "display": "Any",
            "is_any": True,
            "is_high_risk": False,
        }
    ]


def _logging_state(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "enabled" if value else "disabled"
    text = str(value).strip().lower()
    if not text:
        return "disabled"
    if text in {"true", "1", "yes", "on"}:
        return "enabled"
    if text in {"false", "0", "no", "off"}:
        return "disabled"
    return "enabled"


def normalize_sec_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    vendor = _normalize_vendor_name(str(policy.get("vendor", "")))
    enabled = _coerce_bool(policy.get("enable", True))
    action = str(policy.get("action", "")).lower()
    is_permit = action == "permit"
    src_zones = _normalize_zone_value(policy.get("src_zone"))
    dst_zones = _normalize_zone_value(policy.get("dst_zone"))
    src_addresses = _normalize_address_entries(policy.get("src_addr"))
    dst_addresses = _normalize_address_entries(policy.get("dst_addr"))
    services = _normalize_service_entries(policy.get("service"))
    logging_state = _logging_state(policy.get("log"))

    has_any_source = any(item["value"].strip().lower() == "any" for item in src_addresses)
    has_any_destination = any(item["value"].strip().lower() == "any" for item in dst_addresses)
    has_any_service = any(item.get("is_any") for item in services)
    high_risk_services = [item for item in services if item.get("is_high_risk")]
    is_permit_any_any = enabled and is_permit and has_any_source and has_any_destination and has_any_service
    has_high_risk_service = enabled and is_permit and bool(high_risk_services)
    needs_logging_review = enabled and is_permit and logging_state != "enabled"

    findings = []
    if is_permit_any_any:
        findings.append("permit_any_any")
    if has_high_risk_service:
        findings.append("high_risk_service")
    if needs_logging_review:
        findings.append("logging_missing")

    return {
        "vendor": vendor,
        "hostip": policy.get("hostip", ""),
        "rule_id": policy.get("id", ""),
        "rule_name": policy.get("name", ""),
        "description": policy.get("description", "") or "",
        "action": action,
        "enabled": enabled,
        "logging_state": logging_state,
        "source_zones": src_zones,
        "destination_zones": dst_zones,
        "source_addresses": src_addresses,
        "destination_addresses": dst_addresses,
        "services": services,
        "has_any_source": has_any_source,
        "has_any_destination": has_any_destination,
        "has_any_service": has_any_service,
        "is_permit_any_any": is_permit_any_any,
        "has_high_risk_service": has_high_risk_service,
        "high_risk_services": high_risk_services,
        "needs_logging_review": needs_logging_review,
        "findings": findings,
    }


def build_sec_policy_audit_payload(
    policies: Iterable[Dict[str, Any]],
    hostip: str = "",
    vendor: str = "",
) -> Dict[str, Any]:
    normalized = [normalize_sec_policy(policy) for policy in policies]

    return {
        "hostip": hostip,
        "vendor": Vendor.normalize(vendor) if vendor else "",
        "total_rules": len(normalized),
        "enabled_rules": sum(1 for item in normalized if item["enabled"]),
        "permit_any_any_count": sum(1 for item in normalized if item["is_permit_any_any"]),
        "high_risk_service_rule_count": sum(
            1 for item in normalized if item["has_high_risk_service"]
        ),
        "logging_review_count": sum(1 for item in normalized if item["needs_logging_review"]),
        "results": normalized,
    }


def extract_sec_policy_audit_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hostip": payload.get("hostip", ""),
        "vendor": payload.get("vendor", ""),
        "total_rules": payload.get("total_rules", 0),
        "enabled_rules": payload.get("enabled_rules", 0),
        "permit_any_any_count": payload.get("permit_any_any_count", 0),
        "high_risk_service_rule_count": payload.get("high_risk_service_rule_count", 0),
        "logging_review_count": payload.get("logging_review_count", 0),
    }


def extract_sec_policy_findings(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in payload.get("results", []):
        if not item.get("findings"):
            continue
        findings.append(
            {
                "rule_id": item.get("rule_id", ""),
                "rule_name": item.get("rule_name", ""),
                "findings": item.get("findings", []),
            }
        )
    return findings
