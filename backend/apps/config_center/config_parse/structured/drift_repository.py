from __future__ import annotations

from typing import Dict, List, Optional

from apps.config_center.db import structured_drift_mongo


class StructuredDriftRepository:
    def __init__(self, mongo_client=None):
        self.mongo = mongo_client or structured_drift_mongo

    def upsert(self, document: Dict):
        return self.mongo.coll.update_one(
            {'to_config_backup_id': document.get('to_config_backup_id')},
            {'$set': document},
            upsert=True,
        )

    def find_by_to_backup_id(self, config_backup_id: int) -> Optional[Dict]:
        return self.mongo.coll.find_one({'to_config_backup_id': config_backup_id}, {'_id': 0})

    def find_latest_by_device(self, manage_ip: str, config_type: str = 'running') -> Optional[Dict]:
        return self.mongo.coll.find_one(
            {
                'device.manage_ip': manage_ip,
                'backup.config_type': config_type,
            },
            {'_id': 0},
            sort=[('backup.to_backup_time', -1), ('generated_at', -1)],
        )

    def find_history(self, manage_ip: str, config_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
        query = {'device.manage_ip': manage_ip}
        if config_type:
            query['backup.config_type'] = config_type
        cursor = self.mongo.coll.find(query, {'_id': 0}).sort(
            [('backup.to_backup_time', -1), ('generated_at', -1)]
        ).limit(limit)
        return list(cursor)
