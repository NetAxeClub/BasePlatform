# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      manager_async
   Description:
   Author:          Lijiamin
   date：           2023/4/4 14:51
-------------------------------------------------
   Change Activity:
                    2023/4/4 14:51
-------------------------------------------------
"""
import json
import logging
import uuid
from datetime import datetime
from bson import json_util
from backend.bus.bus_async import AsyncMessageBus
from backend.database.db_async import AsyncMongoOps
from backend.calls.routes import routes
from backend.utils.metric import run_time_async

log = logging.getLogger(__name__)
task_db = AsyncMongoOps('task')


class AsyncManager:

    def __init__(self):
        self.bus = AsyncMessageBus()

    @run_time_async
    async def callback(self, body):
        """
        {'library': 'sms', 'send_args': {'phone': ['18651610'], 'content': 'test12345676kkl;'}, 'webhook': {}, 'task_id': 'd962abae-1867-4cc4-914a-c2eaeeed1233', 'task_queue': 'msg_gateway'}
        """
        playload = json.loads(body)
        log.debug(('Receive111: {}'.format(playload)))
        try:
            res = await routes[playload['method']](**playload)
            playload['status'] = res.status.value
            playload['code'] = res.code.value
            playload['data'] = res.data
        except Exception as e:
            log.error("函数运行错误:{}".format(e))
            playload['status'] = 'failled'
            playload['code'] = 400
            playload['data'] = str(e)
        playload['ended_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        playload.pop('_id')
        # 计算时间差
        a_dt = datetime.strptime(playload['ended_at'], '%Y-%m-%d %H:%M:%S')
        b_dt = datetime.strptime(playload['created_at'], '%Y-%m-%d %H:%M:%S')
        delta = a_dt - b_dt
        playload['execution_time'] = delta.seconds  # 处理耗时
        await task_db.update(query={'task_id': playload['task_id']}, data=playload)
        return

    # 格式化任务返回
    async def _render_task_response(self, **task_job):
        resultdata = Response(status="success", code=200, count=0, data={
            "task_id": task_job['task_id'],
            "task_queue": task_job['task_queue'],
            "created_on": task_job['created_at'],
            "task_meta": {
                "created_at": task_job['created_at']
            },
            "task_status": "queued",
            "task_result": 'success',
            "task_errors": None
        }).dict()
        return resultdata

    # 监听自身队列
    async def consume_task(self, queue, routing_key):
        if not self.bus.is_ready:
            await self.bus.connect(queue=queue, routing_key=routing_key, exchange_type='topic')
        await self.bus.subscribe(self.callback)
        # await self.close()

    # 发送消息给自身队列
    async def _send_task(self, **kwargs):
        if not self.bus.is_ready:
            await self.bus.connect(queue='msg_gateway', routing_key='msg_gateway', exchange_type='topic')
        await task_db.insert_data(kwargs)
        await self.bus.publish(message=json.dumps(kwargs, default=json_util.default), routing_key='msg_gateway')
        # await self.close()
        return

    # 业务逻辑，发送消息
    async def send_msg(self, sendcfg: SendMsg, method: str = None) -> Response:
        if isinstance(sendcfg, dict):
            req_data = sendcfg
        else:
            req_data = sendcfg.dict(exclude_none=True)
        if method is not None:
            req_data["method"] = method
        if 'task_id' not in req_data.keys():
            req_data['task_id'] = str(uuid.uuid4())
        req_data['task_queue'] = self.bus.queue
        req_data['status'] = 'queued'
        req_data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self._send_task(**req_data)
        r = await self._render_task_response(**req_data)
        resp = jsonable_encoder(r)
        return resp

    async def query_task(self, **kwargs):
        r = await task_db.find(query_dict=kwargs, fileds={'_id': 0})
        res = Response(code=200, data=r, status='success', msg='success').dict()
        resp = jsonable_encoder(res)
        return resp

    async def all_task(self, query, page, page_size):
        r, count = await task_db.page_query(query_dict=query, fileds={'_id': 0}, page_size=page_size, page=page)
        res = Response(code=200, results=r, status='success', msg='success', count=count).dict()
        resp = jsonable_encoder(res)
        return resp

    # 服务之间消息通信
    async def send_task_to_other(self, queue, routing_key, data):
        if not self.bus.is_ready:
            await self.bus.connect(queue=queue, routing_key=routing_key, exchange_type='topic')
        await task_db.insert_data(data)
        await self.bus.publish(message=json.dumps(data, default=json_util.default), routing_key=routing_key)
        # await self.close()
