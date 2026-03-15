# -*- coding: utf-8 -*-
"""
设备采集服务类（整合版）
合并自 services.py（旧版南向驱动方式）和 services_new.py（本地直连方式）。
services.py 已成为此文件的兼容性转发层，请使用本文件。
"""
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from apps.asset.models import NetworkDevice
from apps.device_api.fields_mapping import DEFAULT_COLLECTION_TYPES
from apps.device_api.models import DeviceSubCollectionPlan, NetconfXMLTemplate
from apps.device_api import COLLECTION_RESULTS_DB, COLLECTION_PLAN, COLLECTION_SUB_PLAN
from apps.device_api.connection_manager import DeviceConnectionManager
from apps.device_api.models_api import resolve_raw_data, save_local_collection_result, inject_metadata

logger = logging.getLogger(__name__)


class DeviceCollectionService:
    """设备采集服务类（新版本）"""

    @staticmethod
    def _build_sub_plan_name(summary_plan_name: str, collection_type: str) -> str:
        """为默认子方案生成全局唯一且长度受控的名称。"""
        name_max_len = DeviceSubCollectionPlan._meta.get_field("name").max_length or 50
        suffix = f"-{collection_type}"
        max_parent_len = max(1, name_max_len - len(suffix))
        parent_part = summary_plan_name[:max_parent_len]
        candidate = f"{parent_part}{suffix}"

        if not DeviceSubCollectionPlan.objects.filter(name=candidate).exists():
            return candidate

        for index in range(1, 1000):
            reserve = len(f"-{index}")
            truncated_parent = parent_part[: max(1, max_parent_len - reserve)]
            candidate = f"{truncated_parent}-{index}{suffix}"[:name_max_len]
            if not DeviceSubCollectionPlan.objects.filter(name=candidate).exists():
                return candidate

        raise ValueError(f"无法为 collection_type={collection_type} 生成唯一子方案名称")

    @staticmethod
    def ensure_default_sub_plans(summary_plan) -> Dict[str, Any]:
        """为父方案补齐默认 collection_type 对应的子方案。"""
        existing_types = set(
            summary_plan.collect_plans.values_list("collection_type", flat=True)
        )
        created_types = []

        for collection_type in DEFAULT_COLLECTION_TYPES:
            if collection_type in existing_types:
                continue

            DeviceSubCollectionPlan.objects.create(
                summary_plan=summary_plan,
                name=DeviceCollectionService._build_sub_plan_name(
                    summary_plan.name, collection_type
                ),
                collection_type=collection_type,
                description="",
            )
            existing_types.add(collection_type)
            created_types.append(collection_type)

        return {
            "created_count": len(created_types),
            "created_types": created_types,
            "total_types": len(DEFAULT_COLLECTION_TYPES),
        }

    @staticmethod
    def get_xml_templates_by_plan(plan_id: int) -> List[NetconfXMLTemplate]:
        """获取采集方案的XML模板"""
        queryset = NetconfXMLTemplate.objects.filter(
            collection_plan_id=plan_id
        )
        return queryset

    @staticmethod
    def collect_with_connection_manager(plan: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用连接管理器执行采集（支持所有采集方式）
        确保单设备只建立一次连接

        Args:
            plan: 子采集方案字典
            device_info: 设备信息字典

        Returns:
            采集结果字典
        """
        manage_ip = device_info.get('manage_ip')
        execute_time = device_info.get('execute_time', datetime.now().isoformat())
        
        logger.info(f"开始执行采集: 方案={plan.get('name')}, 设备={manage_ip}")

        results = {
            'netmiko': None,
            'netconf': None,
            'snmp': None,
            'restconf': None,
            'telemetry': None,
        }

        # 使用连接管理器，确保单设备只建立一次连接
        try:
            with DeviceConnectionManager(manage_ip, device_info) as conn_mgr:
                # 按采集方式分组执行
                if plan.get('netmiko_enabled') and device_info.get('ssh_enable'):
                    try:
                        logger.info(f"执行Netmiko采集: {manage_ip}")
                        command = plan.get('netmiko_method', '')
                        textfsm_template = plan.get('textfsm_template')
                        
                        result = conn_mgr.execute_netmiko_command(
                            command=command,
                            use_textfsm=True,
                            textfsm_template=textfsm_template
                        )
                        
                        # 处理采集结果
                        processed_result = DeviceCollectionService._process_collection_result(
                            plan=plan,
                            device_info=device_info,
                            raw_result=result,
                            collection_method='netmiko',
                            execute_time=execute_time
                        )
                        
                        results['netmiko'] = processed_result
                        logger.info(f"Netmiko采集完成: {manage_ip}")
                    except Exception as e:
                        logger.error(f"Netmiko采集异常: {manage_ip}, {str(e)}", exc_info=True)
                        results['netmiko'] = {'success': False, 'error': str(e)}

                if plan.get('netconf_enabled') and device_info.get('netconf_enable'):
                    try:
                        logger.info(f"执行NETCONF采集: {manage_ip}")
                        xml_templates = plan.get('xml_templates', [])
                        if xml_templates and len(xml_templates) > 0:
                            selected_template = xml_templates[0]
                            xml_template = selected_template.get('xml_template', '')
                            collect_method = selected_template.get('collect_method', 'get')
                            
                            if collect_method == 'get':
                                result = conn_mgr.execute_netconf_get(xml_template)
                            elif collect_method == 'get_config':
                                result = conn_mgr.execute_netconf_get_config(xml_template)
                            else:
                                # RPC方法
                                result = conn_mgr.execute_netconf_get(xml_template)
                            
                            # 处理采集结果
                            processed_result = DeviceCollectionService._process_collection_result(
                                plan=plan,
                                device_info=device_info,
                                raw_result=result,
                                collection_method='netconf',
                                execute_time=execute_time
                            )
                            
                            results['netconf'] = processed_result
                            logger.info(f"NETCONF采集完成: {manage_ip}")
                        else:
                            logger.warning(f"NETCONF采集跳过: {manage_ip} (未配置XML模板)")
                    except Exception as e:
                        logger.error(f"NETCONF采集异常: {manage_ip}, {str(e)}", exc_info=True)
                        results['netconf'] = {'success': False, 'error': str(e)}

                if plan.get('snmp_enabled'):
                    try:
                        logger.info(f"执行SNMP采集: {manage_ip}")
                        oids = plan.get('snmp_oids', [])
                        if oids:
                            result = conn_mgr.execute_snmp_get(oids)
                            
                            # 处理采集结果
                            processed_result = DeviceCollectionService._process_collection_result(
                                plan=plan,
                                device_info=device_info,
                                raw_result=result,
                                collection_method='snmp',
                                execute_time=execute_time
                            )
                            
                            results['snmp'] = processed_result
                            logger.info(f"SNMP采集完成: {manage_ip}")
                        else:
                            logger.warning(f"SNMP采集跳过: {manage_ip} (未配置OID)")
                    except Exception as e:
                        logger.error(f"SNMP采集异常: {manage_ip}, {str(e)}", exc_info=True)
                        results['snmp'] = {'success': False, 'error': str(e)}

                if plan.get('restconf_enabled'):
                    try:
                        logger.info(f"执行RESTCONF采集: {manage_ip}")
                        endpoint = plan.get('restconf_endpoint', '')
                        if endpoint:
                            result = conn_mgr.execute_restconf_get(endpoint)
                            
                            # 处理采集结果
                            processed_result = DeviceCollectionService._process_collection_result(
                                plan=plan,
                                device_info=device_info,
                                raw_result=result,
                                collection_method='restconf',
                                execute_time=execute_time
                            )
                            
                            results['restconf'] = processed_result
                            logger.info(f"RESTCONF采集完成: {manage_ip}")
                        else:
                            logger.warning(f"RESTCONF采集跳过: {manage_ip} (未配置端点)")
                    except Exception as e:
                        logger.error(f"RESTCONF采集异常: {manage_ip}, {str(e)}", exc_info=True)
                        results['restconf'] = {'success': False, 'error': str(e)}

                if plan.get('telemetry_enabled'):
                    try:
                        logger.info(f"执行Telemetry采集: {manage_ip}")
                        subscription_path = plan.get('telemetry_subscription_path', '')
                        sampling_interval = plan.get('telemetry_sampling_interval', 10)
                        if subscription_path:
                            result = conn_mgr.execute_telemetry_subscribe(
                                subscription_path=subscription_path,
                                sampling_interval=sampling_interval
                            )
                            
                            # 处理采集结果
                            processed_result = DeviceCollectionService._process_collection_result(
                                plan=plan,
                                device_info=device_info,
                                raw_result=result,
                                collection_method='telemetry',
                                execute_time=execute_time
                            )
                            
                            results['telemetry'] = processed_result
                            logger.info(f"Telemetry采集完成: {manage_ip}")
                        else:
                            logger.warning(f"Telemetry采集跳过: {manage_ip} (未配置订阅路径)")
                    except Exception as e:
                        logger.error(f"Telemetry采集异常: {manage_ip}, {str(e)}", exc_info=True)
                        results['telemetry'] = {'success': False, 'error': str(e)}

        except Exception as e:
            logger.error(f"连接管理器异常: {manage_ip}, {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f"连接管理器异常: {str(e)}",
                'results': results
            }

        # 检查是否有任何采集成功
        success_methods = [method for method, result in results.items() 
                          if result and result.get('success')]
        
        if not success_methods:
            error_msg = "所有可用的采集方式都失败了"
            logger.error(f"{error_msg}: 设备={manage_ip}")
            return {
                'success': False,
                'error': error_msg,
                'results': results
            }

        logger.info(f"采集完成: {manage_ip}, 成功方式: {', '.join(success_methods)}")
        return {
            'success': True,
            'results': results,
            'success_methods': success_methods
        }

    @staticmethod
    def _process_collection_result(
        plan: Dict[str, Any],
        device_info: Dict[str, Any],
        raw_result: Any,
        collection_method: str,
        execute_time: str
    ) -> Dict[str, Any]:
        """
        处理采集结果，调用数据处理流程并保存到MongoDB

        Args:
            plan: 子采集方案字典
            device_info: 设备信息字典
            raw_result: 原始采集结果
            collection_method: 采集方式
            execute_time: 执行时间

        Returns:
            处理结果字典
        """
        try:
            manage_ip = device_info.get('manage_ip')
            
            # 调用数据处理流程
            # 这里需要将 plan 字典转换为模型对象，或者直接传递字典
            # 为了简化，我们直接调用 resolve_raw_data 函数
            from apps.device_api.models_api import resolve_raw_data
            
            # 构建 plan 对象（简化版，只包含必要字段）
            plan_obj = type('Plan', (), {
                'id': plan.get('id'),
                'name': plan.get('name'),
                'collection_type': plan.get('collection_type'),
                'summary_plan': type('SummaryPlan', (), {
                    'vendor': plan.get('summary_plan_vendor'),
                    'device_type': plan.get('summary_plan_device_type'),
                })(),
                'netmiko_enabled': plan.get('netmiko_enabled', False),
                'netmiko_method': plan.get('netmiko_method', ''),
                'netmiko_path': plan.get('netmiko_path', ''),
                'netmiko_field_mappings': plan.get('netmiko_field_mappings', {}),
                'netconf_enabled': plan.get('netconf_enabled', False),
                'netconf_path': plan.get('netconf_path', ''),
                'netconf_field_mappings': plan.get('netconf_field_mappings', {}),
                'snmp_enabled': plan.get('snmp_enabled', False),
                'snmp_path': plan.get('snmp_path', ''),
                'snmp_field_mappings': plan.get('snmp_field_mappings', {}),
                'restconf_enabled': plan.get('restconf_enabled', False),
                'restconf_path': plan.get('restconf_path', ''),
                'restconf_field_mappings': plan.get('restconf_field_mappings', {}),
                'telemetry_enabled': plan.get('telemetry_enabled', False),
                'telemetry_path': plan.get('telemetry_path', ''),
                'telemetry_field_mappings': plan.get('telemetry_field_mappings', {}),
            })()

            # 调用数据处理函数
            collection_result = {"data": raw_result, "device_ip": manage_ip}
            resolve_status, resolve_error, processed_data = resolve_raw_data(
                plan_obj,
                collection_result,
                collection_method
            )

            if not resolve_status:
                logger.error(f"数据处理失败: {manage_ip}, method={collection_method}, error={resolve_error}")
                return {
                    'success': False,
                    'error': resolve_error
                }

            # 更新子采集任务状态
            task_record = {
                "summary_plan_id": plan.get('summary_plan'),
                "plan_id": plan.get('id'),
                "task_id": f"{manage_ip}_{plan.get('id')}_{collection_method}_{int(time.time())}",
                "device_ip": manage_ip,
                "device_name": device_info.get("name"),
                "idc_name": device_info.get("idc__name"),
                "task_status": "finished",
                "collection_type": plan.get('collection_type'),
                "collection_method": collection_method,
                "vendor": plan.get('summary_plan_vendor'),
                "device_type": plan.get('summary_plan_device_type'),
                "execute_time": execute_time,
                "created_at": datetime.now().isoformat(),
                "task_errors": [],
                "log_time": time.time()
            }
            COLLECTION_SUB_PLAN.insert_one(task_record)

            logger.info(f"采集结果处理完成: {manage_ip}, method={collection_method}, data_count={len(processed_data) if isinstance(processed_data, list) else 1}")

            return {
                'success': True,
                'data_count': len(processed_data) if isinstance(processed_data, list) else 1,
                'task_id': task_record['task_id']
            }

        except Exception as e:
            logger.error(f"处理采集结果异常: {manage_ip}, method={collection_method}, {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def insert_parent_plan_data(plan: Dict[str, Any], device_info: Dict[str, Any], sub_plans_count: int = 0) -> Dict[str, Any]:
        """
        在执行采集之前插入主采集方案记录

        Args:
            plan: 子采集方案字典（包含父方案信息）
            device_info: 设备信息字典
            sub_plans_count: 子采集方案数量

        Returns:
            插入结果
        """
        try:
            device_ip = device_info.get('manage_ip')
            summary_plan_id = plan.get('summary_plan')
            execute_time = device_info.get("execute_time", datetime.now().isoformat())

            # 直接插入新的父任务记录
            task_record = {
                "summary_plan_id": summary_plan_id,
                "summary_plan_name": plan.get('summary_plan_name', ''),
                "idc_name": device_info.get("idc__name", ''),
                "device_name": device_info.get("name", ''),
                "device_ip": device_ip,
                "soft_version": device_info.get("soft_version"),
                "vendor": device_info.get('vendor__alias', ''),
                "vendor_name": device_info.get('vendor__name', ''),
                "task_status": "success",  # 初始状态设置为成功
                "device_type": plan.get('summary_plan_device_type', ''),
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

    # ── 以下方法迁移自 services.py（本地直连采集路径）──────────────────────────

    @staticmethod
    def _build_device_info_for_local(device) -> Dict[str, Any]:
        """从设备 ORM 对象构建 DeviceConnectionManager 所需的 device_info 字典（本地执行用）"""
        device_info = {
            "manage_ip": device.manage_ip,
            "name": getattr(device, "name", ""),
            "idc__name": device.idc.name if device.idc else "",
            "vendor__alias": device.vendor.alias if device.vendor else "Huawei",
            "execute_time": datetime.now().isoformat(),
            "ssh_enable": bool(hasattr(device, "ssh_account") and device.ssh_account),
            "netconf_enable": bool(hasattr(device, "netconf_account") and device.netconf_account),
            "snmp_version": getattr(device, "snmp_version", "v2c"),
            "snmp_community": getattr(device, "snmp_community", ""),
            "snmp_port": getattr(device, "snmp_port", 161),
            "restconf_config": {},
            "telemetry_config": {},
            "ssh": None,
            "netconf": None,
        }
        if hasattr(device, "ssh_account") and device.ssh_account:
            device_info["ssh"] = {
                "username": device.ssh_account.username,
                "password": device.ssh_account.decode_password,
                "port": getattr(device.ssh_account, "port", None) or 22,
            }
        if hasattr(device, "netconf_account") and device.netconf_account:
            device_info["netconf"] = {
                "username": device.netconf_account.username,
                "password": device.netconf_account.decode_password,
                "port": getattr(device.netconf_account, "port", None) or 830,
            }
        return device_info

    @staticmethod
    def _build_plan_payload_for_local(plan) -> Dict[str, Any]:
        xml_templates = []
        if hasattr(plan, "xml_templates"):
            xml_templates = [
                {
                    "collect_method": template.collect_method,
                    "xml_template": template.xml_template,
                    "description": template.description or "",
                }
                for template in plan.xml_templates.all()
            ]

        return {
            "id": plan.id,
            "summary_plan": plan.summary_plan_id,
            "summary_plan_name": getattr(plan.summary_plan, "name", ""),
            "summary_plan_vendor": getattr(plan.summary_plan, "vendor", ""),
            "summary_plan_device_type": getattr(plan.summary_plan, "device_type", ""),
            "name": plan.name,
            "collection_type": plan.collection_type,
            "netmiko_enabled": plan.netmiko_enabled,
            "netmiko_method": plan.netmiko_method,
            "netmiko_path": plan.netmiko_path,
            "netmiko_field_mappings": plan.netmiko_field_mappings or {},
            "netconf_enabled": plan.netconf_enabled,
            "netconf_path": plan.netconf_path,
            "netconf_field_mappings": plan.netconf_field_mappings or {},
            "snmp_enabled": plan.snmp_enabled,
            "snmp_oids": plan.snmp_oids or [],
            "snmp_path": plan.snmp_path,
            "snmp_field_mappings": plan.snmp_field_mappings or {},
            "restconf_enabled": plan.restconf_enabled,
            "restconf_endpoint": plan.restconf_endpoint,
            "restconf_method": plan.restconf_method,
            "restconf_path": plan.restconf_path,
            "restconf_field_mappings": plan.restconf_field_mappings or {},
            "telemetry_enabled": plan.telemetry_enabled,
            "telemetry_subscription_path": plan.telemetry_subscription_path,
            "telemetry_sampling_interval": plan.telemetry_sampling_interval,
            "telemetry_data_format": plan.telemetry_data_format,
            "telemetry_path": plan.telemetry_path,
            "telemetry_field_mappings": plan.telemetry_field_mappings or {},
            "textfsm_template": plan.textfsm_template,
            "xml_templates": xml_templates,
        }

    @staticmethod
    def _update_device_name_from_prompt(conn_mgr, device, device_info: Dict[str, Any]) -> None:
        """从 Netmiko 连接的命令提示符中提取设备名称并回填 NetworkDevice.name（逻辑参考 automation BaseConnection）"""
        try:
            conn = conn_mgr.get_netmiko_connection()
            prompt = conn.find_prompt()
            if not prompt:
                return
            vendor_alias = device_info.get("vendor__alias", "Huawei")
            current_name = getattr(device, "name", "") or ""
            new_name = None
            if vendor_alias in ("H3C", "Huawei"):
                match = re.search(r"(<\S+>)", prompt)
                if match:
                    new_name = match.group(1)[1:-1]
            elif vendor_alias in ("Hillstone", "Ruijie", "centec", "Maipu", "Mellanox", "ZTE"):
                new_name = (prompt[:-1] or "").strip()
            if new_name and new_name != current_name:
                NetworkDevice.objects.filter(manage_ip=device.manage_ip).update(name=new_name)
                logger.info(f"本地采集回填设备名称: {device.manage_ip} -> name={new_name}")
        except Exception as e:
            logger.debug("从 prompt 回填设备名称跳过: %s", e)

    @staticmethod
    def execute_both_collection_local(plan, device) -> Dict[str, Any]:
        """使用程序自身连接执行已启用的采集方式（不走南向驱动）。"""
        try:
            logger.info(
                f"开始执行本地采集: 方案={plan.name}, 设备={device.manage_ip}"
            )
            plan_payload = DeviceCollectionService._build_plan_payload_for_local(plan)
            device_info = DeviceCollectionService._build_device_info_for_local(device)
            result = DeviceCollectionService.collect_with_connection_manager(plan_payload, device_info)
            method_results = result.get("results", {})
            response = {
                "success": result.get("success", False),
                "netconf_result": method_results.get("netconf"),
                "netmiko_result": method_results.get("netmiko"),
                "snmp_result": method_results.get("snmp"),
                "restconf_result": method_results.get("restconf"),
                "telemetry_result": method_results.get("telemetry"),
            }

            if result.get("success"):
                response["message"] = "; ".join(
                    [f"{method.upper()} 采集成功" for method in result.get("success_methods", [])]
                )
            else:
                response["error"] = result.get("error", "所有可用的采集方式均失败")

            return response
        except Exception as e:
            logger.error(
                f"本地采集异常: 方案={plan.name}, 设备={getattr(device, 'manage_ip', '')}, {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "netconf_result": None,
                "netmiko_result": None,
                "snmp_result": None,
                "restconf_result": None,
                "telemetry_result": None,
                "error": str(e),
            }

    @staticmethod
    def execute_both_collection(plan, device, south_driver):
        """同时执行 NETCONF 和 Netmiko 采集（走南向驱动，不保存结果）"""
        try:
            # 延迟导入，避免在不需要南向驱动时引入依赖
            from service_mesh import south_driver_runner
            from confload.confload import config

            logger.info(f"开始执行双重采集: 方案={plan.name}, 设备={device.manage_ip}")
            netconf_result, netmiko_result = None, None
            netconf_success, netmiko_success = False, False

            if plan.netmiko_enabled and hasattr(device, "ssh_account") and device.ssh_account:
                logger.info(f"开始执行Netmiko采集: {device.manage_ip}")
                netmiko_result = DeviceCollectionService._execute_netmiko_south(
                    plan, device, south_driver, south_driver_runner, config
                )
                if netmiko_result.get("success"):
                    netmiko_success = True

            if plan.netconf_enabled and hasattr(device, "netconf_account") and device.netconf_account:
                logger.info(f"开始执行NETCONF采集: {device.manage_ip}")
                netconf_result = DeviceCollectionService._execute_netconf_south(
                    plan, device, south_driver, south_driver_runner, config
                )
                if netconf_result.get("success"):
                    netconf_success = True

            if not netconf_success and not netmiko_success:
                return {
                    "success": False,
                    "netconf_result": netconf_result,
                    "netmiko_result": netmiko_result,
                    "error": "所有可用的采集方式都失败了",
                }
            success_message = []
            if netconf_success:
                success_message.append("NETCONF采集成功")
            if netmiko_success:
                success_message.append("Netmiko采集成功")
            return {
                "success": True,
                "netconf_result": netconf_result,
                "netmiko_result": netmiko_result,
                "message": "; ".join(success_message),
            }
        except Exception as e:
            logger.error(
                f"双重采集异常: 方案={plan.name}, 设备={device.manage_ip}", exc_info=True
            )
            return {
                "success": False,
                "netconf_result": None,
                "netmiko_result": None,
                "error": str(e),
            }

    @staticmethod
    def _execute_netmiko_south(plan, device, south_driver, south_driver_runner, config):
        """南向驱动 Netmiko 采集（内部方法）"""
        try:
            from apps.device_api.common import device_type_map
            command = plan.get_netmiko_method()
            account = device.ssh_account
            vendor_alias = device.vendor.alias if device.vendor else "Huawei"
            device_type = device_type_map.get(vendor_alias, "huawei")
            host_info = {"host": south_driver, "port": int(config.south_http_port)}
            netpalm_info = {
                "library": "netmiko",
                "connection_args": {
                    "device_type": device_type, "host": device.manage_ip,
                    "username": account.username, "password": account.decode_password,
                    "timeout": 5, "session_timeout": 20,
                },
                "command": command,
                "args": {"use_textfsm": True},
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "plan_id": plan.id, "device_ip": device.manage_ip,
                        "device_name": device.name, "idc_name": device.idc.name,
                        "vendor_alias": device.vendor.alias,
                        "collection_method": "netmiko",
                        "collection_type": plan.collection_type, **host_info,
                    },
                },
                "queue_strategy": "fifo",
            }
            if plan.textfsm_template:
                netpalm_info["args"]["textfsm_template"] = plan.textfsm_template
            return south_driver_runner.get_device_config(
                url_prefix="/getconfig", host_info=host_info, netpalm_info=netpalm_info
            )
        except Exception as e:
            logger.error(f"南向驱动 Netmiko 采集失败: {device.manage_ip}, {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _execute_netconf_south(plan, device, south_driver, south_driver_runner, config):
        """南向驱动 NETCONF 采集（内部方法）"""
        try:
            account = device.netconf_account
            host_info = {"host": south_driver, "port": int(config.south_http_port)}
            vendor_alias = device.vendor.alias if device.vendor else "Default"
            netconf_device_type_map = {
                "H3C": "h3c", "Huawei": "huaweiyang", "Cisco": "nexus", "Default": "default",
            }
            device_type = netconf_device_type_map.get(vendor_alias, "h3c")
            xml_templates = plan.xml_templates.first()
            if not xml_templates:
                return {"status": "failed", "data": {}}
            args_filter = xml_templates.xml_template.strip()
            if "<filter type=" not in args_filter:
                filter_xml = f'<filter type="subtree">{args_filter}</filter>'
            else:
                filter_xml = args_filter
            netpalm_info = {
                "library": "ncclient",
                "connection_args": {
                    "host": device.manage_ip, "username": account.username,
                    "password": account.decode_password, "port": 830,
                    "hostkey_verify": False, "allow_agent": False,
                    "look_for_keys": False, "device_params": {"name": device_type},
                },
                "args": {"filter": filter_xml, "render_json": True},
                "webhook": {
                    "name": "base_platform_webhook",
                    "args": {
                        "plan_id": plan.id, "device_ip": device.manage_ip,
                        "device_name": device.name, "idc_name": device.idc.name,
                        "collection_method": "netconf",
                        "collection_type": plan.collection_type, **host_info,
                    },
                },
                "queue_strategy": "fifo",
            }
            collect_method = xml_templates.collect_method
            if collect_method in ("get", "rpc"):
                netpalm_info["args"][collect_method] = True
                url_prefix = "/getconfig/ncclient/get"
            else:
                netpalm_info["args"]["source"] = "running"
                url_prefix = "/getconfig/ncclient"
            return south_driver_runner.get_device_config(
                url_prefix=url_prefix, host_info=host_info, netpalm_info=netpalm_info
            )
        except Exception as e:
            logger.error(f"南向驱动 NETCONF 采集失败: {device.manage_ip}, {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def insert_data_to_mongodb(data):
        """插入数据到 COLLECTION_RESULTS_DB"""
        try:
            result = COLLECTION_RESULTS_DB.insert_one(data)
            return {
                "success": True,
                "data": {"inserted_id": str(result.inserted_id)},
                "message": "数据插入成功",
                "code": 200,
            }
        except Exception as e:
            logger.error(f"插入数据到MongoDB失败: {str(e)}", exc_info=True)
            return {"success": False, "error": f"数据库操作失败: {str(e)}", "code": 500}


# ── 模块级工具函数 ─────────────────────────────────────────────────────────────


def _strip_netconf_filter_wrapper(xml_str: str) -> str:
    """去掉 NETCONF 模板外层 <filter type="subtree">...</filter>，仅保留子树内容。
    ncclient.get(('subtree', data)) 会自动包一层 filter，若模板已带 filter 会导致双层而 RPCError。"""
    if not xml_str or not xml_str.strip():
        return xml_str
    s = xml_str.strip()
    m = re.match(
        r'^\s*<filter\s+type\s*=\s*["\']subtree["\']\s*>\s*(.*)\s*</filter>\s*$',
        s,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return s


class FieldMappingDriver:
    """JSON 数据字段路径解析驱动，用于辅助配置字段映射。"""

    def collect_keys_with_path(self, data, path="", keys_list=None):
        """递归解析 data，返回所有叶子节点的路径列表（用于字段映射配置）。"""
        if keys_list is None:
            keys_list = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                self.collect_keys_with_path(value, new_path, keys_list)
        elif isinstance(data, list):
            for item in data:
                self.collect_keys_with_path(item, f"{path}[*]", keys_list)
        else:
            keys_list.append({"label": path, "value": path})
        return keys_list

    def collect_keys_with_list_key(self, data, path="", keys_list=None):
        """解析 data 中值为 list 的顶层键（用于确定数组键名）。"""
        if keys_list is None:
            keys_list = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    new_path = f"{path}.{key}" if path else key
                    keys_list.append({"label": new_path, "value": new_path})
        return keys_list
