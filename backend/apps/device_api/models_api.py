# -*- coding: utf-8 -*-
import logging
import importlib
import time
from datetime import datetime

from apps.device_api.contract import (
    STANDARD_COLLECTION_CONTEXT_FIELDS,
    build_plan_collection_name,
    freeze_collection_context,
    normalize_collection_type_for_storage,
)
from apps.device_api.fields_mapping import COLLECTION_TYPE_ALIASES, RAW_NETMIKO_COLLECTION_TYPES
from apps.device_api.models import DeviceSubCollectionPlan
from apps.device_api import (
    COLLECTION_RESULTS_DB,
    COLLECTION_SUB_PLAN,
    COLLECTION_PLAN,
    device_identity_mongo,
    arp_mongo,
    mac_mongo,
    mac_bd_mongo,
    mac_vxlan_mongo,
    mac_vxlan_control_mongo,
    vxlan_capability_mongo,
    netconf_capability_mongo,
    cli_output_capability_mongo,
    lldp_mongo,
    ip_interface_mongo,
    interface_brief_mongo,
    aggre_port_mongo,
    fan_status_mongo,
    power_status_mongo,
    temperature_status_mongo,
    cpu_status_mongo,
    memory_status_mongo,
    board_status_mongo,
    irf_status_mongo,
    stack_status_mongo,
    transceiver_status_mongo,
    storage_status_mongo,
    environment_status_mongo,
    clock_status_mongo,
    route_table_mongo,
    bgp_neighbors_mongo,
    bgp_summary_mongo,
    ospf_neighbors_mongo,
    ospf_interfaces_mongo,
    isis_neighbors_mongo,
)
from utils.db.mongo_ops import MongoOps

# collection_type 到 MongoDB 实例的映射
COLLECTION_TYPE_MONGO_MAP = {
    "device_identity": device_identity_mongo,
    "version": device_identity_mongo,
    "arp": arp_mongo,
    "mac": mac_mongo,
    "mac_bd": mac_bd_mongo,
    "mac_vxlan": mac_vxlan_mongo,
    "mac_vxlan_control": mac_vxlan_control_mongo,
    "vxlan_capability": vxlan_capability_mongo,
    "netconf_capability": netconf_capability_mongo,
    "cli_output_capability": cli_output_capability_mongo,
    "lldp": lldp_mongo,
    "ip_interface": ip_interface_mongo,
    "interface_brief": interface_brief_mongo,
    "aggre_port": aggre_port_mongo,
    "fan_status": fan_status_mongo,
    "power_status": power_status_mongo,
    "temperature_status": temperature_status_mongo,
    "cpu_status": cpu_status_mongo,
    "memory_status": memory_status_mongo,
    "board_status": board_status_mongo,
    "irf_status": irf_status_mongo,
    "stack_status": stack_status_mongo,
    "transceiver_status": transceiver_status_mongo,
    "storage_status": storage_status_mongo,
    "environment_status": environment_status_mongo,
    "clock_status": clock_status_mongo,
    "route_table": route_table_mongo,
    "bgp_neighbors": bgp_neighbors_mongo,
    "bgp_summary": bgp_summary_mongo,
    "ospf_neighbors": ospf_neighbors_mongo,
    "ospf_interfaces": ospf_interfaces_mongo,
    "isis_neighbors": isis_neighbors_mongo,
}

PROCESSOR_MODULES = (
    "apps.device_api.processors.h3c",
    "apps.device_api.processors.huawei",
    "apps.device_api.processors.ruijie",
    "apps.device_api.processors.cisco",
    "apps.device_api.processors.hillstone",
    "apps.device_api.processors.legacy_bridge",
)
_processors_bootstrapped = False


def ensure_processors_bootstrapped():
    """确保 processors 模块完成导入注册，避免未导入导致注册表为空。"""
    global _processors_bootstrapped
    if _processors_bootstrapped:
        return

    for module_path in PROCESSOR_MODULES:
        importlib.import_module(module_path)
    _processors_bootstrapped = True


def save_local_collection_result(
    plan,
    device,
    collection_method,
    method_name,
    raw_data,
    processed_data,
    processed_status,
    processed_error=None,
):
    """将本地执行的采集结果写入 COLLECTION_RESULTS_DB，与南向驱动 webhook 回调写入结构一致，便于统一查询。"""
    created_on = datetime.now().isoformat()
    task_id = f"{device.manage_ip}_{plan.id}_{collection_method}_{int(time.time())}"
    base = {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "device_ip": device.manage_ip,
        "device_name": getattr(device, "name", ""),
        "idc_name": device.idc.name if device.idc else "",
        "device_type": plan.summary_plan.device_type,
        "vendor": plan.summary_plan.vendor,
        "collection_method": collection_method,
        "collection_type": plan.collection_type,
        "collected_at": created_on,
        "task_id": task_id,
        "task_status": "finished",
        "task_queue": "",
        "task_errors": [],
        "status": "success",
    }
    doc = {
        **base,
        "method_name": method_name,
        "data": raw_data,
        "processed_data": processed_data,
        "processed_status": processed_status,
        "processed_error": processed_error,
    }
    try:
        COLLECTION_RESULTS_DB.insert_one(doc)
        logging.info(
            f"本地采集结果已写入 TestDeviceCollection: {device.manage_ip} {plan.name} {collection_method}"
        )
    except Exception as e:
        logging.error(
            f"本地采集结果写入 MongoDB 失败: {device.manage_ip} {plan.name} - {e}",
            exc_info=True,
        )


