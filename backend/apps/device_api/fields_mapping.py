"""采集类型字段定义与厂商处理器映射。"""

# 采集结果公共元数据字段（由 inject_metadata 注入）
COMMON_METADATA_FIELDS = ("hostip", "hostname", "idc_name", "log_time")

# 默认按 list 类型存储的字段（用于缺省值补齐）
LIST_VALUE_FIELDS = {"memberports", "location"}


DEV_MAPPING = [
    {"label": "设备型号: model_name", "value": "model_name"},
    {"label": "软件版本: soft_version", "value": "soft_version"},
    {"label": "补丁版本: patch_version", "value": "patch_version"},
]

ARP_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "IP地址: ipaddress", "value": "ipaddress"},
    {"label": "Mac地址: macaddress", "value": "macaddress"},
    {"label": "age: aging", "value": "aging"},
    {"label": "类型: type", "value": "type"},
    {"label": "vlan: vlan", "value": "vlan"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "vpn 实例: vpninstance", "value": "vpninstance"},
]

MAC_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "mac地址: macaddress", "value": "macaddress"},
    {"label": "vlan地址: vlan", "value": "vlan"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "类型: type", "value": "type"},
]

LLDP_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "本地接口: local_interface", "value": "local_interface"},
    {"label": "chassis_id: chassis_id", "value": "chassis_id"},
    {"label": "邻居端口: neighbor_port", "value": "neighbor_port"},
    {"label": "端口描述: portdescription", "value": "portdescription"},
    {"label": "相邻系统名: neighborsysname", "value": "neighborsysname"},
    {"label": "管理IP: management_ip", "value": "management_ip"},
    {"label": "管理类型: management_type", "value": "management_type"},
    {"label": "邻居IP: neighbor_ip", "value": "neighbor_ip"},
]

IP_INTERFACE_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "简介: interface", "value": "interface"},
    {"label": "线路状态: line_status", "value": "line_status"},
    {"label": "协议状态: protocol_status", "value": "protocol_status"},
    {"label": "IP地址: ipaddress", "value": "ipaddress"},
    {"label": "ip掩码: ipmask", "value": "ipmask"},
    {"label": "IP类型: ip_type", "value": "ip_type"},
    {"label": "mtu: mtu", "value": "mtu"},
    {"label": "地址区间: location", "value": "location"},
]

INTERFACE_BRIEF_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "状态: status", "value": "status"},
    {"label": "速率: speed", "value": "speed"},
    {"label": "duplex: duplex", "value": "duplex"},
    {"label": "描述: description", "value": "description"},
]

AGGRE_PORT_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "aggregroup: aggregroup", "value": "aggregroup"},
    {"label": "成员端口: memberports", "value": "memberports"},
    {"label": "状态: status", "value": "status"},
    {"label": "模型: mode", "value": "mode"},
]

field_mapping = {
    "version": {
        "label": "VERSION",
        "value": "version",
        "icon": "version",
        "mapping_fields": DEV_MAPPING,
    },
    "arp": {
        "label": "ARP",
        "value": "arp",
        "icon": "arp",
        "mapping_fields": ARP_MAPPING,
    },
    "arp_evpn": {
        "label": "ARP EVPN",
        "value": "arp_evpn",
        "icon": "arp",
        "mapping_fields": ARP_MAPPING,
    },
    "mac": {
        "label": "MAC",
        "value": "mac",
        "icon": "mac",
        "mapping_fields": MAC_MAPPING,
    },
    "mac_evpn": {
        "label": "MAC EVPN",
        "value": "mac_evpn",
        "icon": "mac",
        "mapping_fields": MAC_MAPPING,
    },
    "lldp": {
        "label": "LLDP",
        "value": "lldp",
        "icon": "lldp",
        "mapping_fields": LLDP_MAPPING,
    },
    "interface_brief": {
        "label": "二层接口",
        "value": "interface_brief",
        "icon": "interface-summary",
        "mapping_fields": INTERFACE_BRIEF_MAPPING,
    },
    "ip_interface": {
        "label": "三层接口",
        "value": "ip_interface",
        "icon": "ip-interface",
        "mapping_fields": IP_INTERFACE_MAPPING,
    },
    "aggre_port": {
        "label": "聚合端口",
        "value": "aggre_port",
        "icon": "aggregation-port",
        "mapping_fields": AGGRE_PORT_MAPPING,
    },
}

