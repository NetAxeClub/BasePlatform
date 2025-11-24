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
# cmdb_mongo = MongoOps(db='Automation', coll='networkdevice')
