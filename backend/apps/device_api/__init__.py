# -*- coding: utf-8 -*-
"""
Device API 应用
"""

from utils.db.mongo_ops import MongoOps

# 全局MongoDB连接对象
COLLECTION_RESULTS_DB = MongoOps(db='Automation', coll='TestDeviceCollection')

# celery 定时任务
COLLECTION_PLAN = MongoOps(db='Automation', coll='PlanCollectionCelery')
COLLECTION_SUB_PLAN = MongoOps(db='Automation', coll='SubPlanCollectionCelery')

# 入库的详细数据
arp_mongo = MongoOps(db='Automation', coll='plan_arp')          # arp类型
mac_mongo = MongoOps(db='Automation', coll='plan_mac')
lldp_mongo = MongoOps(db='Automation', coll='plan_lldp')
ip_interface_mongo = MongoOps(db='Automation', coll='plan_ip_interface')
interface_brief_mongo = MongoOps(db='Automation', coll='plan_interface_brief')
aggre_port_mongo = MongoOps(db='Automation', coll='plan_aggre_port')
fan_status_mongo = MongoOps(db='Automation', coll='plan_fan_status')
power_status_mongo = MongoOps(db='Automation', coll='plan_power_status')
temperature_status_mongo = MongoOps(db='Automation', coll='plan_temperature_status')
clock_status_mongo = MongoOps(db='Automation', coll='plan_clock_status')
route_table_mongo = MongoOps(db='Automation', coll='plan_route_table')
bgp_neighbors_mongo = MongoOps(db='Automation', coll='plan_bgp_neighbors')
bgp_summary_mongo = MongoOps(db='Automation', coll='plan_bgp_summary')
ospf_neighbors_mongo = MongoOps(db='Automation', coll='plan_ospf_neighbors')
ospf_interfaces_mongo = MongoOps(db='Automation', coll='plan_ospf_interfaces')
isis_neighbors_mongo = MongoOps(db='Automation', coll='plan_isis_neighbors')

# cmdb_mongo = MongoOps(db='Automation', coll='networkdevice')
