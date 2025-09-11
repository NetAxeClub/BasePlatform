# -*- coding: utf-8 -*-
"""
Device API 应用
"""

from utils.db.mongo_ops import MongoOps

# 全局MongoDB连接对象
COLLECTION_RESULTS_DB = MongoOps(db='BasePlatform', coll='DeviceCollection')
COLLECTION_LOG_DB = MongoOps(db='BasePlatform', coll='DeviceCollectionLog')
