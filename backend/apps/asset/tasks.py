# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:
   Author:          Lijiamin
   date：           2022/9/8 17:46
-------------------------------------------------
   Change Activity:
                    2022/9/8 17:46
-------------------------------------------------
"""
from __future__ import absolute_import, unicode_literals
import json
import logging
import paramiko

from apps.asset.models import NetworkDevice
from netaxe.celery import AxeTask, app
from utils.connect_layer.snmp.snmp_test import probe_snmp
from utils.crypt_pwd import CryptPwd

admin_file_logger = logging.getLogger('webssh')
asset_task_logger = logging.getLogger(__name__)


@app.task(base=AxeTask, once={'graceful': True})
def admin_file(filename, txts, header=None):
    try:
        if header:
            f = open(filename, 'a')
            f.write(json.dumps(header) + '\n')
            for txt in txts:
                f.write(json.dumps(txt) + '\n')
            f.close()
        else:
            with open(filename, 'a') as f:
                for txt in txts:
                    f.write(txt)
    except Exception as e:
        admin_file_logger.error("记录操作失败:{}".format(str(e)))


def _is_valid_manage_ip(device):
    return bool(device.manage_ip and device.manage_ip != '0.0.0.0')


def _should_check_snmp(device):
    return _is_valid_manage_ip(device) and bool(device.snmp_community and device.snmp_community != '-')


def _should_check_ssh(device):
    return _is_valid_manage_ip(device) and device.ssh_enable == 'account'


def _check_snmp_connectivity(device):
    success, result = probe_snmp(
        ip=device.manage_ip,
        snmp_version=(device.snmp_version or 'v2c'),
        snmp_community=device.snmp_community,
        port=device.snmp_port,
        timeout=5,
        retries=1,
    )
    updates = {'snmp_status': success}
    if success and result and result.strip():
        updates['name'] = result.strip()
    return success, result, updates


def _check_ssh_connectivity(device):
    account = device.ssh_account
    if not account:
        return False, 'SSH纳管账户未配置', {'ssh_status': False}
    if not account.username or not account.password:
        return False, 'SSH纳管账户用户名或密码未配置', {'ssh_status': False}

    crypt = CryptPwd()
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_client.connect(
            device.manage_ip,
            port=account.port or 22,
            username=account.username.strip(),
            password=crypt.decrypt_pwd(account.password).strip(),
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        return True, 'SSH连接测试成功', {'ssh_status': True}
    except Exception as exc:
        return False, str(exc), {'ssh_status': False}
    finally:
        try:
            transport = ssh_client.get_transport()
            if transport:
                transport.close()
            ssh_client.close()
        except Exception:
            pass


@app.task(base=AxeTask, once={'graceful': True})
def check_network_device_protocol_connectivity(device_ids=None):
    """
    巡检 NetworkDevice 的 SNMP / SSH 纳管连通性，并回填探测结果。

    说明：
    - SNMP：存在有效管理 IP 且配置了 SNMP community 的设备参与巡检，成功时回填 snmp_status，
      若获取到设备 sysName 则同时回填 name。
    - SSH：ssh_enable=account 的设备参与巡检，成功/失败回填 ssh_status。
    """
    queryset = NetworkDevice.objects.all().select_related('ssh_account').order_by('-id')
    if device_ids:
        queryset = queryset.filter(id__in=device_ids)

    summary = {
        'device_total': queryset.count(),
        'snmp_candidate': 0,
        'snmp_success': 0,
        'snmp_failed': 0,
        'ssh_candidate': 0,
        'ssh_success': 0,
        'ssh_failed': 0,
        'updated_devices': 0,
    }

    asset_task_logger.info(
        "开始巡检网络设备纳管连通性，总设备数: %s",
        summary['device_total'],
    )

    for device in queryset.iterator(chunk_size=100):
        update_fields = []
        protocol_updates = {}

        if _should_check_snmp(device):
            summary['snmp_candidate'] += 1
            try:
                success, message, updates = _check_snmp_connectivity(device)
                protocol_updates.update(updates)
                if success:
                    summary['snmp_success'] += 1
                    asset_task_logger.info(
                        "设备 %s SNMP巡检成功: %s", device.manage_ip, message)
                else:
                    summary['snmp_failed'] += 1
                    asset_task_logger.warning(
                        "设备 %s SNMP巡检失败: %s", device.manage_ip, message)
            except Exception as exc:
                summary['snmp_failed'] += 1
                protocol_updates['snmp_status'] = False
                asset_task_logger.exception(
                    "设备 %s SNMP巡检异常: %s", device.manage_ip, str(exc))

        if _should_check_ssh(device):
            summary['ssh_candidate'] += 1
            try:
                success, message, updates = _check_ssh_connectivity(device)
                protocol_updates.update(updates)
                if success:
                    summary['ssh_success'] += 1
                    asset_task_logger.info(
                        "设备 %s SSH巡检成功: %s", device.manage_ip, message)
                else:
                    summary['ssh_failed'] += 1
                    asset_task_logger.warning(
                        "设备 %s SSH巡检失败: %s", device.manage_ip, message)
            except Exception as exc:
                summary['ssh_failed'] += 1
                protocol_updates['ssh_status'] = False
                asset_task_logger.exception(
                    "设备 %s SSH巡检异常: %s", device.manage_ip, str(exc))

        for field_name, field_value in protocol_updates.items():
            if getattr(device, field_name) != field_value:
                setattr(device, field_name, field_value)
                update_fields.append(field_name)

        if update_fields:
            device.save(update_fields=update_fields)
            summary['updated_devices'] += 1

    asset_task_logger.info("网络设备纳管连通性巡检完成，统计结果: %s", summary)
    return summary
