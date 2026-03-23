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
import logging
import time
import json
from datetime import datetime
from celery import shared_task
from django.core.cache import cache
from django.db import connections
from apps.device_api.contract import (
    build_plan_collection_name,
    normalize_collection_type_for_storage,
)
from apps.device_api.fields_mapping import field_mapping
from netaxe.celery import AxeTask
from apps.asset.models import NetworkDevice
from apps.device_api.services_new import DeviceCollectionService
from apps.device_api.connection_manager import DeviceConnectionManager
from apps.device_api.models_api import (
    resolve_raw_data,
    inject_metadata,
    inject_collection_context,
    COLLECTION_TYPE_MONGO_MAP,
)
from apps.device_api.tools.collect_device import get_auto_device
from apps.device_api.platform_profiles import DeviceFactService
from apps.device_api.cache_utils import cache_network_data
from apps.device_api.analysis_hooks import (
    count_expected_interface_devices,
    schedule_batch_network_analysis,
)
from apps.device_api import COLLECTION_PLAN, COLLECTION_SUB_PLAN
from apps.device_api import arp_mongo, mac_mongo, lldp_mongo, aggre_port_mongo
from netaxe.settings import DEBUG
from utils.db.mongo_ops import MongoOps, MongoNetOps

logger = logging.getLogger("device_api")

RUNTIME_CONTROL_KWARGS = {"clear_history"}

if DEBUG:
    CELERY_QUEUE = "dev"
else:
    CELERY_QUEUE = "config"


def should_clear_history_before_batch(kwargs=None):
    """决定批次前是否清理历史结果。

    默认保持现有行为；灰度对比、回退演练或人工排障时可显式传入
    clear_history=False 保留历史批次数据。
    """
    if not kwargs:
        return True

    clear_history = kwargs.get("clear_history", True)
    if isinstance(clear_history, str):
        return clear_history.strip().lower() not in {"0", "false", "no", "off"}
    return bool(clear_history)


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


def _host_identity(host: dict) -> str:
    return (
        host.get("device_serial_num")
        or host.get("serial_num")
        or host.get("manage_ip")
        or ""
    )


