# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      __init__.py
   Description:
   Author:          Lijiamin
   date：           2023/4/11 20:46
-------------------------------------------------
   Change Activity:
                    2023/4/11 20:46
-------------------------------------------------
"""
from .redisHelper import RedisOps
redis_conn = RedisOps()

__all__ = ['redis_conn']