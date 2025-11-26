# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      model_api
   Description:
   Author:          Lijiamin
   date：           2022/9/8 11:02
-------------------------------------------------
   Change Activity:
                    2022/9/8 11:02
-------------------------------------------------
"""
import traceback
from datetime import datetime
from collections import OrderedDict
from django.db import connections
from apps.asset.models import NetworkDevice, AssetAccount
from apps.device_api.models import DeviceSubCollectionPlan
from apps.device_api.serializers import DeviceSubCollectionPlanSerializer
from utils.crypt_pwd import CryptPwd


# 获取登录网络设备所需相关信息
def get_auto_device(**kwargs):
    hosts = []

    _CryptPwd = CryptPwd()  # 密码解码
    execute_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # 定时任务执行时间
    support_vendor = ['H3C', 'Huawei', 'Ruijie', 'Maipu', 'Hillstone', 'Mellanox', 'centec', 'Cisco', 'CISCO', 'cisco', 'ZTE']

    if kwargs:
        kwargs['status'] = 0
        kwargs['auto_enable'] = True
        all_devs = NetworkDevice.objects.filter(**kwargs).select_related(
            'idc_model', 'model', 'category', 'vendor', 'idc', 'plan',
            'rack').values(
            'id', 'serial_num', 'manage_ip', 'name', 'soft_version', 'vendor__name', 'vendor__alias',
            'category__name', 'model__name', 'plan_id', 'ssh_enable', 'ssh_account',
            'netconf_enable', 'netconf_account',
            'patch_version', 'soft_version', 'status', 'idc__name', 'auto_enable', 'execute_node',
            'ha_status', 'chassis', 'slot', 'bind_ip__ipaddr')
    else:
        # 获取所有cmdb设备，过滤需要设备:在线,主设备或独立设备,有管理ip,支持的类型
        all_devs = NetworkDevice.objects.filter(
            status=0, vendor__alias__in=support_vendor, auto_enable=True).select_related(
            'idc_model', 'model', 'category', 'vendor', 'idc', 'plan',
            'rack').values(
            'id', 'serial_num', 'manage_ip', 'name', 'soft_version', 'vendor__name', 'vendor__alias',
            'category__name', 'model__name', 'plan_id', 'ssh_enable', 'ssh_account',
            'netconf_enable', 'netconf_account',
            'patch_version', 'soft_version', 'status', 'idc__name', 'auto_enable', 'execute_node',
            'ha_status', 'chassis', 'slot')  # bind_ip__ipaddr

    # 获取所有不重复的account_ids
    account_ids = set()
    for dev in all_devs:
        if dev.get('ssh_enable') == 'account' and dev.get('ssh_account'):
            account_ids.add(dev['ssh_account'])
        if dev.get('netconf_enable') == 'account' and dev.get('netconf_account'):
            account_ids.add(dev['netconf_account'])

    # 优化： 一次性查询所有账户信息
    account_dict = {}
    if account_ids:
        accounts = AssetAccount.objects.filter(id__in=account_ids).values(
            'id', 'name', 'username', 'password', 'protocol', 'port'
        )
        for account in accounts:
            account_dict[account['id']] = account

    # 优化：批量查询所有设备的子采集方案，避免在collect_device中逐个查询
    plan_ids = [dev.get('plan_id') for dev in all_devs if dev.get('plan_id')]
    plan_sub_plans_map = {}
    
    if plan_ids:
        # 批量查询所有子采集方案，避免N+1查询问题
        sub_plans = DeviceSubCollectionPlan.objects.filter(
            summary_plan_id__in=plan_ids,
            summary_plan__is_active=True
        ).select_related('summary_plan').order_by('id')
        
        # 使用序列化器序列化子采集方案，统一数据格式
        serializer = DeviceSubCollectionPlanSerializer(sub_plans, many=True)
        sub_plans_data = serializer.data
        
        # 按 plan_id 分组
        for sub_plan_data in sub_plans_data:
            plan_id = sub_plan_data.get('summary_plan')
            if plan_id not in plan_sub_plans_map:
                plan_sub_plans_map[plan_id] = []
            plan_sub_plans_map[plan_id].append(sub_plan_data)
    
    # 遍历设备，使用预加载的账户信息和子采集方案
    for dev in all_devs:
        try:
            tmp_protocol = []
            if dev.get('ssh_enable') == 'account' and dev.get('ssh_account'):
                tmp_account = account_dict.get(dev['ssh_account'])
                if tmp_account:
                    _protocol = tmp_account["protocol"].lower()
                    dev[_protocol] = dict()
                    dev[_protocol]['username'] = tmp_account["username"]
                    dev[_protocol]['password'] = _CryptPwd.decrypt_pwd(tmp_account["password"])
                    dev[_protocol]['port'] = tmp_account["port"]
                    tmp_protocol.append(_protocol)
            if dev.get('netconf_enable') == 'account' and dev.get('netconf_account'):
                tmp_account = account_dict.get(dev['netconf_account'])
                if tmp_account:
                    _protocol = tmp_account["protocol"].lower()
                    dev[_protocol] = dict()
                    dev[_protocol]['username'] = tmp_account["username"]
                    dev[_protocol]['password'] = _CryptPwd.decrypt_pwd(tmp_account["password"])
                    dev[_protocol]['port'] = tmp_account["port"]
                    tmp_protocol.append(_protocol)
            tmp_protocol = list(set(tmp_protocol))
            dev['protocol'] = tmp_protocol
            
            # 添加子采集方案信息到设备字典中
            plan_id = dev.get('plan_id')
            if plan_id and plan_id in plan_sub_plans_map:
                dev['sub_plans'] = plan_sub_plans_map[plan_id]
            else:
                dev['sub_plans'] = []

            # 最后每个设备加上执行时间
            dev['execute_time'] = execute_time
            hosts.append(dev)
        except Exception as e:
            print(traceback.print_exc())
            print(e)

    result = OrderedDict()
    for item in hosts:
        result.setdefault(item['manage_ip'], {**item})
    connections.close_all()
    return list(result.values())
