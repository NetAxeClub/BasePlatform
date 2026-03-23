"""采集类型字段定义与厂商处理器映射。"""

# 采集结果公共元数据字段（由 inject_metadata 注入）
COMMON_METADATA_FIELDS = ("hostip", "hostname", "idc_name", "log_time")

# 默认按 list 类型存储的字段（用于缺省值补齐）
LIST_VALUE_FIELDS = {
    "memberports",
    "location",
    "bd_ids",
    "vnis",
    "vrfs",
    "nve_ids",
    "evidence",
    "schema_samples",
    "items",
    "src_addr",
    "dst_addr",
    "service",
    "logs",
    "global_ip",
    "global_port",
    "local_ip",
    "local_port",
    "local_exclude_ip",
    "trans_ip",
    "destination_ip",
    "destination_port",
}
RAW_NETMIKO_COLLECTION_TYPES = {
    "cli_output_capability",
    "security_policy",
    "dnat",
    "snat",
}


DEV_MAPPING = [
    {"label": "设备序列号: serial_num", "value": "serial_num"},
    {"label": "厂商别名: vendor_alias", "value": "vendor_alias"},
    {"label": "设备型号: model_name", "value": "model_name"},
    {"label": "软件版本: soft_version", "value": "soft_version"},
    {"label": "补丁版本: patch_version", "value": "patch_version"},
]

CPU_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "CPU名称: cpu_name", "value": "cpu_name"},
    {"label": "CPU利用率: cpu_usage", "value": "cpu_usage"},
    {"label": "采样窗口: sample_window", "value": "sample_window"},
    {"label": "状态: status", "value": "status"},
]

MEMORY_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "内存池: memory_name", "value": "memory_name"},
    {"label": "已使用内存: used_memory", "value": "used_memory"},
    {"label": "总内存: total_memory", "value": "total_memory"},
    {"label": "使用率: memory_usage", "value": "memory_usage"},
    {"label": "状态: status", "value": "status"},
]

BOARD_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "板卡名称: board_name", "value": "board_name"},
    {"label": "板卡型号: board_model", "value": "board_model"},
    {"label": "序列号: serial_num", "value": "serial_num"},
    {"label": "状态: status", "value": "status"},
]

IRF_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "机框编号: chassis_id", "value": "chassis_id"},
    {"label": "成员编号: member_id", "value": "member_id"},
    {"label": "槽位编号: slot", "value": "slot"},
    {"label": "角色: role", "value": "role"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "MAC地址: mac", "value": "mac"},
]

STACK_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "成员编号: member_id", "value": "member_id"},
    {"label": "槽位编号: slot", "value": "slot"},
    {"label": "角色: role", "value": "role"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "MAC地址: mac", "value": "mac"},
]

TRANSCEIVER_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "光模块型号: transceiver_model", "value": "transceiver_model"},
    {"label": "序列号: serial_num", "value": "serial_num"},
    {"label": "厂商: vendor_name", "value": "vendor_name"},
    {"label": "状态: status", "value": "status"},
]

STORAGE_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "存储名称: storage_name", "value": "storage_name"},
    {"label": "已使用空间: used_space", "value": "used_space"},
    {"label": "总空间: total_space", "value": "total_space"},
    {"label": "使用率: storage_usage", "value": "storage_usage"},
    {"label": "状态: status", "value": "status"},
]

ENVIRONMENT_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "指标类型: metric_type", "value": "metric_type"},
    {"label": "指标名称: metric_name", "value": "metric_name"},
    {"label": "指标值: metric_value", "value": "metric_value"},
    {"label": "单位: unit", "value": "unit"},
    {"label": "状态: status", "value": "status"},
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

MAC_BD_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "mac地址: macaddress", "value": "macaddress"},
    {"label": "BD ID: bd_id", "value": "bd_id"},
    {"label": "VLAN: vlan", "value": "vlan"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "类型: type", "value": "type"},
]

MAC_VXLAN_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "mac地址: macaddress", "value": "macaddress"},
    {"label": "BD ID: bd_id", "value": "bd_id"},
    {"label": "VNID: vn_id", "value": "vn_id"},
    {"label": "源IP: source_ip", "value": "source_ip"},
    {"label": "对端IP: peer_ip", "value": "peer_ip"},
    {"label": "隧道类型: tunnel_type", "value": "tunnel_type"},
    {"label": "类型: type", "value": "type"},
]

