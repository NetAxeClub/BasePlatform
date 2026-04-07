# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:     设备采集任务
   Author:          Junhu19
   date：           2024/01/01
-------------------------------------------------
   Change Activity:
                    2024/01/01
-------------------------------------------------

以前方案（automation/tasks.py）定时任务采集逻辑梳理：

一、主调度任务 collect_device_main(**kwargs)
   执行流程：
   1. datas_to_cache() - 将ARP、MAC、LLDP等表数据写入缓存（用于地址定位等功能）
   2. MainIn.cmdb_to_mongo() - 同步CMDB设备信息到MongoDB
   3. get_device_info_v2(**kwargs) - 获取所有符合条件的设备列表
      - 条件：status=0, auto_enable=True, 有采集方案(plan_id)
      - 返回设备信息（包含SSH/Netconf账号密码等）
   4. clear_his_collect_res() - 清空历史采集数据（MongoDB中的旧数据）
   5. 批量下发 collect_device 任务到 Celery 队列（DEBUG='dev'，否则='config'）

二、单个设备采集任务 collect_device(**kwargs)
   执行流程：
   1. 验证设备有效性（IP、采集方案、自动化启用状态）
   2. 根据厂商别名（vendor__alias）选择对应的处理类：
      - H3C -> H3cProc
      - Huawei -> HuaweiProc
      - Hillstone -> HillstoneProc
      - 等等...
   3. 实例化处理类，传入设备信息（包含plan_id）
   4. 调用 class_instance.collection_run() 执行采集

三、厂商处理类 collection_run() 方法（以H3cProc为例）
   执行流程：
   1. 调用父类 BaseConn.collection_run()：
      a. 从 CollectionPlan 获取 commands（JSON格式的命令列表）
      b. 使用 Netmiko 连接设备，执行命令
      c. 将命令输出保存到文件（automation/{hostip}/{cmd}.txt）
      d. 调用 _collection_analysis(paths) 解析数据
   2. 如果配置了 netconf_class，执行 NETCONF 采集：
      a. 根据 netconf_class 选择连接类（如 H3CinfoCollection）
      b. 从 CollectionPlan 获取 netconf_method（JSON格式的方法列表）
      c. 遍历执行每个 netconf 方法
      d. 调用 _netconf_method_map(method, res) 解析数据
   3. 将解析后的数据写入 MongoDB：
      - ARPTable、MACTable、layer2interface、layer3interface
      - AggreTable、LLDPTable、DNAT 等

四、数据解析流程
   1. CLI命令解析（_collection_analysis）：
      - 使用 TextFSM 模板解析命令输出
      - 调用 StandardFSMAnalysis 类的方法处理数据
      - 格式化后写入 MongoDB
   2. NETCONF数据解析（_netconf_method_map）：
      - 根据方法名映射到对应的解析函数
      - 处理XML数据，转换为结构化数据
      - 写入 MongoDB

五、采集方案模型（旧方案 automation.CollectionPlan）
   - vendor: 厂商
   - category: 设备类型（交换机/防火墙/路由器）
   - commands: JSON格式的命令列表，如 ["display arp", "display mac-address"]
   - netconf_method: JSON格式的方法列表，如 ["get_arp", "get_interface"]
   - netconf_class: NETCONF连接类名称，如 "H3CinfoCollection"

六、新方案（device_api）的改进
   - 使用 DeviceCollectionPlans（父方案）+ DeviceSubCollectionPlan（子方案）
   - 子方案支持独立的 Netmiko 和 NETCONF 配置
   - 通过南向驱动服务（south_gateway）统一执行采集
   - 支持字段映射和自定义数据处理
