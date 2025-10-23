import logging
import json
import time
from typing import Dict, List, Any
from django.utils import timezone
from service_mesh import south_driver_runner
from apps.automation.tools.base_connection import device_type_map
from apps.device_api.models import DeviceSubCollectionPlan, NetconfXMLTemplate
from utils.connect_layer.NETCONF.h3c_netconf_db import H3CinfoCollectionDB, H3CSecPathDB
from utils.connect_layer.NETCONF.huawei_netconf_db import HuaweiCollectionDB, HuaweiUSGDB
from apps.device_api import COLLECTION_RESULTS_DB
from confload.confload import config
from bson import ObjectId


logger = logging.getLogger(__name__)


class DeviceCollectionService:
    """设备采集服务类"""

    @staticmethod
    def get_xml_templates_by_plan(plan_id: int) -> List[NetconfXMLTemplate]:
        """获取采集方案的XML模板"""
        queryset = NetconfXMLTemplate.objects.filter(
            collection_plan_id=plan_id,
            is_active=True
        )
        return queryset

    @staticmethod
    def execute_both_collection(plan, device):
        """同时执行NETCONF和Netmiko采集（仅执行采集，不保存结果）"""
        try:
            logger.info(f"开始执行双重采集: 方案={plan.name}, 设备={device.manage_ip}")
            
            netconf_result, netmiko_result = None, None
            netconf_success, netmiko_success = False, False

            # 执行Netmiko采集
            if plan.netmiko_enabled and hasattr(device, 'ssh_account') and device.ssh_account:
                logger.info(f"开始执行Netmiko采集: {device.manage_ip}")
                netmiko_result = DeviceCollectionService.execute_netmiko_collection(plan, device)

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
                netconf_result = DeviceCollectionService.execute_netconf_collection(plan, device)
                
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
    def execute_netmiko_collection(plan, device):
        """执行Netmiko采集执行命令"""
        try:
            # 获取命令列表
            command = plan.get_netmiko_method()
            account = device.ssh_account

            # 获取正确的设备类型
            vendor_alias = device.vendor.alias if device.vendor else 'Huawei'
            device_type = device_type_map.get(vendor_alias, 'huawei')

            host_info = {"host": plan.machine_room_ip, "port": int(config.south_http_port)}

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
                        "type": plan.type,
                        **host_info
                    }
                },
                "queue_strategy": "fifo"
            }

            if plan.textfsm_enabled:
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
    def execute_netconf_collection(plan, device):
        """执行NETCONF采集（仅执行采集，不保存结果）"""
        try:
            logger.info(f"开始执行NETCONF采集: 方案={plan.name}, 设备={device.manage_ip}")

            account = device.netconf_account
            host_info = {"host": plan.machine_room_ip, "port": int(config.south_http_port)}

            vendor_alias = device.vendor.alias if device.vendor else 'Cisco'
            
            # NETCONF设备类型映射
            netconf_device_type_map = {
                "H3C": "h3c",
                "Huawei": "huaweiyang",  # 华为设备使用huaweiyang类型
                "Cisco": "nexus"
            }
            device_type = netconf_device_type_map.get(vendor_alias, "h3c")  # 默认使用h3c
                
            # 获取XML模板
            xml_templates = plan.xml_templates.filter(is_active=True)
            if not xml_templates.exists():
                error_msg = "采集方案未配置有效的NETCONF XML模板"
                logger.error(error_msg)

                return {"status": "failed", "data": {}}

            # TODO 这个地方需要后期调整，因为不能永远只拿第一个，要不然后面的就没有意义
            args_filter = xml_templates[0].xml_template
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
                        "type": plan.type,
                        **host_info
                    }
                },
                "queue_strategy": "fifo",
            }

            netconf_result = south_driver_runner.get_device_config(url_prefix='/getconfig/ncclient/get', host_info=host_info, netpalm_info=netpalm_info)
            logger.info(f"执行CLI采集: {device.manage_ip}")

            return netconf_result

        except Exception as e:
            error_msg = f"Netmiko采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            return {"status": "failed", "data": {}}

    @staticmethod
    def update_field_mappings(plan, field_mappings_type, field_mappings):
        """更新字段映射"""
        try:
            if field_mappings_type == 'netconf':
                plan.netconf_field_mappings = json.dumps(field_mappings, ensure_ascii=False)
            elif field_mappings_type == 'netmiko':
                plan.netmiko_field_mappings = json.dumps(field_mappings, ensure_ascii=False)

            plan.save()
            return {
                'success': True,
                'plan': plan
            }
        except Exception as e:
            logger.error(f"更新字段映射失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def execute_data_processor(result_id: str) -> Dict[str, Any]:
        """执行数据处理函数，将采集结果转换为标准数据格式
        
        Args:
            result_id: MongoDB结果ID
            
        Returns:
            Dict: 处理结果
        """
        try:
            # 验证ObjectId格式
            try:
                object_id = ObjectId(result_id)
            except Exception as e:
                logger.error(f'{e}')
                return {
                    'success': False,
                    'error': '无效的结果ID格式',
                    'code': 400
                }

            # 查询MongoDB获取采集结果
            collection_results = COLLECTION_RESULTS_DB.find({'_id': object_id})

            if not collection_results:
                return {
                    'success': False,
                    'error': '采集结果不存在',
                    'code': 404
                }

            # 获取第一个匹配的文档
            collection_result = collection_results[0]
            plan_id = collection_result.get('plan_id')

            # 根据plan_id获取采集方案对象
            try:
                plan = DeviceSubCollectionPlan.objects.get(id=plan_id)
            except DeviceSubCollectionPlan.DoesNotExist:
                return {
                    'success': False,
                    'error': f'采集方案不存在 (ID: {plan_id})',
                    'code': 404
                }
            
            # 检查采集方案是否启用数据处理
            if not plan.data_processor_enabled or not plan.data_processor:
                return {
                    'success': False,
                    'error': '该采集方案未启用数据处理功能',
                    'code': 400
                }

            # 检查是否有原始数据
            raw_data = collection_result.get('raw_data')
            if not raw_data:
                return {
                    'success': False,
                    'error': '采集结果没有原始数据，无法处理',
                    'code': 400
                }
            
            # 执行数据处理
            start_time = time.time()
            
            try:
                # 如果原始数据是字符串，尝试解析为JSON
                if isinstance(raw_data, str):
                    try:
                        raw_data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，直接使用字符串
                        pass
                
                # 调用采集方案的数据处理方法
                processed_data = plan.process_netconf_data(raw_data)
                
                # 计算处理时间
                processing_time = time.time() - start_time
                
                # 更新MongoDB中的采集结果
                update_data = {
                    'processed_data': processed_data,
                    'status': 'processed',
                    'processing_time': round(processing_time, 3),
                    'processed_at': timezone.now().isoformat()
                }
                
                # 如果处理失败，记录错误信息
                if processed_data is None or (isinstance(processed_data, str) and 'error' in processed_data.lower()):
                    update_data['status'] = 'processing_failed'
                    update_data['error_message'] = str(processed_data)
                
                # 更新MongoDB文档
                COLLECTION_RESULTS_DB.update_one(
                    {'_id': object_id},
                    {'$set': update_data}
                )
                
                return {
                    'success': True,
                    'data': {
                        'processing_time': round(processing_time, 3),
                        'raw_data': raw_data,
                        'processed_data': processed_data,
                        'result_id': str(object_id),
                        'status': update_data['status'],
                        'plan_name': plan.name,
                        'device_ip': collection_result.get('device_ip')
                    }
                }
                
            except Exception as e:
                # 计算处理时间
                processing_time = time.time() - start_time
                
                # 更新状态为异常
                error_data = {
                    'status': 'processing_failed',
                    'error_message': f"数据处理执行失败: {str(e)}",
                    'processing_time': round(processing_time, 3),
                    'processed_at': timezone.now().isoformat()
                }
                
                # 更新MongoDB文档
                COLLECTION_RESULTS_DB.update_one(
                    {'_id': object_id},
                    {'$set': error_data}
                )
                
                return {
                    'success': False,
                    'error': str(e),
                    'data': {
                        'processing_time': round(processing_time, 3),
                        'result_id': str(object_id),
                        'status': 'processing_failed',
                        'plan_name': plan.name,
                        'device_ip': collection_result.get('device_ip')
                    }
                }
                
        except Exception as e:
            logger.error(f"执行数据处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 500
            }

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
