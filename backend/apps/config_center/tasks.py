# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re
import time
import logging
from datetime import datetime, timedelta
from celery import shared_task
# from django.template import loader
from netaxe.celery import AxeTask
from netaxe.settings import DEBUG
from django.utils import timezone
# from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from netaxe.settings import BASE_DIR
from django.db import connections
from apps.automation.tools.base_connection import BaseConn
from apps.automation.tools.model_api import get_device_info_v2
from apps.config_center.git_tools.git_proc import ConfigGit
from apps.config_center.config_parse.config_parse import config_file_parse
from apps.config_center.git_tools.git_proc import push_file
# from apps.config_center.my_nornir import config_backup_nornir
from apps.config_center.models import ConfigBackup, BackupPolicy, ConfigComplianceResult, ConfigComplianceRule
from utils.db.mongo_ops import MongoOps

logger = logging.getLogger('automation')
config_mongo = MongoOps(db='metric', coll='level2')
BACKUP_PATH = BASE_DIR + '/media/device_config/current-configuration'

_ConfigGit = ConfigGit()

if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config'


@shared_task(base=AxeTask, once={'graceful': True})
def config_compliance(**kwargs):
    def compliance_proc(**kwargs):
        compliance = kwargs['compliance']
        _regex = compliance['regex']
        return re.compile(pattern=_regex, flags=re.M).findall(string=kwargs['data_to_parse'])

    vendor_map = ['H3C', 'Huawei', 'Hillstone']
    today = timezone.now().date()

    # 按优先级尝试多个日期范围：先当天（昨天至今），再依次往前一天
    for days_back in range(0, 3):  # 0=昨天至今, 1=前天至昨天, 2=大前天至前天
        start_datetime = timezone.make_aware(
            datetime.combine(today - timedelta(days=days_back + 1), datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(today - timedelta(days=days_back), datetime.max.time())
        )
        config_files_qs = ConfigBackup.objects.filter(
            last_time__range=(start_datetime, end_datetime),
            config_status='SUCCESS'
        )
        count = config_files_qs.count()
        if count > 0:
            if days_back > 0:
                logger.info('当天无配置备份，使用前 %s 天数据进行合规检查，共 %s 条', days_back, count)
            break
    else:
        logger.warning('近 3 天均无 SUCCESS 的配置备份，跳过合规检查')
        return
    for config_file in config_files_qs.iterator():
        if config_file.vendor in vendor_map:
            if not default_storage.exists(config_file.file_path):
                continue
            data_to_parse = default_storage.open(config_file.file_path).read().decode('utf-8')
            rules = ConfigComplianceRule.objects.all().iterator()
            for rule in rules:
                childrens = rule.children.all()
                # 按厂商分组，同一厂商的规则使用逻辑运算符 OR
                for child in childrens:
                    logger.info(f"检查项：{child.name}")
                    logger.info(f"检查项ID：{child.id}")
                    # 跟这个检查项有关的具体匹配规则
                    # 配置文件的vendor_alias  和  规则的compliance vendor 要对的上
                    compliances = child.relate_compliance.all().values()
                    vendor_compliance_list = {}
                    for compliance in compliances:
                        if compliance['vendor'] in vendor_compliance_list.keys():
                            vendor_compliance_list[compliance['vendor']].append(compliance)
                        else:
                            vendor_compliance_list[compliance['vendor']] = [compliance]
                    # 根据厂商分类
                    for vendor_compliance in vendor_compliance_list.keys():
                        final_res = []
                        rule_regex_lines = []
                        match_detail_list = []
                        if vendor_compliance == config_file.vendor:
                            for sub_compliance in vendor_compliance_list[vendor_compliance]:
                                _pattern = sub_compliance['pattern']  # match-compliance  mismatch-compliance
                                _regex = sub_compliance.get('regex', '')
                                res = compliance_proc(
                                    data_to_parse=data_to_parse,
                                    compliance=sub_compliance,
                                )
                                # 收集规则摘要（便于前端展示“检查规则”）
                                rule_regex_lines.append(f"{_pattern}: {_regex}")
                                # 收集匹配详情：匹配到的内容列表，便于展示“为什么合规/不合规”
                                match_detail_list.append({
                                    'pattern': _pattern,
                                    'regex': _regex,
                                    'matched': list(res) if res else [],
                                    'passed': (True if res else False) if _pattern == 'match-compliance' else (False if res else True),
                                })
                                if _pattern == 'match-compliance':
                                    final_res.append(True if res else False)
                                elif _pattern == 'mismatch-compliance':
                                    final_res.append(False if res else True)
                            _data = {
                                'compliance': '合规' if any(final_res) else '不合规',
                                'rule_id': child.id,
                                'manage_ip': config_file.manage_ip,
                                'hostname': config_file.name,
                                'vendor': config_file.vendor,
                                'rule': child.name,
                                'log_time': timezone.now(),
                                'config_file_path': config_file.file_path or '',
                                'backup_time': config_file.last_time,
                                'config_backup_id': config_file.id,
                                'rule_regex': '\n'.join(rule_regex_lines) if rule_regex_lines else None,
                                'match_detail': match_detail_list if match_detail_list else None,
                            }
                            res_query = ConfigComplianceResult.objects.filter(manage_ip=config_file.manage_ip,
                                                                              rule_id=child.id)
                            if res_query:
                                ConfigComplianceResult.objects.filter(manage_ip=config_file.manage_ip,
                                                                      rule_id=child.id).update(
                                    **_data)
                            else:
                                ConfigComplianceResult.objects.create(**_data)


@shared_task(base=AxeTask, once={'graceful': True})
def backup_device_config_sub(**kwargs):
    connections.close_all()
    today = kwargs['today']
    policy_map = kwargs['policy_map']
    hostip = kwargs['manage_ip']  # 设备管理IP地址
    class_instance = BaseConn(**kwargs)
    # filename = f"current-configuration/{hostip}/{kwargs['vendor__alias']}_{hostip}.txt"
    try:
        flag, res = class_instance.backup_command(cmds=policy_map)
        cmd_map = {
            'startup_command': 'startup',
            'current_command': 'running',
        }
        if flag:
            for cmd in res.keys():
                device_q = ConfigBackup.objects.filter(manage_ip=hostip, config_type=cmd_map[cmd])
                if device_q:
                    ConfigBackup.objects.filter(manage_ip=hostip, config_type=cmd_map[cmd]).update(
                        name=kwargs['name'],
                        config_status='SUCCESS',
                        status=kwargs['status'],
                        idc_name=kwargs['idc__name'],
                        vendor=kwargs['vendor__alias'],
                        model_name=kwargs['model__name'],
                        file_path=res[cmd],
                        last_time=today, detail='')
                else:
                    ConfigBackup.objects.create(name=kwargs['name'], manage_ip=hostip, config_type=cmd_map[cmd],
                                                config_status='SUCCESS',
                                                status=kwargs['status'], idc_name=kwargs['idc__name'],
                                                vendor=kwargs['vendor__alias'],
                                                model_name=kwargs['model__name'], file_path=res[cmd],
                                                last_time=today, detail='')
        else:
            device_q = ConfigBackup.objects.filter(manage_ip=hostip)
            if device_q:
                ConfigBackup.objects.filter(manage_ip=hostip).update(name=kwargs['name'],
                                                                     config_status='FAILED',
                                                                     status=kwargs['status'],
                                                                     idc_name=kwargs['idc__name'],
                                                                     vendor=kwargs['vendor__alias'],
                                                                     model_name=kwargs['model__name'],
                                                                     file_path='',
                                                                     last_time=today, detail=res.get('error') or '')
            else:
                ConfigBackup.objects.create(
                    name=kwargs['name'], manage_ip=hostip,
                    config_status='FAILED',
                    status=kwargs['status'], idc_name=kwargs['idc__name'], vendor=kwargs['vendor__alias'],
                    model_name=kwargs['model__name'], last_time=today, detail=res.get('error') or ''
                )
    except RuntimeError as e:
        logger.error(e)
        device_q = ConfigBackup.objects.filter(manage_ip=hostip)
        if device_q:
            ConfigBackup.objects.filter(manage_ip=hostip).update(name=kwargs['name'],
                                                                 config_status='FAILED',
                                                                 status=kwargs['status'], idc_name=kwargs['idc__name'],
                                                                 vendor=kwargs['vendor__alias'],
                                                                 model_name=kwargs['model__name'], file_path='',
                                                                 last_time=today, detail=str(e))
        else:
            ConfigBackup.objects.create(
                name=kwargs['name'], manage_ip=hostip,
                config_status='FAILED',
                status=kwargs['status'], idc_name=kwargs['idc__name'], vendor=kwargs['vendor__alias'],
                model_name=kwargs['model__name'], last_time=today, detail=str(e)
            )
    return {}


@shared_task(base=AxeTask, once={'graceful': True})
def backup_device_config(**kwargs):
    start_time = time.time()
    today = timezone.now()
    if kwargs:
        hosts = get_device_info_v2(**kwargs)
    else:
        hosts = get_device_info_v2()

    logger.info('获取所有设备信息结束')
    p = BackupPolicy.objects.all().values()
    policy_map = {k['vendor']: {'startup_command': k['startup_command'], 'current_command': k['current_command']} for k
                  in p}
    # 参数初始化
    net_tower_tasks = []  # 寻觅任务id集合
    # 批量下发任务
    for host in hosts:
        if host['vendor__alias'] in policy_map.keys() and host['manage_ip'] != '0.0.0.0':
            host['today'] = today
            host['policy_map'] = policy_map[host['vendor__alias']]
            net_tower_tasks.append(
                backup_device_config_sub.apply_async(
                    kwargs=host,
                    queue='config',
                    retry=True))

    # 去除结果中的<EagerResult: None>
    for task in net_tower_tasks:
        if 'EagerResult' in str(type(task)):
            logger.info("存在无效task")
            net_tower_tasks.remove(task)
    # 获取tasks任务数量
    # net_tower_tasks_counters = len(net_tower_tasks)
    # net_tower_tasks_bak = net_tower_tasks.copy()
    # 等待子任务全部执行结束后执行下一步
    while len(net_tower_tasks) != 0:
        for i in net_tower_tasks:
            try:
                if i.ready():
                    net_tower_tasks.remove(i)
            except Exception as e:
                logger.error(str(e))
                net_tower_tasks.remove(i)
        time.sleep(10)
        logger.info(len(net_tower_tasks))
    logger.info('子任务全部执行结束')
    # 配置解析
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(config_file_parse())
    end_time = time.time()
    time_use = int(int(end_time - start_time) / 60)
    # msg_gateway_runner.send_wechat(channel="netdevops",
    #                                content=f"配置备份完成，耗时:{time_use}分\n")
    config_compliance.apply_async(kwargs={}, queue=CELERY_QUEUE, retry=True)
    git_push_config.apply_async(kwargs=dict(today=today), queue=CELERY_QUEUE, retry=True)
    return


@shared_task(base=AxeTask, once={'graceful': True})
def git_push_config(**kwargs):
    today = kwargs['today']
    log_time = datetime.now().strftime("%Y-%m-%d")
    commit_results, changed_files, untracked_files = push_file()
    for commit_hexsha in commit_results:
        commit_info = _ConfigGit.get_commit_detail(commit_hexsha)
        for commit in commit_info:
            ConfigBackup.objects.filter(last_time=today, file_path=commit['value']).update(config_status='SUCCESS')
    config_mongo.insert({
        'name': 'config_backup_git_status',
        'data': {
            'change': len(changed_files),
            'add': len(untracked_files),
        },
        'log_time': log_time
    })
