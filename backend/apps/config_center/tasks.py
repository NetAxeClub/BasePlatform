# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import time
import asyncio
from datetime import datetime
from celery import shared_task
from django.template import loader
from netaxe.celery import AxeTask
from netaxe.settings import DEBUG
from apps.automation.tools.model_api import get_device_info_v2
from apps.config_center.compliance import config_file_verify
from apps.config_center.config_parse.config_parse import config_file_parse
from apps.config_center.git_tools.git_proc import push_file
from apps.config_center.my_nornir import config_backup_nornir
from apps.config_center.models import ConfigBackup
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
    if kwargs:
        hosts = get_device_info_v2(**kwargs)
    else:
        hosts = get_device_info_v2()
    # 配置备份任务
    result = config_backup_nornir(hosts)
    end_time = time.time()
    time_use = int(int(end_time - start_time) / 60)
    fail_host = '\n'.join([x for x in result.failed_hosts.keys()])
    for host in hosts:
        if host['manage_ip'] not in fail_host:
            ConfigBackup.objects.create(
                name=host['name'], manage_ip=host['manage_ip'], config_status='SUCCESS', status=host['status'],
                idc_name=host['idc__name'], vendor_name=host['vendor__name'], model_name=host['model__name']
            )
        else:
            ConfigBackup.objects.create(
                name=host['name'], manage_ip=host['manage_ip'], config_status='FAILED', status=host['status'],
                idc_name=host['idc__name'], vendor_name=host['vendor__name'], model_name=host['model__name']
            )
    msg_gateway_runner.send_wechat(channel="netdevops", content=f"配置备份完成，耗时:{time_use}分\n备份失败设备:\n{fail_host}")
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
    msg_gateway_runner.send_wechat(channel='netdevops', content=f"配置备份推送完成\n变更配置文件数:{len(changed_files)}\n新增配置文件数:{len(untracked_files)}\ncommit:{commit}")
    # 合规性检查
    loop.run_until_complete(config_file_verify())
    return