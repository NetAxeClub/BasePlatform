# -*- coding: utf-8 -*-
"""
山石（Hillstone）防火墙适配器。

委托给 FirewallMain 中已有的 hillstone_xxx_detail() 方法，
在不破坏现有实现的前提下提供统一的策略接口。
"""
from __future__ import annotations

from apps.dcs_control.firewall.base import FirewallAdapter
from apps.dcs_control.firewall.registry import register

# 山石设备固定使用 SSH 模式下发，class_method 统一标识为 'Hillstone'
_SSH_CLASS_METHOD = 'Hillstone'


@register('Hillstone')
class HillstoneAdapter(FirewallAdapter):
    """
    山石防火墙适配器。

    所有配置下发均通过 SSH（Netmiko）完成。
    委托 FirewallMain.hillstone_xxx_detail() 生成具体命令列表。
    """

    @property
    def protocol(self) -> str:
        return 'SSH'

    # ── 地址对象 ──────────────────────────────────────────────────────────────

    def address_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'Hillstone')。
        委托 FirewallMain.hillstone_address_detail()。
        """
        cmds, back_off_cmds = self.fw.hillstone_address_detail(**post_param)
        return cmds, back_off_cmds, _SSH_CLASS_METHOD

    # ── 服务对象 ──────────────────────────────────────────────────────────────

    def service_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'Hillstone')。
        委托 FirewallMain.hillstone_service_detail()。
        """
        cmds, back_off_cmds = self.fw.hillstone_service_detail(**post_param)
        return cmds, back_off_cmds, _SSH_CLASS_METHOD

    # ── DNAT ─────────────────────────────────────────────────────────────────

    def dnat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'Hillstone')。
        委托 FirewallMain.hillstone_dnat_detail()。
        """
        cmds, back_off_cmds = self.fw.hillstone_dnat_detail(**post_param)
        return cmds, back_off_cmds, _SSH_CLASS_METHOD

    # ── SNAT ─────────────────────────────────────────────────────────────────

    def snat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'Hillstone')。
        委托 FirewallMain.hillstone_snat_detail()。
        """
        cmds, back_off_cmds = self.fw.hillstone_snat_detail(**post_param)
        return cmds, back_off_cmds, _SSH_CLASS_METHOD

    # ── 安全策略 ──────────────────────────────────────────────────────────────

    def sec_policy_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'Hillstone')。
        委托 FirewallMain.hillstone_sec_policy_detail()。
        """
        cmds, back_off_cmds = self.fw.hillstone_sec_policy_detail(**post_param)
        return cmds, back_off_cmds, _SSH_CLASS_METHOD
