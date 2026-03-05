# -*- coding: utf-8 -*-
"""
DCS Control 模块 MongoDB 连接实例统一管理。

原 tasks.py 和 views.py 各自独立定义重复的 MongoOps 实例（如 dnat_mongo、sec_policy_mongo），
此处统一管理，其他模块从此处 import，避免多进程/多模块下连接语义不一致。
"""
from utils.db.mongo_ops import MongoOps

# ── 地址对象 ────────────────────────────────────────────────────────────
address_mongo = MongoOps(db='Automation', coll='hillstone_address')

# ── 服务对象 ────────────────────────────────────────────────────────────
service_mongo = MongoOps(db='Automation', coll='hillstone_service')
servgroup_mongo = MongoOps(db='Automation', coll='hillstone_servgroup')

# ── 系统预定义服务 ──────────────────────────────────────────────────────
predefined_mongo = MongoOps(db='Automation', coll='hillstone_service_predefined')

# ── DNAT / SNAT ─────────────────────────────────────────────────────────
dnat_mongo = MongoOps(db='Automation', coll='hillstone_dnat')
snat_mongo = MongoOps(db='Automation', coll='hillstone_snat')

# ── 安全策略 ────────────────────────────────────────────────────────────
sec_policy_mongo = MongoOps(db='Automation', coll='sec_policy')

# ── 安全域 ──────────────────────────────────────────────────────────────
zone_mongo = MongoOps(db='Automation', coll='hillstone_zone')

# ── 故障切换 ────────────────────────────────────────────────────────────
SwitchFailBackDB = MongoOps(db='Automation', coll='switch_failback')
SwitchFailBackTaskDB = MongoOps(db='Automation', coll='switch_failback_task')

# ── CMDB ────────────────────────────────────────────────────────────────
cmdb_mongo = MongoOps(db='XunMiData', coll='networkdevice')
