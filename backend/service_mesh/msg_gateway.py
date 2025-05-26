# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      msg_gateway
   Description:
   Author:          Lijiamin
   date：           2023/7/10 10:39
-------------------------------------------------
   Change Activity:
                    2023/7/10 10:39
-------------------------------------------------
"""
import logging
import requests
import json
# from aiohttp import TCPConnector, ClientSession
# from backend.core.utils.metric import run_time_async
from confload.confload import config

# from backend.core.utils.metric import run_time_sync

log = logging.getLogger(__name__)


class SendRunner:
    # _instance = None

    def __init__(self):
        """
        {'name': 'default@@msg_gateway', 'groupName': 'default', 'clusters': '', 'cacheMillis': 10000,
        'hosts': [{'instanceId': '10.', 'ip': '1.25.2.19', 'port': 301, 'weight': 1.0,
        'healthy': False, 'enabled': True, 'ephemeral': True, 'clusterName': 'DEFAULT',
        'serviceName': 'default@@msg_gateway',
        'metadata': {'routing_key': 'msg_gateway', 'queue': 'msg_gateway'},
        'instanceHeartBeatInterval': 5000, 'ipDeleteTimeout': 30000, 'instanceHeartBeatTimeOut': 15000}],
        'lastRefTime': 1683188537563, 'checksum': '', 'allIPs': False,
        'reachProtectionThreshold': False, 'valid': True}
        """
        self.metadata = None
        self.server_hosts = None
        self.server = None
        self.post_data = {
            "library": 'sms',
            "send_args": {}
        }

    def send(self, library, data: dict, webhook=None):
        """
        {
            "library":"sms",
            "send_args": {
                "phone": ["18651614"],
                "content": "这是一条测试短信，用于测试微服务消息网关的功能123"
            },
            "peer_queue": "alert_gateway_receive",
            "peer_routing_key": "alert_gateway_receive"
        }
        :param library:
        :param data:
        :return:
        """
        self.server = config.service_dicovery('msg_gateway')
        self.server_hosts = self.server['hosts']
        self.metadata = self.server_hosts[0]['metadata']
        for _server in self.server_hosts:
            url = "http://{}:{}/msg_gateway/send".format(_server['ip'], _server['port'])
            payload = {
                "library": library,
                "send_args": data
            }
            headers = {
                'Content-Type': 'application/json'
            }
            if webhook is not None:
                payload['webhook'] = webhook
            res = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            if res.status_code == 200:
                return res.json()
        return {}

    # async def _send(self, library, data, webhook=None):
    #     self.server = config.service_dicovery('msg_gateway')
    #     self.server_hosts = self.server['hosts']
    #     self.metadata = self.server_hosts[0]['metadata']
    #     for _server in self.server_hosts:
    #         url = "http://{}:{}/msg_gateway/send".format(_server['ip'], _server['port'])
    #         payload = {
    #             "library": library,
    #             "send_args": data
    #         }
    #         headers = {
    #             'Content-Type': 'application/json'
    #         }
    #         if webhook is not None:
    #             payload['webhook'] = webhook
    #         async with ClientSession(connector=TCPConnector(verify_ssl=False)) as session:
    #             async with session.post(url, data=json.dumps(payload), headers=headers, timeout=2) as response:
    #                 return response.status, await response.json()

    def get_media(self):
        self.server = config.service_dicovery('msg_gateway')
        self.server_hosts = self.server['hosts']
        self.metadata = self.server_hosts[0]['metadata']
        for _server in self.server_hosts:
            url = "http://{}:{}/msg_gateway/service/channels".format(_server['ip'], _server['port'])
            headers = {
                'Content-Type': 'application/json'
            }

            res = requests.request("GET", url, headers=headers)
            if res.status_code == 200:
                return res.json()
        return {}

    def get_task(self, task_id):
        self.server = config.service_dicovery('msg_gateway')
        self.server_hosts = self.server['hosts']
        self.metadata = self.server_hosts[0]['metadata']
        for _server in self.server_hosts:
            url = "http://{}:{}/msg_gateway/task/{}".format(_server['ip'], _server['port'], task_id)
            headers = {
                'Content-Type': 'application/json'
            }

            res = requests.request("GET", url, headers=headers)
            if res.status_code == 200:
                return res.json()
        return {}

    # @run_time_sync
    # def send_sms(self, user, content, webhook=None, priority=0):
    #     send_args = {
    #         "phone": [user],
    #         "content": content,
    #         "priority": priority
    #     }
    #     return self.send('sms', send_args, webhook)

    def send_sms(self, user: list, content: str, webhook=None, priority=0):
        send_args = {
            "phone": user,
            "content": content,
            "priority": priority,
            "template_id": config.hw_sms_template_id
        }
        return self.send('hw_sms', send_args, webhook)

    def send_ali_sms(self, user: list, template_data: dict, webhook=None, priority=0):
        send_args = {
            "phone": user,
            "template_code": config.ali_sms['duty_template_code'],
            "template_data": template_data,
            "priority": priority,
        }
        return self.send('ali_sms', send_args, webhook)

    # @run_time_sync
    def send_wechat(self, channel, content, webhook=None, priority=0):
        send_args = {
            "user": "@all",
            "content": content,
            "channel": channel,
            "type": "text",
            "priority": priority
        }
        return self.send('wechat', send_args, webhook)

    # @run_time_sync
    def send_phone(self, user: str, content: str, webhook=None, priority=0):
        send_args = {
            "phone": user,
            "content": content.strip().replace(' ', '').replace('\n', '').replace('\t', '').replace('\r', '').strip(),
            "priority": priority
        }
        return self.send('telephone', send_args, webhook)

    # @run_time_sync
    def send_email(self, user, subject, content, webhook=None, priority=0):
        send_args = {
            "user": user,
            "content": content,
            "subject": subject,
            "priority": priority
        }
        return self.send('email', send_args, webhook)

    def send_bot(self, url, content, sign, bot_type):
        send_args = {
            "url": url,
            "content": content,
            "sign": sign if sign else None,
            "bot_type": bot_type
        }
        return self.send('chat_bot', send_args)
