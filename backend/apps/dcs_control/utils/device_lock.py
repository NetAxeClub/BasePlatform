# -*- coding: utf-8 -*-
"""
设备操作原子锁。

解决原 run_cmd_config / run_netconf_config 中 cache.get + cache.set 非原子、
time.sleep(30) 阻塞 Worker 的问题。

cache.add 在 Redis 后端是原子操作：key 不存在时才写入，返回 True；
key 已存在时不覆盖，返回 False。相比 get + set，消除了两次调用间的竞态窗口。
"""
import logging
from contextlib import contextmanager

from django.core.cache import cache

log = logging.getLogger(__name__)

LOCK_TIMEOUT = 300  # 锁最长持有时间（秒），超时自动释放，防止崩溃造成死锁


class DeviceBusyError(Exception):
    """设备当前被其他任务占用，拒绝新操作。"""


@contextmanager
def device_lock(ip: str, timeout: int = LOCK_TIMEOUT):
    """
    原子设备锁上下文管理器。

    用法::

        from apps.dcs_control.utils.device_lock import device_lock, DeviceBusyError

        try:
            with device_lock('192.168.1.1'):
                do_config(...)
        except DeviceBusyError as e:
            return False, '', str(e)

    :param ip: 设备管理 IP
    :param timeout: 锁最长持有秒数，到期自动释放
    :raises DeviceBusyError: 当设备已被其他任务锁定时抛出
    """
    lock_key = f'dcs_device_lock_{ip}'
    acquired = cache.add(lock_key, '1', timeout=timeout)
    if not acquired:
        log.warning("设备锁获取失败（已被占用）: ip=%s", ip)
        raise DeviceBusyError(
            f"设备 {ip} 正在被操作中，请稍后重试（锁超时 {timeout}s）"
        )
    log.debug("设备锁已获取: ip=%s, timeout=%ss", ip, timeout)
    try:
        yield
    finally:
        cache.delete(lock_key)
        log.debug("设备锁已释放: ip=%s", ip)
