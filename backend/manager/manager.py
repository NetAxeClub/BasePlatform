# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      manager
   Description:
   Author:          Lijiamin
   date：           2023/4/3 15:06
-------------------------------------------------
   Change Activity:
                    2023/4/3 15:06
-------------------------------------------------
这里演示使用消息队列的同步方式实现，异步方式同理
"""
import json
import logging
# import uuid
from datetime import datetime
# from bson import json_util
from bus.bus_sync import SyncMessageBus
# from backend.models.task import Response
from calls.routes import routes
from database.db_sync import SyncMongoOps
from confload.confload import config
log = logging.getLogger(__name__)
task_db = SyncMongoOps('task')


def callback(ch, method, properties, body):
    """
    {'library': 'sms', 'send_args': {'phone': ['18651610'], 'content': 'test1234567l;'}, 'webhook': {}, 'task_id': 'd962abae-1867-4cc4-914a-c2eaeeed1233', 'task_queue': 'msg_gateway'}
    """
    playload = json.loads(body.decode())
    log.debug(('Receive111: {}'.format(playload)))
    res = routes['method'](**playload)
    # playload['status'] = res.status.value
    # playload['code'] = res.code.value
    # playload['data'] = res.data
    # playload['ended_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # playload.pop('_id')
    # task_db.update(query={'task_id': playload['task_id']}, data=playload)
    return


class Manager(SyncMessageBus):

    def __init__(self):
        super(Manager, self).__init__()
        # 方法映射路由
        # self.routes = routes

    # 监听自身队列
    def consume_task(self):
        self.subscribe(queue=config.queue, routing_key=config.routing_key, callback=callback)

    # 发送消息
    def pubilch_task(self, queue, routing_key, data):
        self.publish(queue=queue, routing_key=routing_key, body=data)