"""
from __future__ import absolute_import, unicode_literals
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import json
from collections import Counter, defaultdict
from datetime import datetime
from celery import shared_task
from django.core.cache import cache
from django.db import connections
from apps.device_api.contract import (
    build_plan_collection_name,
    normalize_collection_type_for_storage,
)
from apps.device_api.fields_mapping import field_mapping
from apps.device_api.fields_mapping import RAW_NETMIKO_COLLECTION_TYPES
from netaxe.celery import AxeTask
from apps.asset.models import NetworkDevice
from apps.device_api.services_new import DeviceCollectionService
from apps.device_api.connection_manager import DeviceConnectionManager
from apps.device_api.binding_analysis_service import (
    analyze_collection_plan_bindings_service,
)
from apps.device_api.models_api import (
    resolve_raw_data,
    inject_metadata,
    inject_collection_context,
    COLLECTION_TYPE_MONGO_MAP,
    save_local_collection_result,
)
from apps.device_api.tools.collect_device import get_auto_device
from apps.device_api.platform_profiles import DeviceFactService
from apps.device_api.platform_profiles import PlatformProfileService
from apps.device_api.cache_utils import cache_network_data
from apps.device_api.analysis_hooks import (
    count_expected_interface_devices,
    maybe_schedule_interface_utilization,
    schedule_batch_network_analysis,
)
from apps.device_api import (
    COLLECTION_BINDING_ANALYSIS,
    COLLECTION_EXECUTION_LOG,
    COLLECTION_PLAN,
    COLLECTION_RESULTS_DB,
    COLLECTION_SUB_PLAN,
)
from apps.device_api import arp_mongo, mac_mongo, lldp_mongo, aggre_port_mongo
from netaxe.settings import DEBUG
from utils.connect_layer.auto_main import send_ws_msg
from utils.db.mongo_ops import MongoOps, MongoNetOps

logger = logging.getLogger("device_api")

TEMP_NETMIKO_EMPTY_OUTPUT_HINTS = {
    "ospf_neighbors": (
        "ospf is not configured",
        "ospf not configured",
        "ospf is not enabled",
        "ospf not enabled",
        "no ospf neighbor",
        "no ospf peer",
    ),
    "ospf_interfaces": (
        "ospf is not configured",
        "ospf not configured",
        "ospf is not enabled",
        "ospf not enabled",
        "no ospf interface",
    ),
    "isis_neighbors": (
        "isis is not configured",
        "isis not configured",
        "isis is not enabled",
        "isis not enabled",
        "no isis peer",
        "no isis neighbor",
    ),
    "bgp_neighbors": (
        "bgp is not configured",
        "bgp not configured",
        "bgp is not enabled",
        "bgp not enabled",
        "no bgp peer",
        "no bgp neighbor",
    ),
    "bgp_summary": (
        "bgp is not configured",
        "bgp not configured",
        "bgp is not enabled",
        "bgp not enabled",
        "no bgp peer",
        "no bgp neighbor",
    ),
    "lldp": (
        "lldp is not enabled",
        "lldp is disabled",
        "no lldp neighbor",
        "no neighbor information",
    ),
    "mac": (
        "mac address table is empty",
        "mac-address table is empty",
        "no mac address entry",
        "no mac-address entry",
    ),
    "arp": (
        "arp table is empty",
        "no arp entry",
        "no arp information",
    ),
    "vrrp_info": (
        "vrrp is not configured",
        "no vrrp information",
        "no vrrp instance",
    ),
}

TEMP_NETMIKO_GENERIC_EMPTY_HINTS = (
    "not configured",
    "not enabled",
    "no configuration",
    "no relevant configuration",
    "no information",
    "no entry",
    "no entries",
    "no neighbor",
    "no peer",
)

TEMP_NETMIKO_ZERO_COUNT_HINTS = (
    "total entries displayed: 0",
    "total: 0",
    "total 0",
    "0 entries",
    "0 entry",
)

RUNTIME_CONTROL_KWARGS = {"clear_history", "clear_plan_data"}
INCREMENTAL_SNAPSHOT_COLLECTION_TYPES = frozenset(
    {
        "arp",
        "mac",
        "lldp",
        "aggre_port",
        "interface_brief",
        "ip_interface",
    }
)
DEVICE_API_RUNTIME_TASK_CACHE_PREFIX = "device_api:runtime_task:"
DEVICE_API_RUNTIME_TASK_CACHE_TIMEOUT = 6 * 60 * 60
DEVICE_API_RUNTIME_TASK_DEDUP_PREFIX = "device_api:runtime_task:summary_validate:active:"
DEVICE_API_RUNTIME_TASK_DEDUP_TIMEOUT = 30 * 60
DEVICE_API_WS_GROUP_PREFIX = "device_collection_"
BATCH_PROFILE_REBIND_DEFAULT_BLOCKERS = ("binding_plan_mismatch",)
BATCH_PROFILE_REBIND_MAX_WORKERS = 50
BATCH_PROFILE_REBIND_RESULT_SAMPLE_LIMIT = 100

if DEBUG:
    CELERY_QUEUE = "dev"
else:
    CELERY_QUEUE = "config"


def _runtime_task_cache_key(task_id: str) -> str:
    return f"{DEVICE_API_RUNTIME_TASK_CACHE_PREFIX}{task_id}"


def _runtime_summary_validate_dedup_key(
    username: str,
    summary_plan_id,
    device_ip: str,
) -> str:
    user = str(username or "").strip() or "-"
    summary = str(summary_plan_id or "").strip() or "-"
    ip = str(device_ip or "").strip().lower() or "-"
    return f"{DEVICE_API_RUNTIME_TASK_DEDUP_PREFIX}{user}:{summary}:{ip}"


def claim_summary_plan_validation_lock(
    username: str,
    summary_plan_id,
    device_ip: str,
) -> dict:
    dedup_key = _runtime_summary_validate_dedup_key(
        username=username,
        summary_plan_id=summary_plan_id,
        device_ip=device_ip,
    )
    existing_task_id = str(cache.get(dedup_key) or "").strip()
    if existing_task_id:
        snapshot = get_runtime_task_snapshot(existing_task_id)
        if snapshot and snapshot.get("status") in {"queued", "running"}:
            return {
                "claimed": False,
                "task_id": existing_task_id,
                "snapshot": snapshot,
                "dedup_key": dedup_key,
            }
        cache.delete(dedup_key)

    placeholder = f"pending:{datetime.now().isoformat()}"
    claimed = cache.add(
        dedup_key,
        placeholder,
        timeout=DEVICE_API_RUNTIME_TASK_DEDUP_TIMEOUT,
    )
    if not claimed:
        existing_task_id = str(cache.get(dedup_key) or "").strip()
        snapshot = get_runtime_task_snapshot(existing_task_id)
        if snapshot and snapshot.get("status") in {"queued", "running"}:
            return {
                "claimed": False,
                "task_id": existing_task_id,
                "snapshot": snapshot,
                "dedup_key": dedup_key,
            }
        cache.delete(dedup_key)
        cache.add(
            dedup_key,
            placeholder,
            timeout=DEVICE_API_RUNTIME_TASK_DEDUP_TIMEOUT,
        )
    return {
        "claimed": True,
        "task_id": "",
        "snapshot": None,
        "dedup_key": dedup_key,
    }


def bind_summary_plan_validation_lock(
    username: str,
    summary_plan_id,
    device_ip: str,
    task_id: str,
) -> None:
    dedup_key = _runtime_summary_validate_dedup_key(
        username=username,
        summary_plan_id=summary_plan_id,
        device_ip=device_ip,
    )
    cache.set(
        dedup_key,
        str(task_id or "").strip(),
        timeout=DEVICE_API_RUNTIME_TASK_DEDUP_TIMEOUT,
    )


def release_summary_plan_validation_lock(
    username: str,
    summary_plan_id,
    device_ip: str,
    task_id: str = "",
) -> None:
    dedup_key = _runtime_summary_validate_dedup_key(
        username=username,
        summary_plan_id=summary_plan_id,
        device_ip=device_ip,
    )
    current = str(cache.get(dedup_key) or "").strip()
    expected_task_id = str(task_id or "").strip()
    if expected_task_id and current and current != expected_task_id:
        return
    cache.delete(dedup_key)


def get_runtime_task_snapshot(task_id: str):
    if not task_id:
        return None
    return cache.get(_runtime_task_cache_key(task_id))


def _store_runtime_task_snapshot(snapshot: dict) -> dict:
    task_id = str(snapshot.get("task_id") or "").strip()
    if not task_id:
        return snapshot
    payload = {**snapshot, "updated_at": datetime.now().isoformat()}
    cache.set(
        _runtime_task_cache_key(task_id),
        payload,
        timeout=DEVICE_API_RUNTIME_TASK_CACHE_TIMEOUT,
    )
    username = str(payload.get("username") or "").strip()
    if username:
        try:
            send_ws_msg(
                channel="device_collection_message",
                group_name=f"{DEVICE_API_WS_GROUP_PREFIX}{username}",
                data=payload,
            )
        except Exception as exc:
            logger.warning(
                "推送 device_api websocket 事件失败: task_id=%s error=%s", task_id, exc
            )
    return payload


def _build_runtime_task_snapshot(
    *,
    task_id: str,
    task_type: str,
    username: str,
    device_ip: str,
    serial_num: str = "",
    summary_plan_id=None,
    summary_plan_name: str = "",
    plan_id=None,
    plan_name: str = "",
    status: str = "queued",
    message: str = "",
    execute_time: str = "",
    progress: dict = None,
    data: dict = None,
    result_code: int = 200,
    event: dict = None,
):
    return {
        "task_id": task_id,
        "task_type": task_type,
        "username": username,
        "device_ip": device_ip,
        "serial_num": serial_num,
        "summary_plan_id": summary_plan_id,
        "summary_plan_name": summary_plan_name,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "status": status,
        "message": message,
        "execute_time": execute_time,
        "progress": progress or {},
        "data": data or {},
        "result_code": result_code,
        "event": event or {},
    }


def _build_plan_execution_payload(plan, status, message, collection_result=None):
    payload = {
        "plan_id": getattr(plan, "id", None),
        "plan_name": getattr(plan, "name", ""),
        "collection_type": getattr(plan, "collection_type", ""),
        "status": status,
        "message": message,
    }
    if collection_result is not None:
        payload.update(
            {
                "netconf_result": collection_result.get("netconf_result"),
                "netmiko_result": collection_result.get("netmiko_result"),
                "snmp_result": collection_result.get("snmp_result"),
                "restconf_result": collection_result.get("restconf_result"),
                "telemetry_result": collection_result.get("telemetry_result"),
                "execute_time": collection_result.get("execute_time", ""),
            }
        )
    return payload


def _rebuild_parent_summary_from_latest_sub_runs(
    *,
    summary_plan_id,
    device_ip,
    execute_time,
    fallback_summary: dict,
) -> dict:
    """按子方案最新记录重算父方案汇总，避免历史失败残留导致父状态误判。"""
    query = {
        "summary_plan_id": summary_plan_id,
        "device_ip": device_ip,
        "execute_time": execute_time,
    }
    sub_runs = list(
        COLLECTION_SUB_PLAN.coll.find(
            query,
            {
                "_id": 0,
                "plan_id": 1,
                "collection_method": 1,
                "task_status": 1,
                "task_errors": 1,
                "log_time": 1,
            },
        )
    )
    if not sub_runs:
        return fallback_summary

    latest_by_plan = {}
    for run in sub_runs:
        plan_id = run.get("plan_id")
        if plan_id is None:
            continue
        existing = latest_by_plan.get(plan_id)
        if (not existing) or float(run.get("log_time", 0) or 0) >= float(
            existing.get("log_time", 0) or 0
        ):
            latest_by_plan[plan_id] = run

    if not latest_by_plan:
        return fallback_summary

    rebuilt = {
        **(fallback_summary or {}),
        "successful_sub_plans": 0,
        "failed_sub_plans": 0,
        "skipped_sub_plans": 0,
        "failed_details": [],
        "skipped_details": [],
    }
    for run in latest_by_plan.values():
        status = str(run.get("task_status") or "").strip().lower()
        method = str(run.get("collection_method") or "").strip() or "unknown"
        task_errors = run.get("task_errors")
        if isinstance(task_errors, list):
            reason = (
                "; ".join(str(item) for item in task_errors if str(item).strip())
                or "sub_plan_failed"
            )
        else:
            reason = str(task_errors or "sub_plan_failed")

        if status in {"success", "finished"}:
            rebuilt["successful_sub_plans"] += 1
        elif status in {"failed", "error"}:
            rebuilt["failed_sub_plans"] += 1
            rebuilt["failed_details"].append(
                {
                    "plan_id": run.get("plan_id"),
                    "collection_method": method,
                    "reason": reason,
                }
            )
        elif status == "skipped":
            rebuilt["skipped_sub_plans"] += 1
            rebuilt["skipped_details"].append(
                {
                    "plan_id": run.get("plan_id"),
                    "collection_method": method,
                    "reason": reason,
                }
            )
        else:
            rebuilt["failed_sub_plans"] += 1
            rebuilt["failed_details"].append(
                {
                    "plan_id": run.get("plan_id"),
                    "collection_method": method,
                    "reason": f"unexpected_status:{status or 'unknown'}",
                }
            )

    rebuilt["failed_details"] = rebuilt["failed_details"][:20]
    rebuilt["skipped_details"] = rebuilt["skipped_details"][:20]
    return rebuilt


def _group_plan_results_by_collection_type(results):
    grouped_results = {}
    for result in results:
        grouped_results.setdefault(result.get("collection_type", ""), []).append(result)
    return grouped_results


def _validate_plan_for_device(plan, device, device_ip: str, use_local: bool):
    enabled_methods = {
        "netmiko": bool(getattr(plan, "netmiko_enabled", False)),
        "netconf": bool(getattr(plan, "netconf_enabled", False)),
        "snmp": bool(getattr(plan, "snmp_enabled", False)),
        "restconf": bool(getattr(plan, "restconf_enabled", False)),
        "telemetry": bool(getattr(plan, "telemetry_enabled", False)),
    }
    if not any(enabled_methods.values()):
        return False, "采集方案未启用任何采集方式"

    available_methods = []
    error_parts = []

    if enabled_methods["netmiko"]:
        if getattr(device, "ssh_account", None):
            available_methods.append("netmiko")
        else:
            error_parts.append("未配置SSH账户")

    if enabled_methods["netconf"]:
        if getattr(device, "netconf_account", None):
            available_methods.append("netconf")
        else:
            error_parts.append("未配置NETCONF账户")

    if use_local:
        if enabled_methods["snmp"]:
            snmp_community = getattr(device, "snmp_community", "")
            if snmp_community and snmp_community != "-":
                available_methods.append("snmp")
            else:
                error_parts.append("未配置SNMP团体字")

        if enabled_methods["restconf"]:
            available_methods.append("restconf")

        if enabled_methods["telemetry"]:
            error_parts.append("Telemetry 仍在延期范围（未纳入默认主链）")
    elif (
        enabled_methods["snmp"]
        or enabled_methods["restconf"]
        or enabled_methods["telemetry"]
    ):
        error_parts.append("南向驱动验证当前仅支持NETMIKO/NETCONF")

    if not available_methods:
        return False, f"设备 {device_ip} {', '.join(error_parts)}"

    return True, "验证通过"


def _count_method_outcomes(execution_result):
    success_count = 0
    failed_count = 0
    for method in (
        "netmiko_result",
        "netconf_result",
        "snmp_result",
        "restconf_result",
        "telemetry_result",
    ):
        result = execution_result.get(method)
        if not result:
            continue
        if result.get("success"):
            success_count += 1
        else:
            failed_count += 1
    return success_count, failed_count


def _summarize_sample_result(execution_result):
    if not isinstance(execution_result, dict):
        return ""
    for key in (
        "message",
        "error",
        "detail",
        "result",
        "status",
    ):
        value = execution_result.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _summary_validation_status_text(success_count, failed_count, skipped_count, total_plans):
    if total_plans <= 0:
        return "待验证"
    if skipped_count == total_plans:
        return "前置校验未通过"
    if failed_count == 0 and skipped_count == 0:
        return "验证成功"
    if success_count > 0:
        return "部分成功"
    return "验证失败"


@shared_task(base=AxeTask, once={"graceful": True}, bind=True)
def run_summary_plan_validation_task(self, task_context):
    from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan

    task_id = str(getattr(self.request, "id", "") or "")
    username = str(task_context.get("username") or "")
    summary_plan_id = task_context.get("summary_plan_id")
    device_id = task_context.get("device_id")
    device_ip = str(task_context.get("device_ip") or "")
    serial_num = str(task_context.get("serial_num") or "")
    use_local = bool(task_context.get("use_local", False))
    south_driver = str(task_context.get("south_driver") or "")
    plan_ids = [int(plan_id) for plan_id in (task_context.get("plan_ids") or [])]
    execute_time = datetime.now().isoformat()

    snapshot = _build_runtime_task_snapshot(
        task_id=task_id,
        task_type="summary_plan_validate",
        username=username,
        device_ip=device_ip,
        serial_num=serial_num,
        summary_plan_id=summary_plan_id,
        status="running",
        message="验证任务已启动",
        execute_time=execute_time,
        progress={
            "current": 0,
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        },
        data={},
    )
    _store_runtime_task_snapshot(snapshot)

    try:
        summary_plan = DeviceCollectionPlans.objects.prefetch_related(
            "collect_plans", "collect_plans__xml_templates"
        ).get(id=summary_plan_id)
        device = NetworkDevice.objects.select_related("idc").get(id=device_id)
        enabled_plans = [
            plan
            for plan in summary_plan.collect_plans.all()
            if (not plan_ids or plan.id in plan_ids)
        ]

        snapshot["summary_plan_name"] = getattr(summary_plan, "name", "")
        snapshot["progress"]["total"] = len(enabled_plans)
        _store_runtime_task_snapshot(snapshot)

        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0

        def publish_plan_progress(plan, current_index, message, event=None, data=None):
            snapshot["status"] = "running"
            snapshot["message"] = message
            snapshot["plan_id"] = getattr(plan, "id", None)
            snapshot["plan_name"] = getattr(plan, "name", "")
            snapshot["progress"] = {
                "current": current_index,
                "total": len(enabled_plans),
                "success_count": success_count,
                "failed_count": failed_count,
                "skipped_count": skipped_count,
            }
            if event is not None:
                snapshot["event"] = event
            if data is not None:
                snapshot["data"] = data
            _store_runtime_task_snapshot(snapshot)

        if use_local:
            shared_device_info = DeviceCollectionService._build_device_info_for_local(
                device,
                execute_time=execute_time,
            )
            with DeviceConnectionManager(
                device.manage_ip, shared_device_info
            ) as conn_mgr:
                for index, plan in enumerate(enabled_plans, start=1):
                    publish_plan_progress(
                        plan,
                        index - 1,
                        f"正在验证 {plan.name} ({index}/{len(enabled_plans)})",
                    )
                    is_valid, error_msg = _validate_plan_for_device(
                        plan,
                        device,
                        device_ip=device_ip or getattr(device, "manage_ip", ""),
                        use_local=use_local,
                    )
                    if not is_valid:
                        results.append(
                            _build_plan_execution_payload(plan, "skipped", error_msg)
                        )
                        skipped_count += 1
                        publish_plan_progress(
                            plan,
                            index,
                            f"{plan.name} 前置校验未通过",
                            event={"stage": "skipped", "message": error_msg},
                            data={
                                "results": _group_plan_results_by_collection_type(
                                    results
                                )
                            },
                        )
                        continue

                    def plan_progress(event):
                        publish_plan_progress(
                            plan,
                            index - 1,
                            event.get("message") or f"正在执行 {plan.name}",
                            event=event,
                            data={
                                "results": _group_plan_results_by_collection_type(
                                    results
                                )
                            },
                        )

                    execution_result = (
                        DeviceCollectionService.execute_both_collection_local(
                            plan,
                            device,
                            connection_manager=conn_mgr,
                            execute_time=execute_time,
                            progress_callback=plan_progress,
                        )
                    )
                    if execution_result.get("success"):
                        results.append(
                            _build_plan_execution_payload(
                                plan,
                                "success",
                                execution_result.get("message", "验证成功"),
                                execution_result,
                            )
                        )
                        success_count += 1
                    else:
                        results.append(
                            _build_plan_execution_payload(
                                plan,
                                "failed",
                                execution_result.get("error", "验证失败"),
                                execution_result,
                            )
                        )
                        failed_count += 1

                    publish_plan_progress(
                        plan,
                        index,
                        f"{plan.name} 已完成 ({index}/{len(enabled_plans)})",
                        event={"stage": "plan_finished"},
                        data={
                            "results": _group_plan_results_by_collection_type(results)
                        },
                    )
        else:
            for index, plan in enumerate(enabled_plans, start=1):
                publish_plan_progress(
                    plan,
                    index - 1,
                    f"正在验证 {plan.name} ({index}/{len(enabled_plans)})",
                )
                is_valid, error_msg = _validate_plan_for_device(
                    plan,
                    device,
                    device_ip=device_ip or getattr(device, "manage_ip", ""),
                    use_local=use_local,
                )
                if not is_valid:
                    results.append(
                        _build_plan_execution_payload(plan, "skipped", error_msg)
                    )
                    skipped_count += 1
                    publish_plan_progress(
                        plan,
                        index,
                        f"{plan.name} 前置校验未通过",
                        event={"stage": "skipped", "message": error_msg},
                        data={
                            "results": _group_plan_results_by_collection_type(results)
                        },
                    )
                    continue

                execution_result = DeviceCollectionService.execute_both_collection(
                    plan,
                    device,
                    south_driver,
                )
                if execution_result.get("success"):
                    results.append(
                        _build_plan_execution_payload(
                            plan,
                            "success",
                            execution_result.get("message", "验证成功"),
                            execution_result,
                        )
                    )
                    success_count += 1
                else:
                    results.append(
                        _build_plan_execution_payload(
                            plan,
                            "failed",
                            execution_result.get("error", "验证失败"),
                            execution_result,
                        )
                    )
                    failed_count += 1

                publish_plan_progress(
                    plan,
                    index,
                    f"{plan.name} 已完成 ({index}/{len(enabled_plans)})",
                    event={"stage": "plan_finished"},
                    data={"results": _group_plan_results_by_collection_type(results)},
                )

        grouped_results = _group_plan_results_by_collection_type(results)
        total_plans = len(enabled_plans)
        if success_count == total_plans:
            message = f"所有采集方案验证成功 ({success_count}/{total_plans})"
        elif success_count > 0:
            message = f"部分采集方案验证成功 ({success_count}/{total_plans})，失败 {failed_count}，跳过 {skipped_count}"
        elif skipped_count == total_plans:
            message = f"所有采集方案均未通过前置校验 ({skipped_count}/{total_plans})"
        else:
            message = f"所有采集方案验证失败 ({failed_count}/{total_plans})"

        result_code = 200 if success_count > 0 else 500
        if skipped_count == total_plans:
            result_code = 400

        # 持久化父方案运行态字段，供列表页实时展示
        summary_plan.recent_validation_status = _summary_validation_status_text(
            success_count,
            failed_count,
            skipped_count,
            total_plans,
        )
        summary_plan.recent_failed_device_count = 0 if result_code == 200 else 1
        summary_plan.save(
            update_fields=[
                "recent_validation_status",
                "recent_failed_device_count",
                "updated_at",
            ]
        )

        # 持久化子方案运行态字段，避免前端只能展示占位值
        for item in results:
            plan_pk = item.get("plan_id")
            if not plan_pk:
                continue
            _, plan_failed_count = _count_method_outcomes(item)
            latest_sample_result = str(item.get("message") or "").strip()
            if not latest_sample_result:
                for method_key in (
                    "netmiko_result",
                    "netconf_result",
                    "snmp_result",
                    "restconf_result",
                    "telemetry_result",
                ):
                    latest_sample_result = _summarize_sample_result(item.get(method_key))
                    if latest_sample_result:
                        break
            DeviceSubCollectionPlan.objects.filter(id=plan_pk).update(
                recent_failed_count=plan_failed_count,
                latest_sample_result=latest_sample_result,
            )

        snapshot["status"] = "finished" if result_code == 200 else "failed"
        snapshot["message"] = message
        snapshot["progress"] = {
            "current": total_plans,
            "total": total_plans,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        }
        snapshot["result_code"] = result_code
        snapshot["data"] = {
            "summary_plan_id": summary_plan.id,
            "summary_plan_name": summary_plan.name,
            "device_ip": device_ip or getattr(device, "manage_ip", ""),
            "serial_num": serial_num,
            "total_plans": total_plans,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": grouped_results,
        }
        snapshot["event"] = {"stage": "finished"}
        _store_runtime_task_snapshot(snapshot)
        return snapshot
    except Exception as exc:
        logger.error(
            "异步父方案验证失败: summary_plan_id=%s device_id=%s error=%s",
            summary_plan_id,
            device_id,
            exc,
            exc_info=True,
        )
        snapshot["status"] = "failed"
        snapshot["message"] = f"验证失败: {exc}"
        snapshot["result_code"] = 500
        snapshot["event"] = {"stage": "failed"}
        _store_runtime_task_snapshot(snapshot)
        raise
    finally:
        release_summary_plan_validation_lock(
            username=username,
            summary_plan_id=summary_plan_id,
            device_ip=device_ip,
            task_id=task_id,
        )


@shared_task(base=AxeTask, once={"graceful": True}, bind=True)
def run_sub_plan_execute_task(self, task_context):
    from apps.device_api.models import DeviceSubCollectionPlan

    task_id = str(getattr(self.request, "id", "") or "")
    username = str(task_context.get("username") or "")
    plan_id = task_context.get("plan_id")
    device_id = task_context.get("device_id")
    device_ip = str(task_context.get("device_ip") or "")
    serial_num = str(task_context.get("serial_num") or "")
    use_local = bool(task_context.get("use_local", False))
    south_driver = str(task_context.get("south_driver") or "")
    execute_time = datetime.now().isoformat()

    snapshot = _build_runtime_task_snapshot(
        task_id=task_id,
        task_type="sub_plan_execute",
        username=username,
        device_ip=device_ip,
        serial_num=serial_num,
        plan_id=plan_id,
        status="running",
        message="子方案测试任务已启动",
        execute_time=execute_time,
        progress={
            "current": 0,
            "total": 5,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        },
        data={},
    )
    _store_runtime_task_snapshot(snapshot)

    try:
        plan = (
            DeviceSubCollectionPlan.objects.select_related("summary_plan")
            .prefetch_related("xml_templates")
            .get(id=plan_id)
        )
        device = NetworkDevice.objects.select_related("idc").get(id=device_id)

        snapshot["summary_plan_id"] = getattr(plan, "summary_plan_id", None)
        snapshot["summary_plan_name"] = getattr(
            getattr(plan, "summary_plan", None), "name", ""
        )
        snapshot["plan_name"] = getattr(plan, "name", "")
        snapshot["data"] = {
            "collection_type": getattr(plan, "collection_type", ""),
            "execute_time": execute_time,
        }
        _store_runtime_task_snapshot(snapshot)

        def publish_protocol_event(event):
            method = str(event.get("collection_method") or "").lower()
            stage = event.get("stage")
            message = event.get("message") or "执行中"
            if method:
                field_name = f"{method}_result"
                if stage == "finished" and isinstance(event.get("result"), dict):
                    snapshot["data"][field_name] = event["result"]
                elif stage == "failed":
                    snapshot["data"][field_name] = {
                        "success": False,
                        "status": "失败",
                        "message": message,
                        "error": message,
                    }
                else:
                    snapshot["data"][field_name] = {
                        "success": None,
                        "status": "执行中",
                        "message": message,
                    }
            snapshot["message"] = message
            snapshot["event"] = event
            success_count, failed_count = _count_method_outcomes(snapshot["data"])
            snapshot["progress"] = {
                "current": min(success_count + failed_count, 5),
                "total": 5,
                "success_count": success_count,
                "failed_count": failed_count,
                "skipped_count": 0,
            }
            _store_runtime_task_snapshot(snapshot)

        if use_local:
            shared_device_info = DeviceCollectionService._build_device_info_for_local(
                device,
                execute_time=execute_time,
            )
            with DeviceConnectionManager(
                device.manage_ip, shared_device_info
            ) as conn_mgr:
                execution_result = (
                    DeviceCollectionService.execute_both_collection_local(
                        plan,
                        device,
                        connection_manager=conn_mgr,
                        execute_time=execute_time,
                        progress_callback=publish_protocol_event,
                    )
                )
        else:
            execution_result = DeviceCollectionService.execute_both_collection(
                plan,
                device,
                south_driver,
            )

        success_count, failed_count = _count_method_outcomes(execution_result)
        latest_sample_result = str(
            execution_result.get("message")
            or execution_result.get("error")
            or ""
        ).strip()
        if not latest_sample_result:
            for method_key in (
                "netmiko_result",
                "netconf_result",
                "snmp_result",
                "restconf_result",
                "telemetry_result",
            ):
                latest_sample_result = _summarize_sample_result(
                    execution_result.get(method_key)
                )
                if latest_sample_result:
                    break
        plan.recent_failed_count = failed_count
        plan.latest_sample_result = latest_sample_result
        plan.save(
            update_fields=["recent_failed_count", "latest_sample_result", "updated_at"]
        )

        analysis_trigger = {
            "scheduled": False,
            "reason": "not_local_execution",
        }
        if use_local:
            analysis_trigger = maybe_schedule_interface_utilization(
                collection_type=getattr(plan, "collection_type", ""),
                device_ip=device_ip or getattr(device, "manage_ip", ""),
                execute_time=execution_result.get("execute_time"),
                triggered_by="device_api-execute_sub_plan-async-local",
            )
        snapshot["data"] = {
            "collection_type": getattr(plan, "collection_type", ""),
            "execute_time": execution_result.get("execute_time", execute_time),
            "analysis_trigger": analysis_trigger,
            "success_count": success_count,
            "failed_count": failed_count,
            "netconf_result": execution_result.get("netconf_result"),
            "netmiko_result": execution_result.get("netmiko_result"),
            "snmp_result": execution_result.get("snmp_result"),
            "restconf_result": execution_result.get("restconf_result"),
            "telemetry_result": execution_result.get("telemetry_result"),
        }
        snapshot["progress"] = {
            "current": min(success_count + failed_count, 5),
            "total": 5,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": 0,
        }
        if execution_result.get("success"):
            snapshot["status"] = "finished"
            snapshot["message"] = execution_result.get("message", "子方案测试完成")
            snapshot["result_code"] = 200
        else:
            snapshot["status"] = "failed"
            snapshot["message"] = execution_result.get("error", "子方案测试失败")
            snapshot["result_code"] = 500
        snapshot["event"] = {"stage": "finished"}
        _store_runtime_task_snapshot(snapshot)
        return snapshot
    except Exception as exc:
        logger.error(
            "异步子方案测试失败: plan_id=%s device_id=%s error=%s",
            plan_id,
            device_id,
            exc,
            exc_info=True,
        )
        snapshot["status"] = "failed"
        snapshot["message"] = f"子方案测试失败: {exc}"
        snapshot["result_code"] = 500
        snapshot["event"] = {"stage": "failed"}
        _store_runtime_task_snapshot(snapshot)
        raise


def _coerce_runtime_flag(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def should_clear_history_before_batch(kwargs=None):
    """决定批次前是否清理批次任务记录。

    默认保持现有行为；灰度对比、回退演练或人工排障时可显式传入
    clear_history=False 保留当前 execute_time 的批次任务记录。
    """
    if not kwargs:
        return True

    return _coerce_runtime_flag(kwargs.get("clear_history", True), default=True)


def should_clear_plan_data_before_batch(kwargs=None):
    """决定批次前是否显式清理 plan_* 明细表。

    默认关闭，统一快照类表通过单设备覆盖写入实现增量更新；只有在明确要求
    全量重建时，才打开 clear_plan_data=True。
    """
    if not kwargs:
        return False

    return _coerce_runtime_flag(kwargs.get("clear_plan_data", False), default=False)


def split_runtime_control_kwargs(kwargs=None):
    """拆分运行控制参数与设备筛选参数。"""
    if not kwargs:
        return {}, {}

    runtime_options = {}
    device_filters = {}
    for key, value in kwargs.items():
        if key in RUNTIME_CONTROL_KWARGS:
            runtime_options[key] = value
        else:
            device_filters[key] = value
    return runtime_options, device_filters


def _binding_source_priority(binding_source: str) -> int:
    priorities = {
        "manual": 0,
        "auto": 1,
        "legacy_bridge": 2,
    }
    return priorities.get(str(binding_source or "").strip(), 99)


def _safe_timestamp(value) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "timestamp"):
        try:
            return float(value.timestamp())
        except (TypeError, ValueError, OSError):
            return 0.0
    return 0.0


def _normalize_string_list(value, default=None):
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        normalized = []
        for item in value:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
        return normalized or list(default or [])
    text = str(value or "").strip()
    if text:
        return [text]
    return list(default or [])


def _host_identity(host: dict) -> str:
    return (
        host.get("device_serial_num")
        or host.get("serial_num")
        or host.get("manage_ip")
        or ""
    )


def _has_executable_sub_plans(host: dict) -> bool:
    return bool(host.get("sub_plans") or [])


def _host_preference_key(host: dict) -> tuple:
    try:
        plan_rank = -(int(host.get("plan_id") or 0))
    except (TypeError, ValueError):
        plan_rank = 0
    return (
        _binding_source_priority(host.get("binding_source")),
        0 if _has_executable_sub_plans(host) else 1,
        0 if host.get("use_local", True) else 1,
        -_safe_timestamp(host.get("last_bound_at")),
        -_safe_timestamp(host.get("binding_updated_at")),
        -_safe_timestamp(host.get("binding_created_at")),
        plan_rank,
    )


def dedupe_batch_hosts(hosts):
    """按设备去重，避免同一批次对同一台设备重复下发采集任务。"""
    deduped_hosts = {}
    duplicate_count = 0
    duplicate_details = []
    for host in hosts or []:
        identity = _host_identity(host)
        if not identity:
            continue
        existing = deduped_hosts.get(identity)
        if existing is None or _host_preference_key(host) < _host_preference_key(
            existing
        ):
            if existing is not None:
                duplicate_count += 1
                duplicate_details.append(
                    {
                        "identity": identity,
                        "kept_manage_ip": host.get("manage_ip"),
                        "kept_plan_id": host.get("plan_id"),
                        "kept_binding_source": host.get("binding_source"),
                        "dropped_manage_ip": existing.get("manage_ip"),
                        "dropped_plan_id": existing.get("plan_id"),
                        "dropped_binding_source": existing.get("binding_source"),
                    }
                )
            deduped_hosts[identity] = host
        else:
            duplicate_count += 1
            duplicate_details.append(
                {
                    "identity": identity,
                    "kept_manage_ip": existing.get("manage_ip"),
                    "kept_plan_id": existing.get("plan_id"),
                    "kept_binding_source": existing.get("binding_source"),
                    "dropped_manage_ip": host.get("manage_ip"),
                    "dropped_plan_id": host.get("plan_id"),
                    "dropped_binding_source": host.get("binding_source"),
                }
            )
    return list(deduped_hosts.values()), duplicate_count, duplicate_details


def _load_batch_profile_rebind_candidates(devices, target_blockers):
    audit_result = PlatformProfileService.audit_device_coverage(devices)
    device_by_identity = {}
    for device in devices:
        serial_num = str(getattr(device, "serial_num", "") or "").strip()
        manage_ip = str(getattr(device, "manage_ip", "") or "").strip()
        if serial_num:
            device_by_identity[f"serial:{serial_num}"] = device
        if manage_ip:
            device_by_identity[f"ip:{manage_ip}"] = device

    candidates = []
    blocker_counter = Counter()
    for item in audit_result.get("results", []):
        blockers = item.get("blockers") or []
        target_items = [
            blocker
            for blocker in blockers
            if str(blocker.get("code") or "") in target_blockers
        ]
        if not target_items:
            continue
        manage_ip = str(item.get("manage_ip") or "").strip()
        serial_num = str(item.get("serial_num") or "").strip()
        device = device_by_identity.get(
            f"serial:{serial_num}"
        ) or device_by_identity.get(f"ip:{manage_ip}")
        if device is None:
            continue
        target_codes = [
            str(blocker.get("code") or "")
            for blocker in target_items
            if blocker.get("code")
        ]
        for code in target_codes:
            blocker_counter[code] += 1
        candidates.append(
            {
                "device_id": getattr(device, "id", None),
                "manage_ip": manage_ip,
                "serial_num": serial_num,
                "vendor_alias": str(item.get("vendor_alias") or ""),
                "model_name": str(item.get("model_name") or ""),
                "target_profile_code": str(item.get("profile_code") or ""),
                "target_plan_name": str(item.get("plan_name") or ""),
                "target_blockers": target_codes,
            }
        )
    return audit_result, candidates, blocker_counter


def _execute_single_batch_profile_rebind(
    candidate, *, rebind=True, skip_manual_conflict=True
):
    from apps.device_api.models import PlansToDevice

    connections.close_all()
    try:
        device = (
            NetworkDevice.objects.select_related(
                "vendor", "category", "model", "ssh_account", "netconf_account"
            )
            .filter(id=candidate.get("device_id"))
            .first()
        )
        if device is None:
            return {
                "manage_ip": candidate.get("manage_ip", ""),
                "serial_num": candidate.get("serial_num", ""),
                "status": "failed",
                "reason": "device_not_found",
                "target_profile_code": candidate.get("target_profile_code", ""),
                "target_plan_name": candidate.get("target_plan_name", ""),
                "target_blockers": candidate.get("target_blockers", []),
            }

        bindings = list(
            PlansToDevice.objects.select_related("plan").filter(
                is_active=True,
                device_serial_num=getattr(device, "serial_num", "") or "",
            )
        )
        if not bindings and getattr(device, "manage_ip", ""):
            bindings = list(
                PlansToDevice.objects.select_related("plan").filter(
                    is_active=True,
                    manage_ip=getattr(device, "manage_ip", ""),
                )
            )

        target_plan_name = str(candidate.get("target_plan_name") or "")
        has_manual_conflict = any(
            getattr(binding, "binding_source", "")
            == getattr(PlansToDevice, "BINDING_SOURCE_MANUAL", "manual")
            and str(getattr(getattr(binding, "plan", None), "name", "") or "")
            != target_plan_name
            for binding in bindings
        )
        if skip_manual_conflict and has_manual_conflict:
            return {
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
                "status": "skipped",
                "reason": "manual_binding_conflict",
                "target_profile_code": candidate.get("target_profile_code", ""),
                "target_plan_name": target_plan_name,
                "target_blockers": candidate.get("target_blockers", []),
                "active_binding_sources": sorted(
                    {
                        str(getattr(binding, "binding_source", "") or "")
                        for binding in bindings
                        if getattr(binding, "binding_source", "")
                    }
                ),
            }

        result = PlatformProfileService.discover_device_capabilities(
            device,
            category_name=str(
                getattr(getattr(device, "category", None), "name", "") or ""
            ).strip(),
            rebind=rebind,
        )
        auto_bind_result = result.get("auto_bind_result") or {}
        changed = any(
            int(auto_bind_result.get(field) or 0) > 0
            for field in ("created", "updated", "retired")
        )

        status = "success"
        reason = "rebind_applied" if changed else "no_binding_change"
        if result.get("status") == "skipped":
            status = "skipped"
            reason = str(result.get("reason") or "discovery_skipped")
        elif result.get("status") != "finished":
            status = "failed"
            reason = str(result.get("reason") or "discovery_failed")
        elif not rebind:
            reason = "discovery_finished"

        return {
            "manage_ip": getattr(device, "manage_ip", ""),
            "serial_num": getattr(device, "serial_num", ""),
            "status": status,
            "reason": reason,
            "target_profile_code": candidate.get("target_profile_code", ""),
            "target_plan_name": target_plan_name,
            "target_blockers": candidate.get("target_blockers", []),
            "matched_profile_before": result.get("matched_profile_before", ""),
            "matched_profile_after": result.get("matched_profile_after", ""),
            "probe_summary": result.get("probe_summary") or {},
            "auto_bind_result": auto_bind_result,
        }
    except Exception as exc:
        return {
            "manage_ip": candidate.get("manage_ip", ""),
            "serial_num": candidate.get("serial_num", ""),
            "status": "failed",
            "reason": str(exc),
            "target_profile_code": candidate.get("target_profile_code", ""),
            "target_plan_name": candidate.get("target_plan_name", ""),
            "target_blockers": candidate.get("target_blockers", []),
        }
    finally:
        connections.close_all()


def execute_batch_profile_rebind(task_id: str, task_context: dict):
    username = str((task_context or {}).get("username") or "")
    manage_ip = str((task_context or {}).get("manage_ip") or "").strip()
    serial_num = str((task_context or {}).get("serial_num") or "").strip()
    vendor_aliases = _normalize_string_list((task_context or {}).get("vendor_aliases"))
    target_blockers = _normalize_string_list(
        (task_context or {}).get("target_blockers"),
        default=BATCH_PROFILE_REBIND_DEFAULT_BLOCKERS,
    )
    limit = max(int((task_context or {}).get("limit") or 0), 0)
    max_workers = max(int((task_context or {}).get("max_workers") or 10), 1)
    max_workers = min(max_workers, BATCH_PROFILE_REBIND_MAX_WORKERS)
    rebind = _coerce_runtime_flag(
        (task_context or {}).get("rebind", True), default=True
    )
    sample_limit = max(
        int(
            (task_context or {}).get("sample_limit")
            or BATCH_PROFILE_REBIND_RESULT_SAMPLE_LIMIT
        ),
        1,
    )
    sample_limit = min(sample_limit, BATCH_PROFILE_REBIND_RESULT_SAMPLE_LIMIT)

    snapshot = _build_runtime_task_snapshot(
        task_id=task_id,
        task_type="batch_profile_rebind",
        username=username,
        device_ip="",
        serial_num="",
        status="running",
        message="批量画像重绑任务已启动",
        execute_time=datetime.now().isoformat(),
        progress={
            "current": 0,
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        },
        data={
            "filters": {
                "manage_ip": manage_ip or None,
                "serial_num": serial_num or None,
                "vendor_aliases": vendor_aliases,
            },
            "target_blockers": target_blockers,
            "max_workers": max_workers,
            "rebind": rebind,
        },
    )
    _store_runtime_task_snapshot(snapshot)

    queryset = NetworkDevice.objects.filter(status=0, auto_enable=True).select_related(
        "vendor",
        "category",
        "model",
        "ssh_account",
        "netconf_account",
    )
    if manage_ip:
        queryset = queryset.filter(manage_ip=manage_ip)
    if serial_num:
        queryset = queryset.filter(serial_num=serial_num)
    if vendor_aliases:
        queryset = queryset.filter(vendor__alias__in=vendor_aliases)
    if limit > 0:
        queryset = queryset[:limit]
    devices = list(queryset)

    audit_result, candidates, blocker_counter = _load_batch_profile_rebind_candidates(
        devices,
        target_blockers=target_blockers,
    )
    snapshot["progress"]["total"] = len(candidates)
    snapshot["data"]["audit_summary"] = audit_result.get("summary", {})
    snapshot["data"]["candidate_summary"] = {
        "count": len(candidates),
        "target_blockers": dict(blocker_counter),
    }
    _store_runtime_task_snapshot(snapshot)

    if not candidates:
        snapshot["status"] = "finished"
        snapshot["message"] = "没有命中可执行的画像重绑候选设备"
        snapshot["result_code"] = 200
        snapshot["event"] = {"stage": "finished"}
        snapshot["data"]["result_summary"] = {"success": 0, "failed": 0, "skipped": 0}
        _store_runtime_task_snapshot(snapshot)
        return snapshot

    result_counter = Counter()
    reason_counter = Counter()
    profile_counter = Counter()
    result_samples = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(candidates))) as executor:
        future_map = {
            executor.submit(
                _execute_single_batch_profile_rebind,
                candidate,
                rebind=rebind,
                skip_manual_conflict=True,
            ): candidate
            for candidate in candidates
        }
        for index, future in enumerate(as_completed(future_map), start=1):
            result = future.result()
            status = str(result.get("status") or "failed")
            reason = str(result.get("reason") or "")
            result_counter[status] += 1
            if reason:
                reason_counter[reason] += 1
            if result.get("target_profile_code"):
                profile_counter[str(result.get("target_profile_code"))] += 1
            if len(result_samples) < sample_limit:
                result_samples.append(result)

            snapshot["progress"] = {
                "current": index,
                "total": len(candidates),
                "success_count": result_counter.get("success", 0),
                "failed_count": result_counter.get("failed", 0),
                "skipped_count": result_counter.get("skipped", 0),
            }
            snapshot["message"] = f"批量画像重绑执行中 ({index}/{len(candidates)})"
            snapshot["data"]["result_summary"] = {
                "success": result_counter.get("success", 0),
                "failed": result_counter.get("failed", 0),
                "skipped": result_counter.get("skipped", 0),
                "reason_summary": dict(reason_counter),
                "target_profile_summary": dict(profile_counter),
            }
            snapshot["data"]["samples"] = result_samples
            if index == len(candidates) or index % 10 == 0:
                _store_runtime_task_snapshot(snapshot)

    snapshot["status"] = (
        "finished" if result_counter.get("failed", 0) < len(candidates) else "failed"
    )
    snapshot["message"] = (
        f"批量画像重绑完成: success={result_counter.get('success', 0)} "
        f"failed={result_counter.get('failed', 0)} skipped={result_counter.get('skipped', 0)}"
    )
    snapshot["result_code"] = (
        200 if result_counter.get("failed", 0) < len(candidates) else 500
    )
    snapshot["event"] = {"stage": "finished"}
    snapshot["data"]["result_summary"] = {
        "success": result_counter.get("success", 0),
        "failed": result_counter.get("failed", 0),
        "skipped": result_counter.get("skipped", 0),
        "reason_summary": dict(reason_counter),
        "target_profile_summary": dict(profile_counter),
    }
    snapshot["data"]["samples"] = result_samples
    _store_runtime_task_snapshot(snapshot)
    return snapshot


def _load_onboarding_device(device_id):
    if not device_id:
        return None
    return (
        NetworkDevice.objects.select_related(
            "vendor", "category", "model", "ssh_account", "netconf_account"
        )
        .filter(id=device_id)
        .first()
    )


def _validate_onboarding_device(device):
    if device is None:
        return "device_not_found"
    status_value = getattr(device, "status", 1)
    if status_value is None:
        status_value = 1
    if int(status_value) != 0:
        return "device_not_online"
    manage_ip = str(getattr(device, "manage_ip", "") or "").strip()
    if not manage_ip or manage_ip == "0.0.0.0":
        return "invalid_manage_ip"
    if not getattr(getattr(device, "category", None), "name", ""):
        return "missing_category"
    has_netconf = getattr(device, "netconf_enable", "") == "account" and getattr(
        device, "netconf_account", None
    )
    has_ssh = getattr(device, "ssh_enable", "") == "account" and getattr(
        device, "ssh_account", None
    )
    if not (has_netconf or has_ssh):
        return "missing_access_account"
    return ""


@shared_task(base=AxeTask, once={"graceful": True})
def onboard_network_device(device_id, trigger="asset_upsert"):
    """为新纳管设备补齐首轮绑定、首轮采集和二次收敛。"""
    connections.close_all()
    result = {
        "device_id": device_id,
        "trigger": trigger,
        "status": "skipped",
        "reason": "",
        "auto_bind_result": None,
        "initial_collection": None,
        "rebind_result": None,
    }

    device = _load_onboarding_device(device_id)
    validation_error = _validate_onboarding_device(device)
    if validation_error:
        result["reason"] = validation_error
        return result

    category_name = str(
        getattr(getattr(device, "category", None), "name", "") or ""
    ).strip()
    try:
        auto_bind_result = (
            PlatformProfileService.auto_bind_device_by_connection_priority(
                device,
                category_name=category_name,
            )
        )
    except ValueError as exc:
        result["reason"] = str(exc)
        return result
    except Exception as exc:
        logger.error(
            "设备 onboarding 自动绑定失败: device_id=%s manage_ip=%s error=%s",
            device_id,
            getattr(device, "manage_ip", ""),
            exc,
            exc_info=True,
        )
        result["status"] = "failed"
        result["reason"] = str(exc)
        return result

    result["auto_bind_result"] = auto_bind_result
    if auto_bind_result.get("status") != "finished":
        result["reason"] = str(
            auto_bind_result.get("reason") or "auto_bind_not_finished"
        )
        return result

    hosts = get_auto_device(device_serial_num=getattr(device, "serial_num", "") or "")
    if not hosts and getattr(device, "manage_ip", ""):
        hosts = get_auto_device(manage_ip=device.manage_ip)
    deduped_hosts, duplicate_count, duplicate_details = dedupe_batch_hosts(hosts)
    selected_host = deduped_hosts[0] if deduped_hosts else None
    result["initial_collection"] = {
        "status": "skipped",
        "reason": "binding_not_ready",
        "duplicate_bindings": duplicate_count,
        "duplicate_details": duplicate_details[:20],
    }
    if selected_host and selected_host.get("sub_plans"):
        collection_result = plan_collect_device(**selected_host)
        result["initial_collection"] = {
            "status": "finished",
            "result": collection_result,
            "duplicate_bindings": duplicate_count,
            "duplicate_details": duplicate_details[:20],
        }
    elif selected_host:
        result["initial_collection"] = {
            "status": "skipped",
            "reason": "missing_sub_plans",
            "duplicate_bindings": duplicate_count,
            "duplicate_details": duplicate_details[:20],
        }

    device = _load_onboarding_device(device_id)
    if device is None:
        result["status"] = "failed"
        result["reason"] = "device_not_found_after_collection"
        return result

    try:
        result["rebind_result"] = PlatformProfileService.auto_bind_devices([device])
    except Exception as exc:
        logger.error(
            "设备 onboarding 二次收敛失败: device_id=%s manage_ip=%s error=%s",
            device_id,
            getattr(device, "manage_ip", ""),
            exc,
            exc_info=True,
        )
        result["status"] = "failed"
        result["reason"] = str(exc)
        return result

    result["status"] = "finished"
    result["reason"] = ""
    return result


@shared_task(base=AxeTask, once={"graceful": True}, bind=True)
def run_batch_profile_rebind_task(self, task_context):
    task_id = str(getattr(self.request, "id", "") or "")
    return execute_batch_profile_rebind(task_id, task_context or {})


def _truncate_preview(value, max_length=1200):
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = repr(value)
    if len(text) > max_length:
        return text[:max_length] + "...(truncated)"
    return text


def _compact_details(data):
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key, value in data.items() if value not in (None, "", [], {}, ())
    }


def _classify_temporary_netmiko_string_result(
    plan: dict, raw_result, collection_method: str
):
    """临时区分 netmiko 字符串结果中的“无配置”与“模板解析失败”。

    仅在命中强特征时判定为设备确实没有相关配置，其余字符串结果仍回落到 TextFSM 失败路径。
    """
    if str(collection_method or "").lower() != "netmiko":
        return None
    if not isinstance(raw_result, str):
        return None

    collection_type = normalize_collection_type_for_storage(plan.get("collection_type"))
    if collection_type in RAW_NETMIKO_COLLECTION_TYPES:
        return None

    output = str(raw_result or "").strip()
    normalized = output.lower()
    if not normalized:
        return {
            "is_known_empty": True,
            "coverage_reason": "netmiko_feature_not_configured",
            "classifier_reason": "empty_cli_output",
        }

    hints = TEMP_NETMIKO_EMPTY_OUTPUT_HINTS.get(collection_type, ())
    if any(hint in normalized for hint in hints):
        return {
            "is_known_empty": True,
            "coverage_reason": "netmiko_feature_not_configured",
            "classifier_reason": "collection_type_specific_hint",
        }

    if any(hint in normalized for hint in TEMP_NETMIKO_ZERO_COUNT_HINTS):
        generic_match = any(
            hint in normalized for hint in TEMP_NETMIKO_GENERIC_EMPTY_HINTS
        )
        return {
            "is_known_empty": True,
            "coverage_reason": "netmiko_feature_not_configured",
            "classifier_reason": (
                "generic_zero_entry_hint" if generic_match else "zero_entry_hint"
            ),
        }

    return {
        "is_known_empty": False,
        "coverage_reason": "",
        "classifier_reason": "raw_cli_output_requires_template",
    }


def _build_local_device_stub(device_info):
    return type(
        "Device",
        (),
        {
            "manage_ip": device_info.get("manage_ip"),
            "name": device_info.get("name", "") or device_info.get("device_name", ""),
            "idc": (
                type(
                    "Idc",
                    (),
                    {
                        "name": device_info.get("idc__name", "")
                        or device_info.get("idc_name", "")
                    },
                )()
                if (device_info.get("idc__name", "") or device_info.get("idc_name", ""))
                else None
            ),
        },
    )()


def _get_collection_method_name(plan, collection_method):
    return DeviceCollectionService._get_local_result_method_name(
        plan, collection_method
    )


def _record_execution_event(
    *,
    event_scope,
    event_type,
    status="",
    severity="info",
    execute_time="",
    device_info=None,
    plan=None,
    collection_method="",
    reason="",
    error="",
    details=None,
):
    device_info = device_info or {}
    plan = plan or {}
    doc = {
        "event_scope": event_scope,
        "event_type": event_type,
        "status": status,
        "severity": severity,
        "execute_time": execute_time or device_info.get("execute_time", ""),
        "device_ip": device_info.get("manage_ip") or device_info.get("device_ip", ""),
        "device_name": device_info.get("name") or device_info.get("device_name", ""),
        "idc_name": device_info.get("idc__name") or device_info.get("idc_name", ""),
        "summary_plan_id": plan.get("summary_plan"),
        "summary_plan_name": plan.get("summary_plan_name", ""),
        "plan_id": plan.get("id"),
        "plan_name": plan.get("name", ""),
        "collection_type": normalize_collection_type_for_storage(
            plan.get("collection_type", "")
        ),
        "collection_method": collection_method,
        "profile_code": device_info.get("profile_code", ""),
        "binding_source": device_info.get("binding_source", ""),
        "reason": reason,
        "error": error,
        "details": _compact_details(details or {}),
        "created_at": datetime.now().isoformat(),
        "log_time": time.time(),
    }
    try:
        # `device_finished` 可能因为 Celery 重试/回调重复产生重复终态事件。
        # 这里按 (event_scope, event_type, execute_time, device_ip) 做幂等 upsert，
        # 保证同一设备同一执行批次只保留一条终态事件。
        if event_scope == "device" and event_type == "device_finished":
            key = {
                "event_scope": doc.get("event_scope", event_scope),
                "event_type": doc.get("event_type", event_type),
                "execute_time": doc.get("execute_time", ""),
                "device_ip": doc.get("device_ip", ""),
            }
            COLLECTION_EXECUTION_LOG.update_one(
                filter=key,
                update={"$set": doc},
                upsert=True,
            )
        else:
            COLLECTION_EXECUTION_LOG.insert_one(doc)
    except Exception as exc:
        logger.warning(
            "写入执行日志失败: scope=%s event=%s device=%s plan=%s execute_time=%s error=%s",
            event_scope,
            event_type,
            doc["device_ip"],
            doc["plan_id"],
            doc["execute_time"],
            exc,
        )


def datas_to_cache():
    # 获取ARP表的所有数据 tables 用来汇总查询条件
    tables = {
        "plan_arp": {
            "_id": 0,
            "ipaddress": 1,
            "idc_name": 1,
            "hostip": 1,
            "macaddress": 1,
            "interface": 1,
        },
        "plan_mac": {
            "_id": 0,
            "idc_name": 1,
            "interface": 1,
            "hostip": 1,
            "macaddress": 1,
        },
        "plan_lldp": {
            "_id": 0,
            "neighborsysname": 1,
            "hostip": 1,
            "local_interface": 1,
            "neighbor_ip": 1,
        },
        "plan_aggre": {"_id": 0, "memberports": 1, "hostip": 1, "aggregroup": 1},
    }

    # arp 以 arp_ + ip 作为key
    def arp_to_cache():
        arp_res = arp_mongo.find(fields={"_id": 0, "log_time": 0})
        arp_result = dict()
        for _arp in arp_res:
            if _arp["ipaddress"] in arp_result.keys():
                arp_result[_arp["ipaddress"]].append(_arp)
            else:
                arp_result[_arp["ipaddress"]] = [_arp]
        for _arp in arp_result.keys():
            cache_key = ("device_arp", _arp)
            cache_network_data("arp_table", *cache_key, data=arp_result[_arp])

    # mac地址 以 idc + mac 地址作为key
    def mac_to_cache():
        # mac_mongo = MongoOps(db='Automation', coll='MACTable')
        mac_res = mac_mongo.find(fields=tables["plan_mac"])
        mac_result = dict()
        for _mac in mac_res:
            if _mac["idc_name"] + "_" + _mac["macaddress"] in mac_result.keys():
                mac_result[_mac["idc_name"] + "_" + _mac["macaddress"]].append(_mac)
            else:
                mac_result[_mac["idc_name"] + "_" + _mac["macaddress"]] = [_mac]
        for _mac in mac_result.keys():
            cache_key = ("device_mac", _mac)
            cache_network_data("mac_table", *cache_key, data=mac_result[_mac])

    # lldp 以 hostip local_interface 作为key
    def lldp_to_cache():
        lldp_res = lldp_mongo.find(fields=tables["plan_lldp"])
        lldp_result = dict()
        for _lldp in lldp_res:
            if _lldp["hostip"] + "_" + _lldp["local_interface"] in lldp_result.keys():
                lldp_result[_lldp["hostip"] + "_" + _lldp["local_interface"]].append(
                    _lldp
                )
            else:
                lldp_result[_lldp["hostip"] + "_" + _lldp["local_interface"]] = [_lldp]
        for _lldp in lldp_result.keys():
            cache.set("lldp_" + _lldp, json.dumps(lldp_result[_lldp]), 3600 * 12)
        # 反向
        reverse_lldp_result = dict()
        for _lldp in lldp_res:
            if _lldp["neighbor_ip"] is None:
                continue
            if not _lldp["neighbor_ip"]:
                continue
            if not _lldp.get("neighbor_port"):
                continue
            if (
                _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                in reverse_lldp_result.keys()
            ):
                reverse_lldp_result[
                    _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                ].append(_lldp)
            else:
                reverse_lldp_result[
                    _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                ] = [_lldp]
        for _lldp in reverse_lldp_result.keys():
            cache.set(
                "lldp_reverse_" + _lldp,
                json.dumps(reverse_lldp_result[_lldp]),
                3600 * 12,
            )

    # lagg 以 hostip aggregroup 作为key
    def aggre_to_cache():
        lagg_res = aggre_port_mongo.find(fields=tables["plan_aggre"])
        lagg_result = dict()
        for _lagg in lagg_res:
            if _lagg["hostip"] + "_" + _lagg["aggregroup"] in lagg_result.keys():
                lagg_result[_lagg["hostip"] + "_" + _lagg["aggregroup"]].append(_lagg)
            else:
                lagg_result[_lagg["hostip"] + "_" + _lagg["aggregroup"]] = [_lagg]
        for _lagg in lagg_result.keys():
            cache.set("lagg_" + _lagg, json.dumps(lagg_result[_lagg]), 3600 * 12)

    content = ""
    init_time = time.time()
    arp_to_cache()
    content += "{}缓存耗时{}秒\n".format("ARP地址库", int(time.time() - init_time))

    start_time = time.time()
    mac_to_cache()
    content += "{}缓存耗时{}秒\n".format("MAC地址库", int(time.time() - start_time))

    # start_time = time.time()
    # lldp_to_cache()
    # content += "{}缓存耗时{}秒\n".format('LLDP库', int(time.time() - start_time))
    #
    # start_time = time.time()
    # aggre_to_cache()
    # content += "{}缓存耗时{}秒\n".format('聚合端口库', int(time.time() - start_time))

    content += "{}缓存耗时{}秒\n".format("总写入", int(time.time() - init_time))
    logger.debug(content)
    return


class MainIn:
    # CMDB 网络设备信息，并写Mongodb
    @staticmethod
    def cmdb_to_mongo():
        # 获取所有设备信息
        all_devs = (
            NetworkDevice.objects.select_related(
                "idc_model",
                "model",
                "role",
                "attribute",
                "category",
                "vendor",
                "idc",
                "framework",
                "zone",
                "rack",
            )
            .prefetch_related("bind_ip", "account")
            .filter(status=0)
            .values(
                "name",
                "idc__name",
                "serial_num",
                "manage_ip",
                "status",
                "chassis",
                "slot",
                "idc_model__name",
                "u_location_start",
                "u_location_end",
                "rack__name",
            )
        )
        MongoNetOps.post_cmdb(all_devs)
        return


def clear_his_collect_res(execute_time=None, clear_plan_data=False):
    """清理批次运行态集合，并按需清理 plan_* 明细表。"""
    COLLECTION_RESULTS_DB.delete()
    COLLECTION_PLAN.delete()
    COLLECTION_SUB_PLAN.delete()
    COLLECTION_EXECUTION_LOG.delete()

    if not clear_plan_data:
        return

    delete_filter = {"execute_time": execute_time} if execute_time else None
    for collect_type in field_mapping.keys():
        MongoOps(db="Automation", coll=f"plan_{collect_type}").delete(delete_filter)
    return


def _get_collection_db(storage_collection_type: str):
    collection_name = build_plan_collection_name(storage_collection_type)
    collection_db = COLLECTION_TYPE_MONGO_MAP.get(storage_collection_type)
    if collection_db:
        return collection_name, collection_db

    collection_db = MongoOps(db="Automation", coll=collection_name)
    logger.warning(f"使用动态创建的 MongoDB 集合: {collection_name}")
    return collection_name, collection_db


def _should_replace_snapshot_rows(storage_collection_type: str) -> bool:
    return storage_collection_type in INCREMENTAL_SNAPSHOT_COLLECTION_TYPES


def _build_snapshot_replace_filter(
    manage_ip: str,
    storage_collection_type: str,
    collection_method: str,
):
    replace_filter = {
        "hostip": manage_ip,
        "collection_type": storage_collection_type,
    }
    if collection_method:
        replace_filter["collection_method"] = collection_method
    return replace_filter


def _replace_snapshot_rows(
    collection_db,
    *,
    manage_ip: str,
    storage_collection_type: str,
    collection_method: str,
    processed_data,
):
    replace_filter = _build_snapshot_replace_filter(
        manage_ip,
        storage_collection_type,
        collection_method,
    )
    collection_db.delete_many(replace_filter)
    if processed_data:
        collection_db.insert_many(processed_data)


@shared_task(base=AxeTask, once={"graceful": True})
def plan_collect_device(**kwargs):
    """
    单个设备采集任务
    执行设备关联的父采集方案下的所有子采集方案

    :param kwargs: 设备信息字典，包含 manage_ip, plan_id, sub_plans 等
                  sub_plans: 子采集方案列表（从get_auto_device传递过来，避免数据库查询）
    :return:
    """
    connections.close_all()
    host_ip = kwargs.get("manage_ip")  # 设备管理IP地址

    if not host_ip or host_ip == "0.0.0.0":
        logger.warning(f"设备IP无效: {host_ip}")
        return {}

    plan_id = kwargs.get("plan_id")
    if not plan_id:
        logger.warning(f"设备 {host_ip} 未关联数据采集方案")
        return {}

    summary_plan_id = None
    execute_time = kwargs.get("execute_time", datetime.now().isoformat())
    task_summary = {
        "total_sub_plans": 0,
        "successful_sub_plans": 0,
        "failed_sub_plans": 0,
        "skipped_sub_plans": 0,
        "coverage_issue_sub_plans": 0,
        "failed_details": [],
        "skipped_details": [],
        "coverage_details": [],
    }
    parent_record_created = False

    try:
        # 使用从get_auto_device传递过来的子采集方案列表
        sub_plans_list = kwargs.get("sub_plans", [])

        if not sub_plans_list:
            logger.warning(
                f"设备 {host_ip} 关联的采集方案不存在、已禁用或没有子采集方案: plan_id={plan_id}"
            )
            _record_execution_event(
                event_scope="device",
                event_type="device_skipped",
                status="skipped",
                severity="warning",
                execute_time=execute_time,
                device_info=kwargs,
                reason="missing_sub_plans",
                details={"plan_id": plan_id},
            )
            return {}

        logger.info(f"开始采集设备 {host_ip}, 子方案数量: {len(sub_plans_list)}")
        _record_execution_event(
            event_scope="device",
            event_type="device_started",
            status="running",
            execute_time=execute_time,
            device_info=kwargs,
            details={
                "plan_id": plan_id,
                "sub_plans_count": len(sub_plans_list),
                "protocol_breakdown": {
                    "netmiko": len(
                        [p for p in sub_plans_list if p.get("netmiko_enabled")]
                    ),
                    "netconf": len(
                        [p for p in sub_plans_list if p.get("netconf_enabled")]
                    ),
                    "snmp": len([p for p in sub_plans_list if p.get("snmp_enabled")]),
                    "restconf": len(
                        [p for p in sub_plans_list if p.get("restconf_enabled")]
                    ),
                    "telemetry": len(
                        [p for p in sub_plans_list if p.get("telemetry_enabled")]
                    ),
                },
            },
        )

        # 在执行采集之前，插入主采集方案记录
        parent_insert_result = DeviceCollectionService.insert_parent_plan_data(
            plan=sub_plans_list[0],
            device_info=kwargs,
            sub_plans_count=len(sub_plans_list),
        )
        parent_record_created = bool(
            isinstance(parent_insert_result, dict)
            and parent_insert_result.get("success")
        )

        summary_plan_id = sub_plans_list[0].get("summary_plan")
        task_summary["total_sub_plans"] = len(sub_plans_list)

        # 使用连接管理器执行所有子采集方案，确保单设备只建立一次连接
        try:
            # 按采集方式分组子方案
            netmiko_plans = [p for p in sub_plans_list if p.get("netmiko_enabled")]
            netconf_plans = [p for p in sub_plans_list if p.get("netconf_enabled")]
            snmp_plans = [p for p in sub_plans_list if p.get("snmp_enabled")]
            restconf_plans = [p for p in sub_plans_list if p.get("restconf_enabled")]
            telemetry_plans = [p for p in sub_plans_list if p.get("telemetry_enabled")]

            # 使用连接管理器执行采集
            with DeviceConnectionManager(host_ip, kwargs) as conn_mgr:
                # NETCONF 端口不可达/能力交换超时：这里先做一次连接可用性预检查，
                # 避免在批量执行中制造大量失败（P0：先清阻塞，再重跑）。
                if netconf_plans:
                    try:
                        conn_mgr.get_netconf_connection()
                    except Exception as e:
                        text = str(e)
                        if any(
                            token in text
                            for token in (
                                "NETCONF账号信息不存在",
                                "Could not open socket",
                                ":830",
                                "Capability exchange timed out",
                                "AuthenticationException",
                                "Authentication failed",
                            )
                        ):
                            for sub_plan in netconf_plans:
                                method_name = _get_collection_method_name(
                                    sub_plan, "netconf"
                                )
                                task_summary["skipped_sub_plans"] += 1
                                task_summary["skipped_details"].append(
                                    {
                                        "plan_id": sub_plan.get("id"),
                                        "collection_method": "netconf",
                                        "reason": "netconf_connection_unavailable",
                                    }
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_skipped",
                                    status="skipped",
                                    severity="warning",
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="netconf",
                                    reason="netconf_connection_unavailable",
                                    error=text,
                                    details={"method_name": method_name},
                                )
                            netconf_plans = []
                        else:
                            raise

                # 执行所有Netmiko采集（复用同一连接）
                for sub_plan in netmiko_plans:
                    sub_plan_started_at = time.time()
                    method_name = _get_collection_method_name(sub_plan, "netmiko")
                    _record_execution_event(
                        event_scope="sub_plan",
                        event_type="sub_plan_started",
                        status="running",
                        execute_time=execute_time,
                        device_info=kwargs,
                        plan=sub_plan,
                        collection_method="netmiko",
                        details={"method_name": method_name},
                    )
                    try:
                        logger.info(
                            f"执行Netmiko采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        command = sub_plan.get("netmiko_method", "")
                        textfsm_template = sub_plan.get("textfsm_template")
                        collection_type = sub_plan.get("collection_type", "")
                        use_textfsm = (
                            collection_type not in RAW_NETMIKO_COLLECTION_TYPES
                        )

                        result = conn_mgr.execute_netmiko_command(
                            command=command,
                            use_textfsm=use_textfsm,
                            textfsm_template=textfsm_template if use_textfsm else None,
                        )

                        # 处理并保存结果
                        process_result = _process_and_save_result(
                            plan=sub_plan,
                            device_info=kwargs,
                            raw_result=result,
                            collection_method="netmiko",
                        )
                        if isinstance(process_result, dict):
                            process_success = process_result.get("success", False)
                            process_reason = process_result.get(
                                "reason", "processing_failed"
                            )
                        else:
                            process_success = bool(process_result)
                            process_reason = "processing_failed"
                        if process_success:
                            task_summary["successful_sub_plans"] += 1
                            if process_result.get("coverage_issue"):
                                task_summary["coverage_issue_sub_plans"] += 1
                                task_summary["coverage_details"].append(
                                    {
                                        "plan_id": sub_plan.get("id"),
                                        "collection_method": "netmiko",
                                        "reason": process_result.get(
                                            "reason", "coverage_issue"
                                        ),
                                    }
                                )
                            logger.info(
                                f"Netmiko采集完成: {sub_plan['name']} (设备: {host_ip})"
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_finished",
                                status="success",
                                severity=(
                                    "warning"
                                    if process_result.get("coverage_issue")
                                    else "info"
                                ),
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netmiko",
                                reason=process_result.get("reason", ""),
                                details={
                                    "method_name": method_name,
                                    "duration_ms": int(
                                        (time.time() - sub_plan_started_at) * 1000
                                    ),
                                    "data_count": process_result.get("data_count", 0),
                                    "coverage_issue": bool(
                                        process_result.get("coverage_issue")
                                    ),
                                },
                            )
                        else:
                            task_summary["failed_sub_plans"] += 1
                            task_summary["failed_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netmiko",
                                    "reason": process_reason,
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_finished",
                                status="failed",
                                severity="error",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netmiko",
                                reason=process_reason,
                                error=process_reason,
                                details={
                                    "method_name": method_name,
                                    "duration_ms": int(
                                        (time.time() - sub_plan_started_at) * 1000
                                    ),
                                },
                            )
                    except Exception as e:
                        text = str(e)
                        # P0：账号缺失类问题不再计入 failed（避免触发验收阻塞指标）
                        if (
                            isinstance(e, ValueError)
                            and "SSH/Telnet账号信息不存在" in text
                        ):
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netmiko",
                                    "reason": "missing_ssh_telnet_account",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netmiko",
                                reason="missing_ssh_telnet_account",
                                details={"method_name": method_name},
                            )
                            continue

                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "netmiko",
                                "reason": text,
                            }
                        )
                        logger.error(
                            f"Netmiko采集异常: {sub_plan['name']} (设备: {host_ip}), {text}",
                            exc_info=True,
                        )
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_exception",
                            status="failed",
                            severity="error",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="netmiko",
                            reason="collection_exception",
                            error=text,
                            details={
                                "method_name": method_name,
                                "duration_ms": int(
                                    (time.time() - sub_plan_started_at) * 1000
                                ),
                            },
                        )

                # 执行所有NETCONF采集（复用同一连接）
                for sub_plan in netconf_plans:
                    sub_plan_started_at = time.time()
                    method_name = _get_collection_method_name(sub_plan, "netconf")
                    _record_execution_event(
                        event_scope="sub_plan",
                        event_type="sub_plan_started",
                        status="running",
                        execute_time=execute_time,
                        device_info=kwargs,
                        plan=sub_plan,
                        collection_method="netconf",
                        details={"method_name": method_name},
                    )
                    try:
                        logger.info(
                            f"执行NETCONF采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        xml_templates = sub_plan.get("xml_templates", [])
                        if xml_templates and len(xml_templates) > 0:
                            selected_template = xml_templates[0]
                            xml_template = selected_template.get("xml_template", "")
                            collect_method = selected_template.get(
                                "collect_method", "get"
                            )

                            if collect_method == "get":
                                result = conn_mgr.execute_netconf_get(xml_template)
                            elif collect_method == "get_config":
                                result = conn_mgr.execute_netconf_get_config(
                                    xml_template
                                )
                            else:
                                raise ValueError(
                                    f"不支持的 NETCONF collect_method: {collect_method}，仅允许 get/get_config"
                                )

                            # 处理并保存结果
                            process_result = _process_and_save_result(
                                plan=sub_plan,
                                device_info=kwargs,
                                raw_result=result,
                                collection_method="netconf",
                            )
                            if isinstance(process_result, dict):
                                process_success = process_result.get("success", False)
                                process_reason = process_result.get(
                                    "reason", "processing_failed"
                                )
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                if process_result.get("coverage_issue"):
                                    task_summary["coverage_issue_sub_plans"] += 1
                                    task_summary["coverage_details"].append(
                                        {
                                            "plan_id": sub_plan.get("id"),
                                            "collection_method": "netconf",
                                            "reason": process_result.get(
                                                "reason", "coverage_issue"
                                            ),
                                        }
                                    )
                                logger.info(
                                    f"NETCONF采集完成: {sub_plan['name']} (设备: {host_ip})"
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="success",
                                    severity=(
                                        "warning"
                                        if process_result.get("coverage_issue")
                                        else "info"
                                    ),
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="netconf",
                                    reason=process_result.get("reason", ""),
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                        "data_count": process_result.get(
                                            "data_count", 0
                                        ),
                                        "coverage_issue": bool(
                                            process_result.get("coverage_issue")
                                        ),
                                    },
                                )
                            else:
                                task_summary["failed_sub_plans"] += 1
                                task_summary["failed_details"].append(
                                    {
                                        "plan_id": sub_plan.get("id"),
                                        "collection_method": "netconf",
                                        "reason": process_reason,
                                    }
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="failed",
                                    severity="error",
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="netconf",
                                    reason=process_reason,
                                    error=process_reason,
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                    },
                                )
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netconf",
                                    "reason": "missing_xml_template",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netconf",
                                reason="missing_xml_template",
                                details={"method_name": method_name},
                            )
                    except Exception as e:
                        text = str(e)
                        # P0：账号缺失 / 端口不可达 / capability 超时类问题不再计入 failed
                        if (
                            isinstance(e, ValueError)
                            and "NETCONF账号信息不存在" in text
                        ):
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netconf",
                                    "reason": "missing_netconf_account",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netconf",
                                reason="missing_netconf_account",
                                details={"method_name": method_name},
                            )
                            continue

                        if any(
                            token in text
                            for token in (
                                "Could not open socket",
                                ":830",
                                "Capability exchange timed out",
                                "AuthenticationException",
                                "Authentication failed",
                            )
                        ):
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netconf",
                                    "reason": "netconf_connection_unavailable",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="netconf",
                                reason="netconf_connection_unavailable",
                                details={"method_name": method_name},
                            )
                            continue

                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "netconf",
                                "reason": text,
                            }
                        )
                        logger.error(
                            f"NETCONF采集异常: {sub_plan['name']} (设备: {host_ip}), {text}",
                            exc_info=True,
                        )
                        # 采集链路严格按 PlansToDevice 执行，只记录运行态事实，不在这里改绑定。
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_exception",
                            status="failed",
                            severity="error",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="netconf",
                            reason="collection_exception",
                            error=text,
                            details={
                                "method_name": method_name,
                                "duration_ms": int(
                                    (time.time() - sub_plan_started_at) * 1000
                                ),
                            },
                        )

                # 执行所有SNMP采集（复用同一会话）
                for sub_plan in snmp_plans:
                    sub_plan_started_at = time.time()
                    method_name = _get_collection_method_name(sub_plan, "snmp")
                    _record_execution_event(
                        event_scope="sub_plan",
                        event_type="sub_plan_started",
                        status="running",
                        execute_time=execute_time,
                        device_info=kwargs,
                        plan=sub_plan,
                        collection_method="snmp",
                        details={"method_name": method_name},
                    )
                    try:
                        logger.info(
                            f"执行SNMP采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        oids = sub_plan.get("snmp_oids", [])
                        if oids:
                            result = conn_mgr.execute_snmp_get(oids)

                            # 处理并保存结果
                            process_result = _process_and_save_result(
                                plan=sub_plan,
                                device_info=kwargs,
                                raw_result=result,
                                collection_method="snmp",
                            )
                            if isinstance(process_result, dict):
                                process_success = process_result.get("success", False)
                                process_reason = process_result.get(
                                    "reason", "processing_failed"
                                )
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                if process_result.get("coverage_issue"):
                                    task_summary["coverage_issue_sub_plans"] += 1
                                    task_summary["coverage_details"].append(
                                        {
                                            "plan_id": sub_plan.get("id"),
                                            "collection_method": "snmp",
                                            "reason": process_result.get(
                                                "reason", "coverage_issue"
                                            ),
                                        }
                                    )
                                logger.info(
                                    f"SNMP采集完成: {sub_plan['name']} (设备: {host_ip})"
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="success",
                                    severity=(
                                        "warning"
                                        if process_result.get("coverage_issue")
                                        else "info"
                                    ),
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="snmp",
                                    reason=process_result.get("reason", ""),
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                        "data_count": process_result.get(
                                            "data_count", 0
                                        ),
                                        "coverage_issue": bool(
                                            process_result.get("coverage_issue")
                                        ),
                                    },
                                )
                            else:
                                task_summary["failed_sub_plans"] += 1
                                task_summary["failed_details"].append(
                                    {
                                        "plan_id": sub_plan.get("id"),
                                        "collection_method": "snmp",
                                        "reason": process_reason,
                                    }
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="failed",
                                    severity="error",
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="snmp",
                                    reason=process_reason,
                                    error=process_reason,
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                    },
                                )
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "snmp",
                                    "reason": "missing_snmp_oids",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="snmp",
                                reason="missing_snmp_oids",
                                details={"method_name": method_name},
                            )
                    except Exception as e:
                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "snmp",
                                "reason": str(e),
                            }
                        )
                        logger.error(
                            f"SNMP采集异常: {sub_plan['name']} (设备: {host_ip}), {str(e)}",
                            exc_info=True,
                        )
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_exception",
                            status="failed",
                            severity="error",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="snmp",
                            reason="collection_exception",
                            error=str(e),
                            details={
                                "method_name": method_name,
                                "duration_ms": int(
                                    (time.time() - sub_plan_started_at) * 1000
                                ),
                            },
                        )

                # 执行所有RESTCONF采集（复用同一会话）
                for sub_plan in restconf_plans:
                    sub_plan_started_at = time.time()
                    method_name = _get_collection_method_name(sub_plan, "restconf")
                    _record_execution_event(
                        event_scope="sub_plan",
                        event_type="sub_plan_started",
                        status="running",
                        execute_time=execute_time,
                        device_info=kwargs,
                        plan=sub_plan,
                        collection_method="restconf",
                        details={"method_name": method_name},
                    )
                    try:
                        logger.info(
                            f"执行RESTCONF采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        endpoint = sub_plan.get("restconf_endpoint", "")
                        if endpoint:
                            result = conn_mgr.execute_restconf_get(endpoint)

                            # 处理并保存结果
                            process_result = _process_and_save_result(
                                plan=sub_plan,
                                device_info=kwargs,
                                raw_result=result,
                                collection_method="restconf",
                            )
                            if isinstance(process_result, dict):
                                process_success = process_result.get("success", False)
                                process_reason = process_result.get(
                                    "reason", "processing_failed"
                                )
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                if process_result.get("coverage_issue"):
                                    task_summary["coverage_issue_sub_plans"] += 1
                                    task_summary["coverage_details"].append(
                                        {
                                            "plan_id": sub_plan.get("id"),
                                            "collection_method": "restconf",
                                            "reason": process_result.get(
                                                "reason", "coverage_issue"
                                            ),
                                        }
                                    )
                                logger.info(
                                    f"RESTCONF采集完成: {sub_plan['name']} (设备: {host_ip})"
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="success",
                                    severity=(
                                        "warning"
                                        if process_result.get("coverage_issue")
                                        else "info"
                                    ),
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="restconf",
                                    reason=process_result.get("reason", ""),
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                        "data_count": process_result.get(
                                            "data_count", 0
                                        ),
                                        "coverage_issue": bool(
                                            process_result.get("coverage_issue")
                                        ),
                                    },
                                )
                            else:
                                task_summary["failed_sub_plans"] += 1
                                task_summary["failed_details"].append(
                                    {
                                        "plan_id": sub_plan.get("id"),
                                        "collection_method": "restconf",
                                        "reason": process_reason,
                                    }
                                )
                                _record_execution_event(
                                    event_scope="sub_plan",
                                    event_type="sub_plan_finished",
                                    status="failed",
                                    severity="error",
                                    execute_time=execute_time,
                                    device_info=kwargs,
                                    plan=sub_plan,
                                    collection_method="restconf",
                                    reason=process_reason,
                                    error=process_reason,
                                    details={
                                        "method_name": method_name,
                                        "duration_ms": int(
                                            (time.time() - sub_plan_started_at) * 1000
                                        ),
                                    },
                                )
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "restconf",
                                    "reason": "missing_restconf_endpoint",
                                }
                            )
                            _record_execution_event(
                                event_scope="sub_plan",
                                event_type="sub_plan_skipped",
                                status="skipped",
                                severity="warning",
                                execute_time=execute_time,
                                device_info=kwargs,
                                plan=sub_plan,
                                collection_method="restconf",
                                reason="missing_restconf_endpoint",
                                details={"method_name": method_name},
                            )
                    except Exception as e:
                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "restconf",
                                "reason": str(e),
                            }
                        )
                        logger.error(
                            f"RESTCONF采集异常: {sub_plan['name']} (设备: {host_ip}), {str(e)}",
                            exc_info=True,
                        )
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_exception",
                            status="failed",
                            severity="error",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="restconf",
                            reason="collection_exception",
                            error=str(e),
                            details={
                                "method_name": method_name,
                                "duration_ms": int(
                                    (time.time() - sub_plan_started_at) * 1000
                                ),
                            },
                        )

                # 执行所有Telemetry采集（复用同一通道）
                for sub_plan in telemetry_plans:
                    method_name = _get_collection_method_name(sub_plan, "telemetry")
                    try:
                        logger.info(
                            f"执行Telemetry采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        logger.warning(
                            "Telemetry 仍在延期范围，本批次跳过执行: sub_plan=%s, device=%s",
                            sub_plan.get("name"),
                            host_ip,
                        )
                        task_summary["skipped_sub_plans"] += 1
                        task_summary["skipped_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "telemetry",
                                "reason": "telemetry_deferred",
                            }
                        )
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_skipped",
                            status="skipped",
                            severity="warning",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="telemetry",
                            reason="telemetry_deferred",
                            details={"method_name": method_name},
                        )
                    except Exception as e:
                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "telemetry",
                                "reason": str(e),
                            }
                        )
                        logger.error(
                            f"Telemetry采集异常: {sub_plan['name']} (设备: {host_ip}), {str(e)}",
                            exc_info=True,
                        )
                        _record_execution_event(
                            event_scope="sub_plan",
                            event_type="sub_plan_exception",
                            status="failed",
                            severity="error",
                            execute_time=execute_time,
                            device_info=kwargs,
                            plan=sub_plan,
                            collection_method="telemetry",
                            reason="collection_exception",
                            error=str(e),
                            details={"method_name": method_name},
                        )

            # 连接自动关闭（通过上下文管理器）
            logger.info(f"设备 {host_ip} 所有采集任务完成，连接已关闭")
        except Exception as e:
            logger.error(f"设备 {host_ip} 连接或采集异常: {str(e)}", exc_info=True)
            raise

        task_summary = _rebuild_parent_summary_from_latest_sub_runs(
            summary_plan_id=summary_plan_id,
            device_ip=host_ip,
            execute_time=execute_time,
            fallback_summary=task_summary,
        )

        parent_task_status = "success"
        if task_summary["successful_sub_plans"] == 0:
            if task_summary["failed_sub_plans"] > 0:
                parent_task_status = "failed"
            elif task_summary["skipped_sub_plans"] > 0:
                parent_task_status = "skipped"
        elif task_summary["failed_sub_plans"] > 0:
            parent_task_status = "partial_success"

        try:
            update_result = COLLECTION_PLAN.update_one(
                filter={
                    "summary_plan_id": summary_plan_id,
                    "device_ip": host_ip,
                    "execute_time": execute_time,
                },
                update={
                    "$set": {
                        "task_status": parent_task_status,
                        "successful_sub_plans": task_summary["successful_sub_plans"],
                        "failed_sub_plans": task_summary["failed_sub_plans"],
                        "skipped_sub_plans": task_summary["skipped_sub_plans"],
                        "coverage_issue_sub_plans": task_summary[
                            "coverage_issue_sub_plans"
                        ],
                        "failed_details": task_summary["failed_details"][:20],
                        "skipped_details": task_summary["skipped_details"][:20],
                        "coverage_details": task_summary["coverage_details"][:20],
                        "updated_at": datetime.now().isoformat(),
                    }
                },
            )
            if parent_record_created and getattr(update_result, "matched_count", 1) == 0:
                # 兜底更新最近一条 running 记录，避免父任务状态长期停留在 running。
                fallback_doc = None
                try:
                    fallback_doc = COLLECTION_PLAN.coll.find_one(
                        {
                            "summary_plan_id": summary_plan_id,
                            "device_ip": host_ip,
                            "task_status": "running",
                        },
                        {"_id": 0, "execute_time": 1},
                        sort=[("log_time", -1)],
                    )
                except Exception:
                    logger.warning(
                        "查询 running 父任务记录失败: device=%s summary_plan_id=%s execute_time=%s",
                        host_ip,
                        summary_plan_id,
                        execute_time,
                        exc_info=True,
                    )
                fallback_execute_time = (fallback_doc or {}).get("execute_time")
                if fallback_execute_time:
                    COLLECTION_PLAN.update_one(
                        filter={
                            "summary_plan_id": summary_plan_id,
                            "device_ip": host_ip,
                            "execute_time": fallback_execute_time,
                        },
                        update={
                            "$set": {
                                "task_status": parent_task_status,
                                "successful_sub_plans": task_summary["successful_sub_plans"],
                                "failed_sub_plans": task_summary["failed_sub_plans"],
                                "skipped_sub_plans": task_summary["skipped_sub_plans"],
                                "coverage_issue_sub_plans": task_summary[
                                    "coverage_issue_sub_plans"
                                ],
                                "failed_details": task_summary["failed_details"][:20],
                                "skipped_details": task_summary["skipped_details"][:20],
                                "coverage_details": task_summary["coverage_details"][:20],
                                "updated_at": datetime.now().isoformat(),
                            }
                        },
                    )
        except Exception as e:
            logger.warning(
                "更新主采集任务状态失败: device=%s summary_plan_id=%s execute_time=%s error=%s",
                host_ip,
                summary_plan_id,
                execute_time,
                e,
            )

        logger.info(f"设备 {host_ip} 采集完成, 总计: {len(sub_plans_list)}")
        _record_execution_event(
            event_scope="device",
            event_type="device_finished",
            status=parent_task_status,
            severity=(
                "warning"
                if task_summary["failed_sub_plans"]
                or task_summary["coverage_issue_sub_plans"]
                else "info"
            ),
            execute_time=execute_time,
            device_info=kwargs,
            details={
                "total_sub_plans": len(sub_plans_list),
                "successful_sub_plans": task_summary["successful_sub_plans"],
                "failed_sub_plans": task_summary["failed_sub_plans"],
                "skipped_sub_plans": task_summary["skipped_sub_plans"],
                "coverage_issue_sub_plans": task_summary["coverage_issue_sub_plans"],
            },
        )

        return {
            "host_ip": host_ip,
            "total": len(sub_plans_list),
            "execute_time": execute_time,
            "task_status": parent_task_status,
            **task_summary,
        }
    except Exception as e:
        logger.error(f"设备 {host_ip} 采集任务异常: {str(e)}", exc_info=True)
        _record_execution_event(
            event_scope="device",
            event_type="device_exception",
            status="failed",
            severity="error",
            execute_time=execute_time,
            device_info=kwargs,
            reason="device_task_exception",
            error=str(e),
            details={"total_sub_plans": task_summary["total_sub_plans"]},
        )
        if parent_record_created and summary_plan_id is not None:
            try:
                update_result = COLLECTION_PLAN.update_one(
                    filter={
                        "summary_plan_id": summary_plan_id,
                        "device_ip": host_ip,
                        "execute_time": execute_time,
                    },
                    update={
                        "$set": {
                            "task_status": "failed",
                            "failed_sub_plans": max(
                                task_summary["failed_sub_plans"], 1
                            ),
                            "coverage_issue_sub_plans": task_summary[
                                "coverage_issue_sub_plans"
                            ],
                            "failed_details": (
                                task_summary["failed_details"][:20]
                                + [
                                    {
                                        "plan_id": None,
                                        "collection_method": "device",
                                        "reason": str(e),
                                    }
                                ]
                            )[:20],
                            "coverage_details": task_summary["coverage_details"][:20],
                            "updated_at": datetime.now().isoformat(),
                        }
                    },
                )
                if getattr(update_result, "matched_count", 1) == 0:
                    fallback_doc = None
                    try:
                        fallback_doc = COLLECTION_PLAN.coll.find_one(
                            {
                                "summary_plan_id": summary_plan_id,
                                "device_ip": host_ip,
                                "task_status": "running",
                            },
                            {"_id": 0, "execute_time": 1},
                            sort=[("log_time", -1)],
                        )
                    except Exception:
                        logger.warning(
                            "设备级异常后查询 running 父任务记录失败: device=%s summary_plan_id=%s execute_time=%s",
                            host_ip,
                            summary_plan_id,
                            execute_time,
                            exc_info=True,
                        )
                    fallback_execute_time = (fallback_doc or {}).get("execute_time")
                    if fallback_execute_time:
                        COLLECTION_PLAN.update_one(
                            filter={
                                "summary_plan_id": summary_plan_id,
                                "device_ip": host_ip,
                                "execute_time": fallback_execute_time,
                            },
                            update={
                                "$set": {
                                    "task_status": "failed",
                                    "failed_sub_plans": max(
                                        task_summary["failed_sub_plans"], 1
                                    ),
                                    "coverage_issue_sub_plans": task_summary[
                                        "coverage_issue_sub_plans"
                                    ],
                                    "failed_details": (
                                        task_summary["failed_details"][:20]
                                        + [
                                            {
                                                "plan_id": None,
                                                "collection_method": "device",
                                                "reason": str(e),
                                            }
                                        ]
                                    )[:20],
                                    "coverage_details": task_summary["coverage_details"][:20],
                                    "updated_at": datetime.now().isoformat(),
                                }
                            },
                        )
            except Exception as update_error:
                logger.warning(
                    "设备级异常后更新主采集任务失败: device=%s summary_plan_id=%s execute_time=%s error=%s",
                    host_ip,
                    summary_plan_id,
                    execute_time,
                    update_error,
                )
        return {
            "host_ip": host_ip,
            "total": task_summary["total_sub_plans"],
            "execute_time": execute_time,
            "task_status": "failed",
            **task_summary,
        }


def _process_and_save_result(
    plan: dict, device_info: dict, raw_result, collection_method: str
):
    """
    处理并保存采集结果：数据预处理 → 元数据注入 → 写入 MongoDB。

    Args:
        plan: 子采集方案字典
        device_info: 设备信息字典
        raw_result: 原始采集结果
        collection_method: 采集方式
    """
    try:
        manage_ip = device_info.get("manage_ip")
        execute_time = device_info.get("execute_time", datetime.now().isoformat())
        method_name = _get_collection_method_name(plan, collection_method)
        device_stub = _build_local_device_stub(device_info)

        # 构建 plan ORM 对象（用于 resolve_raw_data）
        from apps.device_api.models import DeviceSubCollectionPlan

        try:
            plan_obj = DeviceSubCollectionPlan.objects.select_related(
                "summary_plan"
            ).get(id=plan.get("id"))
        except DeviceSubCollectionPlan.DoesNotExist:
            logger.warning(f"采集方案不存在: plan_id={plan.get('id')}")
            return {"success": False, "reason": "plan_not_found"}

        # ── Layer 1 + 2：数据解析与规范化 ────────────────────────────────
        temp_string_result = _classify_temporary_netmiko_string_result(
            plan,
            raw_result,
            collection_method,
        )
        if temp_string_result and temp_string_result.get("is_known_empty"):
            logger.info(
                "临时识别为无相关配置或空表项: device=%s type=%s method=%s command=%s classifier=%s",
                manage_ip,
                normalize_collection_type_for_storage(plan.get("collection_type")),
                collection_method,
                method_name,
                temp_string_result.get("classifier_reason", ""),
            )
            resolve_status = True
            resolve_error = ""
            processed_data = []
        else:
            collection_result = {"data": raw_result, "device_ip": manage_ip}
            resolve_status, resolve_error, processed_data = resolve_raw_data(
                plan_obj, collection_result, collection_method
            )

            if not resolve_status:
                logger.error(
                    f"数据处理失败: {manage_ip}, method={collection_method}, error={resolve_error}"
                )
                DeviceFactService.mark_discovery_failure(device_info, resolve_error)
                save_local_collection_result(
                    plan_obj,
                    device_stub,
                    collection_method,
                    method_name,
                    raw_result,
                    [],
                    "error",
                    resolve_error,
                )
                return {"success": False, "reason": resolve_error or "resolve_failed"}

        # ── Layer 3：元数据注入 ──────────────────────────────────────────
        meta = {
            "hostip": manage_ip,
            "hostname": device_info.get("name", "")
            or device_info.get("device_name", ""),
            "idc_name": device_info.get("idc__name", "")
            or device_info.get("idc_name", ""),
        }
        inject_metadata(processed_data, meta)
        collection_type = plan.get("collection_type")
        storage_collection_type = normalize_collection_type_for_storage(collection_type)
        inject_collection_context(
            processed_data,
            {
                "summary_plan_id": plan.get("summary_plan"),
                "plan_id": plan.get("id"),
                "collection_type": storage_collection_type,
                "collection_method": collection_method,
                "execute_time": execute_time,
            },
        )

        # ── 写入类型专属 MongoDB 集合 ─────────────────────────────────────
        data_count = len(processed_data) if isinstance(processed_data, list) else 0
        coverage_issue = False
        coverage_reason = ""
        if isinstance(processed_data, list) and storage_collection_type:
            collection_name, collection_db = _get_collection_db(storage_collection_type)
            try:
                if _should_replace_snapshot_rows(storage_collection_type):
                    _replace_snapshot_rows(
                        collection_db,
                        manage_ip=manage_ip,
                        storage_collection_type=storage_collection_type,
                        collection_method=collection_method,
                        processed_data=processed_data,
                    )
                    logger.info(
                        "采集快照已覆盖更新: %s, type=%s, method=%s, count=%s, collection=%s",
                        manage_ip,
                        storage_collection_type,
                        collection_method,
                        len(processed_data),
                        collection_name,
                    )
                elif processed_data:
                    collection_db.insert_many(processed_data)
                    logger.info(
                        "采集数据已保存: %s, type=%s, method=%s, count=%s, collection=%s",
                        manage_ip,
                        storage_collection_type,
                        collection_method,
                        len(processed_data),
                        collection_name,
                    )
            except Exception as e:
                logger.error(
                    f"保存采集数据到 MongoDB 失败: {manage_ip}, type={storage_collection_type}, {str(e)}",
                    exc_info=True,
                )
                save_local_collection_result(
                    plan_obj,
                    device_stub,
                    collection_method,
                    method_name,
                    raw_result,
                    processed_data,
                    "error",
                    str(e),
                )
                return {"success": False, "reason": str(e)}

            if not processed_data:
                logger.warning(
                    "采集结果为空，已清理旧快照: %s, type=%s, method=%s, collection=%s",
                    manage_ip,
                    storage_collection_type,
                    collection_method,
                    collection_name,
                )
                coverage_issue = True
                coverage_reason = (
                    temp_string_result.get("coverage_reason")
                    if temp_string_result and temp_string_result.get("is_known_empty")
                    else "empty_processed_data"
                )
        else:
            logger.warning(
                f"采集结果为空或无法保存: {manage_ip}, type={storage_collection_type}, "
                f"method={collection_method}"
            )
            coverage_issue = True
            if not storage_collection_type:
                coverage_reason = "missing_storage_collection_type"
            else:
                coverage_reason = (
                    temp_string_result.get("coverage_reason")
                    if temp_string_result and temp_string_result.get("is_known_empty")
                    else "empty_processed_data"
                )

        DeviceFactService.update_from_processed_data(
            collection_type=storage_collection_type,
            device_info=device_info,
            processed_data=processed_data,
        )

        # ── 更新子采集任务状态 ────────────────────────────────────────────
        task_record = {
            "summary_plan_id": plan.get("summary_plan"),
            "plan_id": plan.get("id"),
            "task_id": f"{manage_ip}_{plan.get('id')}_{collection_method}_{int(time.time())}",
            "device_ip": manage_ip,
            "device_name": device_info.get("name"),
            "idc_name": device_info.get("idc__name"),
            "task_status": "success",
            "collection_type": storage_collection_type,
            "collection_method": collection_method,
            "method_name": method_name,
            "vendor": plan.get("summary_plan_vendor"),
            "device_type": plan.get("summary_plan_device_type"),
            "execute_time": execute_time,
            "data_count": data_count,
            "coverage_issue": coverage_issue,
            "coverage_reason": coverage_reason,
            "raw_result_preview": _truncate_preview(raw_result),
            "created_at": datetime.now().isoformat(),
            "task_errors": [],
            "log_time": time.time(),
        }
        COLLECTION_SUB_PLAN.insert_one(task_record)
        save_local_collection_result(
            plan_obj,
            device_stub,
            collection_method,
            method_name,
            raw_result,
            processed_data,
            "success",
            coverage_reason if coverage_issue else None,
        )

    except Exception as e:
        logger.error(
            f"处理并保存采集结果异常: {device_info.get('manage_ip')}, "
            f"method={collection_method}, {str(e)}",
            exc_info=True,
        )
        DeviceFactService.mark_discovery_failure(device_info, str(e))
        if "plan_obj" in locals():
            try:
                save_local_collection_result(
                    plan_obj,
                    device_stub,
                    collection_method,
                    method_name,
                    raw_result,
                    [],
                    "error",
                    str(e),
                )
            except Exception:
                pass
        return {"success": False, "reason": str(e)}

    return {
        "success": True,
        "reason": coverage_reason,
        "coverage_issue": coverage_issue,
        "data_count": data_count,
    }


# 通用信息采集主调度任务
@shared_task(base=AxeTask, once={"graceful": True})
def plan_collect_device_main(**kwargs):
    logger.info("开始执行设备信息采集主调度任务")
    datas_to_cache()  # 将数据写入缓存/
    logger.info("数据缓存更新完成")
    runtime_options, device_filters = split_runtime_control_kwargs(kwargs)
    clear_history = should_clear_history_before_batch(runtime_options)
    clear_plan_data = should_clear_plan_data_before_batch(runtime_options)

    # 运行态排障集合需要在批次开始前清空，避免多轮全局采集结果混在一起。
    if clear_history:
        try:
            clear_his_collect_res(clear_plan_data=clear_plan_data)
            logger.info("批次运行态记录已清理: clear_plan_data=%s", clear_plan_data)
        except Exception as e:
            logger.warning(f"清空历史采集数据失败: {str(e)}")
            _record_execution_event(
                event_scope="batch",
                event_type="batch_history_clear_failed",
                status="failed",
                severity="error",
                reason="clear_history_failed",
                error=str(e),
                details={
                    "clear_history": True,
                    "clear_plan_data": clear_plan_data,
                },
            )
            raise RuntimeError(f"清空历史采集数据失败: {str(e)}") from e
    else:
        logger.info("本批次保留历史采集数据: clear_history=False")

    # 同步CMDB设备信息到MongoDB
    try:
        MainIn.cmdb_to_mongo()
        logger.info("CMDB设备信息已同步到MongoDB")
    except Exception as e:
        logger.warning(f"同步CMDB设备信息到MongoDB失败: {str(e)}")

    # 获取设备列表
    if device_filters:
        # 如果有过滤条件，使用过滤条件获取设备
        hosts = get_auto_device(**device_filters)
    else:
        # 获取所有符合条件的设备（status=0, auto_enable=True, 有采集方案）
        hosts = get_auto_device()

    logger.info(f"获取所有设备信息结束，获取到 {len(hosts)} 个设备信息")
    batch_execute_time = hosts[0].get("execute_time") if hosts else ""
    _record_execution_event(
        event_scope="batch",
        event_type="batch_hosts_loaded",
        status="running",
        execute_time=batch_execute_time,
        details={
            "requested_filters": device_filters,
            "runtime_options": runtime_options,
            "fetched_devices": len(hosts),
        },
    )

    deduped_hosts, duplicate_count, duplicate_details = dedupe_batch_hosts(hosts)
    if duplicate_count:
        logger.warning("批次调度已去重重复设备绑定: duplicates=%s", duplicate_count)
        for duplicate in duplicate_details[:100]:
            _record_execution_event(
                event_scope="device",
                event_type="device_deduplicated",
                status="skipped",
                severity="warning",
                execute_time=batch_execute_time,
                device_info={"manage_ip": duplicate.get("dropped_manage_ip", "")},
                reason="duplicate_binding_deduped",
                details=duplicate,
            )

    skipped_hosts_without_sub_plans = [
        host for host in deduped_hosts if not (host.get("sub_plans") or [])
    ]
    if skipped_hosts_without_sub_plans:
        logger.warning(
            "批次调度跳过无可执行子方案设备: count=%s",
            len(skipped_hosts_without_sub_plans),
        )
        for host in skipped_hosts_without_sub_plans[:100]:
            _record_execution_event(
                event_scope="device",
                event_type="device_skipped",
                status="skipped",
                severity="warning",
                execute_time=host.get("execute_time", batch_execute_time),
                device_info=host,
                reason="missing_sub_plans",
                details={
                    "plan_id": host.get("plan_id"),
                    "profile_code": host.get("profile_code", ""),
                    "binding_source": host.get("binding_source", ""),
                },
            )

    valid_hosts = [host for host in deduped_hosts if host.get("sub_plans")]

    # 参数初始化
    net_tower_tasks = []  # 采集任务id集合
    dispatch_failures = []
    total_expected_subtasks = sum(
        len(host.get("sub_plans", [])) for host in valid_hosts
    )
    total_expected_interface_devices = count_expected_interface_devices(valid_hosts)
    batch_execute_time = (
        deduped_hosts[0].get("execute_time") if deduped_hosts else batch_execute_time
    )

    # 清空历史采集数据
    if clear_history:
        _record_execution_event(
            event_scope="batch",
            event_type="batch_history_cleared",
            status="success",
            execute_time=batch_execute_time,
            details={
                "clear_history": True,
                "clear_plan_data": clear_plan_data,
            },
        )
    else:
        _record_execution_event(
            event_scope="batch",
            event_type="batch_history_retained",
            status="skipped",
            execute_time=batch_execute_time,
            reason="clear_history_disabled",
        )

    start_time = time.time()
    dispatched_hosts = []

    # 批量下发任务
    for host in valid_hosts:
        host = dict(host or {})
        host.setdefault("triggered_by", "device_api-plan_collect_device_main")
        host_ip = host.get("manage_ip")
        try:
            task = plan_collect_device.apply_async(
                kwargs=host, queue=CELERY_QUEUE, retry=True
            )
            net_tower_tasks.append(task)
            dispatched_hosts.append(host)
            logger.debug(f"已下发采集任务: {host_ip}, task_id: {task.id}")
            _record_execution_event(
                event_scope="device",
                event_type="device_dispatched",
                status="queued",
                execute_time=host.get("execute_time", batch_execute_time),
                device_info=host,
                details={
                    "celery_task_id": task.id,
                    "plan_id": host.get("plan_id"),
                    "sub_plans_count": len(host.get("sub_plans", [])),
                    "queue": CELERY_QUEUE,
                },
            )
        except Exception as exc:
            dispatch_failures.append(
                {
                    "manage_ip": host_ip,
                    "plan_id": host.get("plan_id"),
                    "error": str(exc),
                }
            )
            logger.error(
                "下发采集任务失败: device=%s error=%s", host_ip, exc, exc_info=True
            )
            _record_execution_event(
                event_scope="device",
                event_type="device_dispatch_failed",
                status="failed",
                severity="error",
                execute_time=host.get("execute_time", batch_execute_time),
                device_info=host,
                reason="dispatch_failed",
                error=str(exc),
                details={
                    "plan_id": host.get("plan_id"),
                    "sub_plans_count": len(host.get("sub_plans", [])),
                    "queue": CELERY_QUEUE,
                },
            )

    logger.info("批量下发任务结束")
    total_time = (time.time() - start_time) / 60
    logger.info(
        f"批量下发任务完成, 总设备数: {len(hosts)}, 有效任务: {len(net_tower_tasks)}, 耗时: {total_time:.2f}分钟"
    )

    analysis_trigger = {
        "scheduled": False,
        "reason": "missing_execute_time",
    }
    if batch_execute_time and dispatched_hosts:
        dispatched_subtasks = sum(
            len(host.get("sub_plans", [])) for host in dispatched_hosts
        )
        dispatched_interface_devices = count_expected_interface_devices(
            dispatched_hosts
        )
        analysis_trigger = schedule_batch_network_analysis(
            execute_time=batch_execute_time,
            expected_devices=len(dispatched_hosts),
            expected_subtasks=dispatched_subtasks,
            expected_interface_devices=dispatched_interface_devices,
            triggered_by="device_api-plan_collect_device_main",
        )
    elif batch_execute_time:
        analysis_trigger = {
            "scheduled": False,
            "reason": "no_dispatched_tasks",
        }
    _record_execution_event(
        event_scope="batch",
        event_type="batch_finished",
        status="partial_success" if dispatch_failures else "success",
        severity=(
            "warning"
            if (duplicate_count or skipped_hosts_without_sub_plans or dispatch_failures)
            else "info"
        ),
        execute_time=batch_execute_time,
        details={
            "fetched_devices": len(hosts),
            "deduplicated_devices": duplicate_count,
            "valid_devices": len(valid_hosts),
            "dispatched_devices": len(dispatched_hosts),
            "dispatch_failed_devices": len(dispatch_failures),
            "skipped_without_sub_plans": len(skipped_hosts_without_sub_plans),
            "expected_subtasks_before_dispatch": total_expected_subtasks,
            "expected_interface_devices_before_dispatch": total_expected_interface_devices,
            "analysis_trigger": analysis_trigger,
            "time_cost_minutes": round(total_time, 2),
        },
    )

    return {
        "total": len(dispatched_hosts),
        "tasks": len(net_tower_tasks),
        "time_cost": f"{total_time:.2f}分钟",
        "clear_history": clear_history,
        "clear_plan_data": clear_plan_data,
        "deduplicated_devices": duplicate_count,
        "skipped_without_sub_plans": len(skipped_hosts_without_sub_plans),
        "dispatch_failed_devices": len(dispatch_failures),
        "analysis_trigger": analysis_trigger,
    }


@shared_task(base=AxeTask, once={"graceful": True})
def analyze_collection_plan_bindings(execute_time="", max_devices=0, sample_limit=100):
    return analyze_collection_plan_bindings_service(
        execute_time=execute_time,
        max_devices=max_devices,
        sample_limit=sample_limit,
        record_execution_event=_record_execution_event,
    )


@shared_task(base=AxeTask, once={"graceful": True})
def batch_update_device_name_by_snmp(**kwargs):
    """
    批量通过SNMP探测更新设备名称
    遍历所有NetworkDevice，根据SNMP配置进行探测，将获取到的system name填入name字段

    :param kwargs: 可选参数
        - device_ids: 指定设备ID列表，如果提供则只处理这些设备
        - skip_empty_snmp: 是否跳过SNMP配置为空的设备，默认True
    :return: 处理结果统计
    """
    from utils.connect_layer.snmp.snmp_test import probe_snmp

    connections.close_all()

    # 获取过滤条件
    # 构建查询
    queryset = NetworkDevice.objects.filter(**kwargs)

    # 统计信息
    total_count = queryset.count()
    success_count = 0
    failed_count = 0
    skipped_count = 0
    updated_count = 0

    logger.info(f"开始批量SNMP探测更新设备名称，总设备数: {total_count}")

    # 遍历所有设备
    for device in queryset.iterator(chunk_size=100):
        try:
            # 检查SNMP配置
            if not device.snmp_community or device.snmp_community == "-":
                skipped_count += 1
                logger.debug(f"设备 {device.manage_ip} SNMP团体字为空，跳过")
                continue

            if not device.snmp_version:
                skipped_count += 1
                logger.debug(f"设备 {device.manage_ip} SNMP版本为空，跳过")
                continue

            # 检查IP地址
            if not device.manage_ip or device.manage_ip == "0.0.0.0":
                skipped_count += 1
                logger.debug(f"设备 {device.id} 管理IP无效，跳过")
                continue

            # 调用SNMP探测
            logger.info(
                f"开始探测设备: {device.manage_ip}, SNMP版本: {device.snmp_version}, 团体字: {device.snmp_community}"
            )

            success, result = probe_snmp(
                ip=device.manage_ip,
                snmp_version=device.snmp_version,
                snmp_community=device.snmp_community,
                port=device.snmp_port,
                timeout=5,
                retries=1,
            )

            if success:
                success_count += 1
                # result 是 system_name
                if result and result.strip():
                    # 更新设备名称
                    old_name = device.name
                    device.name = result.strip()
                    device.snmp_status = True
                    device.save(update_fields=["name", "snmp_status"])
                    updated_count += 1
                    logger.info(
                        f"设备 {device.manage_ip} SNMP探测成功，system name: {result}, 已更新name字段 (旧值: {old_name})"
                    )
                else:
                    # SNMP连接成功但没有获取到system name
                    device.snmp_status = True
                    device.save(update_fields=["snmp_status"])
                    logger.warning(
                        f"设备 {device.manage_ip} SNMP探测成功但未获取到system name"
                    )
            else:
                failed_count += 1
                device.snmp_status = False
                device.save(update_fields=["snmp_status"])
                logger.warning(f"设备 {device.manage_ip} SNMP探测失败: {result}")

        except Exception as e:
            failed_count += 1
            logger.error(
                f"设备 {device.manage_ip} (ID: {device.id}) SNMP探测异常: {str(e)}",
                exc_info=True,
            )
            try:
                device.snmp_status = False
                device.save(update_fields=["snmp_status"])
            except:
                pass

    # 汇总结果
    result_summary = {
        "total": total_count,
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "updated": updated_count,
    }

    logger.info(f"批量SNMP探测完成，统计: {result_summary}")

    return result_summary
