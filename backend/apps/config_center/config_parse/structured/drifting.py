from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils import timezone

from apps.config_center.config_parse.structured.diffing import build_structured_config_diff
from apps.config_center.config_parse.structured.policy import (
    build_policy_context,
    load_effective_drift_policy,
    whitelist_rule_matches,
)


DRIFT_SCHEMA_VERSION = 'config_backup_drift/v1'

SEVERITY_SCORE = {
    'LOW': 20,
    'MEDIUM': 50,
    'HIGH': 80,
    'CRITICAL': 100,
}


def _max_severity(left: str, right: str) -> str:
    ordered = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    return ordered[max(ordered.index(left), ordered.index(right))]


def _changed_count(section_diff: Dict[str, Any]) -> int:
    if 'changed_fields' in section_diff:
        return len(section_diff.get('changed_fields') or []) + len(section_diff.get('added_fields') or []) + len(section_diff.get('removed_fields') or [])
    return len(section_diff.get('changed') or []) + len(section_diff.get('added') or []) + len(section_diff.get('removed') or [])


def _rule_matches_signal(rule: Dict[str, Any], section: str, item: Dict[str, Any]) -> bool:
    if rule.get('section') and rule.get('section') != section:
        return False
    path_suffix = rule.get('path_suffix')
    if path_suffix:
        path = item.get('path', '')
        if not str(path).endswith(path_suffix):
            return False
    if 'when_to' in rule and item.get('to') != rule.get('when_to') and item.get('value') != rule.get('when_to'):
        return False
    if 'when_from' in rule and item.get('from') != rule.get('when_from'):
        return False
    return True


def _collect_paths(section_diff: Dict[str, Any]) -> List[str]:
    paths = []
    for field_name in ('changed_fields', 'added_fields', 'removed_fields'):
        for item in section_diff.get(field_name, []):
            path = item.get('path')
            if path:
                paths.append(path)
    return sorted(set(paths))


def _collect_keys(section_diff: Dict[str, Any]) -> List[str]:
    keys = []
    for field_name in ('added', 'removed', 'changed'):
        for item in section_diff.get(field_name, []):
            key = item.get('key')
            if key:
                keys.append(key)
    return sorted(set(keys))


