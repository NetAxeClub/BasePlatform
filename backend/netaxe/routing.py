# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      routing
   Description:
   Author:          Lijiamin
   date：           2022/7/29 15:03
-------------------------------------------------
   Change Activity:
                    2022/7/29 15:03
-------------------------------------------------
"""
from utils.authentication.asgi_auth import QueryAuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from apps.asset.consumers import WebSSHConsumer, SSHConsumer

application = ProtocolTypeRouter({

    "websocket": QueryAuthMiddlewareStack(
        URLRouter(
            [
                re_path(r'base_platform/ws/ssh/([0-9]+)/', WebSSHConsumer),
                re_path(r'base_platform/ws/server_ssh/([0-9]+)/', SSHConsumer),
                # re_path(r'ws/ssh/([0-9]+)/', WebSSHConsumer),
                # path('ws/ssh/1/', WebSshConsumer),
            ]
        ),
    )
})
