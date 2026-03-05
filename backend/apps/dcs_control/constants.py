# -*- coding: utf-8 -*-
"""
DCS Control 模块常量定义。

统一厂商标识大小写，避免 views.py 用 'hillstone' / tasks.py 用 'Hillstone'
两套写法导致的运行时隐患。
"""
from enum import Enum


class Vendor(str, Enum):
    """
    防火墙厂商标识枚举，统一大小写格式。

    继承 str 使枚举值可直接作字符串比较：
        Vendor.HILLSTONE == 'Hillstone'  # True
    """
    HILLSTONE = 'Hillstone'
    H3C = 'H3C'
    HUAWEI = 'Huawei'

    @classmethod
    def normalize(cls, raw: str) -> str:
        """
        将任意大小写输入转为规范格式字符串。

        >>> Vendor.normalize('hillstone')
        'Hillstone'
        >>> Vendor.normalize('H3C')
        'H3C'
        >>> Vendor.normalize('huawei')
        'Huawei'
        >>> Vendor.normalize('unknown')
        'unknown'   # 无法识别时原样返回，由上层校验处理
        """
        mapping = {v.value.lower(): v.value for v in cls}
        return mapping.get(raw.lower(), raw)

    @classmethod
    def choices(cls) -> list:
        """返回所有合法厂商值列表，用于 JSON Schema enum 字段。"""
        return [v.value for v in cls]
