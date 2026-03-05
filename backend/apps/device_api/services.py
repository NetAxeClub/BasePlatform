# -*- coding: utf-8 -*-
"""
[DEPRECATED] 此文件已废弃，所有功能已迁移至 services_new.py。
请将所有 import 从 services 改为 services_new。

此文件仅作为兼容性转发层保留，计划在确认无残留引用后删除。
"""
# 兼容性重新导出：确保旧的 `from apps.device_api.services import X` 不立即报错
from apps.device_api.services_new import (  # noqa: F401
    DeviceCollectionService,
    FieldMappingDriver,
    _strip_netconf_filter_wrapper,
)
