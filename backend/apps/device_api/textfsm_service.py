 #!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from typing import Dict, List, Any
from utils.connect_layer.auto_main import BatManMain
from apps.automation.tools.base_connection import fsm_flag_map

logger = logging.getLogger(__name__)


class TextFSMService:
    """TextFSM解析服务"""
    
    @staticmethod
    def parse_cli_output(file_path: str, platform: str, command: str = None) -> Dict[str, Any]:
        """解析CLI输出数据"""
        try:
            if not file_path or not platform:
                return {
                    'success': False,
                    'error': '缺少必要参数: file_path, platform',
                    'file_path': file_path
                }
            
            # 如果没有提供command，从文件路径中提取
            if not command:
                tmp = file_path.split('/')[-1]
                _cmd = tmp.split('.')[0]
                command = ' '.join(_cmd.split('_'))
            
            # 使用BatManMain.info_fsm方法解析
            parsed_result = BatManMain.info_fsm(path=file_path, fsm_platform=platform)
            
            # 如果解析失败，记录详细信息用于调试
            if not parsed_result:
                logger.warning(f"TextFSM解析返回空结果: platform={platform}, file={file_path}")
            
            return {
                'success': True,
                'parsed_data': parsed_result,
                'platform': platform,
                'command': command,
                'file_path': file_path
            }
            
        except Exception as e:
            logger.error(f"TextFSM解析失败: platform={platform}, file={file_path}, error={str(e)}")
            return {
                'success': False,
                'error': f'解析失败: {str(e)}',
                'platform': platform,
                'file_path': file_path,
                'suggestion': f'建议检查平台模板 {platform} 是否适用于当前设备输出格式'
            }
    
    @staticmethod
    def get_available_platforms() -> List[str]:
        """获取所有可用的平台"""
        # 使用现有的fsm_flag_map
        return list(fsm_flag_map.values())
    
    @staticmethod
    def get_platform_by_vendor(vendor: str, device_type: str = None) -> str:
        """根据厂商和设备类型获取对应的平台"""
        # 基础映射
        platform = fsm_flag_map.get(vendor, 'cisco_ios')
        
        # 特殊处理华为设备
        if vendor == 'Huawei':
            if device_type and 'firewall' in device_type:
                platform = 'huawei_usg'  # 华为防火墙使用特殊模板
            else:
                # 华为交换机使用VRP模板，更适合display interface brief命令
                platform = 'huawei_vrp'  # 华为交换机使用VRP模板
        
        return platform
    
    @staticmethod
    def parse_cli_results(cli_results: dict, vendor: str = None, device_type: str = None, textfsm_template: str = '') -> List[Dict]:
        """解析CLI结果列表"""

        file_path = cli_results.get('file_path', None)
        if not file_path:
            logger.warning("CLI结果中缺少file_path，无法进行TextFSM解析")
            return None
        
        # TextFSM模板选择逻辑
        if textfsm_template and textfsm_template.strip() != '':
            # 如果采集方案指定了TextFSM模板，使用指定的模板
            platform = textfsm_template
            logger.info(f"使用采集方案指定的TextFSM模板: {platform}")
        else:
            # 如果没有指定模板，根据厂商和设备类型自动选择
            platform = TextFSMService.get_platform_by_vendor(vendor, device_type)
            logger.info(f"使用厂商默认TextFSM模板: vendor={vendor}, device_type={device_type}, platform={platform}")

        parse_result = TextFSMService.parse_cli_output(
            file_path=file_path,
            platform=platform
        )

        if parse_result['success']:
            logger.info(f"TextFSM解析成功: platform={platform}, file={file_path}")
            return parse_result['parsed_data']
        else:
            logger.warning(f"TextFSM解析失败: platform={platform}, file={file_path}, error={parse_result.get('error', 'Unknown error')}")
            return None
