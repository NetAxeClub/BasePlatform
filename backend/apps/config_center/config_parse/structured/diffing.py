from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


LIST_SECTION_KEY_FIELDS = {
    'routing_instances': ('name',),
    'vlans': ('vlan_id',),
    'zones': ('name',),
    'services': ('name',),
    'ntp_servers': ('address', 'vrf'),
    'log_hosts': ('address', 'vrf'),
    'aaa_servers': ('name', 'address'),
    'interfaces': ('name',),
    'access_lists': ('name',),
}

DICT_SECTIONS = ('system', 'features', 'snmp', 'vendor_specific')
LIST_SECTIONS = tuple(LIST_SECTION_KEY_FIELDS.keys())
CONFIG_SECTIONS = DICT_SECTIONS + LIST_SECTIONS


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _join_path(prefix: str, key: str) -> str:
    return f'{prefix}.{key}' if prefix else key


def _compare_mapping(from_value: Any, to_value: Any, prefix: str = '') -> Dict[str, List[Dict[str, Any]]]:
    result = {
        'changed_fields': [],
        'added_fields': [],
        'removed_fields': [],
    }
    from_value = from_value or {}
    to_value = to_value or {}

    if not isinstance(from_value, dict) or not isinstance(to_value, dict):
        if from_value != to_value:
            result['changed_fields'].append({
                'path': prefix or '$',
                'from': from_value,
                'to': to_value,
            })
        return result

    all_keys = sorted(set(from_value.keys()) | set(to_value.keys()))
    for key in all_keys:
        path = _join_path(prefix, str(key))
        if key not in from_value:
            result['added_fields'].append({'path': path, 'value': to_value[key]})
            continue
        if key not in to_value:
            result['removed_fields'].append({'path': path, 'value': from_value[key]})
            continue
        left = from_value[key]
        right = to_value[key]
        if isinstance(left, dict) and isinstance(right, dict):
            nested = _compare_mapping(left, right, path)
            for field_name in result.keys():
                result[field_name].extend(nested[field_name])
            continue
        if left != right:
            result['changed_fields'].append({
                'path': path,
                'from': left,
                'to': right,
            })
    return result


def _item_identity(section: str, item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f'index:{index}'
    key_fields = LIST_SECTION_KEY_FIELDS.get(section, ())
    parts = []
    for field in key_fields:
        value = item.get(field)
        if value not in (None, ''):
            parts.append(f'{field}={value}')
    if parts:
        return '|'.join(parts)
    return f'index:{index}'


def _to_item_map(section: str, items: List[Any]) -> Dict[str, Any]:
    result = {}
    for index, item in enumerate(items):
        result[_item_identity(section, item, index)] = item
    return result


def _compare_list_section(section: str, from_items: List[Any], to_items: List[Any]) -> Dict[str, Any]:
    from_map = _to_item_map(section, from_items or [])
    to_map = _to_item_map(section, to_items or [])
    added = []
    removed = []
    changed = []

    for identity in sorted(set(from_map.keys()) | set(to_map.keys())):
        if identity not in from_map:
            added.append({'key': identity, 'item': to_map[identity]})
            continue
        if identity not in to_map:
            removed.append({'key': identity, 'item': from_map[identity]})
            continue
        left = from_map[identity]
        right = to_map[identity]
        if _json_dumps(left) == _json_dumps(right):
            continue
        if isinstance(left, dict) and isinstance(right, dict):
            field_diff = _compare_mapping(left, right, identity)
        else:
            field_diff = {
                'changed_fields': [{'path': identity, 'from': left, 'to': right}],
                'added_fields': [],
                'removed_fields': [],
            }
        changed.append({
            'key': identity,
            'from_item': left,
            'to_item': right,
            'field_diff': field_diff,
        })

    return {
        'added': added,
        'removed': removed,
        'changed': changed,
        'unchanged_count': max(len(from_map), len(to_map)) - len(added) - len(removed) - len(changed),
    }


def build_structured_config_diff(from_document: Dict[str, Any], to_document: Dict[str, Any]) -> Dict[str, Any]:
    from_config = (from_document or {}).get('config') or {}
    to_config = (to_document or {}).get('config') or {}
    sections = {}
    changed_sections = []
    total_added = 0
    total_removed = 0
    total_changed = 0

    for section in CONFIG_SECTIONS:
        if section in DICT_SECTIONS:
            section_diff = _compare_mapping(from_config.get(section), to_config.get(section), section)
            has_changes = any(section_diff.values())
            added_count = len(section_diff['added_fields'])
            removed_count = len(section_diff['removed_fields'])
            changed_count = len(section_diff['changed_fields'])
        else:
            section_diff = _compare_list_section(section, from_config.get(section) or [], to_config.get(section) or [])
            has_changes = bool(section_diff['added'] or section_diff['removed'] or section_diff['changed'])
            added_count = len(section_diff['added'])
            removed_count = len(section_diff['removed'])
            changed_count = len(section_diff['changed'])
        sections[section] = section_diff
        if has_changes:
            changed_sections.append(section)
        total_added += added_count
        total_removed += removed_count
        total_changed += changed_count

    return {
        'is_changed': bool(changed_sections),
        'summary': {
            'section_count': len(CONFIG_SECTIONS),
            'changed_section_count': len(changed_sections),
            'changed_sections': changed_sections,
            'added_count': total_added,
            'removed_count': total_removed,
            'changed_count': total_changed,
        },
        'sections': sections,
    }

