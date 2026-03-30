from typing import Dict, Callable, Any, List

import logging
from apps.device_api.fields_mapping import (
    get_collection_output_fields,
    default_value_for_field,
)

logger = logging.getLogger(__name__)


class ProcessorRegistry:
    """采集数据处理器注册中心"""
    _processors: Dict[str, Callable] = {}

    @classmethod
    def register(cls, vendor: str, device_type: str, collection_type: str, method: str = 'netmiko'):
        """
        注册处理器的装饰器
        :param vendor: 厂商
        :param device_type: 设备类型
        :param collection_type: 采集类型
        :param method: 采集方式 (netmiko/netconf)
        """
        def decorator(func: Callable):
            key = f"{vendor}:{device_type}:{collection_type}:{method}"
            cls._processors[key] = func
            # logger.info(f"注册处理器: {key} -> {func.__name__}")
            return func
        return decorator

    @classmethod
    def get_processor(cls, vendor: str, device_type: str, collection_type: str, method: str = 'netmiko') -> Callable:
        """
        获取对应的处理器方法。
        查找顺序：
        1. 精确匹配 vendor:device_type:collection_type:method
        2. 降级匹配 vendor::collection_type:method（注册时未指定 device_type）
        """
        key = f"{vendor}:{device_type}:{collection_type}:{method}"
        processor = cls._processors.get(key)
        if processor:
            logger.debug(f"找到处理器: {key}")
            return processor
        # 降级：不限设备类型
        key_fallback = f"{vendor}::{collection_type}:{method}"
        processor = cls._processors.get(key_fallback)
        if processor:
            logger.debug(f"找到处理器 (无设备类型限制): {key_fallback}")
        return processor


# 便捷装饰器
register_processor = ProcessorRegistry.register
get_processor = ProcessorRegistry.get_processor


def normalize_processed_data(collection_type: str, data: Any) -> List[dict]:
    """按采集类型标准字段补齐处理结果。

    - 入参支持 dict/list，统一转成 list[dict]
    - 使用 fields_mapping.py 中定义的字段作为标准字段集合
    - 缺失字段自动补空值（list 字段补 []，其他补 ''）
    """
    if data is None:
        return []

    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        return []

    standard_fields = get_collection_output_fields(collection_type)
    if not standard_fields:
        return [row for row in records if isinstance(row, dict)]

    normalized = []
    for row in records:
        if not isinstance(row, dict):
            continue

        item = {}
        for field in standard_fields:
            value = row.get(field)
            item[field] = value if value is not None else default_value_for_field(field)

        # 保留标准字段之外的扩展字段，避免丢失有用信息
        for key, value in row.items():
            if key not in item:
                item[key] = value

        normalized.append(item)

    return normalized