def _build_base_collection_result(plan, webhook_args, task_info, status):
    """构建基础采集结果字典

    Args:
        plan: 采集方案对象
        webhook_args: webhook参数字典
        task_info: 任务信息字典
        status: 状态字符串

    Returns:
        dict: 基础采集结果字典
    """
    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "device_ip": webhook_args.get("device_ip"),
        "device_name": webhook_args.get("device_name"),
        "idc_name": webhook_args.get("idc_name", ""),
        "device_type": plan.summary_plan.device_type,
        "vendor": plan.summary_plan.vendor,
        "collection_method": webhook_args.get("collection_method", "netmiko"),
        "collection_type": webhook_args.get("collection_type", "arp"),
        "collected_at": task_info.get("created_on", ""),
        "task_id": task_info.get("task_id"),
        "task_status": task_info.get("task_status", ""),
        "task_queue": task_info.get("task_queue", ""),
        "task_errors": task_info.get("task_errors", []),
        "status": status,
    }


def plan_data_to_mongodb(**kwargs):
    """NetPalm webhook回调函数，将采集结果保存到MongoDB

    Args:
        **kwargs: 包含status, task_info, webhook_args等参数

    Returns:
        dict: 处理结果字典，包含status和message字段
    """
    logging.info("开始执行采集方案webhook回调")
    # tmp_db = MongoOps(db='Automation', coll="tmp_data1")
    # tmp_db.insert(kwargs)

    try:
        # 获取基本参数
        status = kwargs.get("status", "")
        task_info = kwargs.get("task_info", {})
        webhook_args = kwargs.get("webhook_args", {})

        logging.info(
            f"接收到的参数 - status: {status}, task_info keys: {list(task_info.keys())}, webhook_args keys: {list(webhook_args.keys())}"
        )

        # 验证必要参数
        if not webhook_args:
            logging.error("webhook_args参数为空")
            return {"status": "failed", "message": "webhook_args参数为空"}

        # 提取webhook参数
        plan_id = webhook_args.get("plan_id")
        device_ip = webhook_args.get("device_ip")
        device_name = webhook_args.get("device_name")
        collection_method = webhook_args.get("collection_method", "netmiko")

        if not plan_id:
            logging.error("plan_id参数缺失")
            return {"status": "failed", "message": "plan_id参数缺失"}

        logging.info(
            f"提取参数 - plan_id: {plan_id}, device_ip: {device_ip}, device_name: {device_name}, collection_method: {collection_method}"
        )

        # 查询采集方案
        try:
            plan = DeviceSubCollectionPlan.objects.select_related("summary_plan").get(
                id=plan_id
            )
            logging.info(f"成功获取采集方案: {plan.name} (ID: {plan_id})")
        except DeviceSubCollectionPlan.DoesNotExist:
            logging.error(f"采集方案不存在: plan_id={plan_id}")
            return {"status": "failed", "message": f"采集方案不存在: plan_id={plan_id}"}
        except Exception as e:
            logging.error(f"查询采集方案失败: {str(e)}", exc_info=True)
            return {"status": "failed", "message": f"查询采集方案失败: {str(e)}"}

        # 获取任务信息
        task_status = task_info.get("task_status", "")
        task_result = task_info.get("task_result", {})

        logging.info(
            f"任务信息 - task_id: {task_info.get('task_id')}, task_status: {task_status}, created_on: {task_info.get('created_on', '')}"
        )
        logging.info(f"采集结果数量: {len(task_result)} 条命令")

        # 构建基础结果字典
        base_result = _build_base_collection_result(
            plan, webhook_args, task_info, status
        )

        # 处理失败情况
        if task_status == "failed":
            collection_result = {
                **base_result,
                "method_name": None,
                "data": None,
                "processed_data": None,
                "processed_status": "success",
                "processed_error": None,
            }
            try:
                COLLECTION_RESULTS_DB.insert_one(collection_result)
                logging.info(f"失败记录已保存: {device_ip} - {plan.name}")
                return {"status": "success", "message": "失败记录已保存到MongoDB"}
            except Exception as e:
                logging.error(
                    f"保存失败记录到MongoDB失败: {device_ip} - 错误: {str(e)}",
                    exc_info=True,
                )
                return {"status": "failed", "message": f"保存失败记录失败: {str(e)}"}

        # 处理成功情况：构建结果并插入
        # task_result 一般只有一条数据，键是命令名，值是对应的结果
        if not task_result:
            logging.warning(f"task_result为空: {device_ip} - {plan.name}")
            return {"status": "failed", "message": "task_result为空，无数据可保存"}

        collection_results = []

        # 遍历处理每条命令结果
        for command_name, command_result in task_result.items():
            collection_result = {
                **base_result,
                "method_name": command_name,
                "data": command_result,
                "processed_data": None,
            }

            # 处理原始数据（P1-G：统一使用 resolve_raw_data，废弃 process_raw_data 路径）
            resolve_status, resolve_error, processed_data = resolve_raw_data(
                plan, collection_result, collection_method
            )

            # Layer 3：注入设备元数据 hostip/hostname/idc_name，保证 processed_data 与设计一致
            if resolve_status and isinstance(processed_data, list) and processed_data:
                meta = {
                    "hostip": base_result.get("device_ip", ""),
                    "hostname": base_result.get("device_name", ""),
                    "idc_name": base_result.get("idc_name", ""),
                }
                inject_metadata(processed_data, meta)

            collection_result["processed_data"] = processed_data
            collection_result["processed_status"] = (
                "success" if resolve_status else "error"
            )
            collection_result["processed_error"] = (
                resolve_error if not resolve_status else None
            )

            collection_results.append(collection_result)

        # 批量插入MongoDB（虽然通常只有一条，但使用批量插入保持一致性）
        try:
            COLLECTION_RESULTS_DB.insert_many(collection_results)
            logging.info(
                f"采集结果已保存: {device_ip} - {plan.name} - 共 {len(collection_results)} 条记录"
            )
        except Exception as e:
            logging.error(
                f"保存采集结果到MongoDB失败: {device_ip} - 错误: {str(e)}",
                exc_info=True,
            )
            return {"status": "failed", "message": f"保存采集结果失败: {str(e)}"}

        logging.info(
            f"webhook回调处理完成: {device_ip} - 共处理 {len(task_result)} 条命令"
        )
        return {"status": "success", "message": "结果插入mongodb成功"}

    except Exception as e:
        logging.error(f"webhook回调执行失败: {str(e)}", exc_info=True)
        return {"status": "failed", "message": f"webhook回调执行失败: {str(e)}"}


