# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      south_gateway
   Description:     南向驱动网关，用于调用南向驱动的配置获取和任务查询接口
   Author:          Lijiamin
   date：           2025/3/24 09:53
-------------------------------------------------
   Change Activity:
                    2025/3/24 09:53
-------------------------------------------------
"""
import logging
import requests
import json
from confload.confload import config

log = logging.getLogger(__name__)


class SouthDriverRunner:
    """南向驱动运行器"""

    def __init__(self):
        """初始化南向驱动连接信息"""
        self.timeout = 30
        self.api_key = config.south_api_key

        log.info("南向驱动运行器初始化完成")

    def _make_request(self, method, endpoint, host_info, data=None, params=None, headers=None):
        """发起HTTP请求的通用方法
        
        Args:
            method (str): HTTP方法 (GET, POST等)
            endpoint (str): API端点路径
            host_info (dict): 包含host和port的字典，格式: {"host": "192.168.1.100", "port": "8080"}
            data (dict): POST请求的数据
            params (dict): GET请求的参数
            headers (dict): 额外的请求头
        """
        host = host_info.get('host')
        port = host_info.get('port')
        
        log.debug(f"开始发起HTTP请求: {method} {endpoint} -> {host}:{port}")
        
        # 验证连接信息
        if not host or not port:
            log.error("Host和Port参数不能为空")
            return {'success': False, 'error': 'Host和Port参数不能为空'}
        
        try:
            # 验证端口是否为有效数字
            int(port)
        except ValueError:
            log.error(f"端口号无效: {port}")
            return {'success': False, 'error': f'端口号无效: {port}'}

        # 设置默认请求头
        default_headers = {
            'Content-Type': 'application/json', 
            'x-api-key': self.api_key
        }
        if headers:
            default_headers.update(headers)

        try:
            url = f"http://{host}:{port}{endpoint}"
            log.debug(f"尝试连接服务器: {url}")
            
            # 发起请求
            if method.upper() == 'POST':
                log.debug(f"发送POST请求，数据大小: {len(json.dumps(data)) if data else 0} bytes")
                response = requests.post(
                    url, 
                    headers=default_headers, 
                    data=json.dumps(data) if data else None,
                    timeout=self.timeout
                )
            elif method.upper() == 'GET':
                log.debug(f"发送GET请求，参数: {params}")
                response = requests.get(
                    url, 
                    headers=default_headers, 
                    params=params,
                    timeout=self.timeout
                )
            else:
                log.error(f"不支持的HTTP方法: {method}")
                return {'success': False, 'error': f'不支持的HTTP方法: {method}'}

            # 检查响应状态
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    log.info(f"请求成功: {url}, 响应数据大小: {len(str(result))} chars")
                    return {'success': True, 'data': result}
                except json.JSONDecodeError:
                    log.warning(f"响应不是有效的JSON格式: {url}")
                    return {'success': True, 'data': response.text}
            else:
                log.warning(f"请求失败: {url}, 状态码: {response.status_code}")
                return {'success': False, 'error': f'请求失败，状态码: {response.status_code}'}
                
        except requests.exceptions.Timeout:
            log.error(f"请求超时: {url}")
            return {'success': False, 'error': '请求超时'}
        except requests.exceptions.ConnectionError:
            log.error(f"连接失败: {url}")
            return {'success': False, 'error': '连接失败'}
        except Exception as e:
            log.error(f"请求异常: {url}, 错误: {str(e)}")
            return {'success': False, 'error': f'请求异常: {str(e)}'}

    def get_device_config(self, url_prefix, host_info, netpalm_info):
        """调用南向驱动的配置获取接口
        
        Args:
            url_prefix: 接口前缀
            host_info (dict): 包含host和port的字典，格式: {"host": "192.168.1.100", "port": "8080"}
            netpalm_info (dict): 包含南向驱动相关信息的字典，格式: {
                "library": "netmiko",
                "connection_args": {"host": "192.168.1.1", "username": "admin", "password": "password"},
                "command": ["show version", "show interfaces"],
                "webhook": {},  # 可选
                "queue_strategy": "default"  # 可选，默认为"default"
            }
        """
        library = netpalm_info.get('library')
        connection_args = netpalm_info.get('connection_args', {})
        command = netpalm_info.get('command', [])
        webhook = netpalm_info.get('webhook')
        queue_strategy = netpalm_info.get('queue_strategy', 'default')
        
        device_ip = connection_args.get('host', connection_args.get('ip', 'unknown'))
        log.info(f"开始获取设备配置 - 设备: {device_ip}, 库: {library}, 命令数: {len(command)}, 目标服务器: {host_info.get('host')}:{host_info.get('port')}")
        
        try:
            # 发起POST请求
            result = self._make_request('POST', url_prefix, host_info, data=netpalm_info)
            
            if result.get('success'):
                log.info(f"配置获取成功 - 设备: {device_ip}")
                return {
                    'success': True,
                    'data': result['data'],
                    'device_ip': device_ip
                }
            else:
                log.error(f"配置获取失败 - 设备: {device_ip}, 错误: {result.get('error', '未知错误')}")
                return {
                    'success': False,
                    'error': result.get('error', '未知错误'),
                    'device_ip': device_ip
                }
                
        except Exception as e:
            log.error(f"配置获取异常 - 设备: {device_ip}, 异常: {str(e)}")
            return {
                'success': False,
                'error': f'配置获取异常: {str(e)}',
                'device_ip': device_ip
            }

    def get_task_by_id(self, host_info, task_id):
        """根据任务ID查询任务详情
        
        Args:
            host_info (dict): 包含host和port的字典，格式: {"host": "192.168.1.100", "port": "8080"}
            task_id (str): 任务ID
        """
        log.info(f"开始查询任务详情 - 任务ID: {task_id}, 目标服务器: {host_info.get('host')}:{host_info.get('port')}")
        
        try:
            # 发起GET请求
            result = self._make_request('GET', f'/task/{task_id}', host_info)
            
            if result.get('success'):
                data = result['data']
                log.info(f"任务查询成功 - 任务ID: {task_id}, 数据大小: {len(str(data))} chars")
                return {
                    'success': True,
                    'data': data,
                    'task_id': task_id
                }
            else:
                log.error(f"任务查询失败 - 任务ID: {task_id}, 错误: {result.get('error', '未知错误')}")
                return {
                    'success': False,
                    'error': result.get('error', '未知错误'),
                    'task_id': task_id
                }
                
        except Exception as e:
            log.error(f"任务查询异常 - 任务ID: {task_id}, 异常: {str(e)}")
            return {
                'success': False,
                'error': f'任务查询异常: {str(e)}',
                'task_id': task_id
            }

