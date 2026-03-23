# Create your views here.
import json
import re
import yaml
import io
import django_filters
import ipaddress
from netaddr import IPNetwork, IPAddress
from jinja2 import Environment, StrictUndefined, exceptions, Template
from django.http import FileResponse
from datetime import date, datetime, timedelta
from django.http import JsonResponse, StreamingHttpResponse
from django.core.files.storage import default_storage
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from ttp import ttp
from netaxe.settings import BASE_DIR
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.api.tools.custom_viewset_base import CustomViewBase
from utils.connect_layer.auto_main import BatManMain
from apps.config_center.config_parse.config_parse import ConfigTree, FSMTree
from apps.config_center.config_parse.structured.diffing import build_structured_config_diff
from apps.config_center.config_parse.structured.drift_repository import StructuredDriftRepository
from apps.config_center.config_parse.structured.drifting import assess_structured_drift_risk
from apps.config_center.config_parse.structured.policy import (
    LOCAL_POLICY_OVERRIDE_PATH,
    build_policy_context,
    build_policy_diff_summary,
    clear_drift_policy_caches,
    load_effective_drift_policy,
    load_active_db_drift_policy_override,
    load_local_drift_policy_override,
    preview_merged_drift_policy,
    validate_drift_policy,
)
from apps.config_center.config_parse.structured.repository import StructuredConfigRepository
from apps.config_center.git_tools.git_proc import ConfigGit
from utils.db.mongo_ops import MongoNetOps, get_mongo_json_res
from .serializers import *
from .models import ConfigCompliance, ConfigComplianceResult, StructuredDriftPolicy, StructuredDriftPolicyAudit

_ConfigGit = ConfigGit()
_StructuredConfigRepository = StructuredConfigRepository()
_StructuredDriftRepository = StructuredDriftRepository()


def build_security_baseline_payload(compliances, root_rule_name):
    """将基线规则按 vendor / 子规则聚合，便于上层直接消费。"""
    vendors = {}
    total_items = 0

    for compliance in compliances:
        total_items += 1
        vendor_bucket = vendors.setdefault(
            compliance.vendor,
            {"vendor": compliance.vendor, "rule_count": 0, "rules": {}},
        )
        rule_name = compliance.rule.name if getattr(compliance, "rule", None) else ""
        parent_name = (
            compliance.rule.parent.name
            if getattr(compliance, "rule", None) and getattr(compliance.rule, "parent", None)
            else root_rule_name
        )
        rule_bucket = vendor_bucket["rules"].setdefault(
            rule_name,
            {
                "rule_name": rule_name,
                "rule_id": getattr(compliance, "rule_id", None) or getattr(getattr(compliance, "rule", None), "id", None),
                "parent_rule": parent_name,
                "items": [],
            },
        )
        rule_bucket["items"].append(
            {
                "id": getattr(compliance, "id", None),
                "vendor": compliance.vendor,
                "pattern": compliance.pattern,
                "regex": compliance.regex,
                "intent": getattr(compliance, "intent", ""),
            }
        )

    vendor_items = []
    for vendor_name in sorted(vendors.keys()):
        vendor_bucket = vendors[vendor_name]
        rules = []
        for rule_name in sorted(vendor_bucket["rules"].keys()):
            rule_bucket = vendor_bucket["rules"][rule_name]
            rule_bucket["item_count"] = len(rule_bucket["items"])
            rules.append(rule_bucket)
        vendor_bucket["rules"] = rules
        vendor_bucket["rule_count"] = len(rules)
        vendor_items.append(vendor_bucket)

    return {
        "root_rule": root_rule_name,
        "vendor_count": len(vendor_items),
        "total_items": total_items,
        "vendors": vendor_items,
    }


class ConfigComplianceResultFilter(django_filters.FilterSet):
    """配置合规结果过滤，排除 JSONField 等不宜做 exact 过滤的字段，避免 filter_overrides 报错"""

    class Meta:
        model = ConfigComplianceResult
        fields = [
            'compliance', 'manage_ip', 'hostname', 'vendor', 'log_time',
            'rule', 'rule_id', 'config_file_path', 'backup_time', 'config_backup_id',
        ]


def is_safe_dict(data: dict) -> bool:
    # 定义危险字符的正则表达式
    # pattern = re.compile(r'<(script|iframe).*?>|([^\w\s./:%,-])', re.IGNORECASE)
    pattern = re.compile(r'<(script|iframe).*?>', re.IGNORECASE)

    # 遍历字典中的值，使用正则表达式进行匹配验证
    for value in data.values():
        if isinstance(value, str) and pattern.search(value):
            return False

    return True


def inverse_mask(cidr: str) -> str:
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    mask = network.hostmask
    return mask.compressed


def format_cidr(cidr: str) -> str:
    net = IPNetwork(cidr.strip())
    return str(net.cidr)


def _truthy(value) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def summarize_compliance_results(results):
    total = len(results)
    compliant = 0
    non_compliant = 0
    unknown = 0
    for item in results:
        status = str(getattr(item, 'compliance', '') or '').strip()
        if status == '合规':
            compliant += 1
        elif status == '不合规':
            non_compliant += 1
        else:
            unknown += 1
    return {
        'total': total,
        'compliant': compliant,
        'non_compliant': non_compliant,
        'unknown': unknown,
    }


