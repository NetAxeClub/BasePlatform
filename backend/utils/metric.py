# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      metric
   Description:
   Author:          Lijiamin
   date：           2023/4/13 14:43
-------------------------------------------------
   Change Activity:
                    2023/4/13 14:43
-------------------------------------------------
"""
import time
import logging
import asyncio
import traceback
import socket
from functools import wraps
from prometheus_client import CollectorRegistry, Gauge, Info, push_to_gateway
from confload.confload import config
log = logging.getLogger(__name__)

hostname = socket.gethostname()
registry = CollectorRegistry(auto_describe=True)
gauge = Gauge('run_time', 'run_time data', labelnames=['node', 'func'], registry=registry)
err_info = Info('run_time_error', 'run_time error', registry=registry)


# 计算函数的运行耗时并推送到pushgateway  用于异步函数装饰器
def run_time_async(async_function):

    async def wrapper(*args, **kwargs):
        # try:
        start_time = time.time()
        await async_function(*args, **kwargs)
        end_time = time.time()
        # g.set_to_current_time()
        gauge.labels(node=hostname, func=async_function.__name__).set(round((end_time - start_time), 2))
        push_to_gateway(config.push_gateway, job=config.project_name, registry=registry)
        log.debug('函数 %s 运行时间为： %.6f秒' % (async_function.__name__, end_time - start_time))
        print('函数 %s 运行时间为： %.6f秒' % (async_function.__name__, end_time - start_time))
        # except Exception as e:
        #     log.error(f"函数{async_function.__name__}运行错误:{str(e)}")
        #     log.error(traceback.print_exc())
        #     # err_info.info({'node': hostname, 'exception': str(e), 'func': async_function.__name__})
        #     # push_to_gateway(config.push_gateway, job=config.project_name, registry=registry)
    return wrapper


# 计算函数的运行耗时并推送到pushgateway  用于异步函数装饰器
def run_time_sync(async_function):

    def wrapper(*args, **kwargs):
        # try:
        start_time = time.time()
        async_function(*args, **kwargs)
        end_time = time.time()
        # g.set_to_current_time()
        gauge.labels(node=hostname, func=async_function.__name__).set(round((end_time - start_time), 2))
        push_to_gateway(config.push_gateway, job=config.project_name, registry=registry)
        log.debug('函数 %s 运行时间为： %.6f秒' % (async_function.__name__, end_time - start_time))
        print('函数 %s 运行时间为： %.6f秒' % (async_function.__name__, end_time - start_time))
    return wrapper