def _host_preference_key(host: dict) -> tuple:
    try:
        plan_rank = -(int(host.get("plan_id") or 0))
    except (TypeError, ValueError):
        plan_rank = 0
    return (
        _binding_source_priority(host.get("binding_source")),
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
    for host in hosts or []:
        identity = _host_identity(host)
        if not identity:
            continue
        existing = deduped_hosts.get(identity)
        if existing is None or _host_preference_key(host) < _host_preference_key(existing):
            if existing is not None:
                duplicate_count += 1
            deduped_hosts[identity] = host
        else:
            duplicate_count += 1
    return list(deduped_hosts.values()), duplicate_count


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


def clear_his_collect_res(execute_time=None):
    delete_filter = {"execute_time": execute_time} if execute_time else None
    COLLECTION_PLAN.delete(delete_filter)
    COLLECTION_SUB_PLAN.delete(delete_filter)

    for collect_type in field_mapping.keys():
        MongoOps(db="Automation", coll=f"plan_{collect_type}").delete(delete_filter)
    return


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
        "failed_details": [],
        "skipped_details": [],
    }
    parent_record_created = False

    try:
        # 使用从get_auto_device传递过来的子采集方案列表
        sub_plans_list = kwargs.get("sub_plans", [])

        if not sub_plans_list:
            logger.warning(
                f"设备 {host_ip} 关联的采集方案不存在、已禁用或没有子采集方案: plan_id={plan_id}"
            )
            return {}

        logger.info(f"开始采集设备 {host_ip}, 子方案数量: {len(sub_plans_list)}")

        # 在执行采集之前，插入主采集方案记录
        parent_insert_result = DeviceCollectionService.insert_parent_plan_data(
            plan=sub_plans_list[0],
            device_info=kwargs,
            sub_plans_count=len(sub_plans_list),
        )
        parent_record_created = bool(
            isinstance(parent_insert_result, dict) and parent_insert_result.get("success")
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
                # 执行所有Netmiko采集（复用同一连接）
                for sub_plan in netmiko_plans:
                    try:
                        logger.info(
                            f"执行Netmiko采集: {sub_plan['name']} (设备: {host_ip})"
                        )
                        command = sub_plan.get("netmiko_method", "")
                        textfsm_template = sub_plan.get("textfsm_template")

                        result = conn_mgr.execute_netmiko_command(
                            command=command,
                            use_textfsm=True,
                            textfsm_template=textfsm_template,
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
                            process_reason = process_result.get("reason", "processing_failed")
                        else:
                            process_success = bool(process_result)
                            process_reason = "processing_failed"
                        if process_success:
                            task_summary["successful_sub_plans"] += 1
                            logger.info(
                                f"Netmiko采集完成: {sub_plan['name']} (设备: {host_ip})"
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
                    except Exception as e:
                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "netmiko",
                                "reason": str(e),
                            }
                        )
                        logger.error(
                            f"Netmiko采集异常: {sub_plan['name']} (设备: {host_ip}), {str(e)}",
                            exc_info=True,
                        )

                # 执行所有NETCONF采集（复用同一连接）
                for sub_plan in netconf_plans:
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
                                process_reason = process_result.get("reason", "processing_failed")
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                logger.info(
                                    f"NETCONF采集完成: {sub_plan['name']} (设备: {host_ip})"
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
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "netconf",
                                    "reason": "missing_xml_template",
                                }
                            )
                    except Exception as e:
                        task_summary["failed_sub_plans"] += 1
                        task_summary["failed_details"].append(
                            {
                                "plan_id": sub_plan.get("id"),
                                "collection_method": "netconf",
                                "reason": str(e),
                            }
                        )
                        logger.error(
                            f"NETCONF采集异常: {sub_plan['name']} (设备: {host_ip}), {str(e)}",
                            exc_info=True,
                        )

                # 执行所有SNMP采集（复用同一会话）
                for sub_plan in snmp_plans:
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
                                process_reason = process_result.get("reason", "processing_failed")
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                logger.info(
                                    f"SNMP采集完成: {sub_plan['name']} (设备: {host_ip})"
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
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "snmp",
                                    "reason": "missing_snmp_oids",
                                }
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

                # 执行所有RESTCONF采集（复用同一会话）
                for sub_plan in restconf_plans:
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
                                process_reason = process_result.get("reason", "processing_failed")
                            else:
                                process_success = bool(process_result)
                                process_reason = "processing_failed"
                            if process_success:
                                task_summary["successful_sub_plans"] += 1
                                logger.info(
                                    f"RESTCONF采集完成: {sub_plan['name']} (设备: {host_ip})"
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
                        else:
                            task_summary["skipped_sub_plans"] += 1
                            task_summary["skipped_details"].append(
                                {
                                    "plan_id": sub_plan.get("id"),
                                    "collection_method": "restconf",
                                    "reason": "missing_restconf_endpoint",
                                }
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

                # 执行所有Telemetry采集（复用同一通道）
                for sub_plan in telemetry_plans:
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

            # 连接自动关闭（通过上下文管理器）
            logger.info(f"设备 {host_ip} 所有采集任务完成，连接已关闭")
        except Exception as e:
            logger.error(f"设备 {host_ip} 连接或采集异常: {str(e)}", exc_info=True)
            raise

        parent_task_status = "success"
        if task_summary["successful_sub_plans"] == 0:
            if task_summary["failed_sub_plans"] > 0:
                parent_task_status = "failed"
            elif task_summary["skipped_sub_plans"] > 0:
                parent_task_status = "skipped"
        elif task_summary["failed_sub_plans"] > 0:
            parent_task_status = "partial_success"

        try:
            COLLECTION_PLAN.update_one(
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
                        "failed_details": task_summary["failed_details"][:20],
                        "skipped_details": task_summary["skipped_details"][:20],
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

        return {
            "host_ip": host_ip,
            "total": len(sub_plans_list),
            "execute_time": execute_time,
            "task_status": parent_task_status,
            **task_summary,
        }
    except Exception as e:
        logger.error(f"设备 {host_ip} 采集任务异常: {str(e)}", exc_info=True)
        if parent_record_created and summary_plan_id is not None:
            try:
                COLLECTION_PLAN.update_one(
                    filter={
                        "summary_plan_id": summary_plan_id,
                        "device_ip": host_ip,
                        "execute_time": execute_time,
                    },
                    update={
                        "$set": {
                            "task_status": "failed",
                            "failed_sub_plans": max(task_summary["failed_sub_plans"], 1),
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
        collection_result = {"data": raw_result, "device_ip": manage_ip}
        resolve_status, resolve_error, processed_data = resolve_raw_data(
            plan_obj, collection_result, collection_method
        )

        if not resolve_status:
            logger.error(
                f"数据处理失败: {manage_ip}, method={collection_method}, error={resolve_error}"
            )
            DeviceFactService.mark_discovery_failure(device_info, resolve_error)
            return {"success": False, "reason": resolve_error or "resolve_failed"}

        # ── Layer 3：元数据注入 ──────────────────────────────────────────
        meta = {
            "hostip": manage_ip,
            "hostname": device_info.get("name", "") or device_info.get("device_name", ""),
            "idc_name": device_info.get("idc__name", "") or device_info.get("idc_name", ""),
        }
        inject_metadata(processed_data, meta)
        collection_type = plan.get("collection_type")
        storage_collection_type = normalize_collection_type_for_storage(
            collection_type
        )
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
        if isinstance(processed_data, list) and processed_data and storage_collection_type:
            collection_name = build_plan_collection_name(storage_collection_type)
            collection_db = COLLECTION_TYPE_MONGO_MAP.get(storage_collection_type)
            if not collection_db:
                from utils.db.mongo_ops import MongoOps

                collection_db = MongoOps(
                    db="Automation", coll=collection_name
                )
                logger.warning(f"使用动态创建的 MongoDB 集合: {collection_name}")
            try:
                collection_db.insert_many(processed_data)
                logger.info(
                    f"采集数据已保存: {manage_ip}, type={storage_collection_type}, "
                    f"method={collection_method}, count={len(processed_data)}"
                )
            except Exception as e:
                logger.error(
                    f"保存采集数据到 MongoDB 失败: {manage_ip}, type={storage_collection_type}, {str(e)}",
                    exc_info=True,
                )
                return {"success": False, "reason": str(e)}
        else:
            logger.warning(
                f"采集结果为空或无法保存: {manage_ip}, type={storage_collection_type}, "
                f"method={collection_method}"
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
            "task_status": "finished",
            "collection_type": storage_collection_type,
            "collection_method": collection_method,
            "vendor": plan.get("summary_plan_vendor"),
            "device_type": plan.get("summary_plan_device_type"),
            "execute_time": execute_time,
            "created_at": datetime.now().isoformat(),
            "task_errors": [],
            "log_time": time.time(),
        }
        COLLECTION_SUB_PLAN.insert_one(task_record)

    except Exception as e:
        logger.error(
            f"处理并保存采集结果异常: {device_info.get('manage_ip')}, "
            f"method={collection_method}, {str(e)}",
            exc_info=True,
        )
        DeviceFactService.mark_discovery_failure(device_info, str(e))
        return {"success": False, "reason": str(e)}

    return {"success": True, "reason": ""}


# 通用信息采集主调度任务
@shared_task(base=AxeTask, once={"graceful": True})
def plan_collect_device_main(**kwargs):
    logger.info("开始执行设备信息采集主调度任务")
    datas_to_cache()  # 将数据写入缓存
    logger.info("数据缓存更新完成")
    runtime_options, device_filters = split_runtime_control_kwargs(kwargs)

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

    deduped_hosts, duplicate_count = dedupe_batch_hosts(hosts)
    if duplicate_count:
        logger.warning("批次调度已去重重复设备绑定: duplicates=%s", duplicate_count)

    skipped_hosts_without_sub_plans = [
        host for host in deduped_hosts if not (host.get("sub_plans") or [])
    ]
    if skipped_hosts_without_sub_plans:
        logger.warning(
            "批次调度跳过无可执行子方案设备: count=%s",
            len(skipped_hosts_without_sub_plans),
        )

    valid_hosts = [host for host in deduped_hosts if host.get("sub_plans")]

    # 参数初始化
    net_tower_tasks = []  # 采集任务id集合
    total_expected_subtasks = sum(len(host.get("sub_plans", [])) for host in valid_hosts)
    total_expected_interface_devices = count_expected_interface_devices(valid_hosts)
    batch_execute_time = deduped_hosts[0].get("execute_time") if deduped_hosts else ""

    clear_history = should_clear_history_before_batch(runtime_options)

    # 清空历史采集数据
    if clear_history:
        try:
            if batch_execute_time:
                clear_his_collect_res(execute_time=batch_execute_time)
                logger.info("历史采集数据已按批次清空: execute_time=%s", batch_execute_time)
            else:
                logger.info("当前批次无 execute_time，跳过历史采集数据清理")
        except Exception as e:
            logger.warning(f"清空历史采集数据失败: {str(e)}")
            raise RuntimeError(f"清空历史采集数据失败: {str(e)}") from e
    else:
        logger.info("本批次保留历史采集数据: clear_history=False")

    start_time = time.time()

    # 批量下发任务
    for host in valid_hosts:
        host_ip = host.get("manage_ip")
        task = plan_collect_device.apply_async(kwargs=host, queue=CELERY_QUEUE, retry=True)
        net_tower_tasks.append(task)
        logger.debug(f"已下发采集任务: {host_ip}, task_id: {task.id}")

    logger.info("批量下发任务结束")
    total_time = (time.time() - start_time) / 60
    logger.info(
        f"批量下发任务完成, 总设备数: {len(hosts)}, 有效任务: {len(net_tower_tasks)}, 耗时: {total_time:.2f}分钟"
    )

    analysis_trigger = {
        "scheduled": False,
        "reason": "missing_execute_time",
    }
    if batch_execute_time:
        analysis_trigger = schedule_batch_network_analysis(
            execute_time=batch_execute_time,
            expected_devices=len(valid_hosts),
            expected_subtasks=total_expected_subtasks,
            expected_interface_devices=total_expected_interface_devices,
            triggered_by="device_api-plan_collect_device_main",
        )

    return {
        "total": len(valid_hosts),
        "tasks": len(net_tower_tasks),
        "time_cost": f"{total_time:.2f}分钟",
        "clear_history": clear_history,
        "deduplicated_devices": duplicate_count,
        "skipped_without_sub_plans": len(skipped_hosts_without_sub_plans),
        "analysis_trigger": analysis_trigger,
    }


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