def build_backup_snapshot_payload(backup, compliance_results, commits=None, preview_content=None):
    commits = commits or []
    latest_commit = commits[0] if commits else None
    data = {
        'config_backup_id': backup.id,
        'manage_ip': backup.manage_ip,
        'device_name': backup.name,
        'vendor': backup.vendor,
        'model_name': backup.model_name,
        'idc_name': backup.idc_name,
        'config_type': backup.config_type,
        'backup_time': backup.last_time.strftime('%Y-%m-%d %H:%M:%S') if backup.last_time else '',
        'config_status': backup.config_status,
        'file_path': backup.file_path,
        'detail': backup.detail or '',
        'git_commit_count': len(commits),
        'latest_commit': latest_commit,
        'compliance_summary': summarize_compliance_results(compliance_results),
        'compliance_results': [
            {
                'id': item.id,
                'rule_id': item.rule_id,
                'rule': item.rule,
                'compliance': item.compliance,
                'backup_time': item.backup_time.strftime('%Y-%m-%d %H:%M:%S') if item.backup_time else '',
                'config_backup_id': item.config_backup_id,
                'config_file_path': item.config_file_path,
                'rule_regex': item.rule_regex,
            }
            for item in compliance_results
        ],
    }
    if preview_content is not None:
        data['preview_content'] = preview_content
    return data


def build_backup_timeline_payload(backups, compliance_results_by_backup, commits_by_path):
    items = []
    for backup in backups:
        compliance_results = compliance_results_by_backup.get(backup.id, [])
        commits = commits_by_path.get(backup.file_path, [])
        items.append({
            'config_backup_id': backup.id,
            'manage_ip': backup.manage_ip,
            'device_name': backup.name,
            'vendor': backup.vendor,
            'config_type': backup.config_type,
            'backup_time': backup.last_time.strftime('%Y-%m-%d %H:%M:%S') if backup.last_time else '',
            'config_status': backup.config_status,
            'file_path': backup.file_path,
            'git_commit_count': len(commits),
            'latest_commit': commits[0] if commits else None,
            'compliance_summary': summarize_compliance_results(compliance_results),
        })
    return items


def build_backup_compare_payload(backup, from_commit, to_commit, diff_result):
    old_str = diff_result.get('old_str', '') or ''
    new_str = diff_result.get('new_str', '') or ''
    return {
        'config_backup_id': backup.id,
        'manage_ip': backup.manage_ip,
        'device_name': backup.name,
        'vendor': backup.vendor,
        'config_type': backup.config_type,
        'file_path': backup.file_path,
        'from_commit': from_commit,
        'to_commit': to_commit,
        'old_content': old_str,
        'new_content': new_str,
        'old_line_count': len(old_str.splitlines()) if old_str else 0,
        'new_line_count': len(new_str.splitlines()) if new_str else 0,
        'added_lines': diff_result.get('added_lines'),
        'deleted_lines': diff_result.get('deleted_lines'),
    }


def _mongo_document_to_jsonable(document):
    if document is None:
        return None
    return json.loads(get_mongo_json_res(document))


def build_structured_snapshot_payload(document):
    jsonable_document = _mongo_document_to_jsonable(document) or {}
    device = jsonable_document.get('device') or {}
    backup = jsonable_document.get('backup') or {}
    parser = jsonable_document.get('parser') or {}
    return {
        'config_backup_id': jsonable_document.get('config_backup_id'),
        'manage_ip': device.get('manage_ip'),
        'device_name': device.get('name'),
        'vendor': device.get('vendor'),
        'vendor_family': device.get('vendor_family'),
        'model_name': device.get('model_name'),
        'idc_name': device.get('idc_name'),
        'config_type': backup.get('config_type'),
        'backup_time': backup.get('backup_time'),
        'file_path': backup.get('file_path'),
        'content_sha1': backup.get('content_sha1'),
        'parser_status': parser.get('status'),
        'parser_profile': parser.get('profile'),
        'schema_version': jsonable_document.get('schema_version'),
        'summary': jsonable_document.get('summary') or {},
        'document': jsonable_document,
    }


def build_structured_timeline_payload(documents):
    items = []
    for document in documents:
        snapshot = build_structured_snapshot_payload(document)
        items.append({
            'config_backup_id': snapshot.get('config_backup_id'),
            'manage_ip': snapshot.get('manage_ip'),
            'device_name': snapshot.get('device_name'),
            'vendor': snapshot.get('vendor'),
            'vendor_family': snapshot.get('vendor_family'),
            'config_type': snapshot.get('config_type'),
            'backup_time': snapshot.get('backup_time'),
            'parser_status': snapshot.get('parser_status'),
            'parser_profile': snapshot.get('parser_profile'),
            'summary': snapshot.get('summary') or {},
        })
    return items


def build_structured_compare_payload(from_document, to_document):
    diff = build_structured_config_diff(
        _mongo_document_to_jsonable(from_document) or {},
        _mongo_document_to_jsonable(to_document) or {},
    )
    risk_assessment = assess_structured_drift_risk(
        diff,
        policy_context=build_policy_context(
            _mongo_document_to_jsonable(from_document) or {},
            _mongo_document_to_jsonable(to_document) or {},
        ),
    )
    return {
        'from_snapshot': build_structured_snapshot_payload(from_document),
        'to_snapshot': build_structured_snapshot_payload(to_document),
        'diff': diff,
        'risk_assessment': risk_assessment,
    }


