# -*- coding: utf-8 -*-
"""
华三（H3C）防火墙适配器。

华三设备通过 Netconf 协议下发，每类操作对应不同的类方法名（class_method）。
委托给 FirewallMain 中已有的 h3c_xxx_detail() 方法。
"""
from __future__ import annotations

from apps.dcs_control.firewall.base import FirewallAdapter
from apps.dcs_control.firewall.registry import register


@register('H3C')
class H3CAdapter(FirewallAdapter):
    """
    华三防火墙适配器。

    所有配置下发均通过 Netconf 完成。
    委托 FirewallMain.h3c_xxx_detail() 生成具体 XML 命令。
    """

    @property
    def protocol(self) -> str:
        return 'NETCONF'

    # ── 地址对象 ──────────────────────────────────────────────────────────────

    def address_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_oms_objs')。
        委托 FirewallMain.h3c_address_detail()，其返回 (flag, cmds, back_off_cmds)。
        flag 由调用方决定是否传入 flow_engine。
        """
        flag, cmds, back_off_cmds = self.fw.h3c_address_detail(**post_param)
        return cmds, back_off_cmds, 'config_oms_objs'

    # ── 服务对象 ──────────────────────────────────────────────────────────────

    def service_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_oms_service_objs')。
        委托 FirewallMain.h3c_service_detail()，其返回 (flag, cmds, back_off_cmds)。
        """
        flag, cmds, back_off_cmds = self.fw.h3c_service_detail(**post_param)
        return cmds, back_off_cmds, 'config_oms_service_objs'

    # ── DNAT ─────────────────────────────────────────────────────────────────

    def dnat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_h3c_dnat')。
        委托 FirewallMain.h3c_dnat_detail()，其返回 (flag, cmds, back_off_cmds)。
        """
        flag, cmds, back_off_cmds = self.fw.h3c_dnat_detail(**post_param)
        return cmds, back_off_cmds, 'config_h3c_dnat'

    # ── SNAT ─────────────────────────────────────────────────────────────────

    def snat_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_h3c_snat')。
        委托 FirewallMain.h3c_snat_detail()。
        """
        flag, cmds, back_off_cmds = self.fw.h3c_snat_detail(**post_param)
        return cmds, back_off_cmds, 'config_h3c_snat'

    # ── 安全策略 ──────────────────────────────────────────────────────────────

    def sec_policy_cmds(self, **post_param) -> tuple:
        """
        返回 (cmds, back_off_cmds, 'config_sec_policy')。
        委托 FirewallMain.h3c_sec_policy_detail()。
        """
        cmds, back_off_cmds = self.fw.h3c_sec_policy_detail(**post_param)
        return cmds, back_off_cmds, 'config_sec_policy'
