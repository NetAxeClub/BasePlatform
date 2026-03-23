from utils.db.mongo_ops import MongoOps


structured_config_mongo = MongoOps(
    db='Automation', coll='config_backup_structured')

structured_drift_mongo = MongoOps(
    db='Automation', coll='config_backup_drift')
