import logging
import json
from typing import Dict, List, Any
from django.db import transaction
from django.utils import timezone
from utils.connect_layer.auto_main import BatManMain
from apps.device_api.textfsm_service import TextFSMService

from apps.automation.tools.base_connection import device_type_map
from apps.device_api.models import DeviceSummaryPlans, DeviceCollectionPlan, NetconfXMLTemplate
from utils.db.mongo_ops import MongoOps
from utils.connect_layer.NETCONF.h3c_netconf_db import H3CinfoCollectionDB, H3CSecPathDB
from utils.connect_layer.NETCONF.huawei_netconf_db import HuaweiCollectionDB, HuaweiUSGDB
from apps.device_api import COLLECTION_RESULTS_DB, COLLECTION_LOG_DB
from bson import ObjectId
import time

logger = logging.getLogger(__name__)


class DeviceCollectionService:
    """设备采集服务类"""

    @staticmethod
    def log_collection_execution(plan, device, collection_type, status, message, details=None):
        """记录采集执行日志到MongoDB
        
        Args:
            plan: 采集方案对象
            device: 设备对象
            collection_type: 采集类型 (netconf/netmiko)
            status: 执行状态 (success/failed)
            message: 执行消息
            details: 详细信息
        """
        try:
            # 获取方法名称，处理可能为None的情况
            if collection_type == 'netconf':
                method_name = plan.get_netconf_method() or 'unknown'
            else:
                method_name = plan.get_netmiko_method() or 'unknown'
            
            log_entry = {
                'summary_plan_id': plan.summary_plan.id,
                'summary_plan_name': plan.summary_plan.name,
                'plan_id': plan.id,
                'plan_name': plan.name,
                'device_ip': device.manage_ip,
                'device_name': device.name,
                'collection_type': collection_type,
                'method_name': method_name,
                'status': status,
                'message': message,
                'details': details or {},
                'executed_at': timezone.now().isoformat(),
                'timestamp': timezone.now()
            }
            
            COLLECTION_LOG_DB.insert_one(log_entry)
            logger.info(f"采集日志已记录: {device.manage_ip} - {plan.name} - {collection_type} - {status}")
            
        except Exception as e:
            logger.error(f"记录采集日志失败: {str(e)}")

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
        """实时同步执行采集任务"""
        try:
            netconf_result, netmiko_result = None, None
            netconf_success, netmiko_success = False, False

            # 执行NETCONF采集
            if plan.netconf_enabled and hasattr(device, 'netconf_account') and device.netconf_account:
                netconf_success, netconf_message = DeviceCollectionService.execute_netconf_collection(
                    plan, device
                )
                if netconf_success:
                    netconf_result = netconf_message
                    logger.info(f"NETCONF采集成功: {device.manage_ip}")
                else:
                    logger.warning(f"NETCONF采集失败: {device.manage_ip} - {netconf_message}")

            # 执行Netmiko采集
            if plan.netmiko_enabled and hasattr(device, 'ssh_account') and device.ssh_account:
                netmiko_success, netmiko_message = DeviceCollectionService.execute_netmiko_collection(
                    plan, device
                )
                if netmiko_success:
                    netmiko_result = netmiko_message
                    logger.info(f"Netmiko采集成功: {device.manage_ip}")
                else:
                    logger.warning(f"Netmiko采集失败: {device.manage_ip} - {netmiko_message}")

            # 检查是否有任何采集成功
            if not netconf_success and not netmiko_success:
                error_msg = "所有可用的采集方式都失败了"
                logger.error(f"{error_msg}: 设备={device.manage_ip}")
                return {
                    'success': False,
                    'netconf_result': None,
                    'netmiko_result': None,
                    'error': error_msg
                }

            # 至少有一种采集方式成功
            success_message = []
            if netconf_success:
                success_message.append("NETCONF采集成功")
            if netmiko_success:
                success_message.append("Netmiko采集成功")

            return {
                'success': True,
                'netconf_result': netconf_result,
                'netmiko_result': netmiko_result,
                'message': "; ".join(success_message)
            }

        except Exception as e:
            error_msg = f"同步采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            return {
                'success': False,
                'netconf_result': None,
                'netmiko_result': None,
                'error': error_msg
            }

    @staticmethod
    def execute_netmiko_collection_only(plan, device):
        """执行Netmiko采集（仅执行命令，不保存结果）"""
        try:
            # 获取命令列表
            command = plan.get_netmiko_method()

            # 执行CLI命令采集
            netmiko_result = DeviceCollectionService.execute_cli_collection(
                device, device.ssh_account, command
            )

            # 检查命令执行是否成功
            if not netmiko_result.get('file_path'):
                error_msg = netmiko_result.get('error', '命令执行失败') 
                logger.error(f"Netmiko命令执行失败: {device.manage_ip} - {error_msg}")
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netmiko', 'failed', error_msg,
                    {'error_type': 'command_execution_failed', 'error_details': error_msg}
                )
                
                return False, error_msg, None

            # 如果配置了TextFSM模板，进行解析
            if netmiko_result.get('file_path'):
                try:
                    processed_data = DeviceCollectionService.parse_textfsm_result(plan, device, netmiko_result)
                    logger.info(f"TextFSM解析成功: {device.manage_ip}")
                except Exception as e:
                    # TextFSM解析失败不影响整体采集结果，只是没有结构化数据
                    logger.warning(f"TextFSM解析失败: {device.manage_ip} - {str(e)}")
                    processed_data = None

            logger.info(f"Netmiko采集成功: {device.manage_ip}")

            # 如果有字段映射，应该进行字段映射
            if plan.netmiko_field_mappings and processed_data:
                try:
                    mapped_data = DeviceCollectionService.apply_field_mappings(
                        processed_data, plan.netmiko_field_mappings
                    )
                    logger.info(f"Netmiko字段映射处理成功: {device.manage_ip}")
                    processed_data = mapped_data
                except Exception as e:
                    logger.warning(f"Netmiko字段映射处理失败: {device.manage_ip} - {str(e)}")
                    # 字段映射失败不影响整体采集结果，继续使用原始数据

            # 构建采集结果数据（不保存到MongoDB）
            collection_result = {
                'plan_id': plan.id,
                'plan_name': plan.name,
                'device_ip': device.manage_ip,
                'device_name': device.name,
                'device_type': plan.summary_plan.device_type,
                'vendor': plan.summary_plan.vendor,
                'collection_method': 'netmiko',
                'method_name': command,
                'raw_data': processed_data,
                'processed_data': processed_data,
                'collected_at': timezone.now().isoformat(),
                'status': 'success'
            }
            
            # 记录成功日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netmiko', 'success', "采集成功",
                {'collection_success': True, 'textfsm_parsed': processed_data is not None}
            )
            
            return True, "采集成功", collection_result

        except Exception as e:
            error_msg = f"Netmiko采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 记录异常日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netmiko', 'failed', error_msg,
                {'exception': str(e)}
            )
            
            return False, error_msg, None

    @staticmethod
    def save_collection_result(collection_result: dict):
        """保存采集结果到MongoDB"""
        try:
            # 检查collection_result是否为None
            if collection_result is None:
                error_msg = "采集结果数据为空，无法保存"
                logger.error(error_msg)
                return False, error_msg

            COLLECTION_RESULTS_DB.insert_one(collection_result)
            logger.info(f"采集结果保存到MongoDB成功: {collection_result.get('device_ip', 'unknown')}")
            return True, "保存成功"
        except Exception as mongo_error:
            error_msg = f"保存采集结果到MongoDB失败: {str(mongo_error)}"
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    def execute_netmiko_collection(plan, device):
        """执行Netmiko采集（完整流程：采集+保存）"""
        try:
            # 第一步：执行采集
            ok, message, collection_result = DeviceCollectionService.execute_netmiko_collection_only(plan, device)
            
            if not ok:
                # 采集失败，保存失败记录
                error_result = {
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'device_ip': device.manage_ip,
                    'device_name': device.name,
                    'device_type': plan.summary_plan.device_type,
                    'vendor': plan.summary_plan.vendor,
                    'collection_method': 'netmiko',
                    'method_name': plan.netmiko_method,
                    'raw_data': None,
                    'processed_data': None,
                    'collected_at': timezone.now().isoformat(),
                    'status': 'failed',
                    'error_message': message
                }
                
                # 保存失败结果
                DeviceCollectionService.save_collection_result(error_result)
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netmiko', 'failed', message,
                    {'error_message': message}
                )
                
                return False, message
            
            # 第二步：保存成功结果
            save_ok, save_message = DeviceCollectionService.save_collection_result(collection_result)
            if not save_ok:
                logger.warning(f"采集成功但保存失败: {device.manage_ip} - {save_message}")
                # 即使保存失败，采集本身是成功的
                final_message = f"采集成功，但保存失败: {save_message}"
                
                # 记录部分成功日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netmiko', 'success', final_message,
                    {'collection_success': True, 'save_failed': True, 'save_error': save_message}
                )
                
                return True, final_message
            
            logger.info(f"Netmiko采集完成: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 记录成功日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netmiko', 'success', "采集并保存成功",
                {'collection_success': True, 'save_success': True}
            )
            
            return True, "采集并保存成功"

        except Exception as e:
            error_msg = f"Netmiko采集异常: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 保存异常结果
            error_result = {
                'plan_id': plan.id,
                'plan_name': plan.name,
                'device_ip': device.manage_ip,
                'device_name': device.name,
                'device_type': plan.summary_plan.device_type,
                'vendor': plan.summary_plan.vendor,
                'collection_method': 'netmiko',
                'method_name': plan.netmiko_method,
                'raw_data': None,
                'processed_data': None,
                'collected_at': timezone.now().isoformat(),
                'status': 'failed',
                'error_message': error_msg
            }
            
            DeviceCollectionService.save_collection_result(error_result)
            
            # 记录异常日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netmiko', 'failed', error_msg,
                {'exception': str(e)}
            )
            
            return False, error_msg

    @staticmethod
    def execute_netconf_collection_only(plan, device):
        """执行NETCONF采集（仅执行采集，不保存结果）"""
        try:
            logger.info(f"开始执行NETCONF采集: 方案={plan.name}, 设备={device.manage_ip}")
            method_name = plan.get_netconf_method()

            # 获取NETCONF类
            vendor_alias = device.vendor.alias if device.vendor else ''
            netconf_class = DeviceCollectionService.get_netconf_class(vendor_alias, device)
            if not netconf_class:
                error_msg = f"不支持的厂商: {vendor_alias}"
                logger.error(error_msg)
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'failed', error_msg,
                    {'error_type': 'unsupported_vendor', 'vendor_alias': vendor_alias}
                )
                
                return False, error_msg, None

            # 构建连接参数
            netconf_params = DeviceCollectionService.build_netconf_params(device, device.netconf_account, vendor_alias)

            # 创建连接器实例
            netconf_connector = netconf_class(**netconf_params)

            # 获取XML模板
            xml_templates = plan.xml_templates.filter(is_active=True)
            if not xml_templates.exists():
                error_msg = "采集方案未配置有效的NETCONF XML模板"
                logger.error(error_msg)
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'failed', error_msg,
                    {'error_type': 'no_xml_templates', 'plan_id': plan.id}
                )
                
                return False, error_msg, None

            # 检查NETCONF连接器是否有对应的方法
            if hasattr(netconf_connector, method_name):
                method = getattr(netconf_connector, method_name)

                # 将XML模板列表传递给具体的方法，让方法自己决定如何执行,这样每个厂商的方法可以根据自己的业务逻辑来灵活控制
                method_params = DeviceCollectionService.get_default_method_params(method_name)              # 获取默认参数
                method_params['xml_templates'] = list(xml_templates)
                result = method(**method_params)

                logger.info(f"NETCONF采集成功: {device.manage_ip}, 方法: {method_name}")
                
                # 如果有字段映射，应该进行字段映射
                processed_data = None  # NETCONF数据通常是结构化的
                if plan.netconf_field_mappings and result:
                    try:
                        mapped_data = DeviceCollectionService.apply_field_mappings(
                            result, plan.netconf_field_mappings
                        )
                        logger.info(f"NETCONF字段映射处理成功: {device.manage_ip}")
                        processed_data = mapped_data
                    except Exception as e:
                        logger.warning(f"NETCONF字段映射处理失败: {device.manage_ip} - {str(e)}")
                        # 字段映射失败不影响整体采集结果，继续使用原始数据
                
                # 构建采集结果数据（不保存到MongoDB）
                result_data = {
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'device_ip': device.manage_ip,
                    'device_name': device.name,
                    'device_type': plan.summary_plan.device_type,
                    'vendor': plan.summary_plan.vendor,
                    'collection_method': 'netconf',
                    'method_name': method_name,
                    'raw_data': result,
                    'processed_data': processed_data,
                    'collected_at': timezone.now().isoformat(),
                    'status': 'success'
                }
                
                # 记录成功日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'success', "采集成功",
                    {'collection_success': True, 'method_name': method_name}
                )
                
                return True, "采集成功", result_data
            else:
                logger.warning(f"NETCONF方法不存在: {method_name}")
                error_msg = f"NETCONF方法不存在: {method_name}"
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'failed', error_msg,
                    {'error_type': 'method_not_found', 'method_name': method_name}
                )
                
                return False, error_msg, None
            
        except Exception as e:
            error_msg = f"NETCONF采集失败: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 记录异常日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netconf', 'failed', error_msg,
                {'exception': str(e)}
            )
            
            return False, error_msg, None
        finally:
            # 断开连接 - 所有NETCONF类都使用closed方法
            if hasattr(netconf_connector, 'closed'):
                netconf_connector.closed()

    @staticmethod
    def execute_netconf_collection(plan, device):
        """执行NETCONF采集（完整流程：采集+保存）"""
        try:
            # 第一步：执行采集
            ok, message, collection_result = DeviceCollectionService.execute_netconf_collection_only(plan, device)
            
            if not ok:
                # 采集失败，保存失败记录
                error_result = {
                    'plan_id': plan.id,
                    'plan_name': plan.name,
                    'device_ip': device.manage_ip,
                    'device_name': device.name,
                    'device_type': plan.summary_plan.device_type,
                    'vendor': plan.summary_plan.vendor,
                    'collection_method': 'netconf',
                    'method_name': plan.netconf_method,
                    'raw_data': None,
                    'processed_data': None,
                    'collected_at': timezone.now().isoformat(),
                    'status': 'failed',
                    'error_message': message
                }
                
                # 保存失败结果
                DeviceCollectionService.save_collection_result(error_result)
                
                # 记录失败日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'failed', message,
                    {'error_message': message}
                )
                
                return False, message
            
            # 第二步：保存成功结果
            save_ok, save_message = DeviceCollectionService.save_collection_result(collection_result)
            if not save_ok:
                logger.warning(f"采集成功但保存失败: {device.manage_ip} - {save_message}")
                # 即使保存失败，采集本身是成功的
                final_message = f"采集成功，但保存失败: {save_message}"
                
                # 记录部分成功日志
                DeviceCollectionService.log_collection_execution(
                    plan, device, 'netconf', 'success', final_message,
                    {'collection_success': True, 'save_failed': True, 'save_error': save_message}
                )
                
                return True, final_message
            
            logger.info(f"NETCONF采集完成: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 记录成功日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netconf', 'success', "采集并保存成功",
                {'collection_success': True, 'save_success': True}
            )
            
            return True, "采集并保存成功"

        except Exception as e:
            error_msg = f"NETCONF采集异常: {str(e)}"
            logger.error(f"{error_msg}: 方案={plan.name}, 设备={device.manage_ip}")
            
            # 保存异常结果
            error_result = {
                'plan_id': plan.id,
                'plan_name': plan.name,
                'device_ip': device.manage_ip,
                'device_name': device.name,
                'device_type': plan.summary_plan.device_type,
                'vendor': plan.summary_plan.vendor,
                'collection_method': 'netconf',
                'method_name': plan.netconf_method,
                'raw_data': None,
                'processed_data': None,
                'collected_at': timezone.now().isoformat(),
                'status': 'failed',
                'error_message': error_msg
            }
            
            DeviceCollectionService.save_collection_result(error_result)
            
            # 记录异常日志
            DeviceCollectionService.log_collection_execution(
                plan, device, 'netconf', 'failed', error_msg,
                {'exception': str(e)}
            )
            
            return False, error_msg

    @staticmethod
    def execute_cli_collection(device, account, command):
        """执行CLI采集"""
        logger.info(f"执行CLI采集: {device.manage_ip}, 命令: {command}")

        # 获取正确的设备类型
        vendor_alias = device.vendor.alias if device.vendor else 'Cisco'
        device_type = device_type_map.get(vendor_alias, 'cisco_ios')
        
        # 准备连接参数
        connection_params = {
            'device_type': device_type,
            'ip': device.manage_ip,
            'port': 22,
            'username': account.username,
            'password': account.decode_password,
            'timeout': 200,  # float，连接超时时间，默认为100
        }

        try:
            # 使用静态方法，不需要实例化BatManMain
            file_paths = BatManMain.send_cmds(command, **connection_params)

            cli_results = {
                'command': command,
                'file_path': file_paths[0] if len(file_paths) > 0 else None,
            }
            logger.info(f"命令执行成功: {command}")
            return cli_results
        except Exception as e:
            logger.error(f"命令执行失败: {command}, 错误: {str(e)}")
            cli_results = {
                'command': command,
                'file_path': None,
                'error': str(e)
            }
            
            return cli_results

    @staticmethod
    def get_netconf_class(vendor_alias, device):
        """获取NETCONF类"""
        vendor_class_map = {
            'H3C': {
                'firewall': 'H3CSecPathDB',
                'switch': 'H3CinfoCollectionDB',
                'default': 'H3CinfoCollectionDB'
            },
            'Huawei': {
                'firewall': 'HuaweiUSGDB',
                'switch': 'HuaweiCollectionDB',
                'default': 'HuaweiCollectionDB'
            }
        }

        if vendor_alias not in vendor_class_map:
            logger.warning(f"不支持的厂商: {vendor_alias}")
            return None

        # 根据设备类型选择类
        device_type = 'default'
        if device.category:
            category_name = device.category.name.lower()
            # 更精确的设备类型判断
            if any(keyword in category_name for keyword in ['防火墙', 'firewall', '安全网关', '安全设备']):
                device_type = 'firewall'
            elif any(keyword in category_name for keyword in ['交换机', 'switch', '交换']):
                device_type = 'switch'
            elif any(keyword in category_name for keyword in ['路由器', 'router', '路由']):
                device_type = 'switch'  # 路由器使用switch类型
            elif any(keyword in category_name for keyword in ['服务器', 'server', '主机']):
                device_type = 'switch'  # 服务器使用switch类型

        class_name = vendor_class_map[vendor_alias].get(device_type, 'default')
        logger.info(f"厂商: {vendor_alias}, 设备类型: {device_type}, 选择类: {class_name}")

        # 动态导入类
        try:
            if vendor_alias == 'H3C':

                return H3CSecPathDB if class_name == 'H3CSecPathDB' else H3CinfoCollectionDB
            elif vendor_alias == 'Huawei':

                return HuaweiUSGDB if class_name == 'HuaweiUSGDB' else HuaweiCollectionDB
        except ImportError as e:
            logger.error(f"导入NETCONF类失败: {e}")
            return None

        return None

    @staticmethod
    def build_netconf_params(device, account, vendor_alias):
        """构建NETCONF连接参数"""
        netconf_params = {
            'host': device.manage_ip,
            'user': account.username,
            'password': account.decode_password,
            'timeout': 600,
            'version': 'default'
        }

        # 确定设备类型
        device_type = 'switch'  # 默认类型
        if device.category:
            category_name = device.category.name.lower()
            # 更精确的设备类型判断
            if any(keyword in category_name for keyword in ['防火墙', 'firewall', '安全网关', '安全设备']):
                device_type = 'firewall'
            elif any(keyword in category_name for keyword in ['交换机', 'switch', '交换']):
                device_type = 'switch'
            elif any(keyword in category_name for keyword in ['路由器', 'router', '路由']):
                device_type = 'switch'  # 路由器使用switch类型
            elif any(keyword in category_name for keyword in ['服务器', 'server', '主机']):
                device_type = 'switch'  # 服务器使用switch类型

        # 设置设备类型参数
        netconf_params['device_type'] = device_type

        # 如果是H3C设备，添加device_params
        if vendor_alias == 'H3C':
            netconf_params['device_params'] = 'h3c'

        logger.info(f"构建NETCONF参数: 设备IP={device.manage_ip}, 设备类型={device_type}, 厂商={vendor_alias}")
        return netconf_params

    @staticmethod
    def get_default_method_params(method_name):
        """获取方法的默认参数
        
        Args:
            method_name: 方法名称
            
        Returns:
            dict: 默认参数字典
        """
        # 为不同的方法提供默认参数
        default_params = {
            'get_global_nat_policy': {
                'mode': 'DNAT',
                'name': ''
            },
            'get_sec_policy': {
                'mode': 'basic',
                'detailed': False
            },
            'collection_interface_info': {
                'detailed': False,
                'mode': 'basic'
            },
            'get_ipv4_group': {
                'name': ''
            },
            'get_ipv4_objs': {
                'name': ''
            },
            'get_ipv4_paging': {
                'name': '',
                'map': True
            },
            'get_sec_zone': {
                'name': ''
            },
            'get_server_groups': {
                'name': ''
            },
            'get_ipv4_routes': {
                'type': 'all'
            }
        }
        
        return default_params.get(method_name, {})

    @staticmethod
    def parse_textfsm_result(plan, device, netmiko_result):
        """解析TextFSM结果"""
        try:
            vendor_alias = device.vendor.alias if device.vendor else None
            textfsm_device_type = None

            # 根据厂商和设备类型确定设备类型
            if vendor_alias == 'Huawei':
                if device.category and '防火墙' in device.category.name:
                    textfsm_device_type = 'firewall'
                else:
                    textfsm_device_type = 'switch'

            parsed_result = TextFSMService.parse_cli_results(
                cli_results=netmiko_result,
                vendor=vendor_alias,
                device_type=textfsm_device_type,
                textfsm_template=plan.textfsm_template
            )

            return parsed_result

        except Exception as e:
            logger.error(f"TextFSM解析失败: {device.manage_ip} - {str(e)}")
            return None

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
    def apply_field_mappings(raw_data, field_mappings):
        """应用字段映射 - 从包含数组的字典中提取指定字段

        Args:
            raw_data: 原始数据，通常是包含数组的字典，如 {"alerts": [...]}
            field_mappings: 字段映射配置，格式如：
                {
                    "status": "alerts[*].status",
                    "value": "alerts[*].values",
                    "hostip": "alerts[*].labels.hostip"
                }
        Returns:
            提取后的字段数据数组，格式如 [{"status": "a", "value": "b", "hostip": "c"}, ...]
        """
        if isinstance(raw_data, list):
            raw_data = {"data": raw_data}

        try:
            # 解析字段映射
            if isinstance(field_mappings, str):
                field_mappings = json.loads(field_mappings)

            # 确保raw_data是字典
            if not isinstance(raw_data, dict):
                logger.warning(f"raw_data不是字典，类型: {type(raw_data)}")
                return []

            # 找到第一个通配符路径来确定数组键
            array_key = None
            for field_path in field_mappings.values():
                if '[*]' in field_path:
                    parts = field_path.split('[*]')
                    if parts[0]:
                        array_key = parts[0].rstrip('.')
                        break

            if not array_key or array_key not in raw_data:
                logger.warning(f"未找到数组键: {array_key}")
                return []

            array_data = raw_data[array_key]
            if not isinstance(array_data, list):
                logger.warning(f"键 {array_key} 对应的值不是数组")
                return []

            processed_data = []

            # 遍历数组中的每个元素
            for item in array_data:
                if not isinstance(item, dict):
                    continue

                # 为每个元素创建一个结果对象
                result_item = {}

                # 对每个字段进行映射
                for field_name, field_path in field_mappings.items():
                    if not field_path:
                        continue

                    # 提取通配符后的路径部分
                    if '[*]' in field_path:
                        after_wildcard = field_path.split('[*]')[1].lstrip('.')
                        if after_wildcard:
                            value = DeviceCollectionService.extract_field_value(item, after_wildcard)
                        else:
                            value = item
                    else:
                        value = DeviceCollectionService.extract_field_value(item, field_path)

                    result_item[field_name] = value

                # 将结果添加到数组中
                processed_data.append(result_item)

            return processed_data

        except Exception as e:
            logger.error(f"应用字段映射失败: {str(e)}")
            return []

    @staticmethod
    def extract_field_value(data, field_path):
        """提取字段值，支持点号分隔的路径

        Args:
            data: 要提取数据的对象（通常是字典）
            field_path: 字段路径，支持格式：
                - key1.key2.key3 (普通路径)
                - key1.0.key2 (带索引的路径)

        Returns:
            提取的字段值
        """
        if not field_path:
            return None

        try:
            # 处理普通路径
            keys = field_path.split('.')
            current = data

            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and key.isdigit():
                    index = int(key)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    return None

            return current

        except Exception as e:
            logger.warning(f"提取字段值失败: {str(e)}")
            return None

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
                plan = DeviceCollectionPlan.objects.get(id=plan_id)
            except DeviceCollectionPlan.DoesNotExist:
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
                processed_data = plan.process_collected_data(raw_data)
                
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
