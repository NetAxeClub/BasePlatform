# -*- coding: utf-8 -*-
"""
一键封堵任务模块（迁移占位）。

当前实现仍在 tasks.py 中的 bulk_deny_by_address。
待迁移完成后，此处将包含完整实现并移除 tasks.py 中的对应代码。
"""
from apps.dcs_control.tasks import bulk_deny_by_address  # noqa: F401