VXLAN_CAPABILITY_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "存在BD配置: has_bd", "value": "has_bd"},
    {"label": "BD数量: bd_count", "value": "bd_count"},
    {"label": "BD编号: bd_ids", "value": "bd_ids"},
    {"label": "存在VXLAN VNI配置: has_vxlan_vni", "value": "has_vxlan_vni"},
    {"label": "VNI数量: vni_count", "value": "vni_count"},
    {"label": "VNI列表: vnis", "value": "vnis"},
    {"label": "存在NVE配置: has_nve", "value": "has_nve"},
    {"label": "NVE ID列表: nve_ids", "value": "nve_ids"},
    {"label": "存在EVPN BGP配置: has_evpn_bgp", "value": "has_evpn_bgp"},
    {"label": "EVPN地址族数量: evpn_af_count", "value": "evpn_af_count"},
    {"label": "EVPN相关VRF: vrfs", "value": "vrfs"},
    {"label": "证据: evidence", "value": "evidence"},
]

NETCONF_CAPABILITY_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "Schema数量: schema_count", "value": "schema_count"},
    {"label": "OpenConfig数量: openconfig_schema_count", "value": "openconfig_schema_count"},
    {"label": "存在BGP Schema: has_bgp_schema", "value": "has_bgp_schema"},
    {"label": "存在L2VPN Schema: has_l2vpn_schema", "value": "has_l2vpn_schema"},
    {"label": "存在IFMGR Schema: has_ifmgr_schema", "value": "has_ifmgr_schema"},
    {"label": "存在Telemetry Schema: has_telemetry_schema", "value": "has_telemetry_schema"},
    {"label": "Schema样本: schema_samples", "value": "schema_samples"},
]

CLI_OUTPUT_CAPABILITY_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "支持display irf: supports_irf_cli", "value": "supports_irf_cli"},
    {"label": "命令未识别: command_unrecognized", "value": "command_unrecognized"},
    {"label": "存在IRF成员: has_irf_members", "value": "has_irf_members"},
    {"label": "证据: evidence", "value": "evidence"},
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

HRP_STATE_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "HA状态: ha_state", "value": "ha_state"},
    {"label": "对端状态: peer_status", "value": "peer_status"},
    {"label": "心跳状态: heartbeat_status", "value": "heartbeat_status"},
    {"label": "配置主: config_master", "value": "config_master"},
    {"label": "切换ID: switch_id", "value": "switch_id"},
    {"label": "切换时间: switch_time", "value": "switch_time"},
    {"label": "切换原因: switch_reason", "value": "switch_reason"},
]

ADDRESS_SET_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "虚拟系统: vsys", "value": "vsys"},
    {"label": "名称: name", "value": "name"},
    {"label": "描述: description", "value": "description"},
    {"label": "对象类型: object_type", "value": "object_type"},
    {"label": "IP条目: ip", "value": "ip"},
    {"label": "范围条目: range", "value": "range"},
    {"label": "排除IP: exclude_ip", "value": "exclude_ip"},
    {"label": "排除范围: exclude_range", "value": "exclude_range"},
    {"label": "成员对象: member", "value": "member"},
    {"label": "解析结果: resolved", "value": "resolved"},
]

NAT_ADDRESS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "地址池名: name", "value": "name"},
    {"label": "虚拟系统: vsys", "value": "vsys"},
    {"label": "地址池类型: address_type", "value": "address_type"},
    {"label": "分段数量: section_count", "value": "section_count"},
    {"label": "分段明细: items", "value": "items"},
]

SERVICE_SET_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "虚拟系统: vsys", "value": "vsys"},
    {"label": "名称: name", "value": "name"},
    {"label": "描述: description", "value": "description"},
    {"label": "协议: protocol", "value": "protocol"},
    {"label": "目的端口起始: dst_port_min", "value": "dst_port_min"},
    {"label": "目的端口结束: dst_port_max", "value": "dst_port_max"},
    {"label": "源端口起始: src_port_min", "value": "src_port_min"},
    {"label": "源端口结束: src_port_max", "value": "src_port_max"},
    {"label": "服务明细: items", "value": "items"},
]

SLB_INFO_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "名称: name", "value": "name"},
    {"label": "类型: slb_type", "value": "slb_type"},
    {"label": "虚拟IP: vip", "value": "vip"},
    {"label": "协议: protocol", "value": "protocol"},
    {"label": "端口: port", "value": "port"},
    {"label": "描述: description", "value": "description"},
    {"label": "成员明细: items", "value": "items"},
]

