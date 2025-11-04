# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from apps.device_api.models import DeviceSubCollectionPlan
from apps.device_api import COLLECTION_RESULTS_DB


def plan_data_to_mongodb(**kwargs):
    """NetPalm webhook回调函数，将采集结果保存到MongoDB
    
    Args:
        **kwargs: 包含status, task_info, webhook_args等参数
        
    Returns:
        dict: 处理结果字典
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
        idc_name = webhook_args.get("idc_name", "")
        collection_method = webhook_args.get("collection_method", "netmiko")
        collection_type = webhook_args.get("collection_type", "arp")

        logging.info(f"提取参数 - plan_id: {plan_id}, device_ip: {device_ip}, device_name: {device_name}, collection_method: {collection_method}")

        # 查询采集方案
        try:
            plan = DeviceSubCollectionPlan.objects.select_related('summary_plan').get(id=plan_id)
            logging.info(f"成功获取采集方案: {plan.name} (ID: {plan_id})")
        except DeviceSubCollectionPlan.DoesNotExist:
            logging.error(f"采集方案不存在: plan_id={plan_id}")
            return {"status": "failed", "message": f"采集方案不存在: plan_id={plan_id}"}
        
        # 获取任务ID
        task_id = task_info.get("task_id")
        created_on = task_info.get("created_on", "")
        task_queue = task_info.get("task_queue", "")
        task_status = task_info.get("task_status", "")
        task_result = task_info.get("task_result", {})
        task_errors = task_info.get("task_errors", [])

        logging.info(f"任务信息 - task_id: {task_id}, task_status: {task_status}, created_on: {created_on}")
        logging.info(f"采集结果数量: {len(task_result)} 条命令")

        # task_result 是一个字典，键是命令名，值是对应的结果
        for command_name, command_result in task_result.items():
            
            collection_result = {
                'plan_id': plan.id,
                'plan_name': plan.name,
                'device_ip': device_ip,
                'device_name': device_name,
                'idc_name': idc_name,
                'device_type': plan.summary_plan.device_type,
                'vendor': plan.summary_plan.vendor,
                'collection_method': collection_method,
                'collection_type': collection_type,
                'method_name': command_name,   # 这个地方有点问题，当是netconf的时候，应该没有command_name
                'data': command_result,
                'processed_data': None,  # 可以在这里添加数据处理逻辑
                'collected_at': created_on,
                'task_id': task_id,
                'task_status': task_status,
                'task_queue': task_queue,
                'task_errors': task_errors,
                'status': status
            }

            # 处理原始数据
            processed_status, processed_error, processed_data = process_raw_data(plan, collection_result, collection_method)
            
            collection_result["processed_data"] = processed_data
            collection_result["processed_status"] = "success" if processed_status else "failed"
            collection_result["processed_error"] = processed_error

            # 保存当前执行流程结果到MongoDB
            try:
                COLLECTION_RESULTS_DB.insert_one(collection_result)
                logging.info(f"采集结果已保存: {device_ip} - {plan.name} - 命令: {command_name}")
            except Exception as e:
                logging.error(f"保存采集结果失败: {device_ip} - 命令: {command_name} - 错误: {str(e)}")

        logging.info(f"webhook回调处理完成: {device_ip} - 共处理 {len(task_result)} 条命令")
        return {"status": "success", "message": "结果插入mongodb成功"}
        
    except Exception as e:
        logging.error(f"webhook回调执行失败: {str(e)}", exc_info=True)
        return {"status": "failed", "message": "webhook回调执行失败"}


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
        command_result = collection_result["data"]      # 原始数据
        mapping_data = []                               # 映射数据
        error_message = ""                              # 记录错误信息
        has_error = False                               # 是否存在错误
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
                collection_result["processed_data"] = processed_data
            else:
                # 未启用处理器或无处理函数，则透传原始数据
                collection_result["processed_data"] = []
            logging.info(f"数据处理函数执行完成: {plan.name}")
        except Exception as e:
            logging.error(f"数据处理函数执行失败: {plan.name} - {str(e)}", exc_info=True)
            method_tag = (collection_method or "unknown").lower()
            return False, f"{method_tag}_processor_failed: {str(e)}", []
        
        # 第二步：字段映射
        # 获取字段映射配置
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
                mapping_data = apply_field_mappings(collection_result, field_mappings, path_config)
                if mapping_data:
                    logging.info(f"字段映射执行成功: {plan.name} - 映射了 {len(mapping_data)} 条记录")
                else:
                    logging.warning(f"字段映射未返回数据: {plan.name}")
            except Exception as e:
                logging.error(f"字段映射执行失败: {plan.name} - {str(e)}", exc_info=True)
                method_tag = (collection_method or "unknown").lower()
                return False, f"{method_tag}_mapping_failed(path={path_config}): {str(e)}", []
        
        # 如果有错误，返回失败状态
        if has_error:
            return False, error_message, []
        
        return True, "", mapping_data
        
    except Exception as e:
        logging.error(f"数据处理异常: {plan.name} - {str(e)}")
        return False, f"exception: {str(e)}", []


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
            processed_data.append(result_item)

        logging.info(f"字段映射完成: 处理了 {len(processed_data)} 条记录，使用了 {len(sorted_fields)} 个字段")
        return processed_data

    except Exception as e:
        logging.error(f"应用字段映射失败: {str(e)}", exc_info=True)
        return []