# 所有采集类型列表，用于创建空白方案时自动生成各类型的子方案
DEFAULT_COLLECTION_TYPES = list(field_mapping.keys())


def get_collection_output_fields(collection_type):
    """获取某采集类型的标准入库字段列表。"""
    config = field_mapping.get(collection_type, {})
    fields = []
    for item in config.get("mapping_fields", []):
        value = item.get("value")
        if value and value not in fields:
            fields.append(value)
    return fields


def default_value_for_field(field_name):
    """返回字段的默认空值。list 字段用 []，其余用空字符串。"""
    return [] if field_name in LIST_VALUE_FIELDS else ""

# 厂商到模块名和类名的映射（支持根据vendor_alias和collection_method查找）
# 格式: {vendor_alias: {method: (module_name, class_name)}}
# 如果某个厂商的所有method都使用同一个类，可以使用 'default' 作为method
vendor_mapping = {
    'H3C': {
        'netmiko': ('h3c', 'H3CPlan'),
        'netconf': ('h3c', 'H3CPlan'),
        'default': ('h3c', 'H3CPlan'),
    },
    'Huawei': {
        'netmiko': ('huawei', 'HuaweiPlan'),
        'netconf': ('huawei', 'HuaweiPlan'),
        'default': ('huawei', 'HuaweiPlan'),
    },
    'Cisco': {
        'netmiko': ('cisco', 'CiscoPlan'),
        'netconf': ('cisco', 'CiscoPlan'),
        'default': ('cisco', 'CiscoPlan'),
    },
    'CISCO': {
        'netmiko': ('cisco', 'CiscoPlan'),
        'netconf': ('cisco', 'CiscoPlan'),
        'default': ('cisco', 'CiscoPlan'),
    },
    'cisco': {
        'netmiko': ('cisco', 'CiscoPlan'),
        'netconf': ('cisco', 'CiscoPlan'),
        'default': ('cisco', 'CiscoPlan'),
    },
    'centec': {
        'netmiko': ('centec', 'CentecPlan'),
        'netconf': ('centec', 'CentecPlan'),
        'default': ('centec', 'CentecPlan'),
    },
    'Hillstone': {
        'netmiko': ('hillstone', 'HillstonePlan'),
        'netconf': ('hillstone', 'HillstonePlan'),
        'default': ('hillstone', 'HillstonePlan'),
    },
    'Maipu': {
        'netmiko': ('maipu', 'MaipuPlan'),
        'netconf': ('maipu', 'MaipuPlan'),
        'default': ('maipu', 'MaipuPlan'),
    },
    'Mellanox': {
        'netmiko': ('mellanox', 'MellanoxPlan'),
        'netconf': ('mellanox', 'MellanoxPlan'),
        'default': ('mellanox', 'MellanoxPlan'),
    },
    'Ruijie': {
        'netmiko': ('ruijie', 'RuiJiePlan'),
        'netconf': ('ruijie', 'RuiJiePlan'),
        'default': ('ruijie', 'RuiJiePlan'),
    },
    'ZTE': {
        'netmiko': ('zte', 'ZtePlan'),
        'netconf': ('zte', 'ZtePlan'),
        'default': ('zte', 'ZtePlan'),
    },
}


def get_vendor_class(vendor_alias, method='default'):
    """
    根据vendor_alias和method获取对应的模块名和类名
    
    Args:
        vendor_alias: 厂商别名
        method: 采集方法 (netmiko/netconf/default)
        
    Returns:
        tuple: (module_name, class_name) 或 (None, None) 如果未找到
    """
    vendor_config = vendor_mapping.get(vendor_alias)
    if not vendor_config:
        return None, None
    
    # 先尝试根据method查找
    result = vendor_config.get(method.lower())
    if result:
        return result
    
    # 如果未找到，尝试使用default
    result = vendor_config.get('default')
    if result:
        return result
    
    # 如果都没有，返回第一个值（向后兼容）
    if vendor_config:
        return list(vendor_config.values())[0]
    
    return None, None