VRRP_INFO_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "VRID: vrid", "value": "vrid"},
    {"label": "虚拟IP: virtual_ip", "value": "virtual_ip"},
    {"label": "掩码: ipmask", "value": "ipmask"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "抢占模式: preempt_mode", "value": "preempt_mode"},
    {"label": "管理状态: admin_state", "value": "admin_state"},
    {"label": "配置状态: config_state", "value": "config_state"},
]

ZONE_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "安全域: name", "value": "name"},
    {"label": "类型: type", "value": "type"},
    {"label": "虚拟交换: vswitch", "value": "vswitch"},
    {"label": "接口数量: ifcount", "value": "ifcount"},
    {"label": "共享: shared", "value": "shared"},
]

SERVICE_PREDEFINED_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "名称: name", "value": "name"},
    {"label": "协议: protocol", "value": "protocol"},
    {"label": "目的端口起始: dst_port_min", "value": "dst_port_min"},
    {"label": "目的端口结束: dst_port_max", "value": "dst_port_max"},
    {"label": "源端口起始: src_port_min", "value": "src_port_min"},
    {"label": "源端口结束: src_port_max", "value": "src_port_max"},
    {"label": "超时: timeout", "value": "timeout"},
    {"label": "原始目的端口: raw_dst_port", "value": "raw_dst_port"},
    {"label": "原始源端口: raw_src_port", "value": "raw_src_port"},
]

POLICY_HIT_COUNT_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "规则ID: id", "value": "id"},
    {"label": "规则名: name", "value": "name"},
    {"label": "命中次数: count", "value": "count"},
]

SECURITY_POLICY_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "规则ID: rule_id", "value": "rule_id"},
    {"label": "规则名: name", "value": "name"},
    {"label": "动作: action", "value": "action"},
    {"label": "源安全域: src_zone", "value": "src_zone"},
    {"label": "目的安全域: dst_zone", "value": "dst_zone"},
    {"label": "源地址: src_addr", "value": "src_addr"},
    {"label": "目的地址: dst_addr", "value": "dst_addr"},
    {"label": "服务: service", "value": "service"},
    {"label": "日志配置: logs", "value": "logs"},
    {"label": "描述: description", "value": "description"},
    {"label": "命中次数: count", "value": "count"},
    {"label": "是否禁用: disabled", "value": "disabled"},
]

DNAT_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "规则ID: rule_id", "value": "rule_id"},
    {"label": "公网地址: global_ip", "value": "global_ip"},
    {"label": "公网端口: global_port", "value": "global_port"},
    {"label": "内网地址: local_ip", "value": "local_ip"},
    {"label": "内网端口: local_port", "value": "local_port"},
    {"label": "入口接口: ingress_interface", "value": "ingress_interface"},
    {"label": "源安全域: from_zone", "value": "from_zone"},
    {"label": "目的安全域: to_zone", "value": "to_zone"},
    {"label": "描述: description", "value": "description"},
    {"label": "是否禁用: disabled", "value": "disabled"},
    {"label": "跟踪方式: track", "value": "track"},
]

SNAT_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "规则ID: rule_id", "value": "rule_id"},
    {"label": "转换地址: trans_ip", "value": "trans_ip"},
    {"label": "源地址: local_ip", "value": "local_ip"},
    {"label": "源排除地址: local_exclude_ip", "value": "local_exclude_ip"},
    {"label": "目的地址: destination_ip", "value": "destination_ip"},
    {"label": "目的端口: destination_port", "value": "destination_port"},
    {"label": "模式: mode", "value": "mode"},
    {"label": "源安全域: source_zone", "value": "source_zone"},
    {"label": "目的安全域: destination_zone", "value": "destination_zone"},
    {"label": "出口接口: egress_interface", "value": "egress_interface"},
    {"label": "描述: description", "value": "description"},
    {"label": "是否禁用: disabled", "value": "disabled"},
    {"label": "跟踪方式: track", "value": "track"},
]

FAN_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "机框: chassis", "value": "chassis"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "风扇ID: fan_id", "value": "fan_id"},
    {"label": "风扇名称: fan_name", "value": "fan_name"},
    {"label": "在位状态: present", "value": "present"},
    {"label": "注册状态: register_state", "value": "register_state"},
    {"label": "状态: status", "value": "status"},
    {"label": "转速: speed", "value": "speed"},
    {"label": "模式: mode", "value": "mode"},
    {"label": "风向: airflow_direction", "value": "airflow_direction"},
    {"label": "期望风向: prefer_airflow_direction", "value": "prefer_airflow_direction"},
]

