from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from django.utils import timezone
from ttp import ttp


SCHEMA_VERSION = 'config_backup_structured/v1'
PARSER_ENGINE = 'ttp'


@dataclass(frozen=True)
class ParseContext:
    config_backup_id: Optional[int] = None
    manage_ip: str = ''
    device_name: str = ''
    vendor: str = ''
    model_name: str = ''
    idc_name: str = ''
    config_type: str = 'running'
    file_path: str = ''
    backup_time: Any = None
    status: Any = None
    config_status: str = ''
    detail: str = ''


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: item for key, item in value.items()
        if item not in (None, '', [], {})
    }


def normalize_bool(value: Any) -> Optional[bool]:
    if value in (True, False):
        return value
    if value is None or value == '':
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('true', 'enable', 'enabled', 'yes', 'on'):
            return True
        if lowered in ('false', 'disable', 'disabled', 'no', 'off'):
            return False
    return bool(value)


def load_ttp_result(raw_result: Any) -> Dict[str, Any]:
    if raw_result in (None, '', []):
        return {}
    if isinstance(raw_result, str):
        parsed = json.loads(raw_result)
    else:
        parsed = raw_result
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                return item
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


class StructuredConfigProfile(ABC):
    aliases: Iterable[str] = ()
    vendor_family = 'generic'
    os_family = 'generic'
    template = ''
    profile_name = 'generic'

    @classmethod
    def matches(cls, vendor: str) -> bool:
        normalized_vendor = (vendor or '').strip().lower()
        return normalized_vendor in {(item or '').strip().lower() for item in cls.aliases}

    def parse(self, text: str) -> Dict[str, Any]:
        parser = ttp(data=text, template=self.template)
        parser.parse()
        result = parser.result(format='json')
        if not result:
            return {}
        return load_ttp_result(result[0])

    def content_sha1(self, text: str) -> str:
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    def default_features(self) -> Dict[str, Optional[bool]]:
        return {
            'ssh_enabled': None,
            'telnet_enabled': None,
            'http_enabled': None,
            'https_enabled': None,
            'snmp_enabled': None,
            'ntp_enabled': None,
            'stp_enabled': None,
            'lldp_enabled': None,
        }

    def default_config(self) -> Dict[str, Any]:
        return {
            'system': {},
            'features': self.default_features(),
            'routing_instances': [],
            'vlans': [],
            'zones': [],
            'services': [],
            'ntp_servers': [],
            'log_hosts': [],
            'aaa_servers': [],
            'interfaces': [],
            'access_lists': [],
            'snmp': {},
            'vendor_specific': {},
        }

    def base_document(self, context: ParseContext, text: str) -> Dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'document_type': 'config_backup_structured',
            'config_backup_id': context.config_backup_id,
            'device': compact_dict({
                'manage_ip': context.manage_ip,
                'name': context.device_name,
                'vendor': context.vendor,
                'vendor_family': self.vendor_family,
                'model_name': context.model_name,
                'idc_name': context.idc_name,
                'status': context.status,
            }),
            'backup': compact_dict({
                'config_type': context.config_type,
                'file_path': context.file_path,
                'backup_time': context.backup_time,
                'config_status': context.config_status,
                'detail': context.detail,
                'content_sha1': self.content_sha1(text),
                'content_length': len(text),
            }),
            'parser': {
                'engine': PARSER_ENGINE,
                'profile': self.profile_name,
                'status': 'SUCCESS',
                'errors': [],
                'parsed_at': timezone.now(),
            },
            'config': self.default_config(),
            'summary': {},
            'vendor_payload': {},
        }

    def build_summary(self, config: Dict[str, Any]) -> Dict[str, Any]:
        features = config.get('features') or {}
        enabled_features = sorted(
            [name for name, enabled in features.items() if enabled is True])
        return {
            'routing_instance_count': len(config.get('routing_instances') or []),
            'vlan_count': len(config.get('vlans') or []),
            'zone_count': len(config.get('zones') or []),
            'service_count': len(config.get('services') or []),
            'ntp_server_count': len(config.get('ntp_servers') or []),
            'log_host_count': len(config.get('log_hosts') or []),
            'aaa_server_count': len(config.get('aaa_servers') or []),
            'interface_count': len(config.get('interfaces') or []),
            'access_list_count': len(config.get('access_lists') or []),
            'enabled_features': enabled_features,
        }

    def build_document(self, context: ParseContext, text: str) -> Dict[str, Any]:
        document = self.base_document(context=context, text=text)
        parsed = self.parse(text)
        config = self.normalize(parsed, text)
        document['config'] = config
        document['summary'] = self.build_summary(config)
        document['vendor_payload'] = parsed
        return document

    @abstractmethod
    def normalize(self, parsed: Dict[str, Any], text: str) -> Dict[str, Any]:
        raise NotImplementedError
