import logging
from collections.abc import Mapping
from typing import Dict, Iterable, Optional

from apps.network_analysis.services import InterfaceUtilizationAnalysisService
from apps.network_analysis.tasks import (
    refresh_interface_utilization,
    refresh_network_analysis_for_batch,
)


logger = logging.getLogger(__name__)

INTERFACE_ANALYSIS_COLLECTION_TYPES = frozenset({"interface_brief", "ip_interface"})


def schedule_batch_network_analysis(
    execute_time: str,
    expected_devices: int = 0,
    expected_subtasks: int = 0,
    expected_interface_devices: int = 0,
    triggered_by: str = "device_api-plan_collect_device_main",
    countdown: int = 30,
) -> Dict[str, object]:
    if not execute_time:
        return {"scheduled": False, "reason": "missing_execute_time"}

    refresh_network_analysis_for_batch.apply_async(
        kwargs={
            "execute_time": execute_time,
            "expected_devices": expected_devices,
            "expected_subtasks": expected_subtasks,
            "expected_interface_devices": expected_interface_devices,
            "triggered_by": triggered_by,
        },
        queue="config",
        retry=True,
        countdown=countdown,
    )
    return {
        "scheduled": True,
        "reason": "scheduled",
        "execute_time": execute_time,
        "expected_devices": expected_devices,
        "expected_subtasks": expected_subtasks,
        "expected_interface_devices": expected_interface_devices,
        "triggered_by": triggered_by,
    }


def count_expected_interface_devices(hosts: Iterable[dict]) -> int:
    interface_devices = set()
    for host in hosts:
        manage_ip = host.get("manage_ip")
        sub_plans = host.get("sub_plans", []) or []
        if not manage_ip:
            continue
        if any(
            (sub_plan or {}).get("collection_type") in INTERFACE_ANALYSIS_COLLECTION_TYPES
            for sub_plan in sub_plans
        ):
            interface_devices.add(manage_ip)
    return len(interface_devices)


def schedule_interface_utilization_refresh(
    device_ip: str,
    execute_time: Optional[str] = None,
    triggered_by: str = "device_api-interface-refresh",
    countdown: int = 0,
) -> Dict[str, object]:
    if not device_ip:
        return {"scheduled": False, "reason": "missing_device_ip"}

    if not InterfaceUtilizationAnalysisService.has_ready_source_data(
        device_ip=device_ip,
        execute_time=execute_time,
    ):
        logger.info(
            "跳过接口利用率分析触发: manage_ip=%s execute_time=%s reason=source_not_ready",
            device_ip,
            execute_time,
        )
        return {
            "scheduled": False,
            "reason": "source_not_ready",
            "device_ip": device_ip,
            "execute_time": execute_time or "",
            "triggered_by": triggered_by,
        }

    refresh_interface_utilization.apply_async(
        kwargs={"device_ip": device_ip, "execute_time": execute_time},
        queue="config",
        retry=True,
        countdown=countdown,
    )
    return {
        "scheduled": True,
        "reason": "scheduled",
        "device_ip": device_ip,
        "execute_time": execute_time or "",
        "triggered_by": triggered_by,
    }


def maybe_schedule_interface_utilization(
    collection_type: str,
    device_ip: str,
    execute_time: Optional[str] = None,
    triggered_by: str = "device_api-interface-refresh",
    countdown: int = 0,
) -> Dict[str, object]:
    if collection_type not in INTERFACE_ANALYSIS_COLLECTION_TYPES:
        return {
            "scheduled": False,
            "reason": "collection_type_not_supported",
            "collection_type": collection_type,
            "device_ip": device_ip,
            "execute_time": execute_time or "",
        }

    return schedule_interface_utilization_refresh(
        device_ip=device_ip,
        execute_time=execute_time,
        triggered_by=triggered_by,
        countdown=countdown,
    )


def extract_webhook_args(payload) -> Dict[str, object]:
    if not hasattr(payload, "get"):
        return {}

    webhook_args = payload.get("webhook_args", {})
    if isinstance(webhook_args, dict):
        return webhook_args
    if isinstance(webhook_args, Mapping):
        return dict(webhook_args)
    return {}