def build_structured_drift_payload(document):
    jsonable_document = _mongo_document_to_jsonable(document) or {}
    device = jsonable_document.get('device') or {}
    backup = jsonable_document.get('backup') or {}
    return {
        'from_config_backup_id': jsonable_document.get('from_config_backup_id'),
        'to_config_backup_id': jsonable_document.get('to_config_backup_id'),
        'manage_ip': device.get('manage_ip'),
        'device_name': device.get('name'),
        'vendor': device.get('vendor'),
        'vendor_family': device.get('vendor_family'),
        'config_type': backup.get('config_type'),
        'from_backup_time': backup.get('from_backup_time'),
        'to_backup_time': backup.get('to_backup_time'),
        'diff_summary': jsonable_document.get('diff_summary') or {},
        'risk_assessment': jsonable_document.get('risk_assessment') or {},
        'policy': jsonable_document.get('policy') or {},
        'document': jsonable_document,
    }


def build_structured_drift_policy_payload(policy, validation, source):
    return {
        'policy': policy,
        'validation': validation,
        'source': source,
    }


def jinja_render(data, template):
    """ Render a jinja template
    """
    if is_safe_dict(data):
        env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
        env.globals.update(inverse_mask=inverse_mask, format_cidr=format_cidr)
        try:
            jinja2_tpl = env.from_string(template)
            rendered_jinja2_tpl = jinja2_tpl.render(data)
        except (exceptions.TemplateSyntaxError, exceptions.TemplateError) as e:
            return False, "Syntax error in jinja2 template: {0}".format(e)
        except (exceptions.TemplateRuntimeError, ValueError, TypeError) as e:
            return False, "Error in your values input filed: {0}".format(e)

        return True, rendered_jinja2_tpl
    return False, "安全校验失败"


class ConfigBackupFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = ConfigBackup
        fields = '__all__'


