# -*- coding: utf-8 -*-
import logging
import importlib
from datetime import datetime

from apps.device_api.fields_mapping import vendor_mapping
from apps.device_api.models import DeviceSubCollectionPlan
from apps.device_api import (
    COLLECTION_RESULTS_DB, COLLECTION_SUB_PLAN, COLLECTION_PLAN,
    arp_mongo, mac_mongo, lldp_mongo, ip_interface_mongo, 
    interface_brief_mongo, aggre_port_mongo
)
from utils.db.mongo_ops import MongoOps

# collection_type 到 MongoDB 实例的映射
COLLECTION_TYPE_MONGO_MAP = {
    'arp': arp_mongo,
    'mac': mac_mongo,
    'lldp': lldp_mongo,
    'ip_interface': ip_interface_mongo,
    'interface_brief': interface_brief_mongo,
    'aggre_port': aggre_port_mongo,
}


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
        'plan_id': plan.id,
        'plan_name': plan.name,
        'device_ip': webhook_args.get("device_ip"),
        'device_name': webhook_args.get("device_name"),
        'idc_name': webhook_args.get("idc_name", ""),
        'device_type': plan.summary_plan.device_type,
        'vendor': plan.summary_plan.vendor,
        'collection_method': webhook_args.get("collection_method", "netmiko"),
        'collection_type': webhook_args.get("collection_type", "arp"),
        'collected_at': task_info.get("created_on", ""),
        'task_id': task_info.get("task_id"),
        'task_status': task_info.get("task_status", ""),
        'task_queue': task_info.get("task_queue", ""),
        'task_errors': task_info.get("task_errors", []),
        'status': status
    }


