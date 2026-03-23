# -*- coding: utf-8 -*-
"""
Device API 应用
"""

from utils.db.mongo_ops import MongoOps

# 运行策略：device_api 为默认主入口，automation 固定为兜底入口。
DEFAULT_COLLECTION_ENTRY = "device_api"
FALLBACK_COLLECTION_ENTRY = "automation"

# 全局MongoDB连接对象
COLLECTION_RESULTS_DB = MongoOps(db='Automation', coll='TestDeviceCollection')

# celery 定时任务
COLLECTION_PLAN = MongoOps(db='Automation', coll='PlanCollectionCelery')
COLLECTION_SUB_PLAN = MongoOps(db='Automation', coll='SubPlanCollectionCelery')
COLLECTION_EXECUTION_LOG = MongoOps(db='Automation', coll='DeviceApiExecutionLog')

# 入库的详细数据
device_identity_mongo = MongoOps(db='Automation', coll='plan_device_identity')
arp_mongo = MongoOps(db='Automation', coll='plan_arp')          # arp类型
mac_mongo = MongoOps(db='Automation', coll='plan_mac')
mac_bd_mongo = MongoOps(db='Automation', coll='plan_mac_bd')
mac_vxlan_mongo = MongoOps(db='Automation', coll='plan_mac_vxlan')
mac_vxlan_control_mongo = MongoOps(db='Automation', coll='plan_mac_vxlan_control')
vxlan_capability_mongo = MongoOps(db='Automation', coll='plan_vxlan_capability')
netconf_capability_mongo = MongoOps(db='Automation', coll='plan_netconf_capability')
cli_output_capability_mongo = MongoOps(db='Automation', coll='plan_cli_output_capability')
lldp_mongo = MongoOps(db='Automation', coll='plan_lldp')
ip_interface_mongo = MongoOps(db='Automation', coll='plan_ip_interface')
interface_brief_mongo = MongoOps(db='Automation', coll='plan_interface_brief')
aggre_port_mongo = MongoOps(db='Automation', coll='plan_aggre_port')
hrp_state_mongo = MongoOps(db='Automation', coll='plan_hrp_state')
address_set_mongo = MongoOps(db='Automation', coll='plan_address_set')
nat_address_mongo = MongoOps(db='Automation', coll='plan_nat_address')
service_set_mongo = MongoOps(db='Automation', coll='plan_service_set')
slb_info_mongo = MongoOps(db='Automation', coll='plan_slb_info')
vrrp_info_mongo = MongoOps(db='Automation', coll='plan_vrrp_info')
zone_mongo = MongoOps(db='Automation', coll='plan_zone')
service_predefined_mongo = MongoOps(db='Automation', coll='plan_service_predefined')
policy_hit_count_mongo = MongoOps(db='Automation', coll='plan_policy_hit_count')
security_policy_mongo = MongoOps(db='Automation', coll='plan_security_policy')
dnat_mongo = MongoOps(db='Automation', coll='plan_dnat')
snat_mongo = MongoOps(db='Automation', coll='plan_snat')
fan_status_mongo = MongoOps(db='Automation', coll='plan_fan_status')
power_status_mongo = MongoOps(db='Automation', coll='plan_power_status')
temperature_status_mongo = MongoOps(db='Automation', coll='plan_temperature_status')
cpu_status_mongo = MongoOps(db='Automation', coll='plan_cpu_status')
memory_status_mongo = MongoOps(db='Automation', coll='plan_memory_status')
board_status_mongo = MongoOps(db='Automation', coll='plan_board_status')
irf_status_mongo = MongoOps(db='Automation', coll='plan_irf_status')
stack_status_mongo = MongoOps(db='Automation', coll='plan_stack_status')
transceiver_status_mongo = MongoOps(db='Automation', coll='plan_transceiver_status')
storage_status_mongo = MongoOps(db='Automation', coll='plan_storage_status')
environment_status_mongo = MongoOps(db='Automation', coll='plan_environment_status')
clock_status_mongo = MongoOps(db='Automation', coll='plan_clock_status')
route_table_mongo = MongoOps(db='Automation', coll='plan_route_table')
bgp_neighbors_mongo = MongoOps(db='Automation', coll='plan_bgp_neighbors')
bgp_summary_mongo = MongoOps(db='Automation', coll='plan_bgp_summary')
ospf_neighbors_mongo = MongoOps(db='Automation', coll='plan_ospf_neighbors')
ospf_interfaces_mongo = MongoOps(db='Automation', coll='plan_ospf_interfaces')
isis_neighbors_mongo = MongoOps(db='Automation', coll='plan_isis_neighbors')

# cmdb_mongo = MongoOps(db='Automation', coll='networkdevice')
