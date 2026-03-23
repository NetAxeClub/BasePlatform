from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from apps.config_center.config_parse.structured.drifting import build_drift_assessment_document
from apps.config_center.config_parse.structured.drift_repository import StructuredDriftRepository
from apps.config_center.config_parse.structured.repository import StructuredConfigRepository


logger = logging.getLogger('automation')


class StructuredConfigDriftService:
    def __init__(
        self,
        config_repository: Optional[StructuredConfigRepository] = None,
        drift_repository: Optional[StructuredDriftRepository] = None,
    ):
        self.config_repository = config_repository or StructuredConfigRepository()
        self.drift_repository = drift_repository or StructuredDriftRepository()

    def _resolve_pair(self, to_document: Dict) -> Optional[Dict]:
        device = (to_document.get('device') or {})
        backup = (to_document.get('backup') or {})
        manage_ip = device.get('manage_ip')
        config_type = backup.get('config_type')
        if not manage_ip or not config_type:
            return None
        history = self.config_repository.find_history(
            manage_ip=manage_ip,
            config_type=config_type,
            limit=100,
        )
        current_backup_id = to_document.get('config_backup_id')
        current_index = next(
            (index for index, item in enumerate(history) if item.get('config_backup_id') == current_backup_id),
            None,
        )
        if current_index is None or current_index + 1 >= len(history):
            return None
        return history[current_index + 1]

    def analyze_document(self, to_document: Dict) -> Optional[Dict]:
        from_document = self._resolve_pair(to_document)
        if not from_document:
            return None
        document = build_drift_assessment_document(from_document, to_document)
        self.drift_repository.upsert(document)
        return document

    def analyze_backup_id(self, config_backup_id: int) -> Optional[Dict]:
        to_document = self.config_repository.find_by_backup_id(config_backup_id)
        if not to_document:
            return None
        return self.analyze_document(to_document)

    def analyze_backups(self, backups: Iterable) -> Dict[str, int]:
        summary = {
            'total': 0,
            'analyzed': 0,
            'skipped': 0,
            'failed': 0,
        }
        for backup in backups:
            summary['total'] += 1
            backup_id = getattr(backup, 'id', None)
            if backup_id is None:
                summary['skipped'] += 1
                continue
            try:
                document = self.analyze_backup_id(backup_id)
                if document is None:
                    summary['skipped'] += 1
                else:
                    summary['analyzed'] += 1
            except Exception as exc:
                summary['failed'] += 1
                logger.exception('结构化漂移分析失败 backup_id=%s error=%s', backup_id, exc)
        return summary