POWER_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "机框: chassis", "value": "chassis"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "电源ID: power_id", "value": "power_id"},
    {"label": "电源名称: power_name", "value": "power_name"},
    {"label": "在位状态: present", "value": "present"},
    {"label": "状态: status", "value": "status"},
    {"label": "模式: mode", "value": "mode"},
    {"label": "电流: current", "value": "current"},
    {"label": "电压: voltage", "value": "voltage"},
    {"label": "输出功率: output_power", "value": "output_power"},
]

TEMPERATURE_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "机框: chassis", "value": "chassis"},
    {"label": "槽位: slot", "value": "slot"},
    {"label": "传感器: sensor", "value": "sensor"},
    {"label": "状态: status", "value": "status"},
    {"label": "温度: temperature", "value": "temperature"},
]

CLOCK_STATUS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "设备时间: device_time", "value": "device_time"},
    {"label": "时区: timezone", "value": "timezone"},
    {"label": "星期: weekday", "value": "weekday"},
    {"label": "日期: device_date", "value": "device_date"},
    {"label": "日期时间: device_datetime", "value": "device_datetime"},
]

ROUTE_TABLE_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "前缀: prefix", "value": "prefix"},
    {"label": "下一跳: next_hop", "value": "next_hop"},
    {"label": "接口: interface", "value": "interface"},
    {"label": "协议: protocol", "value": "protocol"},
    {"label": "协议ID: protocol_id", "value": "protocol_id"},
    {"label": "子协议ID: sub_protocol_id", "value": "sub_protocol_id"},
    {"label": "进程ID: process_id", "value": "process_id"},
    {"label": "优先级: preference", "value": "preference"},
    {"label": "度量值: metric", "value": "metric"},
    {"label": "VRF: vrf", "value": "vrf"},
    {"label": "拓扑: topology", "value": "topology"},
    {"label": "邻居: neighbor", "value": "neighbor"},
    {"label": "路由年龄: age", "value": "age"},
    {"label": "Origin AS: origin_as", "value": "origin_as"},
    {"label": "Last AS: last_as", "value": "last_as"},
]

BGP_NEIGHBORS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "邻居IP: peer_ip", "value": "peer_ip"},
    {"label": "地址族: address_family", "value": "address_family"},
    {"label": "VRF: vrf", "value": "vrf"},
    {"label": "远端AS: remote_as", "value": "remote_as"},
    {"label": "状态: state", "value": "state"},
    {"label": "邻居组: peer_group", "value": "peer_group"},
    {"label": "对端Router ID: remote_router_id", "value": "remote_router_id"},
    {"label": "对等体类型: peer_type", "value": "peer_type"},
    {"label": "本地接口: connect_interface", "value": "connect_interface"},
    {"label": "更新源间隔: update_interval", "value": "update_interval"},
    {"label": "EBGP MaxHop: ebgp_max_hop", "value": "ebgp_max_hop"},
]

BGP_SUMMARY_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "地址族: address_family", "value": "address_family"},
    {"label": "VRF: vrf", "value": "vrf"},
    {"label": "总邻居数: total_peers", "value": "total_peers"},
    {"label": "已建立邻居数: established_peers", "value": "established_peers"},
    {"label": "未建立邻居数: non_established_peers", "value": "non_established_peers"},
    {"label": "主状态: dominant_state", "value": "dominant_state"},
]

OSPF_NEIGHBORS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "区域: area", "value": "area"},
    {"label": "本地接口: local_interface", "value": "local_interface"},
    {"label": "邻居Router ID: neighbor_router_id", "value": "neighbor_router_id"},
    {"label": "邻居地址: neighbor_ip", "value": "neighbor_ip"},
    {"label": "状态: state", "value": "state"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "Dead Time: dead_time", "value": "dead_time"},
]

OSPF_INTERFACES_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "区域: area", "value": "area"},
    {"label": "本地接口: local_interface", "value": "local_interface"},
    {"label": "接口地址: interface_ip", "value": "interface_ip"},
    {"label": "网络类型: network_type", "value": "network_type"},
    {"label": "状态: state", "value": "state"},
    {"label": "Cost: cost", "value": "cost"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "DR: dr", "value": "dr"},
    {"label": "BDR: bdr", "value": "bdr"},
    {"label": "Hello间隔: hello_interval", "value": "hello_interval"},
    {"label": "Dead间隔: dead_interval", "value": "dead_interval"},
]

