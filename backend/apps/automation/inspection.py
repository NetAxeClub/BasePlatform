import json
from typing import Any, Dict, Iterable, List


def _load_json(value: Any, default: Any):
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def inspection_kwargs(flow) -> Dict[str, Any]:
    return _load_json(getattr(flow, "kwargs", "{}"), {})


def inspection_ttp(flow) -> Dict[str, Any]:
    return _load_json(getattr(flow, "ttp", "{}"), {})


def inspection_task_result(flow) -> Any:
    return _load_json(getattr(flow, "task_result", ""), getattr(flow, "task_result", ""))


def _first_non_empty(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def inspection_scope(flow) -> str:
    kwargs_data = inspection_kwargs(flow)
    scope = _first_non_empty(
        kwargs_data.get("inspection_scope"),
        kwargs_data.get("scope"),
        kwargs_data.get("target_scope"),
    )
    if scope:
        return str(scope).lower()
    return "device" if getattr(flow, "device", None) else "fleet"


def inspection_type(flow) -> str:
    kwargs_data = inspection_kwargs(flow)
    ttp_data = inspection_ttp(flow)
    result_data = inspection_task_result(flow)
    return str(
        _first_non_empty(
            kwargs_data.get("inspection_type"),
            kwargs_data.get("inspection_kind"),
            kwargs_data.get("template"),
            kwargs_data.get("category"),
            kwargs_data.get("rule_set"),
            ttp_data.get("inspection_type") if isinstance(ttp_data, dict) else "",
            result_data.get("inspection_type") if isinstance(result_data, dict) else "",
            "generic",
        )
    )


def _summary_from_result_list(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    total = 0
    passed = 0
    failed = 0
    warning = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        total += 1
        status = str(
            item.get("status")
            or item.get("result")
            or item.get("compliance")
            or item.get("level")
            or ""
        ).lower()
        if status in {"pass", "passed", "success", "ok", "compliance", "compliant"}:
            passed += 1
        elif status in {"warning", "warn"}:
            warning += 1
        elif status:
            failed += 1

    summary = {"total": total}
    if passed:
        summary["passed"] = passed
    if failed:
        summary["failed"] = failed
    if warning:
        summary["warning"] = warning
    return summary


def _extract_summary(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        if isinstance(payload, list):
            return _summary_from_result_list(payload)
        return {}

    if isinstance(payload.get("summary"), dict):
        return payload["summary"]

    summary = {}
    for key in ("total", "passed", "failed", "warning", "findings"):
        value = payload.get(key)
        if isinstance(value, int):
            summary[key] = value

    if summary:
        return summary

    for key in ("results", "items", "findings"):
        value = payload.get(key)
        if isinstance(value, list):
            result = _summary_from_result_list(value)
            if key == "findings" and "total" in result:
                result["findings"] = result.pop("total")
            if result:
                return result
    return {}


def inspection_summary(flow) -> Dict[str, Any]:
    for payload in (inspection_task_result(flow), inspection_ttp(flow), inspection_kwargs(flow)):
        summary = _extract_summary(payload)
        if summary:
            return summary
    return {}


def inspection_payload(flow) -> Dict[str, Any]:
    return {
        "inspection_scope": inspection_scope(flow),
        "inspection_type": inspection_type(flow),
        "summary": inspection_summary(flow),
        "kwargs": inspection_kwargs(flow),
        "ttp": inspection_ttp(flow),
        "task_result": inspection_task_result(flow),
    }