def celery_data_mongodb(**kwargs):
    """NetPalm webhook回调函数，将采集结果保存到MongoDB

    Args:
        **kwargs: 包含status, task_info, webhook_args等参数

    Returns:
        dict: 处理结果字典，包含status和message字段
    """
    logging.info("开始执行采集方案webhook回调")

    try:
        # 获取3个基本参数
        status = kwargs.get("status", "")
        task_info = kwargs.get("task_info", {})
        webhook_args = kwargs.get("webhook_args", {})

        logging.info(
            f"接收到的参数 - status: {status}, task_info keys: {list(task_info.keys())}, webhook_args keys: {list(webhook_args.keys())}"
        )

        # 验证必要参数
        if not webhook_args:
            logging.error("webhook_args参数为空")
            return {"status": "failed", "message": "webhook_args参数为空"}

        # 提取webhook参数内容
        summary_plan_id = webhook_args.get("summary_plan_id")
        plan_id = webhook_args.get("plan_id")
        device_ip = webhook_args.get("device_ip")
        device_name = webhook_args.get("device_name")
        vendor_alias = webhook_args.get("vendor_alias")
        collection_method = webhook_args.get("collection_method", "netmiko")
        collection_type = webhook_args.get(
            "collection_type"
        )  # 采集类型，用于选择MongoDB集合
        execute_time = webhook_args.get("execute_time")  # 主采集方案执行时间

        if not plan_id:
            logging.error("plan_id参数缺失")
            return {"status": "failed", "message": "plan_id参数缺失"}

        if collection_type is None:
            logging.error(f"collection_type为空，无法确定MongoDB集合")
            return {"status": "failed", "message": "collection_type为空，无法保存数据"}

        logging.info(
            f"提取参数 - plan_id: {plan_id}, device_ip: {device_ip}, device_name: {device_name}, collection_method: {collection_method}, collection_type: {collection_type}"
        )

        # 查询采集方案
        try:
            plan = DeviceSubCollectionPlan.objects.select_related("summary_plan").get(
                id=plan_id
            )
            logging.info(f"成功获取采集方案: {plan.name} (ID: {plan_id})")
        except DeviceSubCollectionPlan.DoesNotExist:
            logging.error(f"采集方案不存在: plan_id={plan_id}")
            return {"status": "failed", "message": f"采集方案不存在: plan_id={plan_id}"}
        except Exception as e:
            logging.error(f"查询采集方案失败: {str(e)}", exc_info=True)
            return {"status": "failed", "message": f"查询采集方案失败: {str(e)}"}

        # 获取任务信息
        task_status = task_info.get("task_status", "")
        task_result = task_info.get("task_result", {})
        task_id = task_info.get("task_id")

        # 数据回填，进行更新任务状态
        # 如果任务失败，添加错误信息并直接返回
        if status in ["error", "failed"] or task_status == "failed":
            # 1. 先更新子采集任务状态
            error_info = task_info.get("task_errors", [])
            update_sub_task_status(
                "failed", summary_plan_id, plan_id, task_id, error_info
            )

            # 2. 再更新主采集任务状态，然后不用继续往下走了
            update_parent_task_status(
                "failed", summary_plan_id, device_ip, execute_time
            )
            return {"status": "failed", "message": "任务失败状态已更新"}

        # 如果任务完成，添加完成时间（只更新一次，后续不再更新）
        if task_status in ["finished", "success"]:
            # 1. 只更新子采集任务状态,标记为成功, 主采集任务记录默认为成功，不需要记录
            update_sub_task_status(task_status, summary_plan_id, plan_id, task_id, [])

        # 构建基础结果字典
        base_result = _build_base_collection_result(
            plan, webhook_args, task_info, status
        )

        # 没有拿到数据的情况，应该提前返回
        if not task_result:
            logging.warning(f"task_result为空: {device_ip} - {plan.name}")
            # 更新子采集任务记录，数据为空，更新状态为失败
            update_sub_task_status(
                "failed",
                summary_plan_id,
                plan_id,
                task_id,
                ["task_result为空，无数据可处理"],
            )
            # 更新主采集任务记录
            update_parent_task_status(
                "failed", summary_plan_id, device_ip, execute_time
            )
            return {"status": "failed", "message": "task_result为空，无数据可处理"}

        collection_results = []
        data_process_errors = []  # 记录数据处理错误

        # 遍历处理每条命令结果（通常只有一条）
        for command_name, command_result in task_result.items():
            collection_result = {
                **base_result,
                "method_name": command_name,
                "data": command_result,  # 原始数据
            }

            # 处理原始数据
            resolve_status, resolve_error, resolve_data = resolve_raw_data(
                plan, collection_result, collection_method
            )

            if resolve_status:
                # resolve_data 是列表，需要展开添加到 collection_results
                if isinstance(resolve_data, list):
                    collection_results.extend(resolve_data)
                else:
                    # 如果不是列表，直接添加
                    collection_results.append(resolve_data)
            else:
                # 数据处理失败，记录错误
                error_msg = (
                    f"数据处理失败: command={command_name}, error={resolve_error}"
                )
                logging.warning(error_msg)
                data_process_errors.append(error_msg)

        # 如果数据处理失败，更新状态为失败（覆盖之前的finished状态）
        if data_process_errors:
            # 1. 先更新子采集任务记录
            update_sub_task_status(
                "failed", summary_plan_id, plan_id, task_id, data_process_errors
            )
            logging.error(
                f"子采集任务数据处理失败: {device_ip} - {plan.name} - 错误: {data_process_errors}"
            )
            # 2. 再更新主采集任务记录
            update_parent_task_status(
                "failed", summary_plan_id, device_ip, execute_time
            )
            return {
                "status": "failed",
                "message": f"数据处理失败: {data_process_errors}",
            }

        # 如果数据处理没有数据
        if not collection_results:
            logging.warning(f"没有可保存的采集结果: {device_ip} - {plan.name}")
            # 1. 更新子采集任务记录，数据为空，更新状态为失败
            update_sub_task_status(
                "failed", summary_plan_id, plan_id, task_id, ["数据处理后的结果为空"]
            )
            # 2. 更新主采集任务记录
            update_parent_task_status(
                "failed", summary_plan_id, device_ip, execute_time
            )
            return {
                "status": "failed",
                "message": "没有可保存的采集结果，所有数据处理后都为空",
            }

        # Layer 3：注入设备元数据 hostip/hostname/idc_name，保证入库数据与设计一致
        meta = {
            "hostip": base_result.get("device_ip", ""),
            "hostname": base_result.get("device_name", ""),
            "idc_name": base_result.get("idc_name", ""),
        }
        inject_metadata(collection_results, meta)
        inject_collection_context(
            collection_results,
            {
                "summary_plan_id": summary_plan_id,
                "plan_id": plan_id,
                "collection_type": normalize_collection_type_for_storage(collection_type),
                "collection_method": collection_method,
                "execute_time": execute_time,
            },
        )

        try:
            # 根据collection_type选择MongoDB集合，优先使用预定义的实例
            storage_collection_type = normalize_collection_type_for_storage(
                collection_type
            )
            collection_name = build_plan_collection_name(storage_collection_type)
            collection_db = COLLECTION_TYPE_MONGO_MAP.get(storage_collection_type)
            if not collection_db:
                # 如果不在预定义列表中，则动态创建（向后兼容）
                collection_db = MongoOps(db="Automation", coll=collection_name)
                logging.warning(
                    f"使用动态创建的MongoDB集合: Automation.{collection_name} (采集类型: {storage_collection_type})"
                )
            else:
                logging.info(
                    f"使用MongoDB集合: Automation.{collection_name} (采集类型: {storage_collection_type})"
                )

            # 执行插入清洗后的数据
            collection_db.insert_many(collection_results)
            logging.info(
                f"采集结果已保存: {device_ip} - 采集类型: {storage_collection_type} - 共 {len(collection_results)} 条记录 - 集合: {collection_name}"
            )
            try:
                from apps.device_api.platform_profiles import PlatformProfileService

                PlatformProfileService.update_capability_facts(
                    collection_type=storage_collection_type,
                    device_info={
                        "manage_ip": base_result.get("device_ip", ""),
                        "serial_num": webhook_args.get("serial_num", ""),
                        "vendor__alias": plan.summary_plan.vendor,
                    },
                    processed_data=collection_results,
                )
            except Exception as capability_error:
                logging.warning(
                    "能力画像回写失败: %s - %s",
                    device_ip,
                    capability_error,
                )
        except Exception as e:
            logging.error(
                f"保存采集结果到MongoDB失败: {device_ip} - 错误: {str(e)}",
                exc_info=True,
            )
            # 1. 更新子采集任务记录，保存失败，更新状态为失败（覆盖之前的finished状态）
            update_sub_task_status(
                "failed",
                summary_plan_id,
                plan_id,
                task_id,
                [f"保存采集结果失败: {str(e)}"],
            )
            # 2. 更新主采集任务记录
            update_parent_task_status(
                "failed", summary_plan_id, device_ip, execute_time
            )
            return {"status": "failed", "message": f"保存采集结果失败: {str(e)}"}

        logging.info(f"webhook回调处理完成: {device_ip} - 采集类型: {collection_type}")
        return {"status": "success", "message": "结果插入mongodb成功"}

    except Exception as e:
        logging.error(f"webhook回调执行失败: {str(e)}", exc_info=True)
        # # 如果已经获取到必要参数，更新主任务状态为失败
        # try:
        #     # 直接使用 try 块中已获取的变量（如果异常发生在获取这些参数之后，变量已存在）
        #     if summary_plan_id and device_ip and execute_time:
        #         update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
        #         logging.info(f"已更新主任务状态为失败: device_ip={device_ip}, summary_plan_id={summary_plan_id}")
        # except (NameError, Exception) as update_error:
        #     # 如果变量不存在或更新失败，记录警告但不影响主流程
        #     logging.warning(f"更新主任务状态失败: {str(update_error)}")
        return {"status": "failed", "message": f"webhook回调执行失败: {str(e)}"}