ISIS_NEIGHBORS_MAPPING = [
    {"label": "主机IP: hostip", "value": "hostip"},
    {"label": "主机名称: hostname", "value": "hostname"},
    {"label": "机房名称: idc_name", "value": "idc_name"},
    {"label": "邻居System ID: system_id", "value": "system_id"},
    {"label": "本地接口: local_interface", "value": "local_interface"},
    {"label": "Circuit ID: circuit_id", "value": "circuit_id"},
    {"label": "状态: state", "value": "state"},
    {"label": "Hold Time: hold_time", "value": "hold_time"},
    {"label": "邻居类型: neighbor_type", "value": "neighbor_type"},
    {"label": "优先级: priority", "value": "priority"},
    {"label": "区域地址: area", "value": "area"},
    {"label": "邻居地址: peer_ip", "value": "peer_ip"},
    {"label": "Up时间: uptime", "value": "uptime"},
]

field_mapping = {
    "device_identity": {
        "label": "DEVICE IDENTITY",
        "value": "device_identity",
        "icon": "identity",
        "mapping_fields": DEV_MAPPING,
    },
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
    "mac_bd": {
        "label": "MAC BD",
        "value": "mac_bd",
        "icon": "mac",
        "mapping_fields": MAC_BD_MAPPING,
    },
    "mac_vxlan": {
        "label": "MAC VXLAN",
        "value": "mac_vxlan",
        "icon": "mac",
        "mapping_fields": MAC_VXLAN_MAPPING,
    },
    "mac_vxlan_control": {
        "label": "MAC VXLAN CONTROL",
        "value": "mac_vxlan_control",
        "icon": "mac",
        "mapping_fields": MAC_VXLAN_MAPPING,
    },
    "vxlan_capability": {
        "label": "VXLAN CAPABILITY",
        "value": "vxlan_capability",
        "icon": "capability",
        "mapping_fields": VXLAN_CAPABILITY_MAPPING,
    },
    "netconf_capability": {
        "label": "NETCONF CAPABILITY",
        "value": "netconf_capability",
        "icon": "capability",
        "mapping_fields": NETCONF_CAPABILITY_MAPPING,
    },
    "cli_output_capability": {
        "label": "CLI OUTPUT CAPABILITY",
        "value": "cli_output_capability",
        "icon": "capability",
        "mapping_fields": CLI_OUTPUT_CAPABILITY_MAPPING,
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
    "hrp_state": {
        "label": "双机热备状态",
        "value": "hrp_state",
        "icon": "ha-status",
        "mapping_fields": HRP_STATE_MAPPING,
    },
    "address_set": {
        "label": "地址对象",
        "value": "address_set",
        "icon": "address-object",
        "mapping_fields": ADDRESS_SET_MAPPING,
    },
    "nat_address": {
        "label": "NAT地址池",
        "value": "nat_address",
        "icon": "nat-address",
        "mapping_fields": NAT_ADDRESS_MAPPING,
    },
    "service_set": {
        "label": "服务对象",
        "value": "service_set",
        "icon": "service",
        "mapping_fields": SERVICE_SET_MAPPING,
    },
    "slb_info": {
        "label": "SLB信息",
        "value": "slb_info",
        "icon": "slb",
        "mapping_fields": SLB_INFO_MAPPING,
    },
    "vrrp_info": {
        "label": "VRRP信息",
        "value": "vrrp_info",
        "icon": "vrrp",
        "mapping_fields": VRRP_INFO_MAPPING,
    },
    "zone": {
        "label": "安全域",
        "value": "zone",
        "icon": "zone",
        "mapping_fields": ZONE_MAPPING,
    },
    "service_predefined": {
        "label": "预定义服务",
        "value": "service_predefined",
        "icon": "service",
        "mapping_fields": SERVICE_PREDEFINED_MAPPING,
    },
    "policy_hit_count": {
        "label": "策略命中",
        "value": "policy_hit_count",
        "icon": "policy-hit",
        "mapping_fields": POLICY_HIT_COUNT_MAPPING,
    },
    "security_policy": {
        "label": "安全策略",
        "value": "security_policy",
        "icon": "security-policy",
        "mapping_fields": SECURITY_POLICY_MAPPING,
    },
    "dnat": {
        "label": "DNAT",
        "value": "dnat",
        "icon": "dnat",
        "mapping_fields": DNAT_MAPPING,
    },
    "snat": {
        "label": "SNAT",
        "value": "snat",
        "icon": "snat",
        "mapping_fields": SNAT_MAPPING,
    },
    "fan_status": {
        "label": "风扇状态",
        "value": "fan_status",
        "icon": "fan-status",
        "mapping_fields": FAN_STATUS_MAPPING,
    },
    "power_status": {
        "label": "电源状态",
        "value": "power_status",
        "icon": "power-status",
        "mapping_fields": POWER_STATUS_MAPPING,
    },
    "temperature_status": {
        "label": "温度状态",
        "value": "temperature_status",
        "icon": "temperature-status",
        "mapping_fields": TEMPERATURE_STATUS_MAPPING,
    },
    "cpu_status": {
        "label": "CPU状态",
        "value": "cpu_status",
        "icon": "cpu-status",
        "mapping_fields": CPU_STATUS_MAPPING,
    },
    "memory_status": {
        "label": "内存状态",
        "value": "memory_status",
        "icon": "memory-status",
        "mapping_fields": MEMORY_STATUS_MAPPING,
    },
    "board_status": {
        "label": "板卡状态",
        "value": "board_status",
        "icon": "board-status",
        "mapping_fields": BOARD_STATUS_MAPPING,
    },
    "irf_status": {
        "label": "IRF状态",
        "value": "irf_status",
        "icon": "stack-status",
        "mapping_fields": IRF_STATUS_MAPPING,
    },
    "stack_status": {
        "label": "堆叠状态",
        "value": "stack_status",
        "icon": "stack-status",
        "mapping_fields": STACK_STATUS_MAPPING,
    },
    "transceiver_status": {
        "label": "光模块状态",
        "value": "transceiver_status",
        "icon": "transceiver-status",
        "mapping_fields": TRANSCEIVER_STATUS_MAPPING,
    },
    "storage_status": {
        "label": "存储状态",
        "value": "storage_status",
        "icon": "storage-status",
        "mapping_fields": STORAGE_STATUS_MAPPING,
    },
    "environment_status": {
        "label": "环境状态",
        "value": "environment_status",
        "icon": "environment-status",
        "mapping_fields": ENVIRONMENT_STATUS_MAPPING,
    },
    "clock_status": {
        "label": "时钟状态",
        "value": "clock_status",
        "icon": "clock-status",
        "mapping_fields": CLOCK_STATUS_MAPPING,
    },
    "route_table": {
        "label": "路由表",
        "value": "route_table",
        "icon": "route-table",
        "mapping_fields": ROUTE_TABLE_MAPPING,
    },
    "bgp_neighbors": {
        "label": "BGP邻居",
        "value": "bgp_neighbors",
        "icon": "bgp-neighbors",
        "mapping_fields": BGP_NEIGHBORS_MAPPING,
    },
    "bgp_summary": {
        "label": "BGP汇总",
        "value": "bgp_summary",
        "icon": "bgp-summary",
        "mapping_fields": BGP_SUMMARY_MAPPING,
    },
    "ospf_neighbors": {
        "label": "OSPF邻居",
        "value": "ospf_neighbors",
        "icon": "ospf-neighbors",
        "mapping_fields": OSPF_NEIGHBORS_MAPPING,
    },
    "ospf_interfaces": {
        "label": "OSPF接口",
        "value": "ospf_interfaces",
        "icon": "ospf-interfaces",
        "mapping_fields": OSPF_INTERFACES_MAPPING,
    },
    "isis_neighbors": {
        "label": "ISIS邻居",
        "value": "isis_neighbors",
        "icon": "isis-neighbors",
        "mapping_fields": ISIS_NEIGHBORS_MAPPING,
    },
}

COLLECTION_TYPE_ALIASES = {
    "device_identity": "version",
    "vxlan_capability": "netconf_capability",
}

# 所有采集类型列表，用于创建空白方案时自动生成各类型的子方案。
# version / vxlan_capability 仅作为兼容别名保留，不参与默认子方案自动生成。
DEFAULT_COLLECTION_TYPES = [
    key for key in field_mapping.keys() if key not in {"version", "vxlan_capability"}
]


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
