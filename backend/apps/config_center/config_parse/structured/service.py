from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from django.core.files.storage import default_storage

from apps.config_center.config_parse.structured.base import ParseContext
from apps.config_center.config_parse.structured.registry import get_structured_profile
from apps.config_center.config_parse.structured.repository import StructuredConfigRepository


logger = logging.getLogger('automation')


def build_parse_context_from_backup(backup) -> ParseContext:
    return ParseContext(
        config_backup_id=getattr(backup, 'id', None),
        manage_ip=getattr(backup, 'manage_ip', ''),
        device_name=getattr(backup, 'name', ''),
        vendor=getattr(backup, 'vendor', ''),
        model_name=getattr(backup, 'model_name', ''),
        idc_name=getattr(backup, 'idc_name', ''),
        config_type=getattr(backup, 'config_type', 'running'),
        file_path=getattr(backup, 'file_path', ''),
        backup_time=getattr(backup, 'last_time', None),
        status=getattr(backup, 'status', None),
        config_status=getattr(backup, 'config_status', ''),
        detail=getattr(backup, 'detail', ''),
    )


class StructuredConfigParseService:
    def __init__(self, repository: Optional[StructuredConfigRepository] = None):
        self.repository = repository or StructuredConfigRepository()

    def parse_text(self, text: str, context: ParseContext) -> Dict:
        profile = get_structured_profile(context.vendor)
        if profile is None:
            raise ValueError(
                f'unsupported structured parser vendor: {context.vendor}')
        return profile.build_document(context=context, text=text)

    def parse_backup(self, backup):
        file_path = getattr(backup, 'file_path', '') or ''
        if not file_path:
            raise ValueError('backup file_path is empty')
        if not default_storage.exists(file_path):
            raise FileNotFoundError(file_path)
        with default_storage.open(file_path, 'rb') as handler:
            text = handler.read().decode('utf-8', errors='ignore')
        context = build_parse_context_from_backup(backup)
        document = self.parse_text(text=text, context=context)
        self.repository.upsert(document)
        return document

    def parse_backups(self, backups: Iterable) -> Dict[str, int]:
        summary = {
            'total': 0,
            'parsed': 0,
            'failed': 0,
            'skipped': 0,
        }
        for backup in backups:
            summary['total'] += 1
            file_path = getattr(backup, 'file_path', '') or ''
            if not file_path:
                summary['skipped'] += 1
                continue
            try:
                self.parse_backup(backup)
                summary['parsed'] += 1
            except FileNotFoundError:
                summary['skipped'] += 1
                logger.warning('结构化解析跳过，配置文件不存在: %s', file_path)
            except Exception as exc:
                summary['failed'] += 1
                logger.exception(
                    '结构化解析失败 backup_id=%s vendor=%s path=%s error=%s',
                    getattr(backup, 'id', None),
                    getattr(backup, 'vendor', ''),
                    file_path,
                    exc,
                )
        return summary
