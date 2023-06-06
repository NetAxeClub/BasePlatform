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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netaxe.settings')
django.setup()
from manager import app_manager_sync
from confload.confload import config
from utils.metric import run_time_sync


# @run_time_sync
def register_server():
    tmp = {
        "method": "register_server",  # 指定rbac的route 回调方法
        "key": config.project_name,
        "name": "基础平台",
        "url": "http://{}:{}".format(config.server_ip, config.server_port)
    }
    app_manager_sync.pubilch_task(queue='rbac', routing_key='rbac', data=json.dumps(tmp))


# @run_time_sync
def register_menu():
    tmp = {
        "method": "register_menu",  # 指定rbac的route 回调方法
        "key": config.project_name,
        "menu": config.default_menu['menu'],
    }
    app_manager_sync.pubilch_task(queue='rbac', routing_key='rbac', data=json.dumps(tmp))



if __name__ == "__main__":
    # 每隔10分钟执行一次 job() 函数
    # register_server()
    register_menu()
    # schedule.every(10).minutes.do(register_server)
    #
    # # 启动定时任务
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)