def update_parent_task_status(task_status, summary_plan_id, device_ip, execute_time):
    """
    更新主采集方案记录的状态

    :param task_status: 任务状态
    :param summary_plan_id: 主采集方案ID
    :param device_ip: 设备IP地址
    :param execute_time: 执行时间（用于关联主采集方案和子采集方案）
    :return: 更新结果，True表示成功，False表示失败
    """
    try:
        if not execute_time:
            logging.warning("execute_time为空，无法更新主采集方案记录")
            return False

        if not summary_plan_id or not device_ip:
            logging.warning(
                f"参数不完整，无法更新主采集方案记录: summary_plan_id={summary_plan_id}, device_ip={device_ip}"
            )
            return False

        # 更新主采集方案记录的更新时间
        update_result = COLLECTION_PLAN.update_one(
            filter={
                "summary_plan_id": summary_plan_id,
                "device_ip": device_ip,
                "execute_time": execute_time,  # 使用execute_time精确定位记录
            },
            update={
                "$set": {
                    "task_status": task_status,
                    "updated_at": datetime.now().isoformat(),
                }
            },
        )

        if update_result.matched_count > 0:
            logging.debug(
                f"主采集方案记录已更新: device_ip={device_ip}, summary_plan_id={summary_plan_id}, execute_time={execute_time}"
            )
            return True
        else:
            logging.warning(
                f"未找到主采集方案记录: device_ip={device_ip}, summary_plan_id={summary_plan_id}, execute_time={execute_time}"
            )
            return False

    except Exception as e:
        logging.error(f"更新主采集方案记录失败: {str(e)}", exc_info=True)
        return False


