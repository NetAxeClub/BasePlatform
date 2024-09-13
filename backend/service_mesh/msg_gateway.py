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
from utils.metric import run_time_sync
from confload.confload import config

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

    # 单例模式
    # def __new__(cls):
    #     if not cls._instance:
    #         cls._instance = super().__new__(cls)
    #     return cls._instance

    def send(self, library, data: dict):
        """
        {
            "library":"sms",
            "send_args": {
                "phone": ["18651614740"],
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

            res = requests.request("POST", url, headers=headers, data=json.dumps(payload))

            # print(res.status_code)
            # print(res.text)
            # print(res.json())
            # log.debug(res.status_code)
            # log.debug(res.text)
            # log.debug(res.json())
        # if self.metadata is not None:
        #     self.queue = self.metadata['queue']
        #     self.routing_key = self.metadata['routing_key']
        #     self.post_data['library'] = "sms"
        #     self.post_data['send_args'] = data
        #     self.post_data['task_id'] = str(uuid.uuid4())
        # app_manager_async.send_task_to_other(queue=self.metadata['queue'],
        #                                      routing_key=self.metadata['routing_key'],
        #                                      data=self.post_data)
        # headers_val = config.default_webhook_headers
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(url=self.post_url, headers=headers_val, verify_ssl=False, timeout=10,
        #                             data=pl) as response:
        #         res = await response.text()  # 可以根据实际需要进行处理
        #         log.debug('webhook res')
        #         log.debug(res)
        #         print('webhook res', res)

    @run_time_sync
    def send_sms(self, user, content):
        send_args = {
             "phone": [user],
             "content": content
         }
        self.send('wechat', send_args)

    @run_time_sync
    def send_wechat(self, channel, content):
        send_args = {
            "user": "@all",
            "content": content,
            "channel": channel,
            "type": "text"
        }
        self.send('wechat', send_args)

    @run_time_sync
    def send_email(self, user, subject, content):
        send_args = {
            "user": user,
            "content": content,
            "subject": subject
        }
        self.send('email', send_args)