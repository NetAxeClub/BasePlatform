# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from apps.device_api import (
    COLLECTION_RESULTS_DB, COLLECTION_ARP, COLLECTION_MAC, COLLECTION_LLDP, 
    COLLECTION_IP_INTERFACE, COLLECTION_INTERFACE_BRIEF, COLLECTION_AGGRE_PORT
)
from apps.device_api.models import DeviceSubCollectionPlan


def netpalm_data_to_mongodb(**kwargs):
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
        collection_type = webhook_args.get("type", "arp")

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
        task_result = task_info.get("task_result", {})
        created_on = task_info.get("created_on", "")
        task_status = task_info.get("task_status", "")

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
                'method_name': command_name,
                'data': command_result,
                'processed_data': None,  # 可以在这里添加数据处理逻辑
                'collected_at': created_on,
                'task_id': task_id,
                'task_status': task_status,
                'status': status
            }

            # 处理原始数据
            processing_status, processed_data = process_raw_data(plan, collection_result, collection_method)
            collection_result["processed_data"] = processed_data
            collection_result["processing_status"] = processing_status
            
            # 根据处理状态记录日志
            if processing_status:
                logging.info(f"数据处理成功: {device_ip} - 命令: {command_name}")

                # 保存数据到指定MongoDB，比如arp、mac
                result_dict = save_to_collection_db(
                    content=processed_data if isinstance(processed_data, list) else [],
                    hostip=device_ip,
                    collection_type=collection_type,
                    plan=plan,
                    device_name=device_name,
                    created_on=created_on
                )

                if not result_dict.get("status"):
                    logging.error(f"保存数据失败，错误信息为 {result_dict['message']}")

            else:
                logging.error(f"数据处理失败: {device_ip} - 命令: {command_name}")
      
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
    """处理原始数据
    
    Args:
        plan: 采集方案对象
        collection_result: 原始数据
        collection_method: 采集方法 (netmiko/netconf)
        
    Returns:
        tuple: (status, processed_data) - (True/False, 处理后的数据/空列表)
    """
    try:
        command_result = collection_result["data"]
        processed_data = []  # 初始化processed_data
        has_error = False  # 跟踪是否有错误
        
        # 第一步：数据处理函数
        if plan.netmiko_processor_enabled and plan.netmiko_processor:
            logging.info(f"执行数据处理函数: {plan.name}")
            try:
                processed_data = plan.process_netmiko_data(command_result)
                logging.info(f"数据处理函数执行成功: {plan.name}")
            except Exception as e:
                logging.error(f"数据处理函数执行失败: {plan.name} - {str(e)}")
                has_error = True
        
        # 第二步：字段映射
        field_mappings = None
        path_config = None
        
        if collection_method == "netmiko":
            if plan.netmiko_path and plan.netmiko_field_mappings:
                field_mappings = plan.netmiko_field_mappings
                path_config = plan.netmiko_path
                logging.info(f"使用Netmiko字段映射: {plan.name}")
        elif collection_method == "netconf":
            if plan.netconf_path and plan.netconf_field_mappings:
                field_mappings = plan.netconf_field_mappings
                path_config = plan.netconf_path
                logging.info(f"使用NETCONF字段映射: {plan.name}")
        
        if field_mappings and path_config:
            try:
                # 应用字段映射
                mapped_data = apply_field_mappings(collection_result, field_mappings, path_config)
                if mapped_data:
                    processed_data = mapped_data
                    logging.info(f"字段映射执行成功: {plan.name} - 映射了 {len(mapped_data)} 条记录")
                else:
                    logging.warning(f"字段映射未返回数据: {plan.name}")
            except Exception as e:
                logging.error(f"字段映射执行失败: {plan.name} - {str(e)}")
                has_error = True
        
        # 如果有错误，返回失败状态
        if has_error:
            return False, []
        
        return True, processed_data
        
    except Exception as e:
        logging.error(f"数据处理异常: {plan.name} - {str(e)}")
        return False, []


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


def save_to_collection_db(content: list, hostip: str, collection_type: str, plan: dict, device_name: str, created_on: str) -> dict:
    """保存采集数据到采集数据
    
    :param content: 采集结果
    :param hostip: 设备ip
    :param collection_type: 采集类型
    :param plan: plan对象
    :param device_name: 设备名称
    :param created_on: 采集时间
    :return:
    """
    # 获取MongoDB数据库集合
    collection_map = {
        "arp": COLLECTION_ARP,
        "mac": COLLECTION_MAC,
        "lldp": COLLECTION_LLDP,
        "ip_interface": COLLECTION_IP_INTERFACE,
        "interface_brief": COLLECTION_INTERFACE_BRIEF,
        "aggre_port": COLLECTION_AGGRE_PORT
    }
    
    my_mongo = collection_map.get(collection_type, None)

    if len(content) == 0:
        logging.info("processed_data is []")
        return {"status": True, "message": "processed_data is []"}
        
    if not my_mongo:
        logging.error(f"找不到对应的集合: {collection_type}")
        return {"status": False, "message": f"找不到对应的集合: {collection_type}"}
    
    try:
        # 删除该设备的已有数据
        my_mongo.delete_many(query={"hostip": hostip})
        logging.info(f"已删除设备 {hostip} 的旧数据")

        datas = []
        for item in content:
            # 创建新的数据项，避免修改原始数据
            new_item = item.copy()  # 复制原数据
            new_item['hostip'] = hostip
            new_item['collected_at'] = created_on
            datas.append(new_item)
    
        # 批量插入原始数据
        my_mongo.insert_many(datas)
        
        logging.info(f"数据传输成功: {hostip} - 类型: {collection_type}")
        return {'status': True}
        
    except Exception as e:
        logging.error(f"insert_many_failed:{str(e)}")
        logging.error(f"保存到数据库失败: hostip={hostip}, collection_type={collection_type}")
        logging.error(f"数据传输失败: {hostip} - 类型: {collection_type} - {str(e)}")
        return {"status": False, "message": f"保存到数据库失败: {str(e)}"}