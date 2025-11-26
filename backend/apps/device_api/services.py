import logging
import time
from datetime import datetime
from typing import List
from service_mesh import south_driver_runner
from apps.automation.tools.base_connection import device_type_map
from apps.device_api.models import NetconfXMLTemplate
from apps.device_api import COLLECTION_RESULTS_DB, COLLECTION_PLAN, COLLECTION_SUB_PLAN
from confload.confload import config


logger = logging.getLogger(__name__)


class DeviceCollectionService:
    """设备采集服务类"""

    @staticmethod
    def get_xml_templates_by_plan(plan_id: int) -> List[NetconfXMLTemplate]:
        """获取采集方案的XML模板"""
        queryset = NetconfXMLTemplate.objects.filter(
            collection_plan_id=plan_id
        )
        return queryset

    @staticmethod
    def execute_both_collection(plan, device, south_driver):
        """同时执行NETCONF和Netmiko采集（仅执行采集，不保存结果）"""
        try:
            logger.info(f"开始执行双重采集: 方案={plan.name}, 设备={device.manage_ip}")
            
            netconf_result, netmiko_result = None, None
            netconf_success, netmiko_success = False, False

            # 执行Netmiko采集
            if plan.netmiko_enabled and hasattr(device, 'ssh_account') and device.ssh_account:
                logger.info(f"开始执行Netmiko采集: {device.manage_ip}")
                netmiko_result = DeviceCollectionService.execute_netmiko_collection(plan, device, south_driver)

                if netmiko_result.get("success"):
                    netmiko_success = True
                    logger.info(f"Netmiko采集成功: {device.manage_ip}")
                else:
                    logger.warning(f"Netmiko采集失败: {device.manage_ip} - {netmiko_result.get('error', '未知错误')}")
            else:
                logger.info(f"跳过Netmiko采集: {device.manage_ip} (未启用或未配置账户)")

            # 执行NETCONF采集
            if plan.netconf_enabled and hasattr(device, 'netconf_account') and device.netconf_account:
                logger.info(f"开始执行NETCONF采集: {device.manage_ip}")
                netconf_result = DeviceCollectionService.execute_netconf_collection(plan, device, south_driver)
                
                if netconf_result.get("success"):
                    netconf_success = True
                    logger.info(f"NETCONF采集成功: {device.manage_ip}")
                else:
                    logger.warning(f"NETCONF采集失败: {device.manage_ip} - {netconf_result.get('error', '未知错误')}")
            else:
                logger.info(f"跳过NETCONF采集: {device.manage_ip} (未启用或未配置账户)")

            # 检查是否有任何采集成功
            if not netconf_success and not netmiko_success:
                error_msg = "所有可用的采集方式都失败了"
                logger.error(f"{error_msg}: 设备={device.manage_ip}")
                return {
                    'success': False,
                    'netconf_result': netconf_result,
                    'netmiko_result': netmiko_result,
                    'error': error_msg
                }

            # 至少有一种采集方式成功
            success_message = []
            if netconf_success:
                success_message.append("NETCONF采集成功")
            if netmiko_success:
                success_message.append("Netmiko采集成功")

            logger.info(f"双重采集完成: {device.manage_ip} - {'; '.join(success_message)}")
            return {
                'success': True,
                'netconf_result': netconf_result,
                'netmiko_result': netmiko_result,
                'message': "; ".join(success_message)
            }

        except Exception as e:
            error_msg = f"双重采集异常: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}", exc_info=True)
            return {
                'success': False,
                'netconf_result': None,
                'netmiko_result': None,
                'error': error_msg
            }

    @staticmethod
    def execute_netmiko_collection(plan, device, south_driver):
        """执行Netmiko采集执行命令"""
        try:
            logger.info(f"开始执行NETMIKO采集: 方案={plan.name}, 设备={device.manage_ip}")

            # 获取命令列表
            command = plan.get_netmiko_method()
            account = device.ssh_account

            # 获取正确的设备类型
            vendor_alias = device.vendor.alias if device.vendor else 'Huawei'
            device_type = device_type_map.get(vendor_alias, 'huawei')

            host_info = {"host": south_driver, "port": int(config.south_http_port)}

            netpalm_info = {
                "library": "netmiko",
                "connection_args": {
                    "device_type": device_type,
                    "host": device.manage_ip,
                    "username": account.username,
                    "password": account.decode_password,
                    "timeout": 5,
                    "session_timeout": 20
                },
                "command": command,
                "args": {
                    "use_textfsm": True
                },
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "plan_id": plan.id,
                        "device_ip": device.manage_ip,
                        "device_name": device.name,
                        "idc_name": device.idc.name,
                        "collection_method": "netmiko",
                        "collection_type": plan.collection_type,
                        **host_info
                    }
                },
                "queue_strategy": "fifo"
            }

            if plan.textfsm_template:
                netpalm_info["args"]["textfsm_template"] = plan.textfsm_template

            netmiko_result = south_driver_runner.get_device_config(url_prefix='/getconfig', host_info=host_info,
                                                                   netpalm_info=netpalm_info)
            logger.info(f"执行CLI采集: {device.manage_ip}, 命令: {command}")

            return netmiko_result

        except Exception as e:
            error_msg = f"Netmiko采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            return {"status": "failed", "data": {}}

    @staticmethod
    def execute_netconf_collection(plan, device, south_driver):
        """执行NETCONF采集"""
        try:
            logger.info(f"开始执行NETCONF采集: 方案={plan.name}, 设备={device.manage_ip}")

            account = device.netconf_account
            host_info = {"host": south_driver, "port": int(config.south_http_port)}

            vendor_alias = device.vendor.alias if device.vendor else 'Default'
            
            # NETCONF设备类型映射
            netconf_device_type_map = {
                "H3C": "h3c",
                "Huawei": "huaweiyang",             # 华为设备使用huaweiyang类型
                "Cisco": "nexus",
                "Default": "default"
            }
            device_type = netconf_device_type_map.get(vendor_alias, "h3c")  # 默认使用h3c
                
            # 获取XML模板 - 使用第一个模板
            xml_templates = plan.xml_templates.first()
            if not xml_templates:
                error_msg = "采集方案未配置有效的NETCONF XML模板"
                logger.error(error_msg)
                return {"status": "failed", "data": {}}
            
            selected_template = xml_templates
            
            args_filter = selected_template.xml_template
            clean_xml = args_filter.strip()
            if "<filter type=" not in clean_xml:
                filter_xml = f'<filter type="subtree">{clean_xml}</filter>'
            else:
                filter_xml = clean_xml
            logger.info(f"构建的filter XML: {filter_xml}")

            netpalm_info = {
                "library": "ncclient",
                "connection_args": {
                    "host": device.manage_ip,
                    "username": account.username,
                    "password": account.decode_password,
                    "port": 830,
                    "hostkey_verify": False,
                    "allow_agent": False,
                    "look_for_keys": False,
                    "device_params": {"name": device_type},
                },
                "args": {
                    "filter": filter_xml,
                    "render_json": True
                },
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "plan_id": plan.id,
                        "device_ip": device.manage_ip,
                        "device_name": device.name,
                        "idc_name": device.idc.name,
                        "collection_method": "netconf",
                        "collection_type": plan.collection_type,
                        **host_info
                    }
                },
                "queue_strategy": "fifo",
            }

            # 根据收集方法设置参数和URL前缀
            collect_method = selected_template.collect_method
            if collect_method in ("get", "rpc"):
                netpalm_info["args"][collect_method] = True
                url_prefix = '/getconfig/ncclient/get'
            else:
                netpalm_info["args"]["source"] = "running"
                url_prefix = '/getconfig/ncclient'
            
            netconf_result = south_driver_runner.get_device_config(
                url_prefix=url_prefix,
                host_info=host_info,
                netpalm_info=netpalm_info
            )

            logger.info(f"执行CLI采集: {device.manage_ip}")

            return netconf_result

        except Exception as e:
            error_msg = f"Netmiko采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            return {"status": "failed", "data": {}}

    @staticmethod
    def insert_data_to_mongodb(data):
        """插入数据到MongoDB
        
        Args:
            data: 要插入的数据字典
            
        Returns:
            dict: 包含操作结果的字典
        """
        try:
            # 记录操作开始
            logger.info(f"开始插入数据到MongoDB")
            
            # 直接插入数据，不添加任何额外字段
            result = COLLECTION_RESULTS_DB.insert_one(data)
            logger.info(f"成功插入文档，ID: {result.inserted_id}")
            
            return {
                'success': True,
                'data': {'inserted_id': str(result.inserted_id)},
                'message': '数据插入成功',
                'code': 200
            }
                
        except Exception as e:
            logger.error(f"插入数据到MongoDB失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'数据库操作失败: {str(e)}',
                'code': 500
            }

    @staticmethod
    def celery_both_collection(plan, device_info):
        """同时执行NETCONF和Netmiko采集"""
        try:
            manage_ip = device_info.get('manage_ip')            # 设备IP
            logger.info(f"开始执行双重采集: 方案={plan['name']}, 设备={manage_ip}")

            netconf_result, netmiko_result = None, None
            netconf_success, netmiko_success = False, False

            # 执行Netmiko采集
            if plan['netmiko_enabled'] and device_info.get('ssh_enable'):
                logger.info(f"开始执行Netmiko采集: {manage_ip}")
                netmiko_result = DeviceCollectionService.celery_netmiko_collection(plan, device_info)

                if netmiko_result.get("success"):
                    netmiko_success = True
                    logger.info(f"Netmiko采集成功: {manage_ip}")
                else:
                    logger.warning(f"Netmiko采集失败: {manage_ip} - {netmiko_result.get('error', '未知错误')}")
            else:
                logger.info(f"跳过Netmiko采集: {manage_ip} (未启用或未配置账户)")

            # 执行NETCONF采集
            if plan['netconf_enabled'] and device_info.get('netconf_enable'):
                logger.info(f"开始执行NETCONF采集: {manage_ip}")
                netconf_result = DeviceCollectionService.celery_netconf_collection(plan, device_info)

                if netconf_result.get("success"):
                    netconf_success = True
                    logger.info(f"NETCONF采集成功: {manage_ip}")
                else:
                    logger.warning(f"NETCONF采集失败: {manage_ip} - {netconf_result.get('error', '未知错误')}")
            else:
                logger.info(f"跳过NETCONF采集: {manage_ip} (未启用或未配置账户)")

            # 检查是否有任何采集成功
            if not netconf_success and not netmiko_success:
                error_msg = "所有可用的采集方式都失败了"
                logger.error(f"{error_msg}: 设备={manage_ip}")
                return {
                    'success': False,
                    'netconf_result': netconf_result,
                    'netmiko_result': netmiko_result,
                    'error': error_msg
                }

            return {
                'success': True,
                'netconf_result': netconf_result,
                'netmiko_result': netmiko_result,
            }

        except Exception as e:
            error_msg = f"双重采集异常: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan['name']}, 设备={manage_ip}", exc_info=True)
            return {
                'success': False,
                'netconf_result': None,
                'netmiko_result': None,
                'error': error_msg
            }

    @staticmethod
    def celery_netmiko_collection(plan, device_info):
        """执行Netmiko采集执行命令"""
        try:
            manage_ip = device_info.get('manage_ip')
            execute_time = device_info.get('execute_time')
            logger.info(f"开始执行NETMIKO采集: 方案={plan['name']}, 设备={manage_ip}")

            # 获取命令列表
            command = plan['netmiko_method']
            account = device_info.get("ssh")

            # 获取正确的设备类型
            vendor_alias = device_info.get("vendor__alias", 'Huawei')
            device_type = device_type_map.get(vendor_alias, 'huawei')
            
            # 获取南向驱动执行节点
            execute_node = device_info.get("execute_node")
            if not execute_node:
                error_msg = "南向驱动服务不存在"
                logger.error(f"{error_msg}: 设备={manage_ip}")
                return {"success": False, "error": error_msg}

            south_info = {"host": execute_node, "port": int(config.south_http_port)}

            netpalm_info = {
                "library": "netmiko",
                "connection_args": {
                    "device_type": device_type,
                    "host": manage_ip,
                    "username": account.get("username"),
                    "password": account.get("password"),
                    "timeout": 5,
                    "session_timeout": 20
                },
                "command": command,
                "args": {
                    "use_textfsm": True
                },
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "summary_plan_id": plan['summary_plan'],
                        "plan_id": plan['id'],
                        "device_ip": manage_ip,
                        "device_name": device_info.get("name"),
                        "idc_name": device_info.get("idc__name"),
                        "collection_method": "netmiko",
                        "collection_type": plan['collection_type'],
                        "celery_flag": True,
                        "execute_time": execute_time,
                        **south_info
                    }
                },
                "queue_strategy": "fifo"
            }

            if plan['textfsm_template']:
                netpalm_info["args"]["textfsm_template"] = plan['textfsm_template']

            # 这个结果只是返回task_id
            netmiko_result = south_driver_runner.get_device_config(url_prefix='/getconfig', host_info=south_info,
                                                                   netpalm_info=netpalm_info)
            logger.info(f"调用南向驱动，执行节点{execute_node}，执行CLI采集: {manage_ip}, 命令: {command}")

            # 提取task_id
            if netmiko_result and netmiko_result.get("success"):
                result_data = netmiko_result.get("data", {})
                task_id = result_data.get("data", {}).get("task_id", "")

                # 插入子采集任务记录，记录任务初始状态，初始状态设置为queued 排队中
                task_record = {
                    "summary_plan_id": plan['summary_plan'],
                    "plan_id": plan['id'],
                    "task_id": task_id,
                    "device_ip": manage_ip,
                    "device_name": device_info.get("name"),
                    "idc_name": device_info.get("idc__name"),
                    "task_status": "queued",  # 初始状态为排队中
                    "collection_type": plan['collection_type'],
                    "collection_method": "netmiko",
                    "vendor": plan['summary_plan_vendor'],
                    "device_type": plan['summary_plan_device_type'],
                    "execute_time": execute_time,  # 关联主采集方案的执行时间
                    "created_at": datetime.now().isoformat(),  # 实际创建时间
                    "task_errors": [],
                    "log_time": time.time()
                }
                COLLECTION_SUB_PLAN.insert_one(task_record)
                logger.info(f"Netmiko任务记录已创建: task_id={task_id}, device_ip={manage_ip}, plan={plan['name']}")
                return {
                    "success": True, 
                    "result": netmiko_result,
                    "task_id": task_id
                }
            else:
                error_msg = netmiko_result.get("error", "Netmiko采集失败") if netmiko_result else "Netmiko采集失败：接口调用失败"
                logger.error(f"Netmiko采集失败: device_ip={manage_ip}, error={error_msg}")
                return {"success": False, "error": error_msg, "result": netmiko_result}

        except Exception as e:
            error_msg = f"Netmiko采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan['name']}, 设备={manage_ip}")
            return {"success": False, "error": error_msg}

    @staticmethod
    def celery_netconf_collection(plan, device_info):
        """执行NETCONF采集"""
        try:
            manage_ip = device_info.get("manage_ip")
            execute_time = device_info.get("execute_time")
            logger.info(f"开始执行NETCONF采集: 方案={plan['name']}, 设备={manage_ip}")

            account = device_info.get("netconf")
            
            # 检查账号信息
            if not account:
                error_msg = "NETCONF账号信息不存在"
                logger.error(f"{error_msg}: 设备={manage_ip}")
                return {"success": False, "error": error_msg}
            
            # 检查南向驱动地址
            execute_node = device_info.get("execute_node")
            if not execute_node:
                error_msg = "南向驱动服务地址不存在"
                logger.error(f"{error_msg}: 设备={manage_ip}")
                return {"success": False, "error": error_msg}
            
            south_info = {"host": execute_node, "port": int(config.south_http_port)}
            vendor_alias = device_info.get("vendor__alias", 'Default')

            # NETCONF设备类型映射
            netconf_device_type_map = {
                "H3C": "h3c",
                "Huawei": "huaweiyang",  # 华为设备使用huaweiyang类型
                "Cisco": "nexus",
                "Default": "default"
            }
            device_type = netconf_device_type_map.get(vendor_alias, "h3c")  # 默认使用h3c

            # 获取XML模板 - 使用第一个模板
            xml_templates = plan.get('xml_templates', [])
            if not xml_templates or not isinstance(xml_templates, list) or len(xml_templates) == 0:
                error_msg = "采集方案未配置有效的NETCONF XML模板"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            # 取第一个模板（序列化后的字典格式）
            selected_template = xml_templates[0]

            # 从字典中获取字段
            args_filter = selected_template.get('xml_template', '')
            if not args_filter:
                error_msg = "XML模板内容为空"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            clean_xml = args_filter.strip()
            if "<filter type=" not in clean_xml:
                filter_xml = f'<filter type="subtree">{clean_xml}</filter>'
            else:
                filter_xml = clean_xml
            logger.info(f"构建的filter XML: {filter_xml}")

            netpalm_info = {
                "library": "ncclient",
                "connection_args": {
                    "host": manage_ip,
                    "username": account.get("username"),
                    "password": account.get("password"),
                    "port": 830,
                    "hostkey_verify": False,
                    "allow_agent": False,
                    "look_for_keys": False,
                    "device_params": {"name": device_type},
                },
                "args": {
                    "filter": filter_xml,
                    "render_json": True
                },
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "summary_plan_id": plan['summary_plan'],
                        "plan_id": plan['id'],
                        "device_ip": manage_ip,
                        "device_name": device_info.get("name"),
                        "idc_name": device_info.get("idc__name"),
                        "collection_method": "netconf",
                        "collection_type": plan['collection_type'],
                        "celery_flag": True,
                        "execute_time": execute_time,
                        **south_info
                    }
                },
                "queue_strategy": "fifo",
            }

            # 根据收集方法设置参数和URL前缀
            collect_method = selected_template.get('collect_method', 'get')
            if collect_method in ("get", "rpc"):
                netpalm_info["args"][collect_method] = True
                url_prefix = '/getconfig/ncclient/get'
            else:
                netpalm_info["args"]["source"] = "running"
                url_prefix = '/getconfig/ncclient'

            netconf_result = south_driver_runner.get_device_config(
                url_prefix=url_prefix,
                host_info=south_info,
                netpalm_info=netpalm_info
            )

            logger.info(f"执行NETCONF采集: {manage_ip}")

            # 统一返回值格式，提取task_id
            if netconf_result and netconf_result.get("success"):
                result_data = netconf_result.get("data", {})
                # 提取task_id，可能在不同位置
                task_id = result_data.get("data", {}).get("task_id", None)

                # 插入子采集记录，记录任务初始状态
                task_record = {
                    "summary_plan_id": plan['summary_plan'],
                    "plan_id": plan['id'],
                    "task_id": task_id,
                    "device_ip": manage_ip,
                    "device_name": device_info.get("name"),
                    "idc_name": device_info.get("idc__name"),
                    "task_status": "queued",  # 初始状态为排队中
                    "collection_type": plan['collection_type'],
                    "collection_method": "netconf",
                    "vendor": plan['summary_plan_vendor'],
                    "device_type": plan['summary_plan_device_type'],
                    "execute_time": execute_time,  # 关联主采集方案的执行时间
                    "created_at": datetime.now().isoformat(),
                    "task_errors": [],
                    "log_time": time.time()
                }
                COLLECTION_SUB_PLAN.insert_one(task_record)
                logger.info(f"NETCONF任务记录已创建: task_id={task_id}, device_ip={manage_ip}, plan={plan['name']}")

                return {
                    "success": True, 
                    "result": netconf_result,
                    "task_id": task_id
                }
            else:
                error_msg = netconf_result.get("error", "NETCONF采集失败") if netconf_result else "NETCONF采集失败：接口调用失败"
                logger.error(f"NETCONF采集失败: device_ip={manage_ip}, error={error_msg}")
                return {"success": False, "error": error_msg, "result": netconf_result}

        except Exception as e:
            error_msg = f"NETCONF采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan['name']}, 设备={manage_ip}")
            return {"success": False, "error": error_msg}

    @staticmethod
    def insert_parent_plan_data(plan, device_info, sub_plans_count=0):
        """
        在执行采集之前插入主采集方案记录
        
        :param plan: 子采集方案字典（包含父方案信息）
        :param device_info: 设备信息字典
        :param sub_plans_count: 子采集方案数量
        :return: 插入结果
        """
        try:
            device_ip = device_info.get('manage_ip')
            summary_plan_id = plan.get('summary_plan')
            execute_time = device_info.get("execute_time")
            
            # 直接插入新的父任务记录，保留历史采集记录
            task_record = {
                "summary_plan_id": summary_plan_id,
                "summary_plan_name": plan.get('summary_plan_name', ''),
                "idc_name": device_info.get("idc__name", ''),
                "device_name": device_info.get("name", ''),
                "device_ip": device_ip,
                "soft_version": device_info.get("soft_version"),
                "vendor": device_info.get('vendor__alias', ''),
                "vendor_name": device_info.get('vendor__name', ''),
                "task_status": "success",  # 初始状态设置为成功，等后面webhook进行回调
                "device_type": plan.get('summary_plan_device_type', ''),
                "execute_node": device_info.get("execute_node"),
                "sub_plans_count": sub_plans_count,  # 子方案数量
                "execute_time": execute_time,
                "log_time": time.time(),  # 用于排序和查询
            }

            # 主采集方案记录
            COLLECTION_PLAN.insert_one(task_record)
            logger.info(f"主采集方案记录已创建: device_ip={device_ip}, summary_plan_id={summary_plan_id}, "
                      f"sub_plans_count={sub_plans_count}, execute_time={execute_time}")
            
            return {
                "success": True,
                "action": "inserted"
            }

        except Exception as e:
            error_msg = f"插入主采集方案记录失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    

class FieldMappingDriver:

    # 将json数据的key 路径解析出来，返回列表
    def collect_keys_with_path(self, data, path='', keys_list=None):
        if keys_list is None:
            keys_list = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                self.collect_keys_with_path(value, new_path, keys_list)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                new_path = f"{path}[*]"
                self.collect_keys_with_path(item, new_path, keys_list)
        else:
            keys_list.append({'label': path, 'value': path})
        return keys_list

    # 解析根节点
    def collect_keys_with_list_key(self, data, path='', keys_list=None):
        if keys_list is None:
            keys_list = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    new_path = f"{path}.{key}" if path else key
                    keys_list.append({'label': new_path, 'value': new_path})
        return keys_list
