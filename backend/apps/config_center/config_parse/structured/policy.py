from __future__ import annotations

import copy
import fnmatch
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured
from django.db import OperationalError, ProgrammingError


DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / 'policies' / 'default_drift_policy.json'
LOCAL_POLICY_OVERRIDE_PATH = Path(__file__).resolve().parents[5] / 'config' / 'structured_drift_policy.json'


@lru_cache(maxsize=1)
def load_default_drift_policy() -> Dict[str, Any]:
    with DEFAULT_POLICY_PATH.open('r', encoding='utf-8') as handler:
        return json.load(handler)


def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_json_file(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as handler:
        return json.load(handler)


@lru_cache(maxsize=1)
def load_local_drift_policy_override() -> Dict[str, Any]:
    if not LOCAL_POLICY_OVERRIDE_PATH.exists():
        return {}
    return _load_json_file(LOCAL_POLICY_OVERRIDE_PATH)


def validate_drift_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    policy = policy or {}

    if not isinstance(policy, dict):
        return {'is_valid': False, 'errors': ['policy 必须为 JSON object'], 'warnings': []}

    section_rules = policy.get('section_rules', {})
    signal_rules = policy.get('signal_rules', [])
    whitelist = policy.get('whitelist', [])

    if 'version' not in policy:
        warnings.append('未定义 version，建议显式标记策略版本')
    if not isinstance(section_rules, dict):
        errors.append('section_rules 必须为 object')
    else:
        for section, rule in section_rules.items():
            if not isinstance(rule, dict):
                errors.append(f'section_rules.{section} 必须为 object')
                continue
            severity = rule.get('severity')
            if severity and severity not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
                errors.append(f'section_rules.{section}.severity 非法: {severity}')

    if not isinstance(signal_rules, list):
        errors.append('signal_rules 必须为 list')
    else:
        for index, rule in enumerate(signal_rules):
            if not isinstance(rule, dict):
                errors.append(f'signal_rules[{index}] 必须为 object')
                continue
            if not rule.get('section'):
                errors.append(f'signal_rules[{index}].section 不能为空')
            severity = rule.get('severity')
            if severity and severity not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
                errors.append(f'signal_rules[{index}].severity 非法: {severity}')

    if not isinstance(whitelist, list):
        errors.append('whitelist 必须为 list')
    else:
        for index, rule in enumerate(whitelist):
            if not isinstance(rule, dict):
                errors.append(f'whitelist[{index}] 必须为 object')
                continue
            if not isinstance(rule.get('match', {}), dict):
                errors.append(f'whitelist[{index}].match 必须为 object')

    return {
        'is_valid': not errors,
        'errors': errors,
        'warnings': warnings,
    }


@lru_cache(maxsize=1)
def load_effective_drift_policy() -> Dict[str, Any]:
    default_policy = load_default_drift_policy()
    override_policy = load_local_drift_policy_override()
    db_policy = load_active_db_drift_policy_override()
    return _deep_merge_dict(_deep_merge_dict(default_policy, override_policy), db_policy)


@lru_cache(maxsize=1)
def load_active_db_drift_policy_override() -> Dict[str, Any]:
    try:
        from apps.config_center.models import StructuredDriftPolicy

        policy = StructuredDriftPolicy.objects.filter(is_active=True).order_by('-updated_at', '-id').first()
        if policy is None:
            return {}
        return policy.policy_content or {}
    except (AssertionError, AppRegistryNotReady, ImproperlyConfigured, OperationalError, ProgrammingError):
        return {}


def clear_drift_policy_caches():
    load_default_drift_policy.cache_clear()
    load_local_drift_policy_override.cache_clear()
    load_active_db_drift_policy_override.cache_clear()
    load_effective_drift_policy.cache_clear()


def preview_merged_drift_policy(policy_override: Dict[str, Any]) -> Dict[str, Any]:
    default_policy = load_default_drift_policy()
    merged_policy = _deep_merge_dict(default_policy, policy_override or {})
    return {
        'policy': merged_policy,
        'validation': validate_drift_policy(merged_policy),
    }


def build_policy_diff_summary(before_policy: Dict[str, Any], after_policy: Dict[str, Any]) -> Dict[str, Any]:
    before_policy = before_policy or {}
    after_policy = after_policy or {}

    changed = []
    added = []
    removed = []

    def walk(left: Any, right: Any, prefix: str = ''):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left.keys()) | set(right.keys())):
                path = '{}.{}'.format(prefix, key) if prefix else str(key)
                if key not in left:
                    added.append(path)
                    continue
                if key not in right:
                    removed.append(path)
                    continue
                walk(left[key], right[key], path)
            return
        if left != right:
            changed.append(prefix or '$')

    walk(before_policy, after_policy)
    return {
        'is_changed': bool(changed or added or removed),
        'changed_paths': changed,
        'added_paths': added,
        'removed_paths': removed,
        'changed_count': len(changed),
        'added_count': len(added),
        'removed_count': len(removed),
    }


def build_policy_context(from_document: Dict[str, Any], to_document: Dict[str, Any]) -> Dict[str, Any]:
    to_device = (to_document or {}).get('device') or {}
    to_backup = (to_document or {}).get('backup') or {}
    return {
        'manage_ip': to_device.get('manage_ip'),
        'device_name': to_device.get('name'),
        'vendor': to_device.get('vendor'),
        'vendor_family': to_device.get('vendor_family'),
        'model_name': to_device.get('model_name'),
        'idc_name': to_device.get('idc_name'),
        'config_type': to_backup.get('config_type'),
        'from_config_backup_id': (from_document or {}).get('config_backup_id'),
        'to_config_backup_id': (to_document or {}).get('config_backup_id'),
    }


def _match_rule_value(expected: Any, actual: Any) -> bool:
    if expected in (None, '', '*'):
        return True
    if isinstance(expected, list):
        return any(_match_rule_value(item, actual) for item in expected)
    actual_value = '' if actual is None else str(actual)
    expected_value = str(expected)
    return fnmatch.fnmatch(actual_value, expected_value)


def whitelist_rule_matches(rule: Dict[str, Any], finding: Dict[str, Any], context: Dict[str, Any]) -> bool:
    match = rule.get('match') or {}

    if not _match_rule_value(match.get('section', '*'), finding.get('section')):
        return False
    if not _match_rule_value(match.get('vendor', '*'), context.get('vendor')):
        return False
    if not _match_rule_value(match.get('vendor_family', '*'), context.get('vendor_family')):
        return False
    if not _match_rule_value(match.get('manage_ip', '*'), context.get('manage_ip')):
        return False
    if not _match_rule_value(match.get('config_type', '*'), context.get('config_type')):
        return False

    path_suffix = match.get('path_suffix')
    if path_suffix:
        paths = finding.get('paths') or []
        if not any(str(path).endswith(path_suffix) for path in paths):
            return False

    key_pattern = match.get('key')
    if key_pattern:
        keys = finding.get('keys') or []
        if not any(_match_rule_value(key_pattern, key) for key in keys):
            return False

    return True