def plan_data_to_mongodb(**kwargs):
    """NetPalm webhook回调函数，将采集结果保存到MongoDB
    
    Args:
        **kwargs: 包含status, task_info, webhook_args等参数
        
    Returns:
        dict: 处理结果字典，包含status和message字段
    """
    logging.info("开始执行采集方案webhook回调")
    
    try:
        # 获取基本参数
        status = kwargs.get("status", "")
        task_info = kwargs.get("task_info", {})
        webhook_args = kwargs.get("webhook_args", {})
        
        logging.info(f"接收到的参数 - status: {status}, task_info keys: {list(task_info.keys())}, webhook_args keys: {list(webhook_args.keys())}")
        
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

        logging.info(f"提取参数 - plan_id: {plan_id}, device_ip: {device_ip}, device_name: {device_name}, collection_method: {collection_method}")

        # 查询采集方案
        try:
            plan = DeviceSubCollectionPlan.objects.select_related('summary_plan').get(id=plan_id)
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

        logging.info(f"任务信息 - task_id: {task_info.get('task_id')}, task_status: {task_status}, created_on: {task_info.get('created_on', '')}")
        logging.info(f"采集结果数量: {len(task_result)} 条命令")

        # 构建基础结果字典
        base_result = _build_base_collection_result(plan, webhook_args, task_info, status)
        
        # 处理失败情况
        if task_status == "failed":
            collection_result = {
                **base_result,
                'method_name': None,
                'data': None,
                'processed_data': None,
                'processed_status': 'success',
                'processed_error': None,
            }
            try:
                COLLECTION_RESULTS_DB.insert_one(collection_result)
                logging.info(f"失败记录已保存: {device_ip} - {plan.name}")
                return {"status": "success", "message": "失败记录已保存到MongoDB"}
            except Exception as e:
                logging.error(f"保存失败记录到MongoDB失败: {device_ip} - 错误: {str(e)}", exc_info=True)
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
                'method_name': command_name,
                'data': command_result,
                'processed_data': None,
            }

            # 处理原始数据
            processed_status, processed_error, processed_data = process_raw_data(
                plan, collection_result, collection_method
            )
            
            collection_result["processed_data"] = processed_data
            collection_result["processed_status"] = "success" if processed_status else "error"
            collection_result["processed_error"] = processed_error

            collection_results.append(collection_result)

        # 批量插入MongoDB（虽然通常只有一条，但使用批量插入保持一致性）
        try:
            COLLECTION_RESULTS_DB.insert_many(collection_results)
            logging.info(f"采集结果已保存: {device_ip} - {plan.name} - 共 {len(collection_results)} 条记录")
        except Exception as e:
            logging.error(f"保存采集结果到MongoDB失败: {device_ip} - 错误: {str(e)}", exc_info=True)
            return {"status": "failed", "message": f"保存采集结果失败: {str(e)}"}
        
        logging.info(f"webhook回调处理完成: {device_ip} - 共处理 {len(task_result)} 条命令")
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

        logging.info(f"接收到的参数 - status: {status}, task_info keys: {list(task_info.keys())}, webhook_args keys: {list(webhook_args.keys())}")

        # 验证必要参数
        if not webhook_args:
            logging.error("webhook_args参数为空")
            return {"status": "failed", "message": "webhook_args参数为空"}

        # 提取webhook参数内容
        summary_plan_id = webhook_args.get("summary_plan_id")
        plan_id = webhook_args.get("plan_id")
        device_ip = webhook_args.get("device_ip")
        device_name = webhook_args.get("device_name")
        collection_method = webhook_args.get("collection_method", "netmiko")
        collection_type = webhook_args.get("collection_type")       # 采集类型，用于选择MongoDB集合
        execute_time = webhook_args.get("execute_time")

        if not plan_id:
            logging.error("plan_id参数缺失")
            return {"status": "failed", "message": "plan_id参数缺失"}

        if not collection_type:
            logging.error(f"collection_type为空，无法确定MongoDB集合")
            return {"status": "failed", "message": "collection_type为空，无法保存数据"}

        logging.info(
            f"提取参数 - plan_id: {plan_id}, device_ip: {device_ip}, device_name: {device_name}, collection_method: {collection_method}, collection_type: {collection_type}")

        # 查询采集方案
        try:
            plan = DeviceSubCollectionPlan.objects.select_related('summary_plan').get(id=plan_id)
            logging.info(f"成功获取采集方案: {plan.name} (ID: {plan_id})")
            # 如果webhook参数中没有collection_type，从plan中获取
            if not collection_type:
                collection_type = plan.collection_type
                logging.info(f"从采集方案中获取collection_type: {collection_type}")
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
        if task_status == "failed":
            # 1. 先更新子采集任务状态
            error_info = task_info.get("task_errors", [])
            update_sub_task_status("failed", summary_plan_id, plan_id, task_id, error_info)

            # 2. 再更新主采集任务状态，然后不用继续往下走了
            update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
            return {"status": "failed", "message": "任务失败状态已更新"}
        
        # 如果任务完成，添加完成时间（只更新一次，后续不再更新）
        if task_status in ["finished", "success"]:
            # 1. 只更新子采集任务状态,标记为成功
            update_sub_task_status(task_status, summary_plan_id, plan_id, task_id, [])

        # 构建基础结果字典
        base_result = _build_base_collection_result(plan, webhook_args, task_info, status)

        # 没有拿到数据的情况
        if not task_result:
            logging.warning(f"task_result为空: {device_ip} - {plan.name}")

        collection_results = []
        data_process_errors = []  # 记录数据处理错误

        # 遍历处理每条命令结果（通常只有一条）
        for command_name, command_result in task_result.items():
            collection_result = {
                **base_result,
                'method_name': command_name,
                'data': command_result,                 # 原始数据
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
                error_msg = f"数据处理失败: command={command_name}, error={resolve_error}"
                logging.warning(error_msg)
                data_process_errors.append(error_msg)

        # 如果数据处理失败，更新状态为失败（覆盖之前的finished状态）
        if data_process_errors:
            # 1. 先更新子采集任务记录
            update_sub_task_status("failed", summary_plan_id, plan_id, task_id, data_process_errors)
            logging.error(f"子采集任务数据处理失败: {device_ip} - {plan.name} - 错误: {data_process_errors}")
            # 2. 再更新主采集任务记录
            update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
            return {"status": "failed", "message": f"数据处理失败: {data_process_errors}"}

        # 同时保存到通用集合和按类型分类的集合
        if not collection_results:
            logging.warning(f"没有可保存的采集结果: {device_ip} - {plan.name}")
            # 1. 更新子采集任务记录，数据为空，更新状态为失败
            update_sub_task_status("failed", summary_plan_id, plan_id, task_id, ["数据处理后结尾为空"])
            # 2. 更新主采集任务记录
            update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
            return {"status": "failed", "message": "没有可保存的采集结果，所有数据处理后都为空"}

        try:
            # 根据collection_type选择MongoDB集合，优先使用预定义的实例
            collection_name = f"plan_{collection_type}"
            collection_db = COLLECTION_TYPE_MONGO_MAP.get(collection_type)
            if not collection_db:
                # 如果不在预定义列表中，则动态创建（向后兼容）
                collection_db = MongoOps(db='Automation', coll=collection_name)
                logging.warning(f"使用动态创建的MongoDB集合: Automation.{collection_name} (采集类型: {collection_type})")
            else:
                logging.info(f"使用MongoDB集合: Automation.{collection_name} (采集类型: {collection_type})")
            
            collection_db.insert_many(collection_results)
            logging.info(f"采集结果已保存: {device_ip} - {plan.name} - 共 {len(collection_results)} 条记录 - 集合: {collection_name}")
        except Exception as e:
            logging.error(f"保存采集结果到MongoDB失败: {device_ip} - 错误: {str(e)}", exc_info=True)
            # 1. 更新子采集任务记录，保存失败，更新状态为失败（覆盖之前的finished状态）
            update_sub_task_status("failed", summary_plan_id, plan_id, task_id, [f"保存采集结果失败: {str(e)}"])
            # 2. 更新主采集任务记录
            update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
            return {"status": "failed", "message": f"保存采集结果失败: {str(e)}"}

        logging.info(f"webhook回调处理完成: {device_ip} - 共处理 {len(task_result)} 条命令")
        return {"status": "success", "message": "结果插入mongodb成功"}

    except Exception as e:
        logging.error(f"webhook回调执行失败: {str(e)}", exc_info=True)
        # 如果已经获取到必要参数，更新主任务状态为失败
        try:
            # 直接使用 try 块中已获取的变量（如果异常发生在获取这些参数之后，变量已存在）
            if summary_plan_id and device_ip and execute_time:
                update_parent_task_status("failed", summary_plan_id, device_ip, execute_time)
                logging.info(f"已更新主任务状态为失败: device_ip={device_ip}, summary_plan_id={summary_plan_id}")
        except (NameError, Exception) as update_error:
            # 如果变量不存在或更新失败，记录警告但不影响主流程
            logging.warning(f"更新主任务状态失败: {str(update_error)}")
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
                f"参数不完整，无法更新主采集方案记录: summary_plan_id={summary_plan_id}, device_ip={device_ip}")
            return False

        # 更新主采集方案记录的更新时间
        update_result = COLLECTION_PLAN.update_one(
            filter={
                "summary_plan_id": summary_plan_id,
                "device_ip": device_ip,
                "execute_time": execute_time  # 使用execute_time精确定位记录
            },
            update={
                "$set": {
                    "task_status": task_status,
                    "updated_at": datetime.now().isoformat()
                }
            }
        )

        if update_result.matched_count > 0:
            logging.debug(
                f"主采集方案记录已更新: device_ip={device_ip}, summary_plan_id={summary_plan_id}, execute_time={execute_time}")
            return True
        else:
            logging.warning(
                f"未找到主采集方案记录: device_ip={device_ip}, summary_plan_id={summary_plan_id}, execute_time={execute_time}")
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
                "updated_at": datetime.now().isoformat()
            }
        }

        result = COLLECTION_SUB_PLAN.update_one(
            filter={"summary_plan_id": summary_plan_id, "plan_id": plan_id, "task_id": task_id},
            update=update_data
        )
        if result.matched_count == 0:
            logging.warning(f"未找到匹配的任务记录: task_id={task_id}")
        else:
            logging.info(f"任务状态已更新: task_id={task_id}, status={new_status}, matched={result.matched_count}, modified={result.modified_count}")
        return True
    except Exception as e:
        logging.error(f"更新任务状态失败: task_id={task_id}, 错误: {str(e)}", exc_info=True)
        return False


