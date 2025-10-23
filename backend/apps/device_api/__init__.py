# -*- coding: utf-8 -*-
"""
Device API 应用
"""

from utils.db.mongo_ops import MongoOps

# 全局MongoDB连接对象
COLLECTION_RESULTS_DB = MongoOps(db='BasePlatform', coll='DeviceCollection')
COLLECTION_LOG_DB = MongoOps(db='BasePlatform', coll='DeviceCollectionLog')

# 标准数据存入mongodb
COLLECTION_ARP = MongoOps(db='BasePlatform', coll='CollectARPTable')
COLLECTION_MAC = MongoOps(db='BasePlatform', coll='CollectMACTable')
COLLECTION_LLDP = MongoOps(db='BasePlatform', coll='CollectLLDPTable')
COLLECTION_IP_INTERFACE = MongoOps(db='BasePlatform', coll='CollectIPInterfaceTable')
COLLECTION_INTERFACE_BRIEF = MongoOps(db='BasePlatform', coll='CollectInterfaceBriefTable')
COLLECTION_AGGRE_PORT = MongoOps(db='BasePlatform', coll='CollectAggrePortTable')
