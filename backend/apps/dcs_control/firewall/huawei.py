# -*- coding: utf-8 -*-
"""
华为（Huawei）防火墙适配器。

华为设备通过 Netconf 协议下发，每类操作对应不同的类方法名（class_method）。
委托给 FirewallMain 中已有的 huawei_xxx_detail() / huawei_xxx() 方法。
"""
from __future__ import annotations

from apps.dcs_control.firewall.base import FirewallAdapter
from apps.dcs_control.firewall.registry import register


@register('Huawei')
class HuaweiAdapter(FirewallAdapter):
    """
    华为防火墙适配器。

    所有配置下发均通过 Netconf 完成。
    委托 FirewallMain.huawei_xxx_detail() 生成具体 XML 命令。
    """

    @property
    def protocol(self) -> str:
        return 'NETCONF'

    # ── 地址对象 ──────────────────────────────────────────────────────────────

    def address_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_address')。
        委托 FirewallMain.huawei_address_detail()，其返回 (cmds, back_off_cmds)。
        """
        cmds, back_off_cmds = self.fw.huawei_address_detail(**post_param)
        return cmds, back_off_cmds, 'config_address'

    # ── 服务对象 ──────────────────────────────────────────────────────────────

    def service_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_service')。
        委托 FirewallMain.huawei_service_detail()，其返回 (cmds, back_off_cmds)。
        """
        cmds, back_off_cmds = self.fw.huawei_service_detail(**post_param)
        return cmds, back_off_cmds, 'config_service'

    # ── DNAT ─────────────────────────────────────────────────────────────────

    def dnat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_dnat')。
        委托 FirewallMain.huawei_dnat_detail()，其返回 (cmds, back_off_cmds)。
        """
        cmds, back_off_cmds = self.fw.huawei_dnat_detail(**post_param)
        return cmds, back_off_cmds, 'config_dnat'

    # ── SNAT ─────────────────────────────────────────────────────────────────

    def snat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_snat')。
        委托 FirewallMain.huawei_snat_detail()，其返回 (cmds, back_off_cmds)。
        """
        cmds, back_off_cmds = self.fw.huawei_snat_detail(**post_param)
        return cmds, back_off_cmds, 'config_snat'

    # ── 安全策略 ──────────────────────────────────────────────────────────────

    def sec_policy_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_sec_policy')。
        委托 FirewallMain.huawei_sec_policy()，其返回 (cmds, back_off_cmds)。
        """
        cmds, back_off_cmds = self.fw.huawei_sec_policy(**post_param)
        return cmds, back_off_cmds, 'config_sec_policy'
