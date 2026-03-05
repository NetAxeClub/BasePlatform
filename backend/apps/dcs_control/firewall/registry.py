# -*- coding: utf-8 -*-
"""
防火墙适配器注册表。

使用方式::

    # 注册（通常在 Django AppConfig.ready() 中调用 register_all() 一次）
    from apps.dcs_control.firewall.registry import register_all, get_adapter

    register_all()

    # 使用
    fw_main = FirewallMain(hostip)
    adapter = get_adapter('Hillstone', fw_main)
    cmds, back_off, method = adapter.address_cmds(**post_param)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.dcs_control.firewall.base import FirewallAdapter

_REGISTRY: dict[str, type] = {}


def register(vendor: str):
    """
    适配器注册装饰器。

    用法::

        @register('Hillstone')
        class HillstoneAdapter(FirewallAdapter):
            ...
    """
    def decorator(cls):
        _REGISTRY[vendor] = cls
        return cls
    return decorator


def get_adapter(vendor: str, fw_main) -> 'FirewallAdapter':
    """
    根据厂商名获取适配器实例。

    :param vendor: 厂商标识，须与注册时一致（'Hillstone' / 'H3C' / 'Huawei'）
    :param fw_main: FirewallMain 实例
    :raises ValueError: 厂商未注册时抛出
    :returns: 对应厂商的 FirewallAdapter 实例
    """
    cls = _REGISTRY.get(vendor)
    if cls is None:
        registered = list(_REGISTRY.keys())
        raise ValueError(
            f"不支持的厂商: {vendor!r}，已注册厂商: {registered}"
        )
    return cls(fw_main)


def registered_vendors() -> list[str]:
    """返回所有已注册厂商名称列表。"""
    return list(_REGISTRY.keys())


def register_all() -> None:
    """
    触发所有适配器模块的导入，从而触发 @register 装饰器完成注册。
    在 Django AppConfig.ready() 或应用启动时调用一次。
    """
    # 延迟导入，避免在模块加载阶段产生循环依赖
    from apps.dcs_control.firewall import hillstone  # noqa: F401
    from apps.dcs_control.firewall import h3c        # noqa: F401
    from apps.dcs_control.firewall import huawei     # noqa: F401
