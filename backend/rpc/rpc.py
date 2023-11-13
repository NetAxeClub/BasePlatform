# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      rpc
   Description:
   Author:          Lijiamin
   date：           2023/11/13 10:10
-------------------------------------------------
   Change Activity:
                    2023/11/13 10:10
-------------------------------------------------
"""
import json
from confload.confload import config
from pika import BasicProperties
from bus.bus_sync import SyncMessageBus
from backend.apps.automation.sec_main import FirewallMain


class Automation:
    def test(self, **kwargs):
        print(kwargs)
        return {'n': 100}


# 分发器
def dispatcher(method, data):
    _FirewallMain = FirewallMain(data['host'])
    func = getattr(_FirewallMain, method)
    return func(**data)


# 响应RPC请求
def on_request(chan, method_frame, header_frame, body, userdata=None):
    n = json.loads(body)
    print(n)
    if 'method' in n.keys():
        response = dispatcher(n['method'], n['data'])
    else:
        response = {'n': 123456}
    chan.basic_publish(exchange='',
                       routing_key=header_frame.reply_to,
                       properties=BasicProperties(correlation_id=header_frame.correlation_id),
                       body=json.dumps(response))
    chan.basic_ack(delivery_tag=method_frame.delivery_tag)


class SyncRPC:
    def __init__(self):
        self.bus = SyncMessageBus()

    def run_rpc_server(self):
        self.bus.rpc_server(queue=f"rpc_{config.queue}", routing_key=f"rpc_{config.queue}", callback=on_request)

