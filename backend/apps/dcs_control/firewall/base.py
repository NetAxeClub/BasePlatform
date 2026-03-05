# -*- coding: utf-8 -*-
"""
防火墙适配器抽象基类。

每个厂商实现此基类即可接入统一的流程引擎调度。
新增厂商只需：
  1. 继承 FirewallAdapter 实现所有抽象方法
  2. 在自己的模块中用 @register('VendorName') 注册
  3. 在 registry.register_all() 中 import 该模块

每个 build_xxx_cmds() 方法均返回三元组 (cmds, back_off_cmds, class_method)：
  - cmds: 下发命令（SSH 时为命令列表，Netconf 时为 XML 字符串/列表）
  - back_off_cmds: 回退命令
  - class_method: 'Hillstone' 表示 SSH 模式；其余字符串为 Netconf 类方法名
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class FirewallAdapter(ABC):
    """
    防火墙适配器抽象基类。

    :param fw_main: FirewallMain 实例，由各任务传入，包含设备登录信息与方法委托
    """

    def __init__(self, fw_main: Any):
        # FirewallMain 实例：包含 dev_info、dev_infos 及所有厂商特定方法
        self.fw = fw_main

    # ── 地址对象 ─────────────────────────────────────────────────────────────

    @abstractmethod
    def address_cmds(self, **post_param) -> tuple:
        """
        生成地址对象操作命令。

        :returns: (cmds, back_off_cmds, class_method)
        """

    # ── 服务对象 ─────────────────────────────────────────────────────────────

    @abstractmethod
    def service_cmds(self, **post_param) -> tuple:
        """
        生成服务对象操作命令。

        :returns: (cmds, back_off_cmds, class_method)
        """

    # ── DNAT ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def dnat_cmds(self, **post_param) -> tuple:
        """
        生成 DNAT 规则操作命令。

        :returns: (cmds, back_off_cmds, class_method)
        """

    # ── SNAT ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def snat_cmds(self, **post_param) -> tuple:
        """
        生成 SNAT 规则操作命令。

        :returns: (cmds, back_off_cmds, class_method)
        """

    # ── 安全策略 ──────────────────────────────────────────────────────────────

    @abstractmethod
    def sec_policy_cmds(self, **post_param) -> tuple:
        """
        生成安全策略操作命令。

        :returns: (cmds, back_off_cmds, class_method)
        """

    # ── 协议标识（只读属性）────────────────────────────────────────────────────

    @property
    @abstractmethod
    def protocol(self) -> str:
        """返回下发协议: 'SSH' 或 'NETCONF'"""

    def is_ssh(self) -> bool:
        return self.protocol == 'SSH'

    def is_netconf(self) -> bool:
        return self.protocol == 'NETCONF'