def process_raw_data(plan, collection_result, collection_method):
    """数据处理函数，处理原始数据
    
    Args:
        plan: 采集方案对象
        collection_result: 原始数据
        collection_method: 采集方法 (netmiko/netconf)
        
    Returns:
        tuple: (status, error_message, processed_data)
    """
    try:
        command_result = collection_result["data"]      # 原始数据
        method = (collection_method or "").lower()
        
        # 数据处理函数（按采集方式通过分发表调用，异常立即返回）
        try:
            dispatch = {
                "netmiko": (getattr(plan, "netmiko_processor_enabled", False), getattr(plan, "netmiko_processor", None), getattr(plan, "process_netmiko_data", None)),
                "netconf": (getattr(plan, "netconf_processor_enabled", False), getattr(plan, "netconf_processor", None), getattr(plan, "process_netconf_data", None)),
            }
            enabled, code, func = dispatch.get(method, (False, None, None))

            if enabled and code and callable(func):
                logging.info(f"执行{method}数据处理函数: {plan.name}")
                processed_data = func(command_result)
                logging.info(f"数据处理函数执行完成: {plan.name}")
            else:
                # 未启用处理器或无处理函数                 
                logging.info(f"未启用处理器，透传原始数据: {plan.name}")
                processed_data = []
        except Exception as e:
            logging.error(f"数据处理函数执行失败: {plan.name} - {str(e)}", exc_info=True)
            return False, f"{method}_processor_failed: {str(e)}", []
         
        return True, "", processed_data
        
    except Exception as e:
        logging.error(f"数据处理异常: {plan.name} - {str(e)}", exc_info=True)
        return False, f"exception: {str(e)}", []


