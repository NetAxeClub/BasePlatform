from typing import Dict, Callable, Any

import logging

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
            logger.info(f"注册处理器: {key} -> {func.__name__}")
            return func
        return decorator

    @classmethod
    def get_processor(cls, vendor: str, device_type: str, collection_type: str, method: str = 'netmiko') -> Callable:
        """
        获取对应的处理器方法
        """
        key = f"{vendor}:{device_type}:{collection_type}:{method}"
        processor = cls._processors.get(key)
        if processor:
            logger.debug(f"找到处理器: {key}")
        return processor


# 便捷装饰器
register_processor = ProcessorRegistry.register
get_processor = ProcessorRegistry.get_processor
