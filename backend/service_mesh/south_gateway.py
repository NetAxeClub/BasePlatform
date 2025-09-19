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
import time
from confload.confload import config

log = logging.getLogger(__name__)


class SouthDriverRunner:
    """南向驱动运行器"""

    def __init__(self):
        """初始化南向驱动连接信息"""
        self.metadata = None
        self.server_hosts = None
        self.server = None
        self.timeout = 30
        self.api_key = '2a84465a-cf38-46b2-9d86-b84Q7d57f288'
        
        log.info("南向驱动运行器初始化完成")

    def _get_server_info(self, service_name='south_driver'):
        """获取服务发现信息"""
        try:
            log.debug(f"开始获取服务发现信息: {service_name}")
            self.server = config.service_dicovery(service_name)
            self.server_hosts = self.server['hosts']
            
            if not self.server_hosts:
                log.error(f"服务 {service_name} 没有可用的主机")
                return False
                
            if self.server_hosts:
                self.metadata = self.server_hosts[0]['metadata']
                
            log.info(f"成功获取服务发现信息，可用主机数: {len(self.server_hosts)}")
            return True
            
        except Exception as e:
            log.error(f"获取服务发现信息失败: {str(e)}")
            return False

    def _make_request(self, method, endpoint, data=None, params=None, headers=None):
        """发起HTTP请求的通用方法"""
        log.debug(f"开始发起HTTP请求: {method} {endpoint}")
        
        if not self._get_server_info():
            log.error("无法获取服务发现信息，请求终止")
            return {'success': False, 'error': '无法获取服务发现信息'}

        # 设置默认请求头
        default_headers = {
            'Content-Type': 'application/json', 
            'x-api-key': self.api_key
        }
        if headers:
            default_headers.update(headers)

        for i, _server in enumerate(self.server_hosts):
            try:
                url = f"http://{_server['ip']}:{_server['port']}{endpoint}"
                log.debug(f"尝试连接服务器 {i+1}/{len(self.server_hosts)}: {url}")
                
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
                if response.status_code == 200:
                    try:
                        result = response.json()
                        log.info(f"请求成功: {url}, 响应数据大小: {len(str(result))} chars")
                        return {'success': True, 'data': result}
                    except json.JSONDecodeError:
                        log.warning(f"响应不是有效的JSON格式: {url}")
                        return {'success': True, 'data': response.text}
                else:
                    log.warning(f"请求失败: {url}, 状态码: {response.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                log.warning(f"请求超时: {url}")
                continue
            except requests.exceptions.ConnectionError:
                log.warning(f"连接失败: {url}")
                continue
            except Exception as e:
                log.error(f"请求异常: {url}, 错误: {str(e)}")
                continue

        log.error("所有服务器节点都无法连接")
        return {'success': False, 'error': '所有服务器节点都无法连接'}

    def get_config(self, library, connection_args, command, webhook=None, queue_strategy='default'):
        """调用南向驱动的配置获取接口"""
        device_ip = connection_args.get('host', connection_args.get('ip', 'unknown'))
        log.info(f"开始获取设备配置 - 设备: {device_ip}, 库: {library}, 命令数: {len(command)}")
        
        try:
            # 构建请求数据
            request_data = {
                'library': library,
                'connection_args': connection_args,
                'command': command,
                'webhook': webhook or {},
                'queue_strategy': queue_strategy
            }
            
            log.debug(f"请求数据: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 发起POST请求
            result = self._make_request('POST', '/getconfig', data=request_data)
            
            if result.get('status') == 'success':
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

    def get_task_by_id(self, task_id):
        """根据任务ID查询任务详情"""
        log.info(f"开始查询任务详情 - 任务ID: {task_id}")
        
        try:
            # 发起GET请求
            result = self._make_request('GET', f'/task/{task_id}')
            
            if result.get('status') == 'success':
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

