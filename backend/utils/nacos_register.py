# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      nacos
   Description:
   Author:          Lijiamin
   date：           2023/4/14 10:41
-------------------------------------------------
   Change Activity:
                    2023/4/14 10:41
-------------------------------------------------
"""
import logging
import nacos
from confload.confload import config

logger = logging.getLogger('nacos')


def nacos_init():
    if not config.local_dev:
        client = nacos.NacosClient(server_addresses=f"{config.nacos}:{config.nacos_port}", username="nacos", password=config.nacos_password, log_level="INFO")
        status = client.add_naming_instance(service_name=config.queue, ip=config.backend_ip, port=config.backend_port, group_name="default", heartbeat_interval=5)
        if status:
            logger.info("nacos注册成功")