def update_sub_task_status(new_status, summary_plan_id, plan_id, task_id, error_msg):
    """更新子采集任务状态到COLLECTION_DEVICE_MONGODB"""
    try:
        update_data = {
            "$set": {
                "task_status": new_status,
                "task_errors": error_msg,
                "updated_at": datetime.now().isoformat(),
            }
        }

        result = COLLECTION_SUB_PLAN.update_one(
            filter={
                "summary_plan_id": summary_plan_id,
                "plan_id": plan_id,
                "task_id": task_id,
            },
            update=update_data,
        )
        if result.matched_count == 0:
            logging.warning(f"未找到匹配的任务记录: task_id={task_id}")
        else:
            logging.info(
                f"任务状态已更新: task_id={task_id}, status={new_status}, matched={result.matched_count}, modified={result.modified_count}"
            )
        return True
    except Exception as e:
        logging.error(
            f"更新任务状态失败: task_id={task_id}, 错误: {str(e)}", exc_info=True
        )
        return False


def process_raw_data(plan, collection_result, collection_method):
    """[DEPRECATED] 使用旧版 processor 代码字段处理原始数据。

    ⚠️ 已废弃：请使用 resolve_raw_data()。
    此函数仅在 plan_data_to_mongodb（旧版 NetPalm webhook 路径）中保留，
    计划随该路径一起清理。
    """
    try:
        command_result = collection_result["data"]  # 原始数据
        method = (collection_method or "").lower()

        dispatch = {
            "netmiko": (
                getattr(plan, "netmiko_processor_enabled", False),
                getattr(plan, "netmiko_processor", None),
                getattr(plan, "process_netmiko_data", None),
            ),
            "netconf": (
                getattr(plan, "netconf_processor_enabled", False),
                getattr(plan, "netconf_processor", None),
                getattr(plan, "process_netconf_data", None),
            ),
        }
        enabled, code, func = dispatch.get(method, (False, None, None))

        # 未启用或代码为空：直接透传原始数据（运行链路不再执行字段映射）
        if not enabled or not (code and str(code).strip()):
            logging.info(f"自定义处理器未启用，透传原始数据: {plan.name}")
            return True, "", command_result

        # 启用时执行处理器函数
        try:
            if callable(func):
                logging.info(f"执行{method}数据处理函数: {plan.name}")
                processed_data = func(command_result)
                logging.info(f"数据处理函数执行完成: {plan.name}")
                return True, "", processed_data
            logging.info(f"无处理器函数，透传原始数据: {plan.name}")
            return True, "", command_result
        except Exception as e:
            logging.error(
                f"数据处理函数执行失败: {plan.name} - {str(e)}", exc_info=True
            )
            return False, f"{method}_processor_failed: {str(e)}", []

    except Exception as e:
        logging.error(f"数据处理异常: {plan.name} - {str(e)}", exc_info=True)
        return False, f"exception: {str(e)}", []


