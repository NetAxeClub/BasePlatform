import hashlib

from django.conf import settings
from django.core.cache import cache


def get_cache_key(prefix, *args):
    key_str = ":".join(str(arg) for arg in args)
    return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"


def cache_network_data(prefix, *key_args, data, timeout=None):
    key = get_cache_key(prefix, *key_args)
    timeout = timeout or getattr(settings, "CACHE_TTL", 300)
    cache.set(key, data, timeout)
    return data


def get_cached_network_data(prefix, *key_args):
    key = get_cache_key(prefix, *key_args)
    return cache.get(key)