def resolve_raw_data(plan, collection_result, collection_method):
    """函数处理+字段映射原始数据
    
    Args:
        plan: 采集方案对象
        collection_result: 原始数据
        collection_method: 采集方法 (netmiko/netconf)
        
    Returns:
        tuple: (status, error_message, mapping_data)
    """
    try:
        # 首先判断结果是否正常， 如果是 netmiko 采集方式，且 data 字段是字符串，说明 Textfsm 模板解析失败
        if collection_method.lower() == "netmiko" and isinstance(collection_result.get("data", ''), str):
            return False, f"Textfsm 模板解析失败", []

        copy_data = collection_result.copy()            # 首先进行拷贝数据

        command_result = copy_data["data"]              # 原始数据
        mapping_data = []                               # 映射数据
        method = collection_method.lower()
        
        # 第一步：数据处理函数（按采集方式通过分发表调用，异常立即返回）, 有函数则添加中间层processed_data
        try:
            dispatch = {
                "netmiko": (getattr(plan, "netmiko_processor_enabled", False), getattr(plan, "netmiko_processor", None), getattr(plan, "process_netmiko_data", None)),
                "netconf": (getattr(plan, "netconf_processor_enabled", False), getattr(plan, "netconf_processor", None), getattr(plan, "process_netconf_data", None)),
            }
            enabled, code, func = dispatch.get(method, (False, None, None))

            if enabled and code and callable(func):
                logging.info(f"执行{method}数据处理函数: {plan.name}")
                processed_data = func(command_result)
                copy_data["processed_data"] = processed_data
            else:
                # 未启用处理器或无处理函数，则透传原始数据
                copy_data["processed_data"] = []
            logging.info(f"数据处理函数执行完成: {plan.name}")  
        except Exception as e:
            logging.error(f"数据处理函数执行失败: {plan.name} - {str(e)}", exc_info=True)
            return False, f"{collection_method}_process_data_function_failed: {str(e)}", []
        
        # 第二步：字段映射，获取字段映射配置
        field_mappings = None
        path_config = None
        
        if method == "netmiko":
            if plan.netmiko_path and plan.netmiko_field_mappings:
                field_mappings = plan.netmiko_field_mappings
                path_config = plan.netmiko_path
                logging.info(f"使用Netmiko字段映射: {plan.name}")
        elif method == "netconf":
            if plan.netconf_path and plan.netconf_field_mappings:
                field_mappings = plan.netconf_field_mappings
                path_config = plan.netconf_path
                logging.info(f"使用NETCONF字段映射: {plan.name}")
        
        if field_mappings and path_config:
            try:
                mapping_data = apply_field_mappings(copy_data, field_mappings, path_config)
                if mapping_data:
                    logging.info(f"字段映射执行成功: {plan.name} - 映射了 {len(mapping_data)} 条记录")
                else:
                    logging.warning(f"字段映射未返回数据: {plan.name}")
            except Exception as e:
                logging.error(f"字段映射执行失败: {plan.name} - {str(e)}", exc_info=True)
                return False, f"{collection_method}_apply_field_mappings_failed(path={path_config}): {str(e)}", []

        # 3. 根据厂商和类型，调用对应的处理方法
        try:
            resolved_data = apply_vendor_processor(plan, mapping_data)
        except Exception as e:
            logging.error(f"厂商处理方法执行失败: {plan.name} - {str(e)}", exc_info=True)
            return False, f"{collection_method}_apply_vendor_processor_failed: {str(e)}", []

        return True, "", resolved_data
        
    except Exception as e:
        logging.error(f"数据处理异常: {plan.name} - {str(e)}", exc_info=True)
        return False, f"resolve_raw_data_exception: {str(e)}", []