def _inject_manage_ip(result, manage_ip):
    """向结果列表中每条记录注入 manage_ip 字段（不覆盖已有值）。"""
    if not manage_ip or not isinstance(result, list):
        return result
    for item in result:
        if isinstance(item, dict):
            item.setdefault("manage_ip", manage_ip)
    return result


def inject_metadata(data: list, meta: dict) -> list:
    """向处理后的数据列表中每条记录注入设备元数据（Layer 3）。

    注入字段：hostip / hostname / idc_name / log_time。
    当已有值为空（空字符串、None）时用 meta 覆盖，保证与设计一致（processor/tools 可能已写入空串）。

    Args:
        data: Layer1/Layer2 处理后的 list[dict]
        meta: 设备元数据字典，支持键：hostip, hostname, idc_name, log_time

    Returns:
        注入元数据后的 list[dict]
    """
    if not meta or not isinstance(data, list):
        return data
    log_time = meta.get("log_time") or datetime.now()
    for item in data:
        if isinstance(item, dict):
            if not item.get("hostip"):
                item["hostip"] = meta.get("hostip", "")
            if not item.get("hostname"):
                item["hostname"] = meta.get("hostname", "")
            if not item.get("idc_name"):
                item["idc_name"] = meta.get("idc_name", "")
            item.setdefault("log_time", log_time)
    return data


def inject_collection_context(data: list, context: dict) -> list:
    """向采集结果注入方案和执行批次元数据，便于后续精确查询。"""
    if not isinstance(data, list):
        return data
    frozen_context = freeze_collection_context(context)
    for item in data:
        if isinstance(item, dict):
            for key in STANDARD_COLLECTION_CONTEXT_FIELDS:
                if key == "collection_type" or not item.get(key):
                    item[key] = frozen_context.get(key, "")
                else:
                    item.setdefault(key, frozen_context.get(key, ""))
            for key, value in frozen_context.items():
                item.setdefault(key, value)
    return data


