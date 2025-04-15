# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      cache_utils
   Description:
   Author:          Lijiamin
   date：           2025/4/15 16:19
-------------------------------------------------
   Change Activity:
                    2025/4/15 16:19
-------------------------------------------------
"""
from django.core.cache import cache
from django.conf import settings
import hashlib


def get_cache_key(prefix, *args):
    """生成一致的缓存key"""
    key_str = ':'.join(str(arg) for arg in args)
    return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"


def cache_network_data(prefix, *key_args, data, timeout=None):
    """缓存网络数据"""
    key = get_cache_key(prefix, *key_args)
    timeout = timeout or settings.CACHE_TTL
    cache.set(key, data, timeout)
    return data


def get_cached_network_data(prefix, *key_args):
    """获取缓存的网络数据"""
    key = get_cache_key(prefix, *key_args)
    return cache.get(key)
