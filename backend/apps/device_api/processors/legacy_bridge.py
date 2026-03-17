"""长尾厂商处理器桥接层。

将已存在于 tools/ 的厂商解析逻辑注册到 processors/，使解析入口统一走
ProcessorRegistry，同时保留现有解析实现，降低迁移风险。
"""

from apps.device_api.processors.base import register_processor
from apps.device_api.tools.centec import CentecPlan
from apps.device_api.tools.maipu import MaipuPlan
from apps.device_api.tools.mellanox import MellanoxPlan
from apps.device_api.tools.zte import ZtePlan

BRIDGE_COLLECTION_TYPES = (
    "arp",
    "mac",
    "lldp",
    "interface_brief",
    "ip_interface",
    "aggre_port",
)

BRIDGE_TOOL_CLASS_MAP = {
    "ZTE": ZtePlan,
    "Maipu": MaipuPlan,
    "Mellanox": MellanoxPlan,
    "centec": CentecPlan,
    "Centec": CentecPlan,
}


def _build_bridge_processor(vendor: str, collection_type: str, tool_class):
    method_name = f"get_{collection_type}"
    tool_method = getattr(tool_class, method_name)

    @register_processor(vendor=vendor, device_type="", collection_type=collection_type, method="netmiko")
    def _processor(data):
        return tool_method(data)

    _processor.__name__ = f"process_{vendor.lower()}_{collection_type}_netmiko_bridge"
    return _processor


for _vendor, _tool_class in BRIDGE_TOOL_CLASS_MAP.items():
    for _collection_type in BRIDGE_COLLECTION_TYPES:
        _build_bridge_processor(_vendor, _collection_type, _tool_class)