def resolve_raw_data(plan, collection_result, collection_method):
    """处理原始采集数据，仅允许 processors/ 注册处理器参与解析。

    运行链路不再执行子方案字段映射配置（netmiko_path/netconf_path + *_field_mappings），
    也不再回退到 tools/ 旧入口。缺失 processor 视为未覆盖，直接返回失败。

    Args:
        plan: 采集方案对象
        collection_result: 包含原始数据的结果字典，其中 device_ip 字段用于注入 manage_ip
        collection_method: 采集方法 (netmiko/netconf)

    Returns:
        tuple: (status, error_message, processed_data)
    """
    try:
        # netmiko 采集如果 data 是字符串，说明 TextFSM 解析失败（未匹配到模板或模板与设备输出格式不符）
        if (
            collection_method.lower() == "netmiko"
            and collection_type not in RAW_NETMIKO_COLLECTION_TYPES
            and isinstance(
            collection_result.get("data", ""), str
        )):
            raw_preview = (collection_result.get("data") or "")[:500]
            logging.warning(
                "[resolve_raw_data] TextFSM 解析失败，返回原始字符串。"
                "请确认: 1) 环境变量 NET_TEXTFSM 指向含 index 的模板目录(zetmiko/templates); "
                "2) 采集方案中 textfsm_template 或 index 中设备类型/命令与当前设备一致; "
                "3) 设备输出格式与模板匹配。原始输出预览: %s",
                raw_preview.replace("\n", "\\n") if raw_preview else "(空)",
            )
            return False, "Textfsm 模板解析失败", []

        command_result = collection_result["data"]
        method = collection_method.lower()
        manage_ip = collection_result.get("device_ip", "")

        vendor_alias = plan.summary_plan.vendor
        device_type = plan.summary_plan.device_type
        collection_type = plan.collection_type
        resolved_collection_type = COLLECTION_TYPE_ALIASES.get(
            collection_type, collection_type
        )

        # ── 路径 1：查找已注册的 processors/ 解析器（P0-3）────────────────────
        from apps.device_api.processors.base import (
            ProcessorRegistry,
            normalize_processed_data,
        )

        ensure_processors_bootstrapped()
        processor = ProcessorRegistry.get_processor(
            vendor=vendor_alias,
            device_type=device_type,
            collection_type=resolved_collection_type,
            method=method,
        )
        if processor:
            try:
                # version 类采集需回填 NetworkDevice，向处理器传入 manage_ip
                if resolved_collection_type == "version" and command_result and isinstance(command_result, list):
                    command_result = list(command_result)
                    if command_result and isinstance(command_result[0], dict):
                        command_result[0] = dict(command_result[0], _resolve_device_ip=manage_ip)
                result = normalize_processed_data(
                    collection_type, processor(command_result)
                )
                logging.info(
                    f"[resolve] 使用注册处理器 {vendor_alias}:{device_type}:{resolved_collection_type}:{method} - {plan.name}"
                )
                return True, "", _inject_manage_ip(result, manage_ip)
            except NotImplementedError as e:
                # 处理器已注册但仍是 TODO 时，不直接失败，继续走兜底逻辑。
                logging.warning(
                    f"[resolve] 注册处理器未实现，切换兜底路径: {plan.name} - {str(e)}"
                )
            except Exception as e:
                logging.error(
                    f"[resolve] 注册处理器执行失败: {plan.name} - {str(e)}",
                    exc_info=True,
                )
                return False, f"processor_failed: {str(e)}", []

        logging.warning(
            "[resolve] 未找到 processor，数据处理失败: %s:%s:%s:%s - %s",
            vendor_alias,
            device_type,
            resolved_collection_type,
            method,
            plan.name,
        )
        return (
            False,
            f"processor_not_found: {vendor_alias}:{resolved_collection_type}:{method}",
            [],
        )

    except Exception as e:
        logging.error(f"[resolve] 数据处理异常: {plan.name} - {str(e)}", exc_info=True)
        return False, f"resolve_raw_data_exception: {str(e)}", []


_FIELD_MAPPING_PATH_MISSING = object()


def _resolve_mapping_path(data, path, default=_FIELD_MAPPING_PATH_MISSING):
    """解析 a.b.c 形式的嵌套路径，支持 dict 和 list 索引。"""
    if path in (None, ""):
        return data

    current = data
    for part in str(path).split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current.get(part)
            continue

        if isinstance(current, list):
            try:
                index = int(part)
            except (TypeError, ValueError):
                return default
            if index < 0 or index >= len(current):
                return default
            current = current[index]
            continue

        return default

    return current


def _split_array_mapping_path(field_path):
    """拆分 data.items[*].field 为 (data.items, field)。"""
    array_path, _, remainder = str(field_path).partition("[*]")
    return array_path.rstrip("."), remainder.lstrip(".")


