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
import logging
from confload.confload import config
from pika import BasicProperties
from netaxe.settings import DEBUG
from bus.bus_sync import SyncMessageBus
from apps.dcs_control.tasks import FirewallMain
from apps.automation.tools.models_api import get_firewall_list
from apps.dcs_control.tasks import address_set, bulk_deny_by_address, get_firewall_zone

log = logging.getLogger(__name__)
if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config'


# 分发器
def dispatcher(method, data):
    log.info(f"method:{method}")
    try:
        if method == 'get_firewall_list':
            res = get_firewall_list()
            return list(res)
        elif method == 'get_firewall_zone':
            res = get_firewall_zone(**data)
            log.info(str(res))
            return res
        elif method == 'bulk_deny_by_address':
            res = bulk_deny_by_address.apply_async(kwargs=data, queue=CELERY_QUEUE,
                                                   retry=True)  # config_backup
            if str(res) == 'None':
                print('forget')
                res.forget()
            return [{'task_id': str(res)}]
        elif method == 'address_set':
            res = address_set.apply_async(kwargs=data, queue=CELERY_QUEUE,
                                          retry=True)  # config_backup
            if str(res) == 'None':
                print('forget')
                res.forget()
            return [{'task_id': str(res)}]
        else:
            _FirewallMain = FirewallMain(data['host'])
            func = getattr(_FirewallMain, method)
            res = func(**data)
            if res is None:
                return {'code': 200}
            return res
    except Exception as e:
        log.error(e)
        return {'code': 400, "msg": str(e)}


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
