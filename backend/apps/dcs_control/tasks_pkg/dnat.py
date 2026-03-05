# -*- coding: utf-8 -*-
"""
DNAT / SNAT 任务模块（迁移占位）。

当前实现仍在 tasks.py 中的 config_dnat 和 config_snat。
"""
from apps.dcs_control.tasks import config_dnat, config_snat  # noqa: F401