def _apply_whitelist(findings: List[Dict[str, Any]], policy: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    suppressed_findings = []
    active_findings = []
    whitelist = policy.get('whitelist') or []
    for finding in findings:
        matched_rule = None
        for rule in whitelist:
            if whitelist_rule_matches(rule, finding, context):
                matched_rule = rule
                break
        if matched_rule:
            finding['suppressed'] = True
            finding['suppressed_by'] = matched_rule.get('name') or 'unnamed_rule'
            finding['suppressed_reason'] = matched_rule.get('reason', '')
            suppressed_findings.append(finding)
        else:
            active_findings.append(finding)
    return {
        'active_findings': active_findings,
        'suppressed_findings': suppressed_findings,
    }


def assess_structured_drift_risk(
    diff: Dict[str, Any],
    policy_context: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy = policy or load_effective_drift_policy()
    policy_context = policy_context or {}
    findings: List[Dict[str, Any]] = []
    overall_severity = 'LOW'
    total_score = 0

    for section in diff.get('summary', {}).get('changed_sections', []):
        section_diff = diff.get('sections', {}).get(section) or {}
        section_rule = (policy.get('section_rules') or {}).get(section, {})
        severity = section_rule.get('severity', 'LOW')
        summary = {
            'section': section,
            'severity': severity,
            'change_count': _changed_count(section_diff),
            'title': section_rule.get('title'),
            'paths': _collect_paths(section_diff),
            'keys': _collect_keys(section_diff),
        }

        signal_candidates = list(section_diff.get('changed_fields', [])) + list(section_diff.get('added_fields', []))
        for rule in policy.get('signal_rules', []):
            matched_signal = next(
                (item for item in signal_candidates if _rule_matches_signal(rule, section, item)),
                None,
            )
            if matched_signal:
                severity = rule.get('severity', severity)
                summary['title'] = rule.get('title') or summary.get('title')
                if 'to' in matched_signal:
                    summary['detail'] = f'{matched_signal.get("path")}: {matched_signal.get("from")} -> {matched_signal.get("to")}'
                else:
                    summary['detail'] = f'{matched_signal.get("path")}: {matched_signal.get("value")}'
                break

        if section == 'access_lists' and not summary.get('title'):
            summary['title'] = 'ACL 规则发生变化'
            summary['detail'] = f'added={len(section_diff.get("added", []))}, removed={len(section_diff.get("removed", []))}, changed={len(section_diff.get("changed", []))}'
        elif section == 'aaa_servers' and not summary.get('title'):
            summary['title'] = 'AAA 认证链路发生变化'
            summary['detail'] = f'added={len(section_diff.get("added", []))}, removed={len(section_diff.get("removed", []))}, changed={len(section_diff.get("changed", []))}'
        elif section == 'services' and not summary.get('title'):
            summary['title'] = '服务对象发生变化'
            summary['detail'] = f'added={len(section_diff.get("added", []))}, removed={len(section_diff.get("removed", []))}, changed={len(section_diff.get("changed", []))}'
        elif section == 'routing_instances' and not summary.get('title'):
            summary['title'] = 'VRF / 路由实例发生变化'
            summary['detail'] = f'added={len(section_diff.get("added", []))}, removed={len(section_diff.get("removed", []))}, changed={len(section_diff.get("changed", []))}'
        elif section == 'interfaces' and not summary.get('title'):
            summary['title'] = '接口配置发生变化'
            summary['detail'] = f'added={len(section_diff.get("added", []))}, removed={len(section_diff.get("removed", []))}, changed={len(section_diff.get("changed", []))}'
        elif not summary.get('title'):
            summary['title'] = f'{section} 发生配置变化'
            summary['detail'] = f'change_count={summary["change_count"]}'

        summary['severity'] = severity
        findings.append(summary)

    whitelist_result = _apply_whitelist(findings, policy, policy_context)
    findings = whitelist_result['active_findings']
    suppressed_findings = whitelist_result['suppressed_findings']

    for finding in findings:
        severity = finding['severity']
        overall_severity = _max_severity(overall_severity, severity)
        total_score += SEVERITY_SCORE.get(severity, 20)

    if not findings:
        overall_severity = 'LOW'
        total_score = 0

    total_score = min(total_score, 100)
    return {
        'policy_version': policy.get('version', 'unknown'),
        'risk_level': overall_severity,
        'risk_score': total_score,
        'finding_count': len(findings),
        'suppressed_count': len(suppressed_findings),
        'findings': findings,
        'suppressed_findings': suppressed_findings,
    }


def build_drift_assessment_document(from_document: Dict[str, Any], to_document: Dict[str, Any]) -> Dict[str, Any]:
    diff = build_structured_config_diff(from_document, to_document)
    risk = assess_structured_drift_risk(
        diff,
        policy_context=build_policy_context(from_document, to_document),
    )
    device = (to_document.get('device') or {})
    to_backup = (to_document.get('backup') or {})
    from_backup = (from_document.get('backup') or {})
    return {
        'schema_version': DRIFT_SCHEMA_VERSION,
        'document_type': 'config_backup_structured_drift',
        'from_config_backup_id': from_document.get('config_backup_id'),
        'to_config_backup_id': to_document.get('config_backup_id'),
        'device': {
            'manage_ip': device.get('manage_ip'),
            'name': device.get('name'),
            'vendor': device.get('vendor'),
            'vendor_family': device.get('vendor_family'),
            'model_name': device.get('model_name'),
            'idc_name': device.get('idc_name'),
        },
        'backup': {
            'config_type': to_backup.get('config_type'),
            'from_backup_time': from_backup.get('backup_time'),
            'to_backup_time': to_backup.get('backup_time'),
        },
        'diff_summary': diff.get('summary') or {},
        'risk_assessment': risk,
        'policy': {
            'version': risk.get('policy_version'),
        },
        'generated_at': timezone.now(),
    }
