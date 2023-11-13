# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      worker
   Description:
   Author:          Lijiamin
   date：           2023/6/6 10:31
-------------------------------------------------
   Change Activity:
                    2023/6/6 10:31
-------------------------------------------------
"""
import json
import os
import django
import schedule
import time
import sys
import logging
import socket
from multiprocessing import Process

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netaxe.settings')
django.setup()
from manager import app_manager_sync
from rpc import RPC
from confload.confload import config

BASE_DIR = os.path.dirname(__file__)
# 定位到log日志文件
log_path = os.path.join(BASE_DIR, 'logs')
hostname = socket.gethostname()
if not os.path.exists(log_path):
    os.mkdir(log_path)
log = logging.getLogger(__name__)
config.setup_logging(max_debug=True)


def register_server():
    tmp = {
        "method": "register_server",  # 指定rbac的route 回调方法
        "key": config.project_name,
        "name": "基础平台",
        "url": config.web_url
    }
    app_manager_sync.pubilch_task(queue='rbac', routing_key='rbac', data=json.dumps(tmp))


def register_menu():
    tmp = {
        "method": "register_menu",  # 指定rbac的route 回调方法
        "key": config.project_name,
        "menu": config.default_menu['menu'],
    }
    app_manager_sync.pubilch_task(queue='rbac', routing_key='rbac', data=json.dumps(tmp))


# 运行rpc服务器
def run_rpc_server():
    RPC.run_rpc_server()


# 实现work的基本方法
def run_worker():
    try:
        register_server()
        register_menu()
        schedule.every(10).minutes.do(register_server)
        schedule.every(6).hours.do(register_menu)
    except Exception as e:
        return e


# 开启多进程
def worker_constructor():
    try:
        p = Process(target=run_worker, name="worker-{}".format(hostname))
        p.start()
        while True:
            time.sleep(99999999)
    finally:
        sys.exit()


# 开启多进程
def worker_rpc():
    try:
        p = Process(target=run_rpc_server, name="worker-rpc-{}".format(hostname))
        p.start()
        while True:
            time.sleep(99999999)
    finally:
        sys.exit()


# 最终调用
def main(args):
    worker_type = args[-1]
    if worker_type == "default":
        worker_constructor()
    elif worker_type == "rpc":
        worker_rpc()


if __name__ == "__main__":
    main(sys.argv)
