# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re
import time
import asyncio
from datetime import datetime, date, timedelta
from celery import shared_task
from django.template import loader
from netaxe.celery import AxeTask
from netaxe.settings import DEBUG
from django.utils import timezone
from apps.automation.tools.model_api import get_device_info_v2
# from apps.config_center.compliance import config_file_verify
from apps.config_center.config_parse.config_parse import config_file_parse
from apps.config_center.git_tools.git_proc import push_file
from apps.config_center.my_nornir import config_backup_nornir
from apps.config_center.models import ConfigBackup, ConfigCompliance, ConfigComplianceResult
from django.core.files.storage import default_storage
from utils.db.mongo_ops import MongoOps
from service_mesh import msg_gateway_runner

config_mongo = MongoOps(db='netops', coll='ConfigBackupStatistics')

if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config'


@shared_task(base=AxeTask, once={'graceful': True})
def config_backup(**kwargs):
    log_time = datetime.now().strftime("%Y-%m-%d")
    start_time = time.time()
    msg_gateway_runner.send_wechat(channel="netdevops", content=f"配置备份开始，时间:{log_time}")
    today = timezone.now()
    if kwargs:
        hosts = get_device_info_v2(**kwargs)
    else:
        hosts = get_device_info_v2()
    # 配置备份任务
    result = config_backup_nornir(hosts)
    end_time = time.time()
    time_use = int(int(end_time - start_time) / 60)
    fail_host_list = [x for x in result.failed_hosts.keys()]
    fail_host = '\n'.join([x for x in result.failed_hosts.keys()])
    msg_gateway_runner.send_wechat(channel="netdevops",
                                   content=f"配置备份完成，耗时:{time_use}分\n备份失败设备:\n{fail_host}")
    success_host_list = [x['manage_ip'] for x in hosts if x not in fail_host_list]
    # 配置解析
    loop = asyncio.get_event_loop()
    loop.run_until_complete(config_file_parse())
    # config_file_parse()
    # 推送git
    commit, changed_files, untracked_files = push_file()
    if changed_files or untracked_files:
        html_tmp = loader.render_to_string(
            'config_center/config_backup.html',
            dict(commit=commit, changedFiles=changed_files, untracked_files=untracked_files), None, None)
        # html_res = str(html_tmp, "utf-8")
        # email_addr = ['dd@dd.com']
        # email_subject = '配置备份结果_' + datetime.now().strftime("%Y-%m-%d %H:%M")
        # email_text_content = html_res
        # msg_gateway_runner.send_email(user=email_addr, subject=email_subject, content=email_text_content)
    for host in hosts:
        if host['manage_ip'] in fail_host_list:
            ConfigBackup.objects.create(
                name=host['name'], manage_ip=host['manage_ip'],
                config_status='FAILED',
                status=host['status'], idc_name=host['idc__name'],
                vendor_name=host['vendor__name'], model_name=host['model__name'],
                git_type='change', commit='', file_path='', last_time=today
            )
        elif host['manage_ip'] in success_host_list:
            ConfigBackup.objects.create(
                name=host['name'], manage_ip=host['manage_ip'],
                config_status='SUCCESS',
                status=host['status'], idc_name=host['idc__name'],
                vendor_name=host['vendor__name'], model_name=host['model__name'],
                git_type='change', commit='', file_path=result[host['manage_ip']][0].filename, last_time=today
            )
            # 开始配置合规检查
    for change_host in changed_files:
        hostip = change_host.split('/')[1]
        host_info = [host for host in hosts if host['manage_ip'] == hostip]
        if host_info:
            ConfigBackup.objects.filter(name=host_info[0]['name'], manage_ip=host_info[0]['manage_ip'],
                                        status=host_info[0]['status'],
                                        idc_name=host_info[0]['idc__name'],
                                        vendor_name=host_info[0]['vendor__name'],
                                        model_name=host_info[0]['model__name'], last_time=today
                                        ).update(
                config_status='SUCCESS', git_type='change', commit=commit, file_path=change_host
            )
    for untracked_host in untracked_files:
        hostip = untracked_host.split('/')[1]
        host_info = [host for host in hosts if host['manage_ip'] == hostip]
        if host_info:
            ConfigBackup.objects.filter(name=host_info[0]['name'], manage_ip=host_info[0]['manage_ip'],
                                        status=host_info[0]['status'],
                                        idc_name=host_info[0]['idc__name'],
                                        vendor_name=host_info[0]['vendor__name'],
                                        model_name=host_info[0]['model__name'], last_time=today
                                        ).update(
                config_status='SUCCESS', git_type='add', commit=commit, file_path=untracked_host
            )
    msg_gateway_runner.send_wechat(channel='netdevops',
                                   content=f"配置备份推送完成\n变更配置文件数:{len(changed_files)}\n新增配置文件数:{len(untracked_files)}\ncommit:{commit}")
    config_safe_baseline_check.apply_async(kwargs={}, queue=CELERY_QUEUE,
                                           retry=True)
    return


# 配置合规检查
@shared_task(base=AxeTask, once={'graceful': True})
def config_safe_baseline_check(**kwargs):
    vendor_map = {
        'hp_comware': 'H3C',
        'huawei': 'HUAWEI',
    }
    start_datetime = date.today().strftime('%Y-%m-%d') + ' 00:00:00'
    end_datetime = date.today().strftime('%Y-%m-%d') + ' 23:59:59'
    rules_q = ConfigCompliance.objects.all().values()
    res = ConfigBackup.objects.filter(last_time__range=(start_datetime, end_datetime),
                                      manage_ip='10.254.2.151').values()
    for host_info in res:
        vendor = host_info['file_path'].split('/')[-1].split('-')[0]
        if vendor in vendor_map.keys():
            rules = [x for x in rules_q if x['vendor'] == vendor_map[vendor]]
            data_to_parse = default_storage.open(f"device_config/{host_info['file_path']}").read()
            data_to_parse = data_to_parse.decode('utf-8')
            # print(data_to_parse)
            for rule in rules:
                _data = {
                    'compliance': '',
                    'rule_id': rule['id'],
                    'manage_ip': host_info['manage_ip'],
                    'hostname': host_info['name'],
                    'vendor': vendor_map[vendor],
                    'rule': rule['name'],
                    'regex': rule['regex'],
                    'log_time': timezone.now()
                }
                _regex = rule['regex']
                _pattern = rule['pattern']  # match-compliance  mismatch-compliance
                _res = re.compile(pattern=_regex, flags=re.M).findall(string=data_to_parse)
                # 匹配-合规 反之 不匹配-不合规
                if _pattern == 'match-compliance':
                    _data['compliance'] = '合规' if _res else '不合规'
                # 不匹配-合规 反之 匹配-不合规
                elif _pattern == 'mismatch-compliance':
                    _data['compliance'] = '不合规' if _res else '合规'
                res_query = ConfigComplianceResult.objects.filter(manage_ip=host_info['manage_ip'], rule_id=rule['id'])
                # logger.debug('res_query', res_query)
                if res_query:
                    ConfigComplianceResult.objects.filter(manage_ip=host_info['manage_ip'], rule_id=rule['id']).update(
                        **_data)
                else:
                    ConfigComplianceResult.objects.create(**_data)