def apply_field_mappings(data_dict, field_mappings, path_config=None):
    """应用字段映射 - 支持复杂字段映射配置

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
            key=lambda x: x[1].get("sort", 999) if isinstance(x[1], dict) else 999
        )

        # 确定数组键
        array_key = None
        if path_config:
            # 如果提供了path_config，直接使用
            array_key = path_config
        else:
            # 自动检测数组键
            for field_name, field_config in sorted_fields:
                # 处理新格式：field_config是字典，包含value字段
                if isinstance(field_config, dict):
                    field_path = field_config.get("value", "")
                else:
                    # 处理旧格式：field_config直接是字符串路径
                    field_path = field_config
                
                if '[*]' in field_path:
                    parts = field_path.split('[*]')
                    if parts[0]:
                        array_key = parts[0].rstrip('.')
                        break

        if not array_key or array_key not in data_dict:
            logging.warning(f"未找到数组键: {array_key}")
            return []

        array_data = data_dict[array_key]
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
                if '[*]' in field_path:
                    # 处理数组路径，如 "data[*].type"
                    parts = field_path.split('[*]')
                    if len(parts) == 2 and parts[1]:
                        # 从当前item中获取值
                        field_key = parts[1].lstrip('.')
                        value = item.get(field_key, "")
                    else:
                        # 如果路径格式不正确，使用整个item
                        value = item
                elif field_path in data_dict:
                    # 从data_dict顶层获取值
                    value = data_dict[field_path]
                else:
                    # 直接使用值路径作为值
                    value = field_path

                result_item[field_name] = value

            # 将结果添加到数组中
            result_item['log_time'] = log_time
            result_item["hostip"] = host_ip
            processed_data.append(result_item)

        logging.info(f"字段映射完成: 处理了 {len(processed_data)} 条记录，使用了 {len(sorted_fields)} 个字段")
        return processed_data

    except Exception as e:
        logging.error(f"应用字段映射失败: {str(e)}", exc_info=True)
        return []


def apply_vendor_processor(plan, processed_data):
    """根据厂商和采集类型调用对应的处理方法处理数据

    Args:
        plan: 采集方案对象或字典，包含厂商和采集类型信息
        processed_data: 已处理的数据列表

    Returns:
        处理后的数据列表，如果处理失败则返回原始数据
    """
    try:
        if not plan or not processed_data:
            return processed_data

        # 获取厂商和采集类型
        vendor = plan.summary_plan.vendor
        collection_type = plan.collection_type

        # 获取模块名和类名
        module_name, class_name = vendor_mapping.get(vendor, (None, None))

        if not module_name or not class_name:
            logging.warning(f"不支持的厂商: {vendor}，跳过厂商处理")
            return processed_data

        # 动态导入模块
        try:
            module = importlib.import_module(f'apps.device_api.tools.{module_name}')
            plan_class = getattr(module, class_name, None)

            if not plan_class:
                logging.warning(f"未找到类: {class_name}，跳过厂商处理")
                return processed_data

            # 构建方法名：get_{collection_type}
            method_name = f'get_{collection_type}'
            method = getattr(plan_class, method_name, None)

            if method and callable(method):
                # 调用方法处理数据
                resolved_data = method(processed_data)
                logging.info(f"已应用厂商处理方法: {vendor}.{class_name}.{method_name}()")
                return resolved_data
            else:
                logging.warning(f"未找到方法: {class_name}.{method_name}()，跳过厂商处理")
                return processed_data

        except ImportError as e:
            logging.warning(f"导入模块失败: apps.device_api.tools.{module_name}, 错误: {str(e)}")
            return processed_data
        except Exception as e:
            logging.error(f"调用厂商处理方法失败: {str(e)}", exc_info=True)
            return processed_data

    except Exception as e:
        logging.error(f"执行厂商处理方法时发生错误: {str(e)}", exc_info=True)
        # 即使处理失败，也返回原始数据
        return processed_data
