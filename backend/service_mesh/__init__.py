# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      __init__
   Description:
   Author:          Lijiamin
   date：           2023/7/10 11:40
-------------------------------------------------
   Change Activity:
                    2023/7/10 11:40
-------------------------------------------------
"""
from .msg_gateway import SendRunner

__all__ = ["msg_gateway_runner"]

msg_gateway_runner = SendRunner()