# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      bus_sync
   Description:
   Author:          Lijiamin
   date：           2023/3/30 17:14
-------------------------------------------------
   Change Activity:
                    2023/3/30 17:14
-------------------------------------------------
使用pika 封装一个消息总线类，实现消息发布订阅、消息确认、qos、公平队列、限速、消息广播功能
"""
import functools
import uuid
import pika
import json
import time
import logging
from queue import Queue
from threading import Lock
from pika.exchange_type import ExchangeType
from confload.confload import config

logger = logging.getLogger(__name__)


# 回调方法
def on_message(chan, method_frame, header_frame, body, userdata=None):
    """Called when a message is received. Log message and ack it."""
    print('Delivery properties: %s, message metadata: %s', method_frame, header_frame)
    print('Userdata: %s, message body: %s', userdata, body)
    chan.basic_ack(delivery_tag=method_frame.delivery_tag)


def fib(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


class SyncMessageBus:
    def __init__(self):
        self.host = config.mq_host
        self.port = config.mq_port
        self.username = config.mq_username
        self.password = config.mq_password
        self.queue = config.queue
        self.virtual_host = config.virtual_host
        self.connection_pool = Queue()
        self.connection_pool_size = 10
        self.connection_pool_lock = Lock()
        self.channel_pool = Queue()
        self.channel_pool_size = 100
        self.channel_pool_lock = Lock()
        self.exchange = config.exchange
        self.queue_qos = config.queue_qos
        self.routing_key = ''
        self.callback_queue = None
        self.response = None
        self.corr_id = None

    def get_connection(self):
        with self.connection_pool_lock:
            if self.connection_pool.qsize() < self.connection_pool_size:
                credentials = pika.PlainCredentials(self.username, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.virtual_host,
                    credentials=credentials,
                    # heartbeat=0
                )
                connection = pika.BlockingConnection(parameters)
                self.connection_pool.put(connection)
            else:
                connection = self.connection_pool.get()
        return connection

    def get_channel(self):
        with self.channel_pool_lock:
            if self.channel_pool.qsize() < self.channel_pool_size:
                connection = self.get_connection()
                channel = connection.channel()
                self.channel_pool.put(channel)
            else:
                channel = self.channel_pool.get()
        return channel

    def publish(self, queue, routing_key, body, properties=None, durable=True, auto_delete=False):
        channel = self.get_channel()
        arguments = {"x-max-priority": 10}
        channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=ExchangeType.topic,
            durable=durable,
            auto_delete=auto_delete
        )
        channel.queue_declare(queue=queue, durable=durable, auto_delete=auto_delete, arguments=arguments)
        channel.queue_bind(queue=queue, exchange=self.exchange, routing_key=routing_key)
        channel.basic_qos(prefetch_count=self.queue_qos)
        channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=body,
            properties=properties
        )

    def subscribe(self, queue, routing_key, callback, durable=True, auto_delete=False):
        """
        exchange_type  topic  fanout
        """
        channel = self.get_channel()
        arguments = {"x-max-priority": 10}
        channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=ExchangeType.topic,
            durable=durable,
            auto_delete=auto_delete
        )
        channel.queue_declare(queue=queue, durable=durable, auto_delete=auto_delete, arguments=arguments)
        channel.queue_bind(queue=queue, exchange=self.exchange, routing_key=routing_key)
        channel.basic_qos(prefetch_count=self.queue_qos)
        on_message_callback = functools.partial(
            callback, userdata='on_message_userdata')
        channel.basic_consume(queue=queue, on_message_callback=on_message_callback)
        try:
            channel.start_consuming()
        except KeyboardInterrupt as e:
            logger.error(str(e))
            channel.stop_consuming()

    def ack_message(self, delivery_tag):
        channel = self.get_channel()
        channel.basic_ack(delivery_tag=delivery_tag)

    def set_queue_limit(self, queue, max_length=None, max_size=None):
        channel = self.get_channel()
        channel.queue_declare(
            queue=queue,
            arguments={
                'x-max-length': max_length,
                'x-max-length-bytes': max_size
            }
        )

    def set_fair_dispatch(self, callback, queue='', durable=True, auto_delete=False):
        channel = self.get_channel()
        channel.queue_declare(queue=queue, durable=durable, auto_delete=auto_delete)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=queue, on_message_callback=callback)
        channel.start_consuming()

    def set_rate_limit(self, exchange, routing_key, rate_limit):
        channel = self.get_channel()
        channel.exchange_declare(
            exchange=exchange,
            exchange_type='topic'
        )
        channel.queue_declare(
            queue=routing_key,
            arguments={
                'x-max-length': 1,
                'x-message-ttl': int(1 / rate_limit * 1000)
            }
        )
        channel.queue_bind(exchange=exchange, queue=routing_key, routing_key=routing_key)

    def broadcast(self, body, persistent=True):
        channel = self.get_channel()
        channel.basic_publish(exchange='broadcast', routing_key='', body=body,
                              properties=pika.BasicProperties(delivery_mode=2 if persistent else 1))

    def receive_broadcast(self, queue, callback, durable=True, auto_delete=False):
        channel = self.get_channel()
        channel.exchange_declare(
            exchange='broadcast',
            exchange_type='fanout',
            durable=durable,
            auto_delete=auto_delete
        )
        result = channel.queue_declare(queue=queue, exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='broadcast', queue=queue_name)
        channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        channel.start_consuming()

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, n, queue):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        connection = self.get_connection()
        channel = connection.channel()
        result = channel.queue_declare(queue=queue, exclusive=True)
        self.callback_queue = result.method.queue
        channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(n).encode())
        connection.process_data_events(time_limit=None)
        return int(self.response)

    def rpc_server(self, queue, routing_key, callback, durable=True, auto_delete=False):
        channel = self.get_channel()
        arguments = {"x-max-priority": 10}
        channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=ExchangeType.topic,
            durable=durable,
            auto_delete=auto_delete
        )
        channel.queue_declare(queue=queue, durable=durable, auto_delete=auto_delete, arguments=arguments)
        channel.queue_bind(queue=queue, exchange=self.exchange, routing_key=routing_key)
        channel.basic_qos(prefetch_count=1)
        on_message_callback = functools.partial(
            callback, userdata='on_request')
        channel.basic_consume(queue=f"rpc_{config.queue}", on_message_callback=on_message_callback)
        try:
            channel.start_consuming()
        except KeyboardInterrupt as e:
            logger.error(str(e))
            channel.stop_consuming()


# broadcast
def broadcast():
    bus = SyncMessageBus()
    for i in range(50):
        bus.broadcast("message is {}".format(i).encode())
        time.sleep(0.1)


def broadcast_recv1():
    bus = SyncMessageBus()
    bus.receive_broadcast(queue='a', callback=on_message)


def broadcast_recv2():
    bus = SyncMessageBus()
    bus.receive_broadcast(queue='b', callback=on_message)


# 队列发送
def publish():
    bus = SyncMessageBus()
    for i in range(50):
        print(i)
        time.sleep(0.5)
        bus.publish(queue='rbacb', routing_key='rbacb', body="test{}".format(i))


# 队列接收, 可以多次调用
def consume():
    bus = SyncMessageBus()
    bus.subscribe(queue='base_platform', routing_key='base_platform', callback=on_message)