# 配置备份
class ConfigBackupViewSet(CustomViewBase):
    queryset = ConfigBackup.objects.all().order_by('-last_time')
    serializer_class = ConfigBackupSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    filterset_class = ConfigBackupFilter
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('manage_ip', 'name')
    search_fields = ('manage_ip', 'name')

    def get_queryset(self):
        """
        处理不同时间范围的查询过滤
        支持:
        1. 开始和结束日期范围
        2. 指定时间单位(天/时/分)和数值的范围
        3. 时间戳范围查询
        """

        # 获取查询参数
        params = self.request.query_params
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        time_unit = params.get('time_unit')
        time_num = params.get('time_num')
        range_time = params.get('range_time')

        # 处理开始和结束日期范围
        if start_time and end_time:
            start_dt = datetime.strptime(f"{start_time} 00:00:00", '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(f"{end_time} 23:59:59", '%Y-%m-%d %H:%M:%S')
            self.queryset = self.filter_by_date_range(start_dt, end_dt)

        # 处理时间单位和数值范围
        if time_unit and time_num:
            time_num = int(time_num)
            current_time = datetime.now()
            
            time_delta_map = {
                "days": lambda x: timedelta(days=x),
                "hours": lambda x: timedelta(hours=x),
                "minutes": lambda x: timedelta(minutes=x)
            }
            
            if time_unit in time_delta_map:
                start_time = current_time - time_delta_map[time_unit](time_num)
                self.queryset = self.filter_by_date_range(start_time, current_time)

        # 处理时间戳范围
        if range_time is not None:
            dt_object = datetime.fromtimestamp(int(int(range_time)/1000))
            start_dt = datetime.strptime(dt_object.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(dt_object.strftime('%Y-%m-%d ') + "23:59:59", '%Y-%m-%d %H:%M:%S')
            self.queryset = self.filter_by_date_range(start_dt, end_dt)

        return self.queryset

    def filter_by_date_range(self, start_dt, end_dt):
        return self.queryset.filter(last_time__range=(start_dt, end_dt))

    @action(detail=False, methods=['get'])
    def latest_snapshot(self, request):
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type', 'running')
        include_preview = _truthy(request.query_params.get('include_preview'))
        preview_lines = int(request.query_params.get('preview_lines', 50))
        if not manage_ip:
            return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip', 'data': None})

        backup = (
            ConfigBackup.objects.filter(manage_ip=manage_ip, config_type=config_type)
            .order_by('-last_time')
            .first()
        )
        if not backup:
            return JsonResponse({'code': 404, 'message': '未找到配置备份记录', 'data': None})

        compliance_results = list(
            ConfigComplianceResult.objects.filter(config_backup_id=backup.id).order_by('rule')
        )
        commits = _ConfigGit.get_file_all_change_commmit(backup.file_path) if backup.file_path else []
        preview_content = None
        if include_preview and backup.file_path and default_storage.exists(backup.file_path):
            file_content = default_storage.open(backup.file_path).read().decode('utf-8')
            preview_content = '\n'.join(file_content.splitlines()[:preview_lines])

        data = build_backup_snapshot_payload(
            backup=backup,
            compliance_results=compliance_results,
            commits=commits,
            preview_content=preview_content,
        )
        return JsonResponse({'code': 200, 'message': '获取最新配置快照成功', 'data': data})

    @action(detail=False, methods=['get'])
    def history_timeline(self, request):
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type')
        limit = int(request.query_params.get('limit', 20))
        if not manage_ip:
            return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip', 'data': None})

        queryset = ConfigBackup.objects.filter(manage_ip=manage_ip).order_by('-last_time')
        if config_type:
            queryset = queryset.filter(config_type=config_type)
        backups = list(queryset[:limit])
        backup_ids = [item.id for item in backups]

        compliance_results_by_backup = {}
        if backup_ids:
            for item in ConfigComplianceResult.objects.filter(config_backup_id__in=backup_ids).order_by('rule'):
                compliance_results_by_backup.setdefault(item.config_backup_id, []).append(item)

        commits_by_path = {}
        for backup in backups:
            if backup.file_path and backup.file_path not in commits_by_path:
                commits_by_path[backup.file_path] = _ConfigGit.get_file_all_change_commmit(backup.file_path)

        data = {
            'manage_ip': manage_ip,
            'config_type': config_type or 'all',
            'count': len(backups),
            'items': build_backup_timeline_payload(backups, compliance_results_by_backup, commits_by_path),
        }
        return JsonResponse({'code': 200, 'message': '获取配置时间线成功', 'data': data})

    @action(detail=False, methods=['get'])
    def version_compare(self, request):
        config_backup_id = request.query_params.get('config_backup_id')
        if not config_backup_id:
            return JsonResponse({'code': 400, 'message': '缺少必要参数: config_backup_id', 'data': None})

        backup = ConfigBackup.objects.filter(id=config_backup_id).first()
        if not backup:
            return JsonResponse({'code': 404, 'message': '未找到配置备份记录', 'data': None})
        if not backup.file_path:
            return JsonResponse({'code': 400, 'message': '当前备份记录缺少 file_path', 'data': None})

        commits = _ConfigGit.get_file_all_change_commmit(backup.file_path)
        from_commit = request.query_params.get('from_commit')
        to_commit = request.query_params.get('to_commit')
        if not (from_commit and to_commit):
            if len(commits) < 2:
                return JsonResponse({'code': 404, 'message': '该配置文件缺少足够的历史提交用于对比', 'data': None})
            to_commit = commits[0]['value']
            from_commit = commits[1]['value']

        diff_result = _ConfigGit.get_commit_by_file_new(
            file=backup.file_path,
            from_commit=from_commit,
            to_commit=to_commit,
        )
        data = build_backup_compare_payload(
            backup=backup,
            from_commit=from_commit,
            to_commit=to_commit,
            diff_result=diff_result,
        )
        return JsonResponse({'code': 200, 'message': '获取配置版本对比成功', 'data': data})

    @action(detail=False, methods=['get'])
    def latest_structured(self, request):
        config_backup_id = request.query_params.get('config_backup_id')
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type', 'running')

        if config_backup_id:
            try:
                parsed_backup_id = int(config_backup_id)
            except (TypeError, ValueError):
                return JsonResponse({'code': 400, 'message': 'config_backup_id 必须为整数', 'data': None})
            document = _StructuredConfigRepository.find_by_backup_id(parsed_backup_id)
        else:
            if not manage_ip:
                return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip 或 config_backup_id', 'data': None})
            document = _StructuredConfigRepository.find_latest_by_device(manage_ip=manage_ip, config_type=config_type)

        if not document:
            return JsonResponse({'code': 404, 'message': '未找到结构化配置结果', 'data': None})

        data = build_structured_snapshot_payload(document)
        return JsonResponse({'code': 200, 'message': '获取结构化配置快照成功', 'data': data})

    @action(detail=False, methods=['get'])
    def structured_timeline(self, request):
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type')
        limit = int(request.query_params.get('limit', 20))
        limit = min(max(limit, 1), 100)

        if not manage_ip:
            return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip', 'data': None})

        documents = _StructuredConfigRepository.find_history(
            manage_ip=manage_ip,
            config_type=config_type,
            limit=limit,
        )
        data = {
            'manage_ip': manage_ip,
            'config_type': config_type or 'all',
            'count': len(documents),
            'items': build_structured_timeline_payload(documents),
        }
        return JsonResponse({'code': 200, 'message': '获取结构化配置时间线成功', 'data': data})

    @action(detail=False, methods=['get'])
    def structured_compare(self, request):
        from_backup_id = request.query_params.get('from_config_backup_id')
        to_backup_id = request.query_params.get('to_config_backup_id')
        config_backup_id = request.query_params.get('config_backup_id')
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type', 'running')

        if bool(from_backup_id) ^ bool(to_backup_id):
            return JsonResponse({'code': 400, 'message': 'from_config_backup_id 和 to_config_backup_id 需要同时传入', 'data': None})

        from_document = None
        to_document = None

        if from_backup_id and to_backup_id:
            try:
                parsed_from_id = int(from_backup_id)
                parsed_to_id = int(to_backup_id)
            except (TypeError, ValueError):
                return JsonResponse({'code': 400, 'message': '结构化对比参数必须为整数', 'data': None})
            from_document = _StructuredConfigRepository.find_by_backup_id(parsed_from_id)
            to_document = _StructuredConfigRepository.find_by_backup_id(parsed_to_id)
        elif config_backup_id:
            try:
                parsed_backup_id = int(config_backup_id)
            except (TypeError, ValueError):
                return JsonResponse({'code': 400, 'message': 'config_backup_id 必须为整数', 'data': None})
            to_document = _StructuredConfigRepository.find_by_backup_id(parsed_backup_id)
            if to_document:
                device = (to_document.get('device') or {})
                backup = (to_document.get('backup') or {})
                history = _StructuredConfigRepository.find_history(
                    manage_ip=device.get('manage_ip'),
                    config_type=backup.get('config_type'),
                    limit=100,
                )
                current_index = next(
                    (index for index, item in enumerate(history) if item.get('config_backup_id') == parsed_backup_id),
                    None,
                )
                if current_index is not None and current_index + 1 < len(history):
                    from_document = history[current_index + 1]
        else:
            if not manage_ip:
                return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip、config_backup_id 或 from/to_config_backup_id', 'data': None})
            history = _StructuredConfigRepository.find_history(
                manage_ip=manage_ip,
                config_type=config_type,
                limit=2,
            )
            if len(history) >= 2:
                to_document = history[0]
                from_document = history[1]

        if not from_document or not to_document:
            return JsonResponse({'code': 404, 'message': '缺少足够的结构化配置版本用于对比', 'data': None})

        data = build_structured_compare_payload(from_document, to_document)
        return JsonResponse({'code': 200, 'message': '获取结构化配置对比成功', 'data': data})

    @action(detail=False, methods=['get'])
    def latest_structured_drift(self, request):
        config_backup_id = request.query_params.get('config_backup_id')
        manage_ip = request.query_params.get('manage_ip')
        config_type = request.query_params.get('config_type', 'running')

        if config_backup_id:
            try:
                parsed_backup_id = int(config_backup_id)
            except (TypeError, ValueError):
                return JsonResponse({'code': 400, 'message': 'config_backup_id 必须为整数', 'data': None})
            document = _StructuredDriftRepository.find_by_to_backup_id(parsed_backup_id)
        else:
            if not manage_ip:
                return JsonResponse({'code': 400, 'message': '缺少必要参数: manage_ip 或 config_backup_id', 'data': None})
            document = _StructuredDriftRepository.find_latest_by_device(manage_ip=manage_ip, config_type=config_type)

        if not document:
            return JsonResponse({'code': 404, 'message': '未找到结构化漂移分析结果', 'data': None})

        data = build_structured_drift_payload(document)
        return JsonResponse({'code': 200, 'message': '获取结构化漂移分析成功', 'data': data})

    @action(detail=False, methods=['get'])
    def structured_drift_policy(self, request):
        policy = load_effective_drift_policy()
        local_override = load_local_drift_policy_override()
        active_db_override = load_active_db_drift_policy_override()
        data = build_structured_drift_policy_payload(
            policy=policy,
            validation=validate_drift_policy(policy),
            source={
                'default_policy': 'backend/apps/config_center/config_parse/structured/policies/default_drift_policy.json',
                'local_override_path': str(LOCAL_POLICY_OVERRIDE_PATH),
                'local_override_loaded': bool(local_override),
                'local_override_keys': sorted(local_override.keys()) if isinstance(local_override, dict) else [],
                'active_db_override_loaded': bool(active_db_override),
                'active_db_override_keys': sorted(active_db_override.keys()) if isinstance(active_db_override, dict) else [],
            },
        )
        return JsonResponse({'code': 200, 'message': '获取结构化漂移策略成功', 'data': data})

    @action(detail=False, methods=['post'])
    def validate_structured_drift_policy(self, request):
        policy_override = request.data if isinstance(request.data, dict) else {}
        if not policy_override:
            return JsonResponse({'code': 400, 'message': '请求体必须为非空 JSON object', 'data': None})
        preview = preview_merged_drift_policy(policy_override)
        data = build_structured_drift_policy_payload(
            policy=preview['policy'],
            validation=preview['validation'],
            source={
                'mode': 'preview',
                'default_policy': 'backend/apps/config_center/config_parse/structured/policies/default_drift_policy.json',
                'local_override_path': str(LOCAL_POLICY_OVERRIDE_PATH),
                'merged_with_default': True,
            },
        )
        return JsonResponse({'code': 200, 'message': '结构化漂移策略预览完成', 'data': data})


class ConfigComplianceRuleViewSet(CustomViewBase):
    # queryset = ConfigComplianceRule.objects.filter(parent__isnull=True).order_by('-id')
    queryset = ConfigComplianceRule.objects.all().order_by('-id')
    serializer_class = ConfigComplianceRuleSerializer
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('name',)
    search_fields = ('name',)

    def get_queryset(self):
        # tree = self.request.query_params.get('tree', None)
        # if tree is not None:
        #     self.queryset = self.queryset.filter(parent__isnull=True)
        children = self.request.query_params.get('children', None)
        if children is not None:
            self.queryset = self.queryset.filter(children=children)
        compliance = ConfigCompliance.objects
        return self.queryset


# 配置策略
class ConfigBackupPolicyViewSet(CustomViewBase):
    queryset = BackupPolicy.objects.all().order_by('-id')
    serializer_class = ConfigBackupPolicySerializer
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('vendor',)
    search_fields = ('vendor',)


class StructuredDriftPolicyViewSet(CustomViewBase):
    queryset = StructuredDriftPolicy.objects.all().order_by('-updated_at', '-id')
    serializer_class = StructuredDriftPolicySerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('name', 'version', 'is_active')
    search_fields = ('name', 'version')

    def _get_actor(self):
        user = getattr(getattr(self, 'request', None), 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return getattr(user, 'username', '') or 'authenticated_user'
        return 'system'

    def _record_policy_audit(self, action, policy=None, previous_policy=None, note='',
                             before_effective=None, after_effective=None):
        StructuredDriftPolicyAudit.objects.create(
            policy=policy,
            previous_policy=previous_policy,
            action=action,
            actor=self._get_actor(),
            note=note,
            effective_policy_before=before_effective or {},
            effective_policy_after=after_effective or {},
            effective_policy_diff=build_policy_diff_summary(before_effective or {}, after_effective or {}),
        )

    def _sync_active_state(self, instance):
        if not getattr(instance, 'is_active', False):
            return
        StructuredDriftPolicy.objects.exclude(pk=instance.pk).filter(is_active=True).update(is_active=False)

    def perform_create(self, serializer):
        before_effective = load_effective_drift_policy()
        instance = serializer.save()
        self._sync_active_state(instance)
        clear_drift_policy_caches()
        after_effective = load_effective_drift_policy()
        self._record_policy_audit(
            action='CREATE',
            policy=instance,
            previous_policy=None,
            note='create structured drift policy',
            before_effective=before_effective,
            after_effective=after_effective,
        )
        if instance.is_active:
            self._record_policy_audit(
                action='ACTIVATE',
                policy=instance,
                previous_policy=None,
                note='policy created as active',
                before_effective=before_effective,
                after_effective=after_effective,
            )

    def perform_update(self, serializer):
        before_effective = load_effective_drift_policy()
        previous_active = StructuredDriftPolicy.objects.filter(is_active=True).exclude(pk=serializer.instance.pk).order_by('-updated_at', '-id').first()
        instance = serializer.save()
        self._sync_active_state(instance)
        clear_drift_policy_caches()
        after_effective = load_effective_drift_policy()
        self._record_policy_audit(
            action='UPDATE',
            policy=instance,
            previous_policy=previous_active,
            note='update structured drift policy',
            before_effective=before_effective,
            after_effective=after_effective,
        )

    def perform_destroy(self, instance):
        before_effective = load_effective_drift_policy()
        super().perform_destroy(instance)
        clear_drift_policy_caches()
        after_effective = load_effective_drift_policy()
        self._record_policy_audit(
            action='DELETE',
            policy=None,
            previous_policy=instance,
            note='delete structured drift policy',
            before_effective=before_effective,
            after_effective=after_effective,
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        instance = self.get_object()
        before_effective = load_effective_drift_policy()
        previous_active = StructuredDriftPolicy.objects.filter(is_active=True).exclude(pk=instance.pk).order_by('-updated_at', '-id').first()
        StructuredDriftPolicy.objects.exclude(pk=instance.pk).filter(is_active=True).update(is_active=False)
        instance.is_active = True
        instance.save(update_fields=['is_active', 'updated_at'])
        clear_drift_policy_caches()
        after_effective = load_effective_drift_policy()
        self._record_policy_audit(
            action='ACTIVATE',
            policy=instance,
            previous_policy=previous_active,
            note='activate structured drift policy',
            before_effective=before_effective,
            after_effective=after_effective,
        )
        data = self.get_serializer(instance).data
        return JsonResponse({'code': 200, 'message': '结构化漂移策略已激活', 'data': data})

    @action(detail=True, methods=['post'])
    def rollback_to_previous(self, request, pk=None):
        instance = self.get_object()
        if not instance.is_active:
            return JsonResponse({'code': 400, 'message': '仅激活中的策略允许回滚到上一版本', 'data': None})
        latest_transition = (
            StructuredDriftPolicyAudit.objects
            .filter(policy=instance, action__in=['ACTIVATE', 'ROLLBACK'], previous_policy__isnull=False)
            .order_by('-created_at', '-id')
            .first()
        )
        target = getattr(latest_transition, 'previous_policy', None)
        if target is None:
            return JsonResponse({'code': 404, 'message': '未找到可回滚的上一激活版本', 'data': None})

        before_effective = load_effective_drift_policy()
        StructuredDriftPolicy.objects.filter(pk=instance.pk).update(is_active=False)
        StructuredDriftPolicy.objects.exclude(pk=target.pk).filter(is_active=True).update(is_active=False)
        target.is_active = True
        target.save(update_fields=['is_active', 'updated_at'])
        clear_drift_policy_caches()
        after_effective = load_effective_drift_policy()
        self._record_policy_audit(
            action='ROLLBACK',
            policy=target,
            previous_policy=instance,
            note='rollback structured drift policy to previous active version',
            before_effective=before_effective,
            after_effective=after_effective,
        )
        data = self.get_serializer(target).data
        return JsonResponse({'code': 200, 'message': '结构化漂移策略已回滚到上一激活版本', 'data': data})


class StructuredDriftPolicyAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StructuredDriftPolicyAudit.objects.select_related('policy', 'previous_policy').order_by('-created_at', '-id')
    serializer_class = StructuredDriftPolicyAuditSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ('action', 'policy', 'previous_policy')
    search_fields = ('actor', 'note')


# 配置合规表
class ConfigComplianceViewSet(CustomViewBase):
    queryset = ConfigCompliance.objects.all().order_by('-id')
    serializer_class = ConfigComplianceSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    search_fields = ('vendor',)

    @action(detail=False, methods=['get'])
    def security_baselines(self, request):
        """按规则树和厂商聚合返回安全基线规则库。"""
        root_rule_name = request.query_params.get("root_rule", "管理面硬化基线")
        vendor = request.query_params.get("vendor")

        queryset = ConfigCompliance.objects.select_related("rule", "rule__parent").filter(
            rule__parent__name=root_rule_name
        )
        if vendor:
            queryset = queryset.filter(vendor=vendor)

        payload = build_security_baseline_payload(list(queryset), root_rule_name)
        return JsonResponse(
            {
                "code": 200,
                "message": "获取安全基线规则成功",
                "data": payload,
            }
        )


class ConfigComplianceResultViewSet(CustomViewBase):
    queryset = ConfigComplianceResult.objects.all().order_by('-log_time')
    serializer_class = ConfigComplianceResultSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LargeResultsSetPagination
    filterset_class = ConfigComplianceResultFilter
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('manage_ip', 'hostname', 'rule', 'rule_id')


# 配置模板表
class ConfigTemplateViewSet(CustomViewBase):
    """
    配置合规表--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ConfigTemplate.objects.all().order_by('-id')
    serializer_class = ConfigTemplateSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    # pagination_class = LimitSet
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = PublicNetFinalFilter
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    search_fields = 'name'


# TTP模板表
class TTPTemplateViewSet(CustomViewBase):
    """
    配置合规表--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = TTPTemplate.objects.all().order_by('-id')
    serializer_class = TTPTemplateSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    # pagination_class = LimitSet
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = PublicNetFinalFilter
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    search_fields = 'name'


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, obj)


class GitConfig(APIView):
    permission_classes = ()
    authentication_classes = ()
    # permission_classes = (IsAuthenticated,)

    # authentication_classes = (JWTAuthentication, SessionAuthentication)

    def get(self, request):
        """

        :param request:
        :return:
        """
        get_param = request.GET.dict()
        # print('get_param', get_param)
        if 'get_hostip' in get_param.keys():
            _tree = ConfigTree()
            _tree.produce_tree()
            res = _tree.tree_final
            host_list = [x for x in res[0]['children']]
            if host_list:
                data = {
                    "code": 200,
                    "data": host_list,
                    "msg": "成功"
                }
                return JsonResponse(data)
            else:
                data = {
                    "code": 400,
                    "data": {},
                    "msg": "没有获取到git配置文件目录的设备IP列表"
                }
                return JsonResponse(data)
        if all(k in get_param for k in ("get_hostip_file", "config_type")):
            _tree = ConfigTree()
            if get_param['config_type'] == 'startup':
                _tree.produce_tree(root_name='startup-configuration')
            else:
                _tree.produce_tree(root_name='current-configuration')
            res = _tree.tree_final
            host_list = [x for x in res[0]['children'] if x['label'] == get_param['get_hostip_file']]
            if host_list:
                data = {
                    "code": 200,
                    "data": host_list,
                    "msg": "成功"
                }
                return JsonResponse(data)
            else:
                data = {
                    "code": 400,
                    "data": {},
                    "msg": "没有获取到git配置文件目录的设备IP列表"
                }
                return JsonResponse(data)
        if 'get_tree' in get_param.keys():
            _tree = ConfigTree()
            _tree.produce_tree()
            data = {
                "code": 200,
                "data": _tree.tree_final,
                "msg": "获取配置文件树成功"
            }
            return JsonResponse(data)
        if 'filename' in get_param.keys():
            with open(BASE_DIR + '/media/device_config/' + get_param['filename'], "r") as f:
                file_content = f.read()
                data = {
                    "code": 200,
                    "data": file_content,
                    "msg": "获取配置文件内容成功"
                }
                return JsonResponse(data, safe=False)
        if 'get_commit' in get_param.keys():
            res = _ConfigGit.get_file_all_change_commmit(file_path=get_param['file_path'])
            data = {
                "code": 200,
                "data": res,
                "msg": "获取commit记录成功"
            }
            return JsonResponse(data, safe=False)
        if 'commit_detail' in get_param.keys():
            res = _ConfigGit.get_commit_detail(get_param['commit_detail'])
            data = {
                "code": 200,
                "data": res,
                "msg": "获取commit轨迹成功"
            }
            return JsonResponse(data, safe=False)
        if all(k in get_param for k in ("file", "from_commit", "to_commit")):
            res = _ConfigGit.get_commit_by_file_new(**get_param)
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        # 获取单个文件指定commit下的变更信息
        if all(k in get_param for k in ("file", "single_commit")):
            res = _ConfigGit.get_commit_modified_by_filename(get_param['single_commit'], get_param['file'])
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        # 获取单个文件指定commit下的原始文件内容
        if all(k in get_param for k in ("file", "single_commit_real_content")):
            res = _ConfigGit.get_commit_file_content(get_param['single_commit_real_content'], get_param['file'])
            data = {
                "code": 200,
                "data": [res],
                "msg": "获取文件变更详情成功"
            }
            return JsonResponse(data, safe=False)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ComplianceResults(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'get_results' in get_param.keys():
            _res = MongoNetOps.compliance_result()
            data = {
                "code": 200,
                "data": _res,
                "msg": "获取合规检查结果成功"
            }
            return JsonResponse(data, encoder=DateEncoder)
        if any(k in get_param for k in ("rule", "compliance")):
            _res = MongoNetOps.compliance_result(**{k: v for k, v in get_param.items() if v != ''})
            data = {
                "code": 200,
                "data": _res,
                "msg": "获取合规检查结果成功"
            }
            return JsonResponse(data, encoder=DateEncoder)


class RegexTest(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)

    def post(self, request):
        post_data = request.data
        if any(k in post_data for k in ("content", "regex")):
            _regex = post_data['regex']
            content = post_data['content']  # match-compliance  mismatch-compliance
            _res = re.compile(pattern=_regex, flags=re.M).findall(string=content)
            data = {
                "code": 200,
                "data": _res,
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)


# TTP 前端页面接口
class TTPParse(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        pass

    def post(self, request):
        post_data = request.data
        if any(k in post_data for k in ("test_content", "ttp_template")):
            data_to_parse = post_data['test_content']
            ttp_template = post_data['ttp_template']
            parser = ttp(data=data_to_parse, template=ttp_template)
            parser.parse()
            # print result in JSON format
            results = parser.result(format='json')[0]
            _res = ''
            data = {
                "code": 200,
                "data": results,
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)


# TextFSM 前端页面接口
class TextFSMParse(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'get_tree' in get_param.keys():
            _tree = FSMTree()
            _tree.produce_tree()
            data = {
                "code": 200,
                "data": _tree.tree_final,
                "msg": "获取文件树成功"
            }
            return JsonResponse(data)
        if 'filename' in get_param.keys():
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + get_param['filename'], "r",
                      encoding="utf-8") as f:
                file_content = f.read()
            data = {
                "code": 200,
                "data": file_content,
                "msg": "获取配置文件内容成功"
            }
            return JsonResponse(data, safe=False)
        data = {
            "code": 400,
            "data": [],
            "msg": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        if 'add_fsm_platform' in post_data.keys():
            filename = post_data['add_fsm_platform']
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + filename, "w",
                      encoding="utf-8") as f:
                f.write('')
            data = {
                "code": 200,
                "data": 'ok',
                "msg": "新建配置文件内容成功"
            }
            return JsonResponse(data, safe=False)
        if any(k in post_data for k in ("save_fsm_template", "filename")):
            save_fsm_template = post_data['save_fsm_template']
            with open(BASE_DIR + '/utils/connect_layer/zetmiko/templates/' + post_data['filename'], "w",
                      encoding="utf-8") as f:
                f.write(save_fsm_template)
            data = {
                "code": 200,
                "data": 'ok',
                "msg": "保存配置文件内容成功"
            }
            return JsonResponse(data, safe=False)

        if any(k in post_data for k in ("test_content", "fsm_platform")):
            data_to_parse = post_data['test_content']
            fsm_platform = post_data['fsm_platform']
            res = BatManMain.test_fsm(content=data_to_parse, template=fsm_platform)
            data = {
                "code": 200,
                "data": json.dumps(res),
                "msg": "解析完成"
            }
            return JsonResponse(data, encoder=DateEncoder)

        data = {
            "code": 400,
            "data": [],
            "msg": "没有匹配到任何参数"
        }
        return JsonResponse(data, encoder=DateEncoder)


class Jinja2View(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        # jinja2渲染结果
        if all(k in post_data for k in ("render", "yaml_content", "jinja2_content")):
            yaml_content = post_data['yaml_content']
            yaml_res = yaml.safe_load(yaml_content)
            data_to_parse = post_data['jinja2_content']
            success, render_res = jinja_render(yaml_res, data_to_parse)
            data = {
                "code": 200 if success else 400,
                "results": [
                    {
                        'yaml_res': yaml_res,
                        'render_res': render_res,
                    }
                ],
                "message": "解析成功"
            }
            return JsonResponse(data)

        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ConfigFileView(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_params = request.GET.dict()
        if 'file_path' in get_params.keys():
            res = _ConfigGit.get_file_all_change_commmit(file_path=get_params['file_path'])
            data = {
                "code": 200,
                "results": res,
                "message": "获取成功"
            }
            return JsonResponse(data)
        # 暂时没调用上
        if 'download_file' in get_params.keys():
            f = _ConfigGit.get_file_all_change_commmit(file_path=get_params['file_path'])
            response = FileResponse(f, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename={get_params["download_file"]}'
            return response
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)

    def post(self, request):
        post_data = request.data
        if post_data["commit"]:
            get_file_commit = _ConfigGit.get_file_content_by_commit(post_data['file_path'], post_data["commit"])
            if get_file_commit:
                data = {
                    "code": 200,
                    "results": get_file_commit,
                    "message": "success"
                }
                return JsonResponse(data)
        else:
            try:
                file_content = default_storage.open(f"device_config/{post_data['file_path']}").read().decode('utf-8')
                data = {
                    "code": 200,
                    "results": file_content,
                    "msg": "success"
                }
                return JsonResponse(data, safe=False)
            except Exception as e:
                return JsonResponse({"code": 400, "msg": str(e)}, safe=False)
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)


class ConfigFileListView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        get_file_commit = _ConfigGit.get_file_content_by_commit(get_param['file_path'], get_param["commit"])
        if get_file_commit:
            file_stream = io.BytesIO(bytes(get_file_commit.encode()))
            # 设置HTTP响应头
            response = StreamingHttpResponse(file_stream, content_type='application/octet-stream')
            response['Content-Disposition'] = f"attachment; filename={get_param['file_path'].split('/')[-1]}"
            return response
        data = {
            "code": 400,
            "results": [],
            "message": "没有捕获任何操作"
        }
        return JsonResponse(data)
