from __future__ import annotations

from typing import Dict, List, Optional

from apps.config_center.db import structured_config_mongo


class StructuredConfigRepository:
    def __init__(self, mongo_client=None):
        self.mongo = mongo_client or structured_config_mongo

    def build_filter(self, document: Dict) -> Dict:
        config_backup_id = document.get('config_backup_id')
        if config_backup_id is not None:
            return {'config_backup_id': config_backup_id}
        device = document.get('device') or {}
        backup = document.get('backup') or {}
        return {
            'device.manage_ip': device.get('manage_ip'),
            'backup.config_type': backup.get('config_type'),
            'backup.file_path': backup.get('file_path'),
        }

    def upsert(self, document: Dict):
        document_filter = self.build_filter(document)
        return self.mongo.coll.update_one(document_filter, {'$set': document}, upsert=True)

    def find_by_backup_id(self, config_backup_id: int) -> Optional[Dict]:
        return self.mongo.coll.find_one({'config_backup_id': config_backup_id}, {'_id': 0})

    def find_latest_by_device(self, manage_ip: str, config_type: str = 'running') -> Optional[Dict]:
        return self.mongo.coll.find_one(
            {
                'device.manage_ip': manage_ip,
                'backup.config_type': config_type,
            },
            {'_id': 0},
            sort=[('backup.backup_time', -1), ('parser.parsed_at', -1)],
        )

    def find_history(self, manage_ip: str, config_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
        query = {'device.manage_ip': manage_ip}
        if config_type:
            query['backup.config_type'] = config_type
        cursor = self.mongo.coll.find(query, {'_id': 0}).sort(
            [('backup.backup_time', -1), ('parser.parsed_at', -1)]
        ).limit(limit)
        return list(cursor)
