# -*- coding: utf-8 -*-
"""
DCS Control 任务包（tasks_pkg）。

向后兼容桥接层：从原 tasks.py 中 re-export 所有 Celery 任务，
同时作为后续逐步迁移的目标目录。

迁移路径
--------
当前：views.py 及其他模块从 apps.dcs_control.tasks 导入
目标：逐步将各任务文件从 tasks.py 拆出到对应的 tasks_pkg/*.py 中，
     并在 tasks_pkg/__init__.py 中更新导入路径。

当完整迁移后，将原 tasks.py 重命名为 tasks_legacy.py 保留备份，
tasks_pkg/ 目录重命名为 tasks/，views.py 导入路径无需变更。
"""
from apps.dcs_control.tasks import (  # noqa: F401  (re-export)
    # Celery 任务
    address_set,
    service_set,
    config_snat,
    config_dnat,
    config_slb,
    config_sec_policy,
    bulk_deny_by_address,
    config_auto_switch,

    # 核心类（供 views.py 和其他模块使用）
    FirewallMain,
    SecFirewallMain,
    SecPolicyMain,

    # 工具函数
    run_cmd_config,
    run_netconf_config,
    get_firewall_zone,
    edit_sec_policy,
    send_msg_sec_manage,
)