def apply_field_mappings(data_dict, field_mappings, path_config=None):
    """[DEPRECATED] 应用字段映射 - 支持复杂字段映射配置

    Args:
        data_dict: 原始数据，通常是包含数组的字典，如 {"data": [...]}
        field_mappings: 字段映射配置，支持格式：
            {
                "field_name": {
                    "sort": 1,
                    "type": "system",
                    "value": "data[*].field_key" 或 "top_level_key"
                }
            }
        path_config: 可选，指定数据数组的键名，如果不提供则自动检测
    Returns:
        提取后的字段数据数组，按sort字段排序，格式如 [{"field1": "a", "field2": "b"}, ...]
    """
    if isinstance(data_dict, list):
        data_dict = {"data": data_dict}

    try:
        # 解析字段映射
        if isinstance(field_mappings, str):
            import json

            field_mappings = json.loads(field_mappings)

        # 确保data_dict是字典
        if not isinstance(data_dict, dict):
            logging.warning(f"data_dict不是字典，类型: {type(data_dict)}")
            return []

        # 按sort字段排序字段映射
        sorted_fields = sorted(
            field_mappings.items(),
            key=lambda x: x[1].get("sort", 999) if isinstance(x[1], dict) else 999,
        )

        # 确定数组键
        array_key = None
        if path_config:
            # 如果提供了path_config，直接使用
            array_key = str(path_config).rstrip(".")
        else:
            # 自动检测数组键
            for field_name, field_config in sorted_fields:
                # 处理新格式：field_config是字典，包含value字段
                if isinstance(field_config, dict):
                    field_path = field_config.get("value", "")
                else:
                    # 处理旧格式：field_config直接是字符串路径
                    field_path = field_config

                if "[*]" in field_path:
                    detected_array_key, _ = _split_array_mapping_path(field_path)
                    if detected_array_key:
                        array_key = detected_array_key
                        break

        if not array_key:
            logging.warning(f"未找到数组键: {array_key}")
            return []

        array_data = _resolve_mapping_path(data_dict, array_key)
        if not isinstance(array_data, list):
            logging.warning(f"键 {array_key} 对应的值不是数组")
            return []

        processed_data = []
        log_time = datetime.now()
        host_ip = data_dict.get("device_ip")

        # 遍历数组中的每个元素
        for item in array_data:
            if not isinstance(item, dict):
                continue

            # 为每个元素创建一个结果对象
            result_item = {}

            # 对每个字段进行映射（按sort排序）
            for field_name, field_config in sorted_fields:
                # 处理新格式：field_config是字典，包含value字段
                if isinstance(field_config, dict):
                    field_path = field_config.get("value", "")
                else:
                    # 处理旧格式：field_config直接是字符串路径
                    field_path = field_config

                if not field_path:
                    continue

                # 解析值路径
                if "[*]" in field_path:
                    # 处理数组路径，如 "top.items[*].meta.ip"
                    current_array_key, item_path = _split_array_mapping_path(field_path)
                    if current_array_key == array_key:
                        value = _resolve_mapping_path(
                            item,
                            item_path,
                            default="" if item_path else item,
                        )
                    else:
                        value = ""
                else:
                    # 先从当前数组元素解析，再尝试根对象；都不存在时视为常量值
                    value = _resolve_mapping_path(item, field_path)
                    if value is _FIELD_MAPPING_PATH_MISSING:
                        value = _resolve_mapping_path(data_dict, field_path)
                    if value is _FIELD_MAPPING_PATH_MISSING:
                        value = field_path

                result_item[field_name] = value

            # 将结果添加到数组中
            result_item["log_time"] = log_time
            result_item["hostip"] = host_ip
            processed_data.append(result_item)

        logging.info(
            f"字段映射完成: 处理了 {len(processed_data)} 条记录，使用了 {len(sorted_fields)} 个字段"
        )
        return processed_data

    except Exception as e:
        logging.error(f"应用字段映射失败: {str(e)}", exc_info=True)
        return []


def apply_vendor_processor(plan, processed_data):
    """按厂商与采集类型做统一预处理（规范化），netmiko 与 netconf 的最终数据都会经此函数。

    用于统一不同厂商、型号、软件版本带来的数据格式差异，例如：
    - MAC 地址统一写法（大小写、分隔符等）
    - 接口名统一格式（如 GE1/0/1 -> GigabitEthernet1/0/1）
    - 其它字段的清洗与归一化

    由 resolve_raw_data 在字段映射之后调用，保证入库前格式一致。

    Args:
        plan: 采集方案对象或字典，包含 summary_plan.vendor、collection_type
        processed_data: 字段映射后的数据列表（list of dict）

    Returns:
        规范化后的数据列表；无对应方法或异常时返回原始 processed_data
    """
    try:
        if not plan or not processed_data:
            return processed_data

        # 获取厂商和采集类型
        vendor = plan.summary_plan.vendor
        collection_type = plan.collection_type

        # 获取模块名和类名（使用default方法，因为apply_vendor_processor不区分采集方法）
        module_name, class_name = get_vendor_class(vendor, "default")

        if not module_name or not class_name:
            logging.warning(f"不支持的厂商: {vendor}，跳过厂商处理")
            return processed_data

        # 动态导入模块
        try:
            module = importlib.import_module(f"apps.device_api.tools.{module_name}")
            plan_class = getattr(module, class_name, None)

            if not plan_class:
                logging.warning(f"未找到类: {class_name}，跳过厂商处理")
                return processed_data

            # 构建方法名：get_{collection_type}
            method_name = f"get_{collection_type}"
            method = getattr(plan_class, method_name, None)

            if method and callable(method):
                # 调用方法处理数据
                resolved_data = method(processed_data)
                logging.info(
                    f"已应用厂商处理方法: {vendor}.{class_name}.{method_name}()"
                )
                return resolved_data
            else:
                logging.warning(
                    f"未找到方法: {class_name}.{method_name}()，跳过厂商处理"
                )
                return processed_data

        except ImportError as e:
            logging.warning(
                f"导入模块失败: apps.device_api.tools.{module_name}, 错误: {str(e)}"
            )
            return processed_data
        except Exception as e:
            logging.error(f"调用厂商处理方法失败: {str(e)}", exc_info=True)
            return processed_data

    except Exception as e:
        logging.error(f"执行厂商处理方法时发生错误: {str(e)}", exc_info=True)
        # 即使处理失败，也返回原始数据
        return processed_data
