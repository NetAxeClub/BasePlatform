# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      bus
   Description:     消息总线类
   Author:          Lijiamin
   date：           2023/3/30 15:43
-------------------------------------------------
   Change Activity:
                    2023/3/30 15:43
-------------------------------------------------
使用aio_pika 封装一个消息总线类，使用连接池实现消息发布订阅、消息确认、qos、公平队列、限速、消息广播功能
"""
import time
import aio_pika
from backend.confload.confload import config


class AsyncMessageBus:
    def __init__(self):
        self.host = config.mq_host
        self.port = config.mq_port
        self.username = config.mq_username
        self.password = config.mq_password
        self.queue = config.queue
        self.exchange = config.exchange
        self.routing_key = config.routing_key
        self.queue_qos = config.queue_qos
        self.connection = None
        self.channel = None
        self.exchange_obj = config.exchange
        self.queue_obj = None
        self.virtual_host = config.virtual_host
        self.is_ready = False

    async def connect(self, queue, routing_key, exchange_type, durable=True, auto_delete=False):
        """
        exchange_type  topic  fanout
        """
        exchange_type_map = {
            'topic': aio_pika.ExchangeType.TOPIC,
            'fanout': aio_pika.ExchangeType.FANOUT,
        }
        arguments = {"x-max-priority": 10}
        self.connection = await aio_pika.connect_robust(host=self.host, port=self.port, login=self.username, password=self.password, virtualhost=self.virtual_host)
        self.channel = await self.connection.channel()
        self.exchange_obj = await self.channel.declare_exchange(self.exchange, exchange_type_map[exchange_type], durable=durable, auto_delete=auto_delete)
        self.queue_obj = await self.channel.declare_queue(queue, durable=durable, auto_delete=auto_delete, arguments=arguments)
        await self.queue_obj.bind(self.exchange_obj, routing_key)
        await self.channel.set_qos(self.queue_qos)
        self.is_ready = True

    async def broadcast_connect(self, durable=True, auto_delete=False):
        """
        exchange_type  topic  fanout
        """
        self.connection = await aio_pika.connect_robust(host=self.host, port=self.port, login=self.username, password=self.password, virtualhost=self.virtual_host)
        self.channel = await self.connection.channel()
        self.exchange_obj = await self.channel.declare_exchange('broadcast', aio_pika.ExchangeType.FANOUT,
                                                                durable=durable,
                                                                auto_delete=auto_delete)
        await self.channel.set_qos(self.queue_qos)

    async def publish(self, message: str, routing_key: str):
        await self.exchange_obj.publish(aio_pika.Message(body=message.encode()), routing_key=routing_key)

    async def subscribe(self, callback):
        async with self.queue_obj.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await callback(message.body.decode())
                    # await message.ack()

    async def close(self):
        await self.connection.close()
        self.is_ready = False

    async def broadcast(self, message: str):
        await self.exchange_obj.publish(aio_pika.Message(body=message.encode()), routing_key=self.routing_key)

    async def receive_broadcast(self, queue, callback, durable=True, auto_delete=False):
        queue_name = await self.channel.declare_queue(name=queue, exclusive=True, durable=durable,
                                                      auto_delete=auto_delete)
        await queue_name.bind('broadcast', self.routing_key)
        async with queue_name.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await callback(message.body.decode())


# 回调方法
async def callbacka(info):
    print(info)
    time.sleep(0.5)


async def callbackb(message):
    print(message.body.decode())


# 广播发送
async def broadcast_publish():
    bus = AsyncMessageBus()
    await bus.broadcast_connect()
    for i in range(50):
        await bus.broadcast("test{}".format(i))
    await bus.close()


# 广播接收a
async def broadcast_subscribe_a():
    bus = AsyncMessageBus()
    await bus.broadcast_connect()
    await bus.receive_broadcast(queue='a', callback=callbacka)
    await bus.close()


# 广播接收
async def broadcast_subscribe_b():
    bus = AsyncMessageBus()
    await bus.broadcast_connect()
    await bus.receive_broadcast(queue='b', callback=callbacka)
    await bus.close()


# 队列发送
async def publish():
    bus = AsyncMessageBus()
    await bus.connect(queue='msg_gateway', routing_key='msg_gateway', exchange_type='topic')
    for i in range(50):
        await bus.publish("test{}".format(i), routing_key='msg_gateway')
    await bus.close()


# 队列接收
async def consume():
    bus = AsyncMessageBus()
    await bus.connect(queue='test11', routing_key='test11', exchange_type='topic')
    await bus.subscribe(callbacka)
    await bus.close()

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(publish())
#     asyncio.run(consume())
