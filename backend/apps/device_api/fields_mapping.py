# 采集类型 需要入库的标准字段

APR_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "IP地址: ipaddress", "value": "ipaddress"},
    {"label": "Mac地址: macaddress", "value": "macaddress"},
    {"label": "age: aging", "value": "aging"},
    {"label": "类型: type", "value": "type"},
    {"label": "vlan: vlan", "value": "vlan"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "vpn 实例: vpninstance", "value": "vpninstance"}
]


MAC_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "mac地址: macaddress", "value": "macaddress"},
    {"label": "vlan地址: vlan", "value": "vlan"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "类型: type", "value": "type"}
]

LLDP_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "本地接口: local_interface", "value": "local_interface"},
    {"label": "chassis_id: chassis_id", "value": "chassis_id"},
    {"label": "邻居端口: neighbor_port", "value": "neighbor_port"},
    {"label": "端口描述: portdescription", "value": "portdescription"},
    {"label": "相邻系统名: neighborsysname", "value": "neighborsysname"},
    {"label": "管理IP: management_ip", "value": "management_ip"},
    {"label": "管理类型: management_type", "value": "management_type"},
    {"label": "邻居IP: neighbor_ip", "value": "neighbor_ip"}
]

IP_INTERFACE_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "简介: interface", "value": "interface"},
    {"label": "线路状态: line_status", "value": "line_status"},
    {"label": "协议状态: protocol_status", "value": "protocol_status"},
    {"label": "IP地址: ipaddress", "value": "ipaddress"},
    {"label": "ip掩码:  ipmask", "value": " ipmask"},
    {"label": "IP类型:  ip_type", "value": " ip_type"},
    {"label": "mtu: mtu", "value": "mtu"}
]


INTERFACE_BRIEF_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "状态: status", "value": "status"},
    {"label": "速率: speed", "value": "speed"},
    {"label": "duplex: duplex", "value": "duplex"},
    {"label": "描述: description", "value": "description"}
]

AGGRE_PORT_MAPPING = [
    # {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "aggregroup: aggregroup", "value": "aggregroup"},
    {"label": "成员端口: memberports", "value": "memberports"},
    {"label": "状态: status", "value": "status"},
    {"label": "模型: mode", "value": "mode"}
]


field_mapping = {
    "arp": {"label": "ARP", "value": "arp", "icon": "arp", "mapping_fields": APR_MAPPING},
    "mac": {"label": "MAC", "value": "mac", "icon": "mac", "mapping_fields": MAC_MAPPING},
    "lldp": {"label": "LLDP", "value": "lldp", "icon": "lldp", "mapping_fields": LLDP_MAPPING},
    "ip_interface": {"label": "三层接口", "value": "ip_interface", "icon": "ip-interface", "mapping_fields": IP_INTERFACE_MAPPING},
    "interface_brief": {"label": "接口摘要", "value": "interface_brief", "icon": "interface-summary", "mapping_fields": INTERFACE_BRIEF_MAPPING},
    "aggre_port": {"label": "聚合端口", "value": "aggre_port", "icon": "aggregation-port", "mapping_fields": AGGRE_PORT_MAPPING}
}

# 厂商到模块名和类名的映射
vendor_mapping = {
    'H3C': ('h3c', 'H3CPlan'),
    'Huawei': ('huawei', 'HuaweiPlan'),
    'Cisco': ('cisco', 'CiscoPlan'),
    'CISCO': ('cisco', 'CiscoPlan'),
    'cisco': ('cisco', 'CiscoPlan'),
    'centec': ('centec', 'CentecPlan'),
    'Hillstone': ('hillstone', 'HillstonePlan'),
    'Maipu': ('maipu', 'MaipuPlan'),
    'Mellanox': ('mellanox', 'MellanoxPlan'),
    'Ruijie': ('ruijie', 'RuiJiePlan'),
    'ZTE': ('zte', 'ZtePlan'),
}
