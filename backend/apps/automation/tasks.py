# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:
   Author:          Lijiamin
   date：           2022/9/8 09:32
-------------------------------------------------
   Change Activity:
                    2022/9/8 09:32
-------------------------------------------------
"""
from __future__ import absolute_import, unicode_literals

import json
import logging
import math
import re
import asyncio
import time
import traceback
import ipaddr as IPaddr
import netaddr
from celery import shared_task
from netaxe.celery import AxeTask
from collections import OrderedDict
from django_celery_results.models import TaskResult
from django.core.cache import cache
from django.db import connections
from datetime import datetime, date
from apps.asset.models import NetworkDevice
from apps.automation.models import CollectionRule, CollectionMatchRule
from apps.int_utilization.models import InterfaceUsed
from apps.automation.tools.h3c import H3cProc
from apps.automation.tools.hillstone import HillstoneProc
from apps.automation.tools.huawei import HuaweiProc
from apps.automation.tools.maipu import MaipuProc
from apps.automation.tools.cisco import CiscoProc
from apps.automation.tools.mellanox import MellanoxProc
from apps.automation.tools.ruijie import RuijieProc
from apps.automation.tools.centec import CentecProc
from apps.automation.tools.model_api import get_device_info_v2
from utils.connect_layer.auto_main import HuaweiS, HillstoneFsm
from utils.db.mongo_ops import MongoOps, MongoNetOps, XunMiOps
from driver import discovered_plugins


logger = logging.getLogger('automation')


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        # if isinstance(obj, datetime.datetime):
        #     return int(mktime(obj.timetuple()))
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        else:
            return json.JSONEncoder.default(self, obj)


arp_mongo = MongoOps(db='Automation', coll='ARPTable')
mac_mongo = MongoOps(db='Automation', coll='MACTable')
lagg_mongo = MongoOps(db='Automation', coll='AggreTable')
lldp_mongo = MongoOps(db='Automation', coll='LLDPTable')
cmdb_mongo = MongoOps(db='Automation', coll='networkdevice')
show_ip_mongo = MongoOps(db='Automation', coll='layer3interface')
log_mongo = MongoOps(db='logs', coll='xumi_time_cost')
interface_mongo = MongoOps(db='Automation', coll='layer2interface')


def clear_his_collect_res():
    # 清空定位成功数据
    # 清空testfsm记录
    MongoOps(db='Automation', coll='collect_textfsm_info').delete()
    # 清空netconf失败记录
    MongoOps(db='Automation', coll='netconf_failed').delete()
    netconf_db = MongoOps(db='NETCONF', coll='netconf_interface_ipv4v6')
    netconf_tables = netconf_db.all_table()
    for netconf_table in netconf_tables:
        MongoOps(db='NETCONF', coll=netconf_table).delete()
    return


# 接口格式化类
class InterfaceFormat(object):
    @staticmethod
    def h3c_interface_format(interface):
        if re.search(r'^(GE)', interface):
            return interface.replace('GE', 'GigabitEthernet')

        elif re.search(r'^(BAGG)', interface):
            return interface.replace('BAGG', 'Bridge-Aggregation')

        elif re.search(r'^(RAGG)', interface):
            return interface.replace('RAGG', 'Route-Aggregation')

        elif re.search(r'^(XGE)', interface):
            return interface.replace('XGE', 'Ten-GigabitEthernet')
        elif re.search(r'^(HGE)', interface):
            return interface.replace('XGE', 'HundredGigE')

        elif re.search(r'^(FGE)', interface):
            return interface.replace('FGE', 'FortyGigE')

        elif re.search(r'^(MGE)', interface):
            return interface.replace('MGE', 'M-GigabitEthernet')

        elif re.search(r'^(M-GE)', interface):
            return interface.replace('M-GE', 'M-GigabitEtherne')

        return interface

    @staticmethod
    def huawei_interface_format(interface):
        if re.search(r'^(GE)', interface):
            return interface.replace('GE', 'GigabitEthernet')

        elif re.search(r'^(XGE)', interface):
            return interface.replace('XGE', 'XGigabitEthernet')

        return interface

    @staticmethod
    def maipu_interface_format(interface):
        if re.search(r'^(te)', interface):
            return interface.replace('te', 'tengigabitethernet')

        return interface

    @staticmethod  # 按接口名称速率转换
    def h3c_speed_format(interface):
        if re.search(r'^(GE)', interface) or re.search(
                r'^(GigabitEthernet)', interface):
            return '1G'

        elif re.search(r'^(XGE)', interface) or re.search(r'^(Ten-GigabitEthernet)', interface):
            return '10G'

        elif re.search(r'^(FGE)', interface) or re.search(r'^(FortyGigE)', interface):
            return '40G'

        elif re.search(r'^(Twenty-FiveGigE)', interface):
            return '100G'

        elif re.search(r'^(MGE)', interface) or re.search(r'^(MEth)', interface):
            return '1G'

        elif re.search(r'^(M-GE)', interface):
            return '1G'
        return interface

    @staticmethod  # 按接口名称速率转换
    def ruijie_speed_format(interface):
        if re.search(r'^(GigabitEthernet)', interface):
            return '1G'
        elif re.search(r'^(TenGigabitEthernet)', interface):
            return '10G'
        elif re.search(r'^(TFGigabitEthernet)', interface):
            return '10G'
        elif re.search(r'^(FortyGigabitEthernet)', interface):
            return '40G'
        elif re.search(r'^(HundredGigabitEthernet)', interface):
            return '100G'
        return interface

    @staticmethod
    def mathintspeed(value):
        """接口speed单位换算"""
        k = 1000
        try:
            value = int(value) * 1000000
        except:
            return value
        if value == 0:
            return str(value)
        # value = value * 8
        sizes = ['bytes', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
        c = math.floor(math.log(value) / math.log(k))
        value = (value / math.pow(k, c))
        value = '% 6.0f' % value
        value = str(value) + sizes[c]
        return value.strip()


# 接口利用率计算
@shared_task(base=AxeTask)
def interface_used(device_ip=None):
    connections.close_all()
    """
    接口利用率最新分析表
    :return:
    """
    # 接口利用率落库mongo
    interface_log_mongo = MongoOps(db='logs', coll='interface_used_log')
    interface_log_mongo.delete_many()
    data_time = datetime.now()

    def data_to_table(**data: any) -> None:
        """
        执行落库和写缓存
        :param data:
        :return:
        """
        hostip = data['hostip']
        try:
            if 'chassis' in data.keys():
                dev_obj = NetworkDevice.objects.filter(
                    manage_ip=data['hostip'], chassis=data['chassis'], status=0).values(
                    'id', 'manage_ip', 'name').first()
                data.pop('chassis')
            elif 'slot' in data.keys():
                dev_obj = NetworkDevice.objects.filter(
                    manage_ip=data['hostip'], slot=data['slot'], status=0).values(
                    'id', 'manage_ip', 'name').first()
                data.pop('slot')
            else:
                dev_obj = NetworkDevice.objects.filter(
                    manage_ip=data['hostip'], status=0).values(
                    'id', 'manage_ip', 'name').first()
            if dev_obj:
                post_data = dict()
                post_data['host'] = dev_obj['name']
                post_data['host_ip'] = dev_obj['manage_ip']
                post_data['host_id'] = dev_obj['id']
                if data['int_used'] == 0:
                    post_data['utilization'] = 0
                elif data['int_total'] == 0:
                    post_data['utilization'] = 0
                else:
                    post_data['utilization'] = round(
                        (data['int_used'] / data['int_total']) * 100, 2)
                post_data['log_time'] = data_time
                data.pop('hostip')
                for k in data.keys():
                    post_data[k.lower()] = data[k]
                # 计算设备类型，千兆还是万兆25G 100G 200G
                key_list = []
                speed_map = {
                    'int_used_1g': '1G',
                    'int_unused_1g': '1G',
                    'int_used_10g': '10G',
                    'int_unused_10g': '10G',
                    'int_used_20g': '20G',
                    'int_unused_20g': '20G',
                    'int_used_25g': '25G',
                    'int_unused_25g': '25G',
                    'int_used_40g': '40G',
                    'int_unused_40g': '40G',
                    'int_used_100g': '100G',
                    'int_unused_100g': '100G',
                    'int_used_200g': '200G',
                    'int_unused_200g': '200G',
                    'int_used_400g': '400G',
                    'int_unused_400g': '400G',
                }
                for k, v in data.items():
                    if k.lower() in speed_map.keys():
                        key_list.append(
                            {
                                "type": speed_map[k.lower()],
                                "sum": v
                            }
                        )
                int_1g = sum([x['sum'] for x in key_list if x['type'] == '1G'])
                int_10g = sum([x['sum'] for x in key_list if x['type'] == '10G'])
                int_20g = sum([x['sum'] for x in key_list if x['type'] == '20G'])
                int_25g = sum([x['sum'] for x in key_list if x['type'] == '25G'])
                int_40g = sum([x['sum'] for x in key_list if x['type'] == '40G'])
                int_100g = sum([x['sum'] for x in key_list if x['type'] == '100G'])
                int_200g = sum([x['sum'] for x in key_list if x['type'] == '200G'])
                int_400g = sum([x['sum'] for x in key_list if x['type'] == '400G'])
                new_port_speed = [
                    {
                        'type': '1G',
                        'sum': int_1g,
                    },
                    {
                        'type': '10G',
                        'sum': int_10g,
                    },
                    {
                        'type': '20G',
                        'sum': int_20g,
                    },
                    {
                        'type': '25G',
                        'sum': int_25g,
                    },
                    {
                        'type': '40G',
                        'sum': int_40g,
                    },
                    {
                        'type': '100G',
                        'sum': int_100g,
                    },
                    {
                        'type': '200G',
                        'sum': int_200g,
                    },
                    {
                        'type': '400G',
                        'sum': int_400g,
                    },
                ]
                if key_list:
                    max_port = max([int_1g, int_10g, int_20g, int_25g, int_40g, int_100g, int_200g, int_400g])
                    post_data['host_type'] = ''.join([x['type'] for x in new_port_speed if x['sum'] == max_port])
                logger.info('落库data:{}'.format(post_data))
                try:
                    InterfaceUsed.objects.create(**post_data)
                    cache.set("interface_used_" + str(post_data['host_id']),
                              json.dumps(post_data, cls=JsonEncoder), 3600 * 5)
                except Exception as e:
                    interface_log_mongo.insert(
                        dict(
                            hostip=hostip,
                            msg=str(e),
                            post_data=post_data))
        except Exception as e:
            # print(e)
            # print(traceback.print_exc())
            interface_log_mongo.insert(
                dict(
                    hostip=hostip,
                    msg='get数据错误未得到唯一对象' +
                        str(e)))
        return

    # 单独调试使用
    if device_ip:
        hosts = [device_ip]
    else:
        # 获取设备列表然后去重
        host_list = interface_mongo.find(fileds={'_id': 0, 'hostip': 1})
        # 所有待分析接口利用率的网络设备
        hosts = list(set([x['hostip'] for x in host_list]))
    for host in hosts:
        # 获取接口cmdb信息
        host_cmdb = cmdb_mongo.find(query_dict=dict(manage_ip=host, status=0),
                                    fileds={'_id': 0, 'slot': 1, 'chassis': 1})
        chassis_res = list(set([x['chassis'] for x in host_cmdb]))
        slot_res = list(set([x['slot'] for x in host_cmdb]))
        # 获取接口2层列表
        tmp = interface_mongo.find(
            query_dict=dict(
                hostip=host), fileds={
                '_id': 0})
        # 获取接口speed去重后的指标
        speed_list = list(set([x['speed'] for x in tmp])
                          )  # ['40G', '10G', '1G']
        # 判断堆叠
        mongo_res_slot = []
        for i in tmp:
            if i['interface'].startswith('lo'):
                continue
            elif i['interface'].startswith('mgmt'):
                continue
            elif i['interface'].startswith('AggregatePort'):
                continue
            _tmp_slot = i['interface'].split('/')[0]
            mongo_res_slot.append(int(_tmp_slot[-1]))
        mongo_res_slot = list(set(mongo_res_slot))
        logger.info(mongo_res_slot, slot_res)
        if len(mongo_res_slot) == len(slot_res) and mongo_res_slot == slot_res:
            print('匹配独立设备')
            # 用于存储根据slot作为key ，接口列表作为value的 key-value结构
            _tmp_res = dict()
            for _slot in mongo_res_slot:
                _tmp_res[_slot] = []
                for i in tmp:
                    _int_slot = i['interface'].split('/')[0]
                    if _slot == int(_int_slot[-1]):
                        _tmp_res[_slot].append(i)
            for k_slot, v in _tmp_res.items():
                host_final_res = dict()
                host_final_res['int_total'] = 0
                host_final_res['int_used'] = 0
                host_final_res['int_unused'] = 0
                for key in speed_list:
                    if not key:
                        continue
                    if key == '1000m' or key == '1000M':
                        key = '1G'
                    elif key == '10000m' or key == '10000M':
                        key = '10G'
                    host_final_res['int_used_' + key] = 0
                    host_final_res['int_unused_' + key] = 0
                    for i in v:
                        if i['status'] == 'up' or i['status'] == 'UP':
                            if i['speed'] == key:
                                host_final_res['int_total'] += 1  # 接口总数
                                host_final_res['int_used_' + key] += 1  # 速率使用
                                host_final_res['int_used'] += 1  # 总使用
                        elif i['status'] == 'down' or i['status'] == 'DOWN':
                            if i['speed'] == key:
                                host_final_res['int_total'] += 1
                                host_final_res['int_unused_' + key] += 1
                                host_final_res['int_unused'] += 1
                print(k_slot, host_final_res)
                host_final_res['hostip'] = host
                host_final_res['slot'] = k_slot
                data_to_table(**host_final_res)
                # interface_res_mongo.insert(host_final_res)
        elif len(mongo_res_slot) == len(chassis_res) and mongo_res_slot == chassis_res:
            print('匹配框式')
            # 用于存储根据slot作为key ，接口列表作为value的 key-value结构
            _tmp_res = dict()
            for _slot in mongo_res_slot:
                _tmp_res[_slot] = []
                for i in tmp:
                    _int_slot = i['interface'].split('/')[0]
                    if _slot == int(_int_slot[-1]):
                        _tmp_res[_slot].append(i)
            for k_slot, v in _tmp_res.items():
                host_final_res = dict()
                host_final_res['int_total'] = 0
                host_final_res['int_used'] = 0
                host_final_res['int_unused'] = 0
                for key in speed_list:
                    if not key:
                        continue
                    if key == '1000m' or key == '1000M':
                        key = '1G'
                    elif key == '10000m' or key == '10000M':
                        key = '10G'
                    host_final_res['int_used_' + key] = 0
                    host_final_res['int_unused_' + key] = 0
                    for i in v:
                        if i['status'] == 'up' or i['status'] == 'UP':
                            if i['speed'] == key:
                                host_final_res['int_total'] += 1  # 接口总数
                                host_final_res['int_used_' + key] += 1  # 速率使用
                                host_final_res['int_used'] += 1  # 总使用
                        elif i['status'] == 'down' or i['status'] == 'DOWN':
                            if i['speed'] == key:
                                host_final_res['int_total'] += 1
                                host_final_res['int_unused_' + key] += 1
                                host_final_res['int_unused'] += 1
                print(k_slot, host_final_res)
                host_final_res['hostip'] = host
                host_final_res['chassis'] = k_slot
                data_to_table(**host_final_res)
                # interface_res_mongo.insert(host_final_res)
        else:
            print('slot不匹配')
            host_final_res = dict()
            host_final_res['hostip'] = host
            host_final_res['int_total'] = 0
            host_final_res['int_used'] = 0
            host_final_res['int_unused'] = 0
            for key in speed_list:
                if not key:
                    continue
                if key == '1000m' or key == '1000M':
                    key = '1G'
                elif key == '10000m' or key == '10000M':
                    key = '10G'
                host_final_res['int_used_' + key] = 0
                host_final_res['int_unused_' + key] = 0
                for i in tmp:
                    if i['status'] == 'up' or i['status'] == 'UP':
                        if i['speed'] == key:
                            host_final_res['int_total'] += 1  # 接口总数
                            host_final_res['int_used_' + key] += 1  # 速率使用
                            host_final_res['int_used'] += 1  # 总使用
                    elif i['status'] == 'down' or i['status'] == 'DOWN' or i['status'] == 'Administratively DOWN':
                        if i['speed'] == key:
                            host_final_res['int_total'] += 1
                            host_final_res['int_unused_' + key] += 1
                            host_final_res['int_unused'] += 1
            data_to_table(**host_final_res)
            # print(host_final_res)

    # #send_msg_netops"完成{}个IP地址对应网络设备的接口利用率更新".format(str(len(hosts))))
    return


def standard_analysis_main():
    start_time = time.time()
    # mac地址合法性检查，正则匹配
    mac_kwargs = {'macaddress': re.compile('(\\w+-\\w+-\\w+)')}
    total_arp_tmp = arp_mongo.find_re(
        mac_kwargs,
        fileds={
            '_id': 0,
            'ipaddress': 1})
    total_arp_res = [x['ipaddress'] for x in total_arp_tmp]
    total_layer3ip_tmp = show_ip_mongo.find(fileds={'_id': 0, 'ipaddress': 1})
    total_layer3ip_res = [x['ipaddress'] for x in total_layer3ip_tmp]
    public_scan_tmp = MongoOps(
        db='logs',
        coll='scan_port_res').find_re(
        mac_kwargs,
        fileds={
            '_id': 0,
            'global_ip': 1})
    public_scan_res = [x['global_ip'] for x in public_scan_tmp]
    total_ip_tmp = list(set(total_arp_res)) + list(set(total_layer3ip_res)) + list(set(public_scan_res))
    # total_ip_tmp = MongoOps(db='Automation', coll='ARPTable').find(fileds={'_id': 0, 'ipaddress': 1})
    # total_ip_res = list(set([x['ipaddress'] for x in total_ip_tmp]))
    # result = OrderedDict()
    # # 多字典合并去重
    # for item in total_ip_tmp:
    #     result.setdefault(item, {**item})
    # xunmi_res = list(result.values())
    xunmi_res = [dict(ipaddress=x) for x in total_ip_tmp]
    # 所有IP明细存入mongo, 作为后面地址定位源数据
    total_ip_mongo = MongoOps(db='Automation', coll='Total_ip_list')
    total_ip_mongo.delete()
    total_ip_mongo.insert_many(xunmi_res)
    # ip地址统计信息存入monggo，首页显示
    ip_state_mongo = MongoOps(db='BasePlatform', coll='server_ip_statistics')
    ip_state_mongo.insert(dict(
        total=len(xunmi_res), log_time=datetime.today().strftime("%Y-%m-%d")
    ))
    total_time = (time.time() - start_time) / 60
    return


def datas_to_cache():
    # 获取ARP表的所有数据 tables 用来汇总查询条件
    tables = {
        'ARPTable': {'_id': 0, 'ipaddress': 1, 'idc_name': 1, 'hostip': 1, 'macaddress': 1, 'interface': 1},
        'MACTable': {'_id': 0, 'idc_name': 1, 'interface': 1, 'hostip': 1, 'macaddress': 1},
        'AggreTable': {'_id': 0, 'memberports': 1, 'hostip': 1, 'aggregroup': 1},
        'LLDPTable': {'_id': 0, 'neighborsysname': 1, 'hostip': 1, 'local_interface': 1, 'neighbor_ip': 1},
        'layer3interface': {'_id': 0, 'ipaddress': 1, 'hostip': 1},
    }
    init_time = time.time()
    start_time = time.time()

    # cmdb 以 name 作为key
    def cmdb_to_cache():
        cmdb_res = cmdb_mongo.find(query_dict={'status': 0}, fileds={'_id': 0, 'manage_ip': 1, 'name': 1})
        cmdb_result = dict()
        cmdb_ip_result = dict()
        for _asset in cmdb_res:
            if _asset['name'] is not None:
                if _asset['name'] in cmdb_result.keys():
                    cmdb_result[_asset['name']].append(_asset)
                else:
                    cmdb_result[_asset['name']] = [_asset]
            if _asset['manage_ip'] != '0.0.0.0':
                if _asset['manage_ip'] in cmdb_ip_result.keys():
                    cmdb_ip_result[_asset['manage_ip']].append(_asset)
                else:
                    cmdb_ip_result[_asset['manage_ip']] = [_asset]
        for _asset in cmdb_result.keys():
            cache.set(
                "cmdb_" + _asset,
                json.dumps(
                    cmdb_result[_asset]),
                3600 * 12)
        for _asset in cmdb_ip_result.keys():
            cache.set(
                "cmdb_" + _asset,
                json.dumps(
                    cmdb_result[_asset]),
                3600 * 12)

    # arp 以 arp_ + ip 作为key
    def arp_to_cache():
        # arp_mongo = MongoOps(db='Automation', coll='ARPTable')
        arp_res = arp_mongo.find(fileds={'_id': 0, 'log_time': 0})
        arp_result = dict()
        for _arp in arp_res:
            if _arp['ipaddress'] in arp_result.keys():
                arp_result[_arp['ipaddress']].append(_arp)
            else:
                arp_result[_arp['ipaddress']] = [_arp]
        for _arp in arp_result.keys():
            cache.set("arp_" + _arp, json.dumps(arp_result[_arp]), 3600 * 12)

    # mac地址 以 idc + mac 地址作为key
    def mac_to_cache():
        # mac_mongo = MongoOps(db='Automation', coll='MACTable')
        mac_res = mac_mongo.find(
            fileds={
                '_id': 0,
                'idc_name': 1,
                'interface': 1,
                'hostip': 1,
                'macaddress': 1})
        mac_result = dict()
        for _mac in mac_res:
            if _mac['idc_name'] + '_' + \
                    _mac['macaddress'] in mac_result.keys():
                mac_result[_mac['idc_name'] + '_' +
                           _mac['macaddress']].append(_mac)
            else:
                mac_result[_mac['idc_name'] + '_' +
                           _mac['macaddress']] = [_mac]
        for _mac in mac_result.keys():
            cache.set(
                "macaddress_" + _mac,
                json.dumps(
                    mac_result[_mac]),
                3600 * 12)

    # lagg 以 hostip aggregroup 作为key
    def lagg_to_cache():
        # lagg_mongo = MongoOps(db='Automation', coll='AggreTable')
        lagg_res = lagg_mongo.find(fileds=tables['AggreTable'])
        lagg_result = dict()
        for _lagg in lagg_res:
            if _lagg['hostip'] + '_' + \
                    _lagg['aggregroup'] in lagg_result.keys():
                lagg_result[_lagg['hostip'] + '_' +
                            _lagg['aggregroup']].append(_lagg)
            else:
                lagg_result[_lagg['hostip'] + '_' +
                            _lagg['aggregroup']] = [_lagg]
        for _lagg in lagg_result.keys():
            cache.set(
                "lagg_" + _lagg,
                json.dumps(
                    lagg_result[_lagg]),
                3600 * 12)

    # lldp 以 hostip local_interface 作为key
    def lldp_to_cache():
        # lldp_mongo = MongoOps(db='Automation', coll='LLDPTable')
        lldp_res = lldp_mongo.find(fileds=tables['LLDPTable'])
        lldp_result = dict()
        for _lldp in lldp_res:
            if _lldp['hostip'] + '_' + \
                    _lldp['local_interface'] in lldp_result.keys():
                lldp_result[_lldp['hostip'] + '_' +
                            _lldp['local_interface']].append(_lldp)
            else:
                lldp_result[_lldp['hostip'] + '_' +
                            _lldp['local_interface']] = [_lldp]
        for _lldp in lldp_result.keys():
            cache.set(
                "lldp_" + _lldp,
                json.dumps(
                    lldp_result[_lldp]),
                3600 * 12)

    # layer3interface以 hostip ipaddress 作为key
    def layer3interface_to_cache():
        # show_ip_mongo = MongoOps(db='Automation', coll='layer3interface')
        show_ip_res = show_ip_mongo.find(fileds=tables['layer3interface'])
        show_ip_result = dict()
        for _show_ip in show_ip_res:
            if _show_ip['hostip'] + '_' + \
                    _show_ip['ipaddress'] in show_ip_result.keys():
                show_ip_result[_show_ip['hostip'] + '_' +
                               _show_ip['ipaddress']].append(_show_ip)
            else:
                show_ip_result[_show_ip['hostip'] + '_' +
                               _show_ip['ipaddress']] = [_show_ip]
        for _show_ip in show_ip_result.keys():
            cache.set(
                "layer3interface_" + _show_ip,
                json.dumps(
                    show_ip_result[_show_ip]),
                3600 * 12)

    cmdb_to_cache()
    content = ''
    content += "{}缓存耗时{}秒\n".format('CMDB', int(time.time() - start_time))
    start_time = time.time()
    arp_to_cache()
    # print("{}缓存耗时{}秒\n".format('ARP地址库', int(time.time() - start_time)))
    content += "{}缓存耗时{}秒\n".format('ARP地址库', int(time.time() - start_time))
    start_time = time.time()
    mac_to_cache()
    # print("{}缓存耗时{}秒\n".format('mac地址库', int(time.time() - start_time)))
    content += "{}缓存耗时{}秒\n".format('MAC地址库', int(time.time() - start_time))
    start_time = time.time()
    lagg_to_cache()
    # print("{}缓存耗时{}秒\n".format('聚合端口库', int(time.time() - start_time)))
    content += "{}缓存耗时{}秒\n".format('聚合端口库', int(time.time() - start_time))
    start_time = time.time()
    lldp_to_cache()
    # print("{}缓存耗时{}秒\n".format('LLDP库', int(time.time() - start_time)))
    content += "{}缓存耗时{}秒\n".format('LLDP库', int(time.time() - start_time))
    start_time = time.time()
    layer3interface_to_cache()
    # print("{}缓存耗时{}秒\n".format('三层接口地址库', int(time.time() - start_time)))
    content += "{}缓存耗时{}秒\n".format('三层接口地址库', int(time.time() - start_time))
    content += "{}缓存耗时{}秒\n".format('总写入', int(time.time() - init_time))
    logger.debug(content)
    return


class MainIn:
    # CMDB 网络设备信息，并写Mongodb
    @staticmethod
    def cmdb_to_mongo():
        # 获取所有设备信息
        all_devs = NetworkDevice.objects.select_related('idc_model',
                                                        'model',
                                                        'role',
                                                        'attribute',
                                                        'category',
                                                        'vendor',
                                                        'idc',
                                                        'framework',
                                                        'zone',
                                                        'rack').prefetch_related('bind_ip', 'account').filter(
            status=0).values(
            'name', 'idc__name', 'serial_num', 'manage_ip', 'status', 'chassis', 'slot', 'idc_model__name',
            'u_location_start', 'u_location_end','rack__name')
        MongoNetOps.post_cmdb(all_devs)
        return

    # 定位结果业务化落库
    @staticmethod
    async def tracking_format(ip_address, hostip,
                              log_time, memberport, macaddress) -> None:
        hostinfo = cmdb_mongo.find(query_dict=dict(manage_ip=hostip, status=0),
                                   fileds={'_id': 0, 'idc__name': 1, 'name': 1, 'serial_num': 1, 'idc_model__name': 1,
                                           'rack__name': 1, 'u_location_start': 1, 'u_location_end': 1})
        node_location = ','.join([str(
            x.get('idc_model__name')) +
                                  '_' +
                                  str(x.get('rack__name')) +
                                  '_' +
                                  str(x.get('u_location_start')) +
                                  '-' + str(x.get('u_location_end')) for x in hostinfo])
        if log_time:
            log_time = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S")
        if hostinfo:
            if hostinfo[0]['name'] is None:
                hostname = ''
            else:
                hostname = hostinfo[0]['name']
            memberport_list = memberport.split(',') if memberport.find(',') != -1 else [memberport]
            mongo_data = {
                'log_time': log_time,
                'node_hostname': hostname if len(hostinfo) > 0 else '',
                'node_ip': hostip,
                'node_location': node_location,
                'idc_name': hostinfo[0]['idc__name'],
                'serial_num': hostinfo[0]['serial_num'],
                'node_interface': memberport,
                'memberport': memberport_list,
                'server_ip_address': ip_address,
                'server_mac_address': macaddress,
            }
            plugin = discovered_plugins.get('plugins.extensibles.xunmi')
            if plugin is not None:
                methods = sorted([x for x in plugin.__all__])
                start_time = time.time()
                for method in methods:
                    if callable(eval("discovered_plugins.get('plugins.extensibles.xunmi').{}".format(method))):
                        try:
                            flag, res = await eval(
                                "discovered_plugins.get('plugins.extensibles.xunmi').{}".format(method))(
                                **dict(ip_address=ip_address, hostip=hostip))
                            if flag:
                                mongo_data.update(res)
                                # break
                        except Exception as e:
                            logger.info(f"{ip_address}定位使用插件异常")
                            logger.exception(e)
                end_time = time.time() - start_time
                logger.info("插件执行耗时：{}".format(str(end_time)))
            XunMiOps.xunmi_ops(**mongo_data)
        return

    @staticmethod
    async def xunmi_sub(**kwargs):
        """
        用来承接上层xunmi_check方法中的根据接口查询LLDP往下的逻辑
        接收参数  ip_address  mac  arp
        :param kwargs:
        :return:
        """
        tmp_result = []
        ip_address = kwargs['ip_address']
        mac = kwargs['mac']
        arp = kwargs['arp']
        lldp_res = cache.get('lldp_{}_{}'.format(mac['hostip'], mac['interface']))
        if not lldp_res:
            lldp_res = cache.get('lldp_reverse_{}_{}'.format(mac['hostip'], mac['interface']))
        if lldp_res:
            lldp_res = json.loads(lldp_res)
            neighbor_ip = lldp_res[0]['neighbor_ip']
            if neighbor_ip:
                _ip_res = cache.get('layer3interface_{}_{}'.format(neighbor_ip, ip_address))
                if _ip_res:
                    _ip_res = json.loads(_ip_res)
                    tmp_result.append(dict(host=mac['hostip'],
                                           interface=mac['interface'],
                                           macaddress=arp['macaddress'],
                                           memberport=mac['interface']))
                    return tmp_result, True

        tmp_result.append(dict(host=mac['hostip'],
                               interface=mac['interface'],
                               macaddress=arp['macaddress'],
                               memberport=mac['interface']))
        return tmp_result, False


@shared_task(base=AxeTask, once={'graceful': True})
def collect_device(**kwargs):
    connections.close_all()
    hostip = kwargs['manage_ip']  # 设备管理IP地址
    if hostip == '0.0.0.0':
        return {}
    plan = kwargs.get('plan_id', '')
    # todo 后期移动到上层调用的时候过滤掉
    if not plan:
        # #send_msg_netops"设备:{}\n未关联数据采集方案".format(hostip))
        return {}
    if not kwargs['auto_enable']:
        # #send_msg_netops"设备:{}\n未启用自动化纳管功能".format(hostip))
        return {}
    vendor_alias = kwargs['vendor__alias']  # 设备厂商名称（英文  别名）
    CLASS_MAP = {
        'H3C': H3cProc,
        'Huawei': HuaweiProc,
        'Hillstone': HillstoneProc,
        'Mellanox': MellanoxProc,
        'centec': CentecProc,
        'Ruijie': RuijieProc,
        'Maipu': MaipuProc,
        'Cisco': CiscoProc,
    }
    if vendor_alias in CLASS_MAP.keys():
        class_instance = CLASS_MAP[vendor_alias](**kwargs)
        class_instance.collection_run()
    return


# 通用信息采集主调度任务
@shared_task(base=AxeTask, once={'graceful': True})
def collect_device_main(**kwargs):
    logger.info('开始执行信息采集主调度任务')
    try:
        MainIn.cmdb_to_mongo()
    except Exception as e:
        pass
    if kwargs:
        hosts = get_device_info_v2(**kwargs)
    else:
        hosts = get_device_info_v2()
    logger.info('获取所有设备信息结束')
    # 参数初始化
    net_tower_tasks = []  # 寻觅任务id集合
    ping_result = []  # ping不通设备存储
    # 清空所有采集数据
    try:
        clear_his_collect_res()
    except Exception as e:
        pass
    start_time = time.time()
    # 批量下发任务
    for host in hosts:
        net_tower_tasks.append(
            collect_device.apply_async(
                kwargs=host,
                queue='config',
                retry=True))

    logger.info('批量下发任务结束')

    # 去除结果中的<EagerResult: None>
    for task in net_tower_tasks:
        if 'EagerResult' in str(type(task)):
            logger.info("存在无效task")
            net_tower_tasks.remove(task)

    # 获取tasks任务数量
    net_tower_tasks_counters = len(net_tower_tasks)
    net_tower_tasks_bak = net_tower_tasks.copy()

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
    logger.info('子任务全部执行结束')

    # 获取子任务执行结果，处理后发送
    FAILURE_TASK = []  # 失败任务
    for task_id in net_tower_tasks_bak:
        try:
            task_result = TaskResult.objects.filter(task_id=task_id).values('task_args', 'task_kwargs', 'status',
                                                                            'result')
            task_status = list(task_result)[0]['status']  # str
            if task_status == 'FAILURE':  # celery执行失败
                FAILURE_TASK.append((task_id, task_status))
                logger.error(
                    'celery执行失败,\ntask_id:{},\ntask_status{}\n'.format(
                        task_id, task_status))
        except Exception as e:  # 查询task_results失败
            FAILURE_TASK.append((task_id, e))
            logger.error(
                '查询task_results失败,\nTask_id:{},\nERROR:{}\n'.format(
                    task_id, e))
    logger.info('子任务执行结果查询结束')
    # 采集失败任务数量
    failed_logs_mongo = MongoOps(db='Automation', coll='collect_failed_logs')
    failed_res = failed_logs_mongo.find(fileds={'_id': 0})  # type int
    failed_res_list = [x['ip'] for x in failed_res]
    # netconf 失败数
    failed_netconf_mongo = MongoOps(db='Automation', coll='netconf_failed')
    failed_netconf_res = failed_netconf_mongo.find(
        fileds={'_id': 0})  # type int
    failed_netconf_list = [x['ip'] for x in failed_netconf_res]
    # 结果发送微信、邮箱
    total_time = (time.time() - start_time) / 60
    send_message = '设备数据采集分析结束:\n任务总数: {}\ncelery任务失败数：{}\n采集失败数：{} 详见mongo collect_failed_logs\n' \
                   'netconf 失败设备:{}\nPing不通设备：{}\n总耗时：{}分钟\n' \
        .format(net_tower_tasks_counters, len(FAILURE_TASK), '\n'.join(failed_res_list), '\n'.join(failed_netconf_list),
                '\n'.join(ping_result), int(total_time))
    logger.info(send_message)
    datas_to_cache()
    try:
        standard_analysis_main()
        interface_used.apply_async()
        tracking_main.apply_async()
    except Exception as e:
        pass
    return


# 采集规则子任务
@shared_task(base=AxeTask, once={'graceful': True})
def collect_info_sub(**kwargs):
    host = kwargs['host']
    rule = kwargs['rule']
    CLASS_MAP = {
        'H3C': H3cProc,
        'Huawei': HuaweiProc,
        'Hillstone': HillstoneProc,
        'Mellanox': MellanoxProc,
        'centec': CentecProc,
        'Ruijie': RuijieProc,
        'Maipu': MaipuProc,
        'Cisco': CiscoProc,
    }
    if kwargs['vendor_alias'] in CLASS_MAP.keys():
        class_instance = CLASS_MAP[kwargs['vendor_alias']](**host)
        class_instance.collection_rule(**rule)
    return


# 采集规则主任务
@shared_task(base=AxeTask, once={'graceful': True})
def collcet_device_by_rule():
    """采集规则主任务"""
    rule_query = CollectionRule.objects.prefetch_related(
        'match_rule').values('id', 'operation', 'module', 'method', 'execute', 'plugin')
    all_task = []

    # 循环每一条采集规则
    for sub_rule in rule_query:
        match_rule = CollectionMatchRule.objects.filter(rule__id=sub_rule['id']).values()
        query_params = {}
        for sub_match_rule in match_rule:
            query_params["{}{}".format(sub_match_rule['fields'], sub_match_rule['operator'])] = sub_match_rule[
                'value']
        hosts = get_device_info_v2(**query_params)
        # 批量下发任务
        for host in hosts:
            params = {
                'host': host,
                'rule': sub_rule
            }
            all_task.append(
                collect_info_sub.apply_async(
                    kwargs=params,
                    queue='config',
                    retry=True))
    # 获取tasks任务数量
    all_tasks_counters = len(all_task)


async def xunmi_operation(**kwargs):

    start_time = time.time()
    ip_address = kwargs['ipaddress']
    log_time = kwargs.get('log_time')
    arp_res = cache.get('arp_' + ip_address)
    if arp_res:
        arp_res = json.loads(arp_res)
    else:
        logger.info("{}没有ARP表项，直接退出".format(ip_address))
        # 没有ARP， 直接退出，防止频繁查询mongo
        return
    arp_result = OrderedDict()
    # 多字典合并去重
    for item in arp_res:
        arp_result.setdefault(item['macaddress'], {**item})
    final_arp_res = list(arp_result.values())
    tmp_result = []
    for arp in final_arp_res:
        if arp['macaddress'] is None:
            continue
        if arp['interface'] is None:
            continue
        logger.debug('ip{}:macaddress_{}_{}'.format(ip_address, arp['idc_name'], arp['macaddress']))
        mac_res = cache.get('macaddress_{}_{}'.format(arp['idc_name'], arp['macaddress']))
        if mac_res:
            mac_res = json.loads(mac_res)
            for mac in mac_res:
                mac_interface = mac['interface']
                try:
                    if mac_interface.find('.') != -1:
                        mac_interface = mac_interface.split('.')[0]
                except Exception as e:
                    logger.error("ip{}:{}".format(ip_address, str(e)))
                lagg_res = cache.get('lagg_{}_{}'.format(mac['hostip'], mac_interface))
                # 是聚合口
                if lagg_res:
                    lagg_res = json.loads(lagg_res)
                    lagg_res = lagg_res[0]
                    if len(lagg_res['memberports']) >= 1:
                        lldp_num = 0
                        for port in lagg_res['memberports']:
                            lldp_res = cache.get(
                                'lldp_{}_{}'.format(lagg_res['hostip'], port))
                            if not lldp_res:
                                lldp_res = cache.get('lldp_reverse_{}_{}'.format(lagg_res['hostip'], port))
                            if lldp_res:
                                lldp_res = json.loads(lldp_res)
                                # print("====>是聚合口，有LLDP信息", lldp_res)
                                if not lldp_res[0]['neighborsysname']:
                                    # print('有聚合组且LLDP邻居系统名为空', mac['hostip'], mac['interface'])
                                    tmp_result.append(dict(host=mac['hostip'],
                                                           interface=mac['interface'],
                                                           macaddress=arp['macaddress'],
                                                           memberport=','.join(lagg_res['memberports'])))
                                    continue
                                if lldp_res[0]['neighbor_ip']:
                                    lldp_num += 1
                                    # print('聚合组=>LLDP邻居系统名不为空')
                                    neighbor_hostip = lldp_res[0]['neighbor_ip']
                                    _ip_res = cache.get('layer3interface_{}_{}'.format(neighbor_hostip, ip_address))
                                    if _ip_res:
                                        tmp_result.append(dict(host=mac['hostip'],
                                                               interface=mac['interface'],
                                                               macaddress=arp['macaddress'],
                                                               memberport=','.join(lagg_res['memberports'])))
                                        break

                        if lldp_num == 0:
                            tmp_result.append(dict(host=mac['hostip'],
                                                   interface=mac['interface'],
                                                   macaddress=arp['macaddress'],
                                                   memberport=','.join(lagg_res['memberports'])))
                else:
                    # logger.info('ip {}:======>不是聚合口:'.format(ip_address))
                    res, break_falg = await MainIn.xunmi_sub(**dict(mac=mac, arp=arp, ip_address=ip_address))
                    tmp_result += res
                    if break_falg:
                        break
    # 如果没有查询结果，则以ARP信息为最终结果
    if not tmp_result:
        logger.info("ip {}没有MAC查询结果，则以ARP信息为最终结果".format(ip_address))
        arp_res = cache.get('arp_{}'.format(ip_address))
        if arp_res:
            arp_res = json.loads(arp_res)
            for arp in arp_res:
                if arp['interface'] is None:
                    continue
                lagg_res = cache.get('lagg_{}_{}'.format(arp['hostip'], arp['interface']))
                # 是聚合口
                if lagg_res:
                    lagg_res = json.loads(lagg_res)
                    lagg_res = lagg_res[0]
                    if len(lagg_res['memberports']) >= 1:
                        # logger.debug("没有查询结果，则以ARP信息为最终结果 且是聚合口")
                        for port in lagg_res['memberports']:
                            lldp_res = cache.get(
                                'lldp_' + lagg_res['hostip'] + '_' + port)
                            if not lldp_res:
                                lldp_res = cache.get('lldp_reverse_' + lagg_res['hostip'] + '_' + port)
                            if lldp_res:
                                lldp_res = json.loads(lldp_res)
                            else:
                                lldp_res = lldp_mongo.find(
                                    query_dict=dict(hostip=lagg_res['hostip'], local_interface=port),
                                    fileds={'_id': 0, 'neighborsysname': 1})
                            if lldp_res:
                                if lldp_res[0]['neighborsysname']:
                                    tmp_neighbor_ip = cache.get('cmdb_{}'.format(lldp_res[0]['neighborsysname']))
                                    if tmp_neighbor_ip:
                                        tmp_neighbor_ip = json.loads(
                                            tmp_neighbor_ip)
                                    else:
                                        tmp_neighbor_ip = cmdb_mongo.find(
                                            query_dict=dict(
                                                name=lldp_res[0]['neighborsysname'], status=0),
                                            fileds={'_id': 0, 'manage_ip': 1})
                                    if tmp_neighbor_ip:
                                        neighbor_hostip = tmp_neighbor_ip[0]['manage_ip']
                                        _ip_res = cache.get(
                                            'layer3interface_{}_{}'.format(neighbor_hostip, ip_address))
                                        if _ip_res:
                                            _ip_res = json.loads(_ip_res)
                                        else:
                                            _ip_res = show_ip_mongo.find(
                                                query_dict=dict(ipaddress=ip_address, hostip=neighbor_hostip))
                                        if _ip_res:
                                            logger.debug('有聚合组且有直连LLDP邻居')
                                            tmp_result.append(dict(host=arp['hostip'],
                                                                   interface=port,
                                                                   macaddress=arp['macaddress'],
                                                                   memberport=','.join(lagg_res['memberports'])))
                                            break
                                if not lldp_res[0]['neighborsysname']:
                                    logger.debug('有聚合组且LLDP邻居系统名为空')
                                    tmp_result.append(dict(host=arp['hostip'],
                                                           interface=port,
                                                           macaddress=arp['macaddress'],
                                                           memberport=','.join(lagg_res['memberports'])))
                                    continue
                            else:
                                logger.debug('有聚合组且没有LLDP邻居')
                                tmp_result.append(dict(host=arp['hostip'],
                                                       interface=arp['interface'],
                                                       macaddress=arp['macaddress'],
                                                       memberport=','.join(lagg_res['memberports'])))
                        tmp_result.append(dict(host=arp['hostip'],
                                               interface=arp['interface'],
                                               macaddress=arp['macaddress'],
                                               memberport=','.join(lagg_res['memberports'])))
                else:
                    # logger.debug("没有查询结果，则以ARP信息为最终结果 非聚合口")
                    lldp_res = cache.get('lldp_{}_{}'.format(arp['hostip'], arp['interface']))
                    if not lldp_res:
                        lldp_res = cache.get('lldp_reverse_{}_{}'.format(arp['hostip'], arp['interface']))
                    if lldp_res:
                        lldp_res = json.loads(lldp_res)
                        if lldp_res[0]['neighborsysname']:
                            tmp_neighbor_ip = cmdb_mongo.find(query_dict=dict(
                                name=lldp_res[0]['neighborsysname'], status=0), fileds={'_id': 0, 'manage_ip': 1})
                            if tmp_neighbor_ip:
                                # 需要把需要定位的IP和设备管理IP作为参数查询layer3interface，目的是校验
                                neighbor_hostip = tmp_neighbor_ip[0]['manage_ip']
                                _ip_res = show_ip_mongo.find(
                                    query_dict=dict(ipaddress=ip_address, hostip=neighbor_hostip),
                                    fileds={'_id': 0})
                                if _ip_res:
                                    tmp_result.append(dict(host=arp['hostip'],
                                                           interface=arp['interface'],
                                                           macaddress=arp['macaddress'],
                                                           memberport=arp['interface']))
                                else:
                                    tmp_result.append(dict(host=arp['hostip'],
                                                           interface=arp['interface'],
                                                           macaddress=arp['macaddress'],
                                                           memberport=arp['interface']))

                        if not lldp_res[0]['neighborsysname']:
                            tmp_result.append(dict(host=arp['hostip'],
                                                   interface=arp['interface'],
                                                   macaddress=arp['macaddress'],
                                                   memberport=arp['interface']))

                    else:
                        tmp_result.append(dict(host=arp['hostip'],
                                               interface=arp['interface'],
                                               macaddress=arp['macaddress'],
                                               memberport=arp['interface']))
    final_res = OrderedDict()
    # 多字典合并去重
    for item in tmp_result:
        final_res.setdefault(item['host'], {**item})
    main_in_result = list(final_res.values())
    for i in main_in_result:
        logger.info("ip {}:===最终结果===》".format(ip_address))
        if i['macaddress']:
            # 判断MAC地址合法性  (\w+-\w+-\w+)
            if re.search(r'^(\w+-\w+-\w+)', i['macaddress']):
                await MainIn.tracking_format(ip_address, i['host'], log_time, i['memberport'], i['macaddress'])
    total_time = int((time.time() - start_time))
    logger.info("{}地址查询耗时{}秒".format(ip_address, total_time))
    return


@shared_task(base=AxeTask, once={'graceful': True})
def tracking_sub(*args):
    b = time.time()
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _ip in args:
        params = dict(ipaddress=_ip['ipaddress'], log_time=log_time)
        # await xunmi_operation(**params)
        asyncio.run(xunmi_operation(**params))
    e = time.time()
    logger.info('async cost time: %s' % (e - b))
    # asyncio.run(async_operation())
    return {'cost': int(e - b)}


@shared_task(base=AxeTask, once={'graceful': True})
def tracking_main():
    connections.close_all()
    start_time = time.time()
    # 重建寻觅表索引
    try:
        XunMiOps.xunmi_reindex()
    except Exception as e:
        logger.error("重建寻觅表索引失败:{}".format(str(e)))
    total_ip_mongo = MongoOps(db='Automation', coll='Total_ip_list')
    total_ip_res = total_ip_mongo.find(fileds={'_id': 0})
    for ip_address in range(0, len(total_ip_res), 20):
        # asyncio.run(tracking_sub(*total_ip_res[ip_address:ip_address + 20]))
        tracking_sub.apply_async(args=total_ip_res[ip_address:ip_address + 20], queue='xunmi', retry=True)
    send_message = "【自动化】地址定位任务下发完成：\n总数量：{}个" \
        .format(len(total_ip_res))
    logger.info(send_message)
    end_time = time.time()
    print("time :", int(end_time - start_time))
    # #send_msg_netops'step3:' + send_message)


# 自动化通用mongo接口
class AutomationMongo(object):

    @staticmethod
    def insert_path(hostip, fsm_flag, paths, version, hostname):
        my_mongo = MongoOps(db='Automation', coll='collect_textfsm_info')
        tmp = my_mongo.find(query_dict=dict(ip=hostip), fileds={'_id': 0})
        if tmp:
            my_mongo.update(filter=dict(ip=hostip), update={"$set": {'fsm_flag': fsm_flag, 'hostname': hostname,
                                                                     'paths': paths, 'version': version}})
        else:
            my_mongo.insert(
                dict(
                    ip=hostip,
                    fsm_flag=fsm_flag,
                    paths=paths,
                    version=version,
                    hostname=hostname))
        return

    @staticmethod
    def failed_log(ip, fsm_flag, cmd, version):
        failed_mongo = MongoOps(db='Automation', coll='fsm_failed_logs')
        failed_mongo.insert(
            dict(
                ip=ip,
                fsm_flag=fsm_flag,
                cmd=cmd,
                version=version))

    # 新增支持netconf功能设备
    @staticmethod
    def insert_support_netconf(hostip, vendor):
        netconf_mongo = MongoOps(db='Automation', coll='support_netconf')
        tmp = netconf_mongo.find(query_dict=dict(ip=hostip), fileds={'_id': 0})
        if tmp:
            netconf_mongo.update(
                filter=dict(
                    ip=hostip), update={
                    "$set": {
                        'vendor': vendor}})
        else:
            netconf_mongo.insert(dict(ip=hostip, vendor=vendor))
        return

    # 新增netconf失败记录
    @staticmethod
    def insert_netconf_failed_logs(hostip, vendor, msg, exce=None):
        netconf_mongo = MongoOps(db='Automation', coll='netconf_failed')
        tmp = netconf_mongo.find(
            query_dict=dict(
                ip=hostip,
                vendor=vendor,
                msg=msg, exce=exce),
            fileds={
                '_id': 0})
        if tmp:
            netconf_mongo.delete_many(
                query=dict(
                    ip=hostip,
                    vendor=vendor,
                    msg=msg, exce=exce))
        else:
            netconf_mongo.insert(dict(ip=hostip, vendor=vendor, msg=msg, exce=exce))
        return

    @staticmethod
    def get_support_netconf(hostip):
        netconf_mongo = MongoOps(db='Automation', coll='support_netconf')
        tmp = netconf_mongo.find(query_dict=dict(ip=hostip), fileds={'_id': 0})
        if tmp:
            return True
        else:
            return False

    # 插入总表项集合
    @staticmethod
    def insert_table(db, hostip, datas, tablename, delete=True):
        # db='Automation',
        my_mongo = MongoOps(db=db, coll=tablename)
        if delete:
            my_mongo.delete_many(query=dict(hostip=hostip))
        my_mongo.insert_many(datas)
        # netconf_mongo.insert_many(datas)
        return

    @staticmethod
    def dnat_ops(hostip: str, datas: list) -> None:
        """
        :param datas:
        :param hostip:
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='DNAT')
        my_mongo.delete_many(query=dict(hostip=hostip))
        my_mongo.insert_many(datas)
        # my_mongo.update(filter=dict(hostip=hostip), update={"$set": datas})
        return

    # 采集任务之前，清除所有采集库结果
    @staticmethod
    def clear_his_collect_res():
        # 清空check校验任务
        MongoOps(db='Automation', coll='tracking_task').delete()
        # 清空寻觅定位耗时记录
        MongoOps(db='logs', coll='xumi_time_cost').delete()
        # 清空定位成功数据
        XunMiOps.delete_success_ip_list()
        # 清空testfsm记录
        MongoOps(db='Automation', coll='collect_textfsm_info').delete()
        # 清空arp 和 mac 过期数据
        MongoNetOps.clear_arp_mac_table()
        # 清空mongo中的失败任务记录
        MongoOps(db='Automation', coll='collect_failed_logs').delete()
        MongoOps(db='Automation', coll='firewall_error').delete()
        MongoOps(db='Automation', coll='patch_error').delete()
        # MongoOps(db='Automation', coll='DNAT').delete()
        # 清空netconf失败记录
        MongoOps(db='Automation', coll='netconf_failed').delete()
        # MongoOps(db='Automation', coll='ARPTable').delete()
        # MongoOps(db='Automation', coll='AggreTable').delete()
        # MongoOps(db='Automation', coll='LLDPTable').delete()
        # MongoOps(db='Automation', coll='MACTable').delete()
        # MongoOps(db='Automation', coll='hillstone_interface').delete()
        # MongoOps(db='Automation', coll='hillstone_address').delete()
        # MongoOps(db='Automation', coll='hillstone_service').delete()
        # MongoOps(db='Automation', coll='hillstone_servgroup').delete()
        # MongoOps(db='Automation', coll='hillstone_slb_server').delete()
        # MongoOps(db='Automation', coll='hillstone_dnat').delete()
        # MongoOps(db='Automation', coll='layer2interface').delete()
        # MongoOps(db='Automation', coll='layer3interface').delete()
        # MongoOps(db='Automation', coll='mellanox_interface').delete()
        netconf_db = MongoOps(db='NETCONF', coll='netconf_interface_ipv4v6')
        netconf_tables = netconf_db.all_table()
        for netconf_table in netconf_tables:
            MongoOps(db='NETCONF', coll=netconf_table).delete()
        return


# 通用文本信息分析任务类
class StandardFSMAnalysis(object):

    # 二层接口分析
    @staticmethod
    def layer_2_interface(res, fsm_flag, hostip):
        layer2datas = []
        if fsm_flag == 'hp_comware':
            """
            {'interface': 'BAGG1', 'status': 'UP', 'speed': '20G(a)', 'duplex': 'F(a)', 'type': 'A', 'pvid': '1',
             'description': ''}
            {'interface': 'BAGG2', 'status': 'UP', 'speed': '20G(a)', 'duplex': 'F(a)', 'type': 'A', 'pvid': '1',
             'description': ''}
            """
            for i in res:
                if i['interface'].startswith('BAGG'):
                    continue
                elif i['interface'].startswith('RAGG'):
                    continue
                elif i['interface'].startswith('Vlan'):
                    continue
                if i['speed'].find('-') != -1:
                    i['speed'] = 'IRF'
                elif i['speed'].find('(') != -1:
                    i['speed'] = i['speed'].split('(')[0]
                if i['duplex'].find('-') != -1:
                    i['duplex'] = 'IRF'
                if i['speed'] == 'auto':
                    i['speed'] = InterfaceFormat.h3c_speed_format(
                        i['interface'])
                data = dict(hostip=hostip,
                            interface=InterfaceFormat.h3c_interface_format(
                                i['interface']),
                            status=i['status'],
                            speed=InterfaceFormat.mathintspeed(i['speed']),
                            duplex=i['duplex'],
                            description=i['description'])
                layer2datas.append(data)
        elif fsm_flag == 'mellanox':
            """
            {'interface': 'lo', 'adminstate': 'yes', 'operationalstate': 'yes', 'lastchange': '', 'description': '',
             'macaddress': '', 'mtu': '', 'supportedspeeds': '', 'advertisedspeeds': '', 'actualspeed': '',
             'manageip': '127.0.0.1', 'ipv4address': [], 'ipv4type': []}
            {'interface': 'mgmt0', 'adminstate': 'yes', 'operationalstate': 'yes', 'lastchange': '', 'description': '',
             'macaddress': '', 'mtu': '', 'supportedspeeds': '', 'advertisedspeeds': '', 'actualspeed': '',
             'manageip': '10.254.12.67', 'ipv4address': [], 'ipv4type': []}
            {'interface': 'mgmt1', 'adminstate': 'yes', 'operationalstate': 'no', 'lastchange': '', 'description': '',
             'macaddress': '', 'mtu': '', 'supportedspeeds': '', 'advertisedspeeds': '', 'actualspeed': '',
             'manageip': '', 'ipv4address': [], 'ipv4type': []}
            {'interface': 'Eth1/1', 'adminstate': 'Enabled', 'operationalstate': 'Up',
             'lastchange': '84w 3d and 22:02:20 ago (9 oper change)', 'description': 'N/A',
             'macaddress': '7C:FE:90:F0:15:88', 'mtu': '9216 bytes (Maximum packet size 9238 bytes)',
             'supportedspeeds': '1G 10G 25G 40G 50G 56G 100G', 'advertisedspeeds': '100G', 'actualspeed': '100G',
             'manageip': '', 'ipv4address': ['10.253.12.185/30'], 'ipv4type': ['primary']}
            {'interface': 'Eth1/2', 'adminstate': 'Enabled', 'operationalstate': 'Up',
             'lastchange': '84w 3d and 22:02:19 ago (9 oper change)', 'description': 'N/A',
             'macaddress': '7C:FE:90:F0:15:88', 'mtu': '9216 bytes (Maximum packet size 9238 bytes)',
             'supportedspeeds': '1G 10G 25G 40G 50G 56G 100G', 'advertisedspeeds': '100G', 'actualspeed': '100G',
             'manageip': '', 'ipv4address': ['10.253.12.189/30'], 'ipv4type': ['primary']}
            """
            for i in res:
                if i['interface'].find('lo') != -1:
                    continue
                elif i['interface'].find('mgmt') != -1:
                    continue
                supportedspeeds = i['actualspeed']
                try:
                    supportedspeeds = i['supportedspeeds'].split()[-1]

                except Exception as e:
                    pass
                data = dict(hostip=hostip,
                            interface=i['interface'],
                            status=i['operationalstate'],
                            speed=InterfaceFormat.mathintspeed(
                                i['actualspeed']),
                            maxspeed=supportedspeeds,
                            duplex=i.get('duplex'),
                            mtu=i['mtu'],
                            lastchange=i['lastchange'],
                            description=i['description'])
                layer2datas.append(data)
        elif fsm_flag == 'ruijie':
            """
            {'interface': 'GigabitEthernet 1/0/1', 'status': 'down',
            'vlan': '1526', 'duplex': 'Unknown', 'speed': 'Unknown', 'type': 'copper'}
            """
            for i in res:
                if i['interface'].startswith('AggregatePort'):
                    continue
                if i['speed'] == 'Unknown' or i['speed'] == 'unknown':
                    i['speed'] = InterfaceFormat.ruijie_speed_format(
                        i['interface'])
                data = dict(hostip=hostip,
                            interface=i['interface'],
                            status=i['status'],
                            # speed=i['speed'],
                            speed=InterfaceFormat.mathintspeed(i['speed']),
                            duplex=i['duplex'],
                            description=i.get('description'))
                layer2datas.append(data)
        elif fsm_flag == 'centec':
            """
            {'interface': 'eth-0-1', 'status': 'down',
            'duplex': 'full', 'speed': '40000', 'mode': 'ACCESS', 'type': 'Unknown', 'description': ''}
            """
            for i in res:
                speed = i['speed']
                if i['speed'].startswith('a-'):
                    speed = i['speed'].split('a-')[1]
                data = dict(hostip=hostip,
                            interface=i['interface'],
                            status=i['status'],
                            speed=InterfaceFormat.mathintspeed(speed),
                            duplex=i['duplex'],
                            description=i.get('description'))
                layer2datas.append(data)
        if layer2datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer2datas,
                tablename='layer2interface')
        return

    # 三层IP接口分析  华为 mellanox hillstone 单独处理不用此方法
    @staticmethod
    def layer_3_interface(res, fsm_flag, hostip):
        layer3datas = []
        if fsm_flag == 'hp_comware':
            # {'intf': 'FortyGigE1/0/49', 'line_status': 'UP', 'protocol_status': 'UP', 'ipaddr': ['100.71.0.146/30'],
            #  'ip_type': ['Primary'], 'mtu': '1500'}
            # {'intf': 'FortyGigE1/0/50', 'line_status': 'UP', 'protocol_status': 'UP', 'ipaddr': ['100.71.0.154/30'],
            #  'ip_type': ['Primary'], 'mtu': '1500'}
            # {'intf': 'FortyGigE1/0/53', 'line_status': 'UP', 'protocol_status': 'UP', 'ipaddr': [], 'ip_type': [],
            #  'mtu': ''}
            for i in res:
                if isinstance(i['ipaddr'], list):
                    for _ip in range(len(i['ipaddr'])):
                        # _ip 为数组下标 0，1，2，3
                        if i['ipaddr'][_ip].find('/') != -1:
                            _ipnet = IPaddr.IPv4Network(i['ipaddr'][_ip])
                            data = dict(
                                hostip=hostip,
                                interface=InterfaceFormat.h3c_interface_format(
                                    i['intf']),
                                line_status=i['line_status'],
                                protocol_status=i['protocol_status'],
                                ipaddress=str(_ipnet.ip),
                                ipmask=str(_ipnet.netmask),
                                ip_type=i['ip_type'][_ip],
                                mtu=i['mtu'])
                            layer3datas.append(data)
                        else:
                            data = dict(
                                hostip=hostip,
                                interface=InterfaceFormat.h3c_interface_format(
                                    i['intf']),
                                line_status=i['line_status'],
                                protocol_status=i['protocol_status'],
                                ipaddress=i['ipaddr'][_ip],
                                ipmask='',
                                ip_type=i['ip_type'][_ip],
                                mtu=i['mtu'])
                            layer3datas.append(data)
                else:
                    if i['ipaddr'].find('/') != -1:
                        _ipnet = IPaddr.IPv4Network(i['ipaddr'])
                        ipaddr = str(_ipnet.ip)
                        ipmask = str(_ipnet.netmask)
                        data = dict(
                            hostip=hostip,
                            interface=InterfaceFormat.h3c_interface_format(
                                i['intf']),
                            line_status=i['line_status'],
                            protocol_status=i['protocol_status'],
                            ipaddress=ipaddr,
                            ipmask=ipmask,
                            ip_type=i['ip_type'],
                            mtu=i['mtu'])
                        layer3datas.append(data)
                    else:
                        data = dict(
                            hostip=hostip,
                            interface=InterfaceFormat.h3c_interface_format(
                                i['intf']),
                            line_status=i['line_status'],
                            protocol_status=i['protocol_status'],
                            ipaddress=i['ipaddr'],
                            ipmask='',
                            ip_type=i['ip_type'],
                            mtu=i['mtu'])
                        layer3datas.append(data)
        elif fsm_flag == 'ruijie':
            # {'interface': 'TFGigabitEthernet 1/1',
            # 'priipaddr': '100.72.0.41/30', 'secipaddr': 'no address', 'status': 'up', 'protocol': 'up'}
            for i in res:
                if i['priipaddr'] != 'no address':
                    _ip = netaddr.IPNetwork(i['priipaddr'])
                    data = dict(
                        hostip=hostip,
                        interface=i['interface'],
                        line_status=i['status'],
                        protocol_status=i['protocol'],
                        ipaddress=str(_ip.ip.format()),
                        ipmask=str(_ip.netmask.format()),
                        ip_type='Primary',
                        mtu='')
                    layer3datas.append(data)
                elif i['secipaddr'] != 'no address':
                    _ip = netaddr.IPNetwork(i['priipaddr'])
                    data = dict(
                        hostip=hostip,
                        interface=i['interface'],
                        line_status=i['status'],
                        protocol_status=i['protocol'],
                        ipaddress=str(_ip.ip.format()),
                        ipmask=str(_ip.netmask.format()),
                        ip_type='Sub',
                        mtu='')
                    layer3datas.append(data)
                else:
                    data = dict(
                        hostip=hostip,
                        interface=i['interface'],
                        line_status=i['status'],
                        protocol_status=i['protocol'],
                        ipaddress=i['priipaddr'],
                        ip_type='',
                        mtu='')
                    layer3datas.append(data)
        elif fsm_flag == 'centec':
            # {'interface': 'eth-0-21', 'ip': '10.253.13.174', 'status': 'up', 'protocol': 'up'}
            # {'interface': 'eth-0-22', 'ip': '10.253.13.182', 'status': 'up', 'protocol': 'up'}
            for i in res:
                data = dict(
                    hostip=hostip,
                    interface=i['interface'],
                    line_status=i['status'],
                    protocol_status=i['protocol'],
                    ipaddress=i['ip'],
                    ip_type='',
                    mtu='')
                layer3datas.append(data)
        elif fsm_flag == 'mellanox':
            for i in res:
                if i['ipaddr'] != 'Unassigned':
                    _ip = netaddr.IPNetwork(i['ipaddr'])
                    data = dict(
                        hostip=hostip,
                        interface=i['interface'],
                        line_status=i['operstate'],
                        protocol_status='',
                        ipaddress=str(_ip.ip.format()),
                        ipmask=str(_ip.netmask.format()),
                        ip_type=i['primary'],
                        mtu=i['mtu']
                    )
                    layer3datas.append(data)
        if layer3datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer3datas,
                tablename='layer3interface')
        return

    @staticmethod
    def mac_address_proc(res, fsm_flag, hostip, idc, hostname):
        mac_datas = []
        if fsm_flag == 'huawei_vrp':
            # {'macaddress': 'ae6b-3744-2fca', 'vlan': '688', 'interface': 'Eth-Trunk43', 'type': 'dynamic'}
            for i in res:
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=i['macaddress'],
                    vlan=i['vlan'],
                    interface=InterfaceFormat.huawei_interface_format(
                        i['interface']),
                    type=i['type'],
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'hp_comware':
            # {'macaddress': '0440-a9e4-73d2', 'vlan': '1', 'state': 'Learned', 'interface': 'BAGG47', 'aging': 'Y'}
            for i in res:
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=i['macaddress'],
                    vlan=i['vlan'],
                    interface=InterfaceFormat.h3c_interface_format(
                        i['interface']),
                    type=i['state'],
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'hillstone':
            # {'macaddress': '001c.5457.f21d',
            # 'switch': 'vlan3001', 'interface': 'ethernet0/6', 'type': 'D', 'age': '5786'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=macaddress,
                    vlan=i['switch'],
                    interface=i['interface'],
                    type=i['type'],
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'mellanox':
            # {'vlan': '100', 'interface': 'Eth1/6', 'macaddress': '24:8A:07:0A:4F:F0', 'type': 'Dynamic'}
            # {'vlan': '100', 'interface': 'Eth1/45', 'macaddress': '24:8A:07:0A:4F:F8', 'type': 'Dynamic'}
            for i in res:
                try:
                    tmp = i['macaddress'].split(':')
                    macaddress = tmp[0] + tmp[1] + '-' + \
                                 tmp[2] + tmp[3] + '-' + tmp[4] + tmp[5]
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=macaddress.lower(),
                    vlan=i['vlan'],
                    interface=i['interface'],
                    type=i['type'],
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'ruijie':
            # {'vlan': '1411', 'macaddress': '0000.0000.0100',
            # 'type': 'DYNAMIC', 'interface': 'TenGigabitEthernet 2/0/2'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=macaddress,
                    vlan=i['vlan'],
                    interface=i['interface'].strip(),
                    type=i['type'].lower(),
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'centec':
            # {'vlan': '129', 'macaddress': 'fa16.3e83.0591', 'type': 'dynamic',
            # 'ports': 'VxLAN: 10.255.250.11->172.31.208.62(MO)'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=macaddress,
                    vlan=i['vlan'],
                    interface=i['ports'].strip(),
                    type=i['type'].lower(),
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        elif fsm_flag == 'maipu':
            # {'vlan': '13', 'macaddress': 'F474.882A.CA64', 'type': 'DYNAMIC',
            # 'interface': 'link-agg4', 'state': 'FWD', 'flag': '[M]'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    macaddress=macaddress.lower(),
                    vlan=i['vlan'],
                    interface=i['interface'].strip(),
                    type=i['type'].lower(),
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
        if mac_datas:
            AutomationMongo.insert_table(
                'Automation', hostip, mac_datas, 'MACTable')
        return

    # ARP信息分析
    @staticmethod
    def arp_table_proc(res, fsm_flag, hostip, idc, hostname):
        arp_datas = []
        if fsm_flag == 'huawei_vrp':
            # {'ipaddress': '172.16.70.84', 'macaddress': '0050-569f-34af',
            # 'expire': '20', 'type': 'D-0/0', 'vlan': '570', 'interface': 'Eth-Trunk13', 'vpninstance': ''}
            for i in res:
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ipaddress'],
                    macaddress=i['macaddress'],
                    aging=i['expire'],
                    type=i['type'],
                    vlan=i['vlan'],
                    interface=InterfaceFormat.huawei_interface_format(
                        i['interface']),
                    vpninstance=i['vpninstance'],
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'hp_comware':
            # {'ipaddress': '10.101.15.61', 'macaddress': 'fa16-3e8d-7c0a', 'vlan': '5',
            # 'interface': 'BAGG2', 'aging': '1191', 'type': 'D'}
            for i in res:
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ipaddress'],
                    macaddress=i['macaddress'],
                    aging=i['aging'],
                    type=i['type'],
                    vlan=i['vlan'],
                    interface=InterfaceFormat.h3c_interface_format(
                        i['interface']),
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'hillstone':
            # {'protocol': 'Internet', 'ipaddress': '36.7.109.2', 'age': '5593',
            # 'macaddress': '7c1e.0624.a05c', 'typeflag': 'ARPA', 'interface': 'vlan101'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ipaddress'],
                    macaddress=macaddress,
                    aging=i['age'],
                    type=i['typeflag'],
                    vlan='',
                    interface=i['interface'],
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'mellanox':
            for i in res:
                try:
                    tmp = i['macaddress'].split(':')
                    macaddress = tmp[0] + tmp[1] + '-' + \
                                 tmp[2] + tmp[3] + '-' + tmp[4] + tmp[5]
                except Exception as e:
                    macaddress = i.get('macaddress')
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ipaddr'],
                    macaddress=macaddress.lower(),
                    aging='',
                    type=i['type'],
                    vlan='',
                    interface=i['interface'],
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'ruijie':
            # {'protocol': 'Internet', 'address': '172.17.1.1', 'agemin': '--', 'hardware': '5869.6c20.0023', 'type': 'arpa', 'interface': 'VLAN 1501       '}
            # {'protocol': 'Internet', 'address': '172.17.1.2', 'agemin': '7', 'hardware': '5869.6c20.001b', 'type': 'arpa', 'interface': 'VLAN 1501       '}
            for i in res:
                try:
                    macaddress = i['hardware'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('hardware')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['address'],
                    macaddress=macaddress,
                    aging=i['agemin'],
                    type=i['type'],
                    vlan=i.get('vlan'),
                    interface=i['interface'].strip(),
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'centec':
            # {'protocol': 'Internet', 'ip': '172.31.129.3', 'age': '33',
            # 'macaddress': '001e.080c.71d7', 'interface': 'vlan129'}
            # {'protocol': 'Internet', 'ip': '172.31.129.4', 'age': '14',
            # 'macaddress': 'fa16.3e5d.7359', 'interface': 'vlan129(tunnel)'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ip'],
                    macaddress=macaddress,
                    aging=i['age'],
                    type='',
                    vlan='',
                    interface=i['interface'],
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        elif fsm_flag == 'maipu':
            # {'ipaddress': '10.254.0.9', 'protocol': 'Internet', 'macaddress': '0050.5692.e42e',
            # 'age': '1', 'type': 'ARPA', 'vlan': 'vlan100', 'interface': 'link-agg1'}
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=hostip,
                    hostname=hostname,
                    idc_name=idc,
                    ipaddress=i['ipaddress'],
                    macaddress=macaddress.lower(),
                    aging=i['age'],
                    type=i['type'],
                    vlan=i['vlan'],
                    interface=i['interface'],
                    vpninstance='',
                    log_time=datetime.now()
                )
                arp_datas.append(tmp)
        if arp_datas:
            AutomationMongo.insert_table(
                'Automation', hostip, arp_datas, 'ARPTable')

    # LLDP信息分析
    @staticmethod
    def lldp_proc(res, fsm_flag, hostip):
        lldp_datas = []
        if fsm_flag == 'huawei_vrp':
            """
             {'local_interface': 'XGigabitEthernet2/4/0/11', 'chassis_id': 'e097-9653-ff60',
             'neighbor_port': 'XGigabitEthernet0/0/2', 'portdescription': 'XGigabitEthernet0/0/2',
             'neighborsysname': 'GSJF_5#_S5710-1', 'management_ip': 'e097-9653-ff60', 'management_type': 'all802'}
             {'local_interface': 'GigabitEthernet2/3/0/0', 'chassis_id': '7054-f596-f530',
             'neighbor_port': 'GigabitEthernet1/3/0/0', 'portdescription': 'To:G2/3/0/0',
             'neighborsysname': 'A2.NET.PO.CO.002', 'management_ip': '172.16.252.1', 'management_type': 'ipV4'}
             {'local_interface': 'XGigabitEthernet1/5/0/1', 'chassis_id': 'f8b1-562f-5d7b', 'neighbor_port': 'Te1/1/1',
             'portdescription': 'NA', 'neighborsysname': 'NA', 'management_ip': '', 'management_type': ''}
            """
            for i in res:
                neighbor_ip = ''
                if i['neighborsysname']:
                    tmp_neighbor_ip = cache.get('cmdb_' + i['neighborsysname'])
                    if tmp_neighbor_ip:
                        tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                        neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                    else:
                        tmp_neighbor_ip = NetworkDevice.objects.filter(name=i['neighborsysname']
                                                                       ).values('manage_ip')
                        neighbor_ip = tmp_neighbor_ip[0]['manage_ip'] if tmp_neighbor_ip else ''
                tmp = dict(
                    hostip=hostip,
                    local_interface=i['local_interface'],
                    chassis_id=i['chassis_id'],
                    neighbor_port=i['neighbor_port'],
                    portdescription=i['portdescription'],
                    neighborsysname=i['neighborsysname'],
                    management_ip=i['management_ip'],
                    management_type=i['management_type'],
                    neighbor_ip=neighbor_ip
                )
                lldp_datas.append(tmp)
        elif fsm_flag == 'hp_comware':
            """
            {'local_interface': 'Ten-GigabitEthernet1/0/32', 'chassis_id': '9ce8-9568-b322',
            'neighbor_port': 'Ten-GigabitEthernet2/0/32', 'portdescription': 'Ten-GigabitEthernet2/0/32 Interface',
            'neighborsysname': 'DZ.NET.IN.AS.X01', 'management_ip': '100.64.0.1', 'management_type': 'IPv4'}
            {'local_interface': 'Ten-GigabitEthernet1/0/38', 'chassis_id': '4077-a9f5-02ac',
            'neighbor_port': 'Ten-GigabitEthernet1/1/6', 'portdescription': 'Ten-GigabitEthernet1/1/6 Interface',
            'neighborsysname': 'DZ.JSZX.IN.FW.001', 'management_ip': '80e4-550d-f166', 'management_type': 'All802'}

            """
            for i in res:
                neighbor_ip = ''
                if i['neighborsysname']:
                    tmp_neighbor_ip = cache.get('cmdb_' + i['neighborsysname'])
                    if tmp_neighbor_ip:
                        tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                        neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                    else:
                        tmp_neighbor_ip = NetworkDevice.objects.filter(name=i['neighborsysname']
                                                                       ).values('manage_ip').first()
                        neighbor_ip = tmp_neighbor_ip['manage_ip'] if tmp_neighbor_ip else ''
                tmp = dict(
                    hostip=hostip,
                    local_interface=i['local_interface'],
                    chassis_id=i['chassis_id'],
                    neighbor_port=i['neighbor_port'],
                    portdescription=i['portdescription'],
                    neighborsysname=i['neighborsysname'],
                    management_ip=i['management_ip'],
                    management_type=i['management_type'],
                    neighbor_ip=neighbor_ip
                )
                lldp_datas.append(tmp)
        elif fsm_flag == 'maipu':
            """
            {'local_interface': 'te0/46', 'neighbor_port': 'Ten-GigabitEthernet2/0/48', 
            'neighborsysname': 'B3.NET.INT.DS.X02'}
            """
            for i in res:
                neighbor_ip = ''
                if i['neighborsysname']:
                    tmp_neighbor_ip = cache.get('cmdb_' + i['neighborsysname'])
                    if tmp_neighbor_ip:
                        tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                        neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                    else:
                        tmp_neighbor_ip = NetworkDevice.objects.filter(name=i['neighborsysname']
                                                                       ).values('manage_ip').first()
                        neighbor_ip = tmp_neighbor_ip['manage_ip'] if tmp_neighbor_ip else ''
                tmp = dict(
                    hostip=hostip,
                    local_interface=InterfaceFormat.maipu_interface_format(i['local_interface']),
                    chassis_id='',
                    neighbor_port=i['neighbor_port'],
                    portdescription='',
                    neighborsysname=i['neighborsysname'],
                    management_ip=neighbor_ip,
                    management_type='',
                    neighbor_ip=neighbor_ip
                )
                lldp_datas.append(tmp)
        if lldp_datas:
            AutomationMongo.insert_table(
                'Automation', hostip, lldp_datas, 'LLDPTable')

    # 链路聚合分析
    @staticmethod
    def aggre_port_proc(res, fsm_flag, hostip):
        aggre_datas = []
        if fsm_flag == 'hp_comware':
            """
             {'aggname': 'Bridge-Aggregation1', 'mode': 'Static', 'memberports': ['XGE1/0/1', 'XGE2/0/1'],
             'status': ['U', 'U']}
             {'aggname': 'Bridge-Aggregation2', 'mode': 'Dynamic', 'memberports': ['XGE1/0/2', 'XGE2/0/2'],
             'status': ['U', 'U']}
             {'aggname': 'Bridge-Aggregation5', 'mode': 'Dynamic', 'memberports': ['XGE1/0/5', 'XGE2/0/5'],
             'status': ['U', 'U']}
             {'aggname': 'Bridge-Aggregation9', 'mode': 'Dynamic', 'memberports': ['XGE1/0/9', 'XGE2/0/9'],
             'status': ['S', 'S']}
            """
            for i in res:
                if isinstance(i['memberports'], list):
                    memberports = []
                    for member in i['memberports']:
                        memberports.append(
                            InterfaceFormat.h3c_interface_format(member))
                else:
                    memberports = i['memberports']
                tmp = dict(
                    hostip=hostip,
                    aggregroup=i['aggname'],
                    memberports=memberports,
                    status=i['status'],
                    mode=i.get('mode')
                )
                aggre_datas.append(tmp)
        elif fsm_flag == 'mellanox':
            """
            {'group': '1', 'portchannel': 'Po29(U)', 'type': 'LACP', 'memberports': 'Eth1/29(P) Eth1/32(P)'}
            {'group': '2', 'portchannel': 'Po30(U)', 'type': 'LACP', 'memberports': 'Eth1/30(P) Eth1/31(P)'}
            """
            for i in res:
                try:
                    memberports = []
                    tmp_members = i['memberports'].split()
                    for member in tmp_members:
                        memberports.append(member.split('(')[0])
                except Exception as e:
                    memberports = i['memberports'].split()
                tmp = dict(
                    hostip=hostip,
                    aggregroup=i['portchannel'],
                    memberports=memberports,
                    status='',
                    mode=i.get('type')
                )
                aggre_datas.append(tmp)
        elif fsm_flag == 'ruijie':
            """
             {'aggregateport': 'Ag103', 'maxports': '16',
            'switchportmode': 'Disabled', 'loadbalance': 'src-dst-mac', 'ports': 'TF1/3   ,TF1/4   '}
            """
            for i in res:
                try:
                    memberports = []
                    tmp_members = i['ports'].split(',')
                    for member in tmp_members:
                        memberports.append(member.strip())
                except Exception as e:
                    memberports = i['memberports'].split(',')
                tmp = dict(
                    hostip=hostip,
                    aggregroup=i['aggregateport'],
                    memberports=memberports,
                    status='',
                    mode=''
                )
                aggre_datas.append(tmp)
        elif fsm_flag == 'huawei_vrp':
            for i in res:
                if isinstance(i['portname'], list):
                    memberports = []
                    for member in i['portname']:
                        memberports.append(
                            InterfaceFormat.huawei_interface_format(member))
                else:
                    memberports = i['portname']
                tmp = dict(
                    hostip=hostip,
                    aggregroup=i['trunk_num'],
                    memberports=memberports,
                    status=i['portstatus'],
                    mode=''
                )
                aggre_datas.append(tmp)
        elif fsm_flag == 'maipu':
            # {'interface': '40ge0/53', 'aggregate': '53', 'selected': 'YES',
            # 'attached': 'YES', 'mode': 'Active', 'lacp_enable': 'Lacp_Enabled_Full_Duplex'}
            # {'interface': '40ge0/54', 'aggregate': '53', 'selected': 'YES',
            # 'attached': 'YES', 'mode': 'Active', 'lacp_enable': 'Lacp_Enabled_Full_Duplex'}
            tmp = {}
            for i in res:
                if i['aggregate'] in tmp.keys():
                    tmp[i['aggregate']]['memberports'].append(i['interface'])
                    tmp[i['aggregate']]['status'].append(i['selected'])
                    tmp[i['aggregate']]['mode'].append(i['mode'])
                else:
                    tmp[i['aggregate']] = {
                        'memberports': [i['interface']],
                        'status': [i['selected']],
                        'mode': [i['mode']]
                    }
            for i in tmp.keys():
                aggre_datas.append(dict(
                    hostip=hostip,
                    aggregroup=i,
                    memberports=tmp[i]['memberports'],
                    status=tmp[i]['status'],
                    mode=tmp[i]['mode']
                ))
        if aggre_datas:
            AutomationMongo.insert_table(
                'Automation', hostip, aggre_datas, 'AggreTable')

    # EVPN信息分析
    @staticmethod
    def evpn_route_arp(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            pass
        elif fsm_flag == 'hp_comware':
            pass
        pass
        # EVPN信息分析

    @staticmethod
    def evpn_route_mac(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            pass
        elif fsm_flag == 'hp_comware':
            pass
        pass

    @staticmethod
    def l2vpn_vsi_verbose(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            pass
        elif fsm_flag == 'hp_comware':
            pass
        pass

    @staticmethod
    def l2vpn_mac(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            pass
        elif fsm_flag == 'hp_comware':
            pass
        pass

    @staticmethod
    def power_proc(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            """
            {'chassis': '1', 'powerno': 'PWR1', 'present': 'YES', 'mode': 'AC', 'state': 'Supply', 'current': '3.2800',
             'voltage': '53.6700', 'realpwr': '177.1000'}
            {'chassis': '1', 'powerno': 'PWR2', 'present': 'YES', 'mode': 'AC', 'state': 'Supply', 'current': '3.2300',
             'voltage': '53.6700', 'realpwr': '172.2000'}
            {'chassis': '1', 'powerno': 'PWR3', 'present': 'NO', 'mode': 'N/A', 'state': 'N/A', 'current': 'N/A',
             'voltage': 'N/A', 'realpwr': 'N/A'}
            {'chassis': '1', 'powerno': 'PWR4', 'present': 'NO', 'mode': 'N/A', 'state': 'N/A', 'current': 'N/A',
             'voltage': 'N/A', 'realpwr': 'N/A'}
            {'chassis': '2', 'powerno': 'PWR1', 'present': 'YES', 'mode': 'AC', 'state': 'Supply', 'current': '3.2800',
             'voltage': '53.5500', 'realpwr': '174.0000'}
            {'chassis': '2', 'powerno': 'PWR2', 'present': 'YES', 'mode': 'AC', 'state': 'Supply', 'current': '3.3000',
             'voltage': '53.7300', 'realpwr': '176.2000'}
            {'chassis': '2', 'powerno': 'PWR3', 'present': 'NO', 'mode': 'N/A', 'state': 'N/A', 'current': 'N/A',
             'voltage': 'N/A', 'realpwr': 'N/A'}
            {'chassis': '2', 'powerno': 'PWR4', 'present': 'NO', 'mode': 'N/A', 'state': 'N/A', 'current': 'N/A',
             'voltage': 'N/A', 'realpwr': 'N/A'}
             """
            pass
        elif fsm_flag == 'hp_comware':
            """
            {'slot': '1', 'powerid': '1', 'state': 'Normal', 'mode': 'AC', 'current': '--', 'voltage': '--',
             'power': '--'}
            {'slot': '1', 'powerid': '2', 'state': 'Normal', 'mode': 'AC', 'current': '--', 'voltage': '--',
             'power': '--'}
            {'slot': '2', 'powerid': '1', 'state': 'Normal', 'mode': 'AC', 'current': '--', 'voltage': '--',
             'power': '--'}
            {'slot': '2', 'powerid': '2', 'state': 'Normal', 'mode': 'AC', 'current': '--', 'voltage': '--',
             'power': '--'}
            """
            pass
        elif fsm_flag == 'mellanox':
            """
            {'module': 'PS1', 'device': 'power-mon', 'sensor': 'input',
            'power': '95.12', 'voltage': '229.00',
            'current': '0.42', 'capacity': '460.00', 'feed': 'AC', 'status': 'OK'}
            """
            pass
        elif fsm_flag == 'ruijie':
            """
            {'device': '1', 'item': '1', 'type': 'NO DEVICE', 'serialnum': '-',
            'ver': '-', 'ratepower': '-', 'outpower': '-', 'vol': '-', 'temp': '-', 'status': 'NoLink'}
            {'device': '1', 'item': '2', 'type': 'M6000-AC500', 'serialnum': 'A81908140401062',
            'ver': '1.10', 'ratepower': '100', 'outpower': '-', 'vol': '-', 'temp': '-', 'status': 'LinkAndPower'}
            """
            pass
        pass

    @staticmethod
    def fan_proc(res, fsm_flag, hostip):
        if fsm_flag == 'huawei_vrp':
            """
            {'chassis': '1', 'fanid': '1', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '29%(1530)', 'mode': 'AUTO'}
            {'chassis': '1', 'fanid': '2', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '29%(1515)', 'mode': 'AUTO'}
            {'chassis': '1', 'fanid': '3', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '49%(1665)', 'mode': 'AUTO'}
            {'chassis': '1', 'fanid': '4', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '49%(1665)', 'mode': 'AUTO'}
            {'chassis': '2', 'fanid': '1', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '29%(1515)', 'mode': 'AUTO'}
            {'chassis': '2', 'fanid': '2', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '29%(1530)', 'mode': 'AUTO'}
            {'chassis': '2', 'fanid': '3', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '49%(1665)', 'mode': 'AUTO'}
            {'chassis': '2', 'fanid': '4', 'fannum': '1-2', 'present': 'YES', 'register': 'YES', 'speed': '49%(1665)', 'mode': 'AUTO'}
            """
            pass
        elif fsm_flag == 'hp_comware':
            # {'slot': '1', 'fanid': '1', 'airflowdirection': '', 'preferairflowdirection': '', 'state': 'Normal'}
            # {'slot': '1', 'fanid': '2', 'airflowdirection': '', 'preferairflowdirection': '', 'state': 'Normal'}
            # {'slot': '1', 'fanid': '1', 'airflowdirection': '', 'preferairflowdirection': '', 'state': 'Normal'}
            # {'slot': '1', 'fanid': '2', 'airflowdirection': '', 'preferairflowdirection': '', 'state': 'Normal'}
            pass
        elif fsm_flag == 'mellanox':
            # {'module': 'FAN1', 'device': 'FAN', 'fan': 'F1', 'speedrpm': '20491.00', 'status': 'OK'}
            # {'module': 'FAN1', 'device': 'FAN', 'fan': 'F2', 'speedrpm': '18050.00', 'status': 'OK'}
            pass
        elif fsm_flag == 'ruijie':
            # {'device': '1', 'item': '3', 'status': 'Normal', 'serialnum': '-', 'ver': '-', 'speed': '1'}
            # {'device': '2', 'item': '1', 'status': 'Normal', 'serialnum': '-', 'ver': '-', 'speed': '1'}
            pass
        pass

    @staticmethod
    def environment_proc(res, fsm_flag, hostip):
        """
        盛科：
        {'fanindex': '1-1', 'fanstatus': 'OK', 'fanspeedrate': '40%', 'fanmode': 'Auto', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '1-2', 'fanstatus': 'OK', 'fanspeedrate': '40%', 'fanmode': 'Auto', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '1-3', 'fanstatus': 'OK', 'fanspeedrate': '40%', 'fanmode': 'Auto', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '1-4', 'fanstatus': 'OK', 'fanspeedrate': '40%', 'fanmode': 'Auto', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '', 'fanstatus': '', 'fanspeedrate': '', 'fanmode': '', 'powerindex': '1', 'powerstatus': 'PRESENT', 'power': 'OK', 'powertype': 'AC', 'poweralert': 'NO', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '', 'fanstatus': '', 'fanspeedrate': '', 'fanmode': '', 'powerindex': '2', 'powerstatus': 'PRESENT', 'power': 'OK', 'powertype': 'AC', 'poweralert': 'NO', 'sensorindex': '', 'temperature': '', 'loweralarm': '', 'upperalarm': '', 'criticallimit': '', 'position': ''}
        {'fanindex': '', 'fanstatus': '', 'fanspeedrate': '', 'fanmode': '', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '1', 'temperature': '44', 'loweralarm': '5', 'upperalarm': '65', 'criticallimit': '80', 'position': 'AROUND_CHIP'}
        {'fanindex': '', 'fanstatus': '', 'fanspeedrate': '', 'fanmode': '', 'powerindex': '', 'powerstatus': '', 'power': '', 'powertype': '', 'poweralert': '', 'sensorindex': '2', 'temperature': '68', 'loweralarm': '-10', 'upperalarm': '100', 'criticallimit': '110', 'position': 'SWITCH_CHIP'}
        :param res:
        :param fsm_flag:
        :return:
        """
        if fsm_flag == 'centec':
            pass

    # 华为VRP display interface全量信息专用
    @staticmethod
    def huawei_interface(path, hostip):
        """
        """
        eth_trunk_res = HuaweiS.eth_trunk(path=path)
        interface_res = HuaweiS.interface(path=path)
        aggre_datas = []
        layer3datas = []
        layer2datas = []
        if eth_trunk_res:
            for i in eth_trunk_res:
                if i['IPADDR']:
                    for _ip in range(len(i['IPADDR'])):
                        # _ip 为数组下标 0，1，2，3
                        if i['IPADDR'][_ip].find('/') != -1:
                            _ipnet = IPaddr.IPv4Network(i['IPADDR'][_ip])
                            data = dict(
                                hostip=hostip,
                                interface=i['Interface'],
                                line_status=i['Status'],
                                protocol_status=i['ProtocolStatus'],
                                ipaddress=str(_ipnet.ip),
                                ipmask=str(_ipnet.netmask),
                                ip_type=i['IPTYPE'][_ip],
                                mtu='')
                            layer3datas.append(data)
                tmp = dict(
                    hostip=hostip,
                    aggregroup=i['Interface'],
                    memberports=i['MemberPort'],
                    status=i['MemberPortStatus'],
                    mode=''
                )
                aggre_datas.append(tmp)
        if interface_res:
            for i in interface_res:
                if i['IPADDR']:
                    for _ip in range(len(i['IPADDR'])):
                        # _ip 为数组下标 0，1，2，3
                        if i['IPADDR'][_ip].find('/') != -1:
                            _ipnet = IPaddr.IPv4Network(i['IPADDR'][_ip])
                            data = dict(
                                hostip=hostip,
                                interface=i['Interface'],
                                line_status=i['Status'],
                                protocol_status=i['ProtocolStatus'],
                                ipaddress=str(_ipnet.ip),
                                ipmask=str(_ipnet.netmask),
                                ip_type=i['IPTYPE'][_ip],
                                mtu='')
                            layer3datas.append(data)
                if i['Interface'].startswith('LoopBack'):
                    continue
                if i['Interface'].startswith('NULL'):
                    continue
                if i['Interface'].startswith('Vlanif'):
                    continue
                if i['Interface'].startswith('Ethernet0/0/0'):
                    continue
                data = dict(hostip=hostip,
                            interface=i['Interface'],
                            status=i['Status'],
                            # speed=i['Speed'],
                            speed=InterfaceFormat.mathintspeed(i['Speed']),
                            duplex=i['Duplex'],
                            description=i['Description'])
                layer2datas.append(data)
        if aggre_datas:
            AutomationMongo.insert_table(
                'Automation', hostip, aggre_datas, 'AggreTable')
        if layer3datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer3datas,
                tablename='layer3interface')
        if layer2datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer2datas,
                tablename='layer2interface')
        return

    # mellanox show interfaces全量信息专用
    @staticmethod
    def mellanox_interface(res, fsm_flag, hostip):
        result = []
        """
        """
        layer3datas = []
        layer2datas = []
        for i in res:
            i['hostip'] = hostip
            if i['interface'].startswith('mgmt'):
                continue
            if i['interface'].startswith('lo'):
                continue
            # TODO(jmli12): 解析需要改成ttp模式
            # if i['ipv4address']:
            #     for _ip in range(len(i['ipv4address'])):
            #         # _ip 为数组下标 0，1，2，3
            #         if i['ipv4address'][_ip].find('/') != -1:
            #             _ipnet = IPaddr.IPv4Network(i['ipv4address'][_ip])
            #             data = dict(
            #                 hostip=hostip,
            #                 interface=i['interface'],
            #                 line_status=i['operationalstate'].lower(),
            #                 protocol_status='',
            #                 ipaddress=str(_ipnet.ip.format()),
            #                 ipmask=str(_ipnet.netmask.format()),
            #                 ip_type=i['ipv4type'][_ip],
            #                 mtu=i.get('mtu'))
            #             layer3datas.append(data)
            data = dict(hostip=hostip,
                        interface=i['interface'],
                        status=i['operationalstate'].lower(),
                        speed=i['advertisedspeeds'],
                        # advertisedspeeds  actualspeed 100G  40G
                        duplex='',
                        description=i['description'])
            layer2datas.append(data)
            result.append(i)
        if result:
            AutomationMongo.insert_table(
                'Automation', hostip, result, 'mellanox_interface')
        # if layer3datas:
        #     AutomationMongo.insert_table(db='Automation', hostip=hostip, datas=layer3datas, tablename='layer3interface')
        if layer2datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer2datas,
                tablename='layer2interface')
        return

    # hillstone zone
    @staticmethod
    def hillstone_zone(res, fsm_flag, hostip):
        for i in res:
            i['hostip'] = hostip
        AutomationMongo.insert_table(
            db='Automation',
            hostip=hostip,
            datas=res,
            tablename='hillstone_zone')
        return

    # hillstone show interface全量信息专用
    @staticmethod
    def hillstone_interface(res, hostip):
        """
        增加IP地址定位格式
        :param res:
        :param fsm_flag:
        :param hostip:
        :return:
        """
        result = []
        layer3datas = []
        layer2datas = []
        int_regex = re.compile('ethernet')
        for i in res:
            i['hostip'] = hostip
            physical_status_map = {'U': 'up', 'D': 'down', 'K': 'ha'}
            try:
                # H:physical state;A:admin state;L:link state;P:protocol state;U:up;D:down;K:ha keep up
                # macaddr = i['macaddress'].replace('.', '-')
                tmp = i['halp'].split()
                physical_status = physical_status_map[tmp[0]]
                line_status = physical_status_map[tmp[2]]
                protocol_status = physical_status_map[tmp[3]]
            except BaseException:
                # macaddr = i['macaddress']
                physical_status = ''
                line_status = ''
                protocol_status = ''
            if int_regex.search(i['interface']):
                if i['interface'].startswith('ethernet'):
                    speed = '1G'
                elif i['interface'].startswith('xethernet'):
                    speed = '10G'
                else:
                    speed = 'auto'
                data = dict(hostip=hostip,
                            interface=i['interface'],
                            status=physical_status,
                            speed=speed,
                            duplex='',
                            description=i['description'])
                layer2datas.append(data)
            if i['ipaddr']:
                _ipnet = IPaddr.IPv4Network(i['ipaddr'])
                # 安全纳管引擎，服务发布 定位用
                location = []
                if i['ipaddr'] != '0.0.0.0/0':
                    _location_ip = netaddr.IPNetwork(i['ipaddr'])
                    # 只添加公网地址用于DNAT发布策略匹配
                    if not _location_ip.is_private():
                        location = [dict(start=_location_ip.first,
                                         end=_location_ip.last)]
                data = dict(
                    hostip=hostip,
                    interface=i['interface'],
                    line_status=line_status,
                    protocol_status=protocol_status,
                    ipaddress=str(_ipnet.ip),
                    ipmask=str(_ipnet.netmask),
                    ip_type='',
                    mtu='', location=location)
                layer3datas.append(data)
            result.append(i)
        AutomationMongo.insert_table(
            'Automation', hostip, result, 'hillstone_interface')
        if layer2datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer2datas,
                tablename='layer2interface')
        if layer3datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer3datas,
                tablename='layer3interface')
        return

    @staticmethod
    def maipu_interface(res, hostip):
        """ 10.254.13.11 demo
        {'interface': 'tengigabitethernet0/46', 'protocolstatus': 'up', 'description': '[10.254.13.253][XGE 2/0/48]',
         'ipaddr': ['100.65.0.46/29'], 'macaddress': 'ccd8.1f18.cc2b', 'speed': '10000 M', 'duplex': 'full'}
        :param res:
        :param hostip:
        :return:
        """
        layer3datas = []
        layer2datas = []
        for i in res:
            speed = i['speed']
            if speed == '1000 M':
                speed = '1G'
            elif speed == '10000 M':
                speed = '10G'
            elif speed == '1000M':
                speed = '10G'
            data = dict(hostip=hostip,
                        interface=i['interface'],
                        status=i['protocolstatus'],
                        speed=speed,
                        duplex=i['duplex'],
                        description=i['description'])
            layer2datas.append(data)
            if i['ipaddr']:
                for _ip in i['ipaddr']:
                    _ipnet = IPaddr.IPv4Network(_ip)
                    data = dict(
                        hostip=hostip,
                        interface=i['interface'],
                        line_status=i['protocolstatus'],
                        protocol_status=i['protocolstatus'],
                        ipaddress=str(_ipnet.ip),
                        ipmask=str(_ipnet.netmask),
                        ip_type='',
                        mtu=i['mtu'], location=[])
                    layer3datas.append(data)
        if layer2datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer2datas,
                tablename='layer2interface')
        if layer3datas:
            AutomationMongo.insert_table(
                db='Automation',
                hostip=hostip,
                datas=layer3datas,
                tablename='layer3interface')
        return

    # 山石防火墙安全策略写入mongo
    @staticmethod
    def hillstone_sec_policy(host, datas, method='bulk'):
        """
        action: 'deny',
        dst_addr: {
            addr: 'Any'
        },
        id: '4',
        name: '封锁IP策略',
        service: 'Any',
        src_addr: {
            addr: '封锁IP'
        },
        hostip: '172.16.75.1'
        :param host:
        :param datas:
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='sec_policy')
        address_mongo = MongoOps(db='Automation', coll='hillstone_address')
        # 地址数据映射集
        address_map = dict()
        address_res = address_mongo.find(
            query_dict=dict(
                hostip=host), fileds={
                "_id": 0})
        if address_res:
            for _addr in address_res:
                if _addr['name'] in address_map.keys():
                    address_map[_addr['name']].append(_addr)
                else:
                    address_map[_addr['name']] = [_addr]
        if method == 'bulk':
            my_mongo.delete_many(query=dict(hostip=host))
        results = []
        for i in datas:
            # print(i)
            tmp = dict()
            tmp['src_ip_split'] = []
            tmp['dst_ip_split'] = []
            service = []
            src_addr = []
            dst_addr = []
            # if i.get('service'):
            #     if isinstance(i['service'], list):
            #         service = [x['service'] for x in i['service']]
            #     else:
            #         service.append(i['service']['service'])
            log = ''
            if i.get('logs'):
                if isinstance(i['logs'], dict):
                    log = i['logs']['log']
                elif isinstance(i['logs'], list):
                    log = ','.join([x['log'] for x in i['logs']])
            # 地址对象
            # src_addr = ''
            if i.get('src_addr'):
                # tmp_src_addr = []
                if isinstance(i['src_addr'], dict):
                    # tmp_src_addr = [i['src_addr'][x] for x in i['src_addr'].keys()]
                    # src_addr = ','.join(tmp_src_addr)
                    if 'object' in i['src_addr'].keys():
                        # src_addr = i['src_addr']['object']
                        # _addr_res = address_mongo.find(query_dict=dict(address=src_addr, hostip=host), fileds={'_id': 0})
                        src_addr.append(dict(object=i['src_addr']['object']))
                        if i['src_addr']['object'] in address_map.keys():
                            _addr_res = address_map[i['src_addr']['object']]
                            for _sub_src_ip in _addr_res:
                                if 'ip' in _sub_src_ip.keys():
                                    for _t_ip in _sub_src_ip['ip']:
                                        tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(_t_ip['ip']).first,
                                                                        end=netaddr.IPNetwork(_t_ip['ip']).last))
                                if 'range' in _sub_src_ip.keys():
                                    for _t_ip in _sub_src_ip['range']:
                                        tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(_t_ip['start']).value,
                                                                        end=netaddr.IPAddress(_t_ip['end']).value))
                    elif 'ip' in i['src_addr'].keys():
                        _ip = netaddr.IPNetwork(i['src_addr']['ip'])
                        src_addr.append(dict(ip=i['src_addr']['ip']))
                        tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(_ip).first,
                                                        end=netaddr.IPNetwork(_ip).last))
                    elif 'range' in i['src_addr'].keys():
                        start_ip = i['src_addr']['range'].split()[0]
                        end_ip = i['src_addr']['range'].split()[1]
                        src_addr.append(dict(range=start_ip + '-' + end_ip))
                        tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(start_ip).first,
                                                        end=netaddr.IPNetwork(end_ip).last))

                elif isinstance(i['src_addr'], list):
                    # src_addr = ','.join([x['addr'] for x in i['src_addr']])
                    for _src_tmp in i['src_addr']:
                        # tmp_src_addr += [_src_tmp[x] for x in _src_tmp.keys()]
                        if 'object' in _src_tmp.keys():
                            src_addr.append(dict(object=_src_tmp['object']))
                            if _src_tmp['object'] in address_map.keys():
                                _addr_res = address_map[_src_tmp['object']]
                                for _sub_src_ip in _addr_res:
                                    if 'ip' in _sub_src_ip.keys():
                                        for _t_ip in _sub_src_ip['ip']:
                                            tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(_t_ip['ip']).first,
                                                                            end=netaddr.IPNetwork(_t_ip['ip']).last))
                                    if 'range' in _sub_src_ip.keys():
                                        for _t_ip in _sub_src_ip['range']:
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPAddress(_t_ip['start']).value,
                                                     end=netaddr.IPAddress(_t_ip['end']).value))
                        elif 'ip' in _src_tmp.keys():
                            _ip = netaddr.IPNetwork(_src_tmp['ip'])
                            src_addr.append(dict(ip=_src_tmp['ip']))
                            tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(_ip).first,
                                                            end=netaddr.IPNetwork(_ip).last))
                        elif 'range' in _src_tmp.keys():
                            start_ip = _src_tmp['range'].split()[0]
                            end_ip = _src_tmp['range'].split()[1]
                            src_addr.append(
                                dict(range=start_ip + '-' + end_ip))
                            tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(start_ip).first,
                                                            end=netaddr.IPNetwork(end_ip).last))
                    # src_addr = ','.join(tmp_src_addr)
            # dst_addr = ''
            if i.get('dst_addr'):
                # tmp_dst_addr = []
                if isinstance(i['dst_addr'], dict):
                    # tmp_dst_addr = [i['dst_addr'][x] for x in i['dst_addr'].keys()]
                    # dst_addr = ','.join(tmp_dst_addr)
                    if 'object' in i['dst_addr'].keys():
                        dst_addr.append(dict(object=i['dst_addr']['object']))
                        if i['dst_addr']['object'] in address_map.keys():
                            _addr_res = address_map[i['dst_addr']['object']]
                            for _sub_dst_ip in _addr_res:
                                if 'ip' in _sub_dst_ip.keys():
                                    for _t_ip in _sub_dst_ip['ip']:
                                        tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(_t_ip['ip']).first,
                                                                        end=netaddr.IPNetwork(_t_ip['ip']).last))
                                if 'range' in _sub_dst_ip.keys():
                                    for _t_ip in _sub_dst_ip['range']:
                                        tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(_t_ip['start']).value,
                                                                        end=netaddr.IPAddress(_t_ip['end']).value))
                    elif 'ip' in i['dst_addr'].keys():
                        dst_addr.append(dict(ip=i['dst_addr']['ip']))
                        _ip = netaddr.IPNetwork(i['dst_addr']['ip'])
                        tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(_ip).first,
                                                        end=netaddr.IPNetwork(_ip).last))
                    elif 'range' in i['dst_addr'].keys():
                        start_ip = i['dst_addr']['range'].split()[0]
                        end_ip = i['dst_addr']['range'].split()[1]
                        dst_addr.append(dict(range=start_ip + '-' + end_ip))
                        tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(start_ip).first,
                                                        end=netaddr.IPNetwork(end_ip).last))
                elif isinstance(i['dst_addr'], list):
                    # dst_addr = ','.join([x['addr'] for x in i['dst_addr']])
                    for _dst_tmp in i['dst_addr']:
                        # tmp_dst_addr += [_dst_tmp[x] for x in _dst_tmp.keys()]
                        if 'object' in _dst_tmp.keys():
                            dst_addr.append(dict(object=_dst_tmp['object']))
                            if _dst_tmp['object'] in address_map.keys():
                                _addr_res = address_map[_dst_tmp['object']]
                                for _sub_src_ip in _addr_res:
                                    if 'ip' in _sub_src_ip.keys():
                                        for _t_ip in _sub_src_ip['ip']:
                                            tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(_t_ip['ip']).first,
                                                                            end=netaddr.IPNetwork(_t_ip['ip']).last))
                                    if 'range' in _sub_src_ip.keys():
                                        for _t_ip in _sub_src_ip['range']:
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPAddress(_t_ip['start']).value,
                                                     end=netaddr.IPAddress(_t_ip['end']).value))
                        elif 'ip' in _dst_tmp.keys():
                            dst_addr.append(dict(ip=_dst_tmp['ip']))
                            _ip = netaddr.IPNetwork(_dst_tmp['ip'])
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(_ip).first,
                                                            end=netaddr.IPNetwork(_ip).last))
                        elif 'range' in _dst_tmp.keys():
                            start_ip = _dst_tmp['range'].split()[0]
                            end_ip = _dst_tmp['range'].split()[1]
                            dst_addr.append(
                                dict(range=start_ip + '-' + end_ip))
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(start_ip).first,
                                                            end=netaddr.IPNetwork(end_ip).last))
                    # dst_addr = ','.join(tmp_dst_addr)
            enable = True
            if i.get('disable'):
                enable = False
            tmp['vendor'] = 'hillstone'
            tmp['hostip'] = i['hostip']
            tmp['id'] = i.get('id')
            tmp['name'] = i.get('name')
            tmp['action'] = i.get('action')
            tmp['enable'] = enable
            tmp['src_zone'] = i.get('src-zone') if i.get('src-zone') else 'Any'
            tmp['dst_zone'] = i.get('dst-zone') if i.get('dst-zone') else 'Any'
            tmp['service'] = i.get('service')
            tmp['src_addr'] = i.get('src_addr')  # 地址组
            tmp['dst_addr'] = i.get('dst_addr')  # 地址组
            tmp['log'] = log
            tmp['description'] = i.get('description')
            results.append(tmp)
        my_mongo.insert_many(results)
        return

    @staticmethod  # 接口比较耗时
    def hillstone_configfile(path, hostip):
        address_mongo = MongoOps(db='Automation', coll='hillstone_address')
        service_mongo = MongoOps(db='Automation', coll='hillstone_service')
        servgroup_mongo = MongoOps(db='Automation', coll='hillstone_servgroup')
        slb_server_mongo = MongoOps(
            db='Automation', coll='hillstone_slb_server')
        aggr_group_mongo = MongoOps(db='Automation', coll='AggreTable')
        service_predefined_mongo = MongoOps(
            db='Automation', coll='hillstone_service_predefined')
        # 安全策略1
        try:
            sec_policy_res = HillstoneFsm.sec_policy(path=path)
            sec_policy_result = []
            if sec_policy_res:
                for i in sec_policy_res:
                    i['hostip'] = hostip
                    sec_policy_result.append(i)
            if sec_policy_result:
                try:
                    StandardFSMAnalysis.hillstone_sec_policy(
                        hostip, sec_policy_result)
                except Exception as e:
                    pass
                    # #send_msg_netops
                    #     "山石防火墙安全策略入库失败,设备:{},错误:{}".format(
                    #         hostip, str(e)))
        except Exception as e:
            print('山石配置文件安全策略解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='sec_policy',
                version=str(e))
        # 地址组
        try:
            address_res = HillstoneFsm.address_group(path=path)
            address_result = []
            for i in address_res:
                i['hostip'] = hostip
                address_result.append(i)
            if address_result:
                address_mongo.delete_many(query=dict(hostip=hostip))
                address_mongo.insert_many(address_result)
        except Exception as e:
            print('山石配置文件地址组解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='address',
                version=str(e))
        # 服务
        try:
            service_res = HillstoneFsm.service_proc(path=path)
            service_result = []
            for i in service_res:
                i['hostip'] = hostip
                service_result.append(i)
            if service_result:
                service_mongo.delete_many(query=dict(hostip=hostip))
                service_mongo.insert_many(service_result)
        except Exception as e:
            print('山石配置文件服务解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='service',
                version=str(e))
        # 服务组
        try:
            servgroup_res = HillstoneFsm.servgroup_proc(path=path)
            servgroup_result = []
            for i in servgroup_res:
                i['hostip'] = hostip
                # if i['Service'] == 'FTP':
                #     i['Service'] = '21'
                # elif i['Service'] == 'HTTP':
                #     i['Service'] = '80'
                # elif i['Service'] == 'HTTPS':
                #     i['Service'] = '443'
                servgroup_result.append(i)
            if servgroup_result:
                servgroup_mongo.delete_many(query=dict(hostip=hostip))
                servgroup_mongo.insert_many(servgroup_result)
        except Exception as e:
            print('山石配置文件服务组解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='servgroup',
                version=str(e))
        # slb
        try:
            slb_server_res = HillstoneFsm.slb_server_proc(path=path)
            # 如果没有需要清空
            if slb_server_res:
                slb_server_result = []
                for i in slb_server_res:
                    i['hostip'] = hostip
                    slb_server_result.append(i)
                if slb_server_result:
                    slb_server_mongo.delete_many(query=dict(hostip=hostip))
                    slb_server_mongo.insert_many(slb_server_result)
            else:
                slb_server_mongo.delete_many(query=dict(hostip=hostip))
        except Exception as e:
            print('山石配置文件SLB解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='slb_server',
                version=str(e))
        # 聚合组
        try:
            aggr_group_res = HillstoneFsm.aggr_group(path=path)
            aggr_group_result = dict()
            aggre_datas = []
            if aggr_group_res:
                aggregate_group = list(
                    set([x['aggregate'] for x in aggr_group_res]))
                if aggregate_group:
                    for aggr_key in aggregate_group:
                        if aggr_key:
                            for member in aggr_group_res:
                                if member['aggregate'] == aggr_key:
                                    if aggr_key not in aggr_group_result.keys():
                                        aggr_group_result[aggr_key] = [
                                            {member['INTF']: member['status']}]
                                    else:
                                        aggr_group_result[aggr_key].append(
                                            {member['INTF']: member['status']})
            for k, v in aggr_group_result.items():
                # print(k, v)
                # {'aggregate2': [{'xethernet4/0': ''}, {'xethernet4/1': ''}],
                #  'aggregate1': [{'ethernet0/3': ''}, {'ethernet0/5': ''}]}
                member_list = []
                member_status = []
                for member in v:
                    for mem_k, mem_v in member.items():
                        member_list.append(mem_k)
                        tmp_status = 'Up' if mem_v != 'shutdown' else 'shutdown'
                        member_status.append(tmp_status)
                tmp = dict(hostip=hostip,
                           aggregroup=k,
                           memberports=member_list,
                           status=member_status,
                           mode='')
                aggre_datas.append(tmp)
            if aggre_datas:
                aggr_group_mongo.delete_many(query=dict(hostip=hostip))
                aggr_group_mongo.insert_many(aggre_datas)
        except Exception as e:
            print('山石配置文件聚合组解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='aggr_group',
                version=str(e))
        # DNAT表项拼接
        try:
            dnat_res = HillstoneFsm.dnat_proc(path=path)
            # if not dnat_res:
            #     #send_msg_netops"山石防火墙:{} DNAT表项解析为空".format(hostip))
            dnat_result = []
            dnat_data = []
            # print("DNAT总数", len(dnat_res))
            # 获取系统预定义服务集合
            service_predefined_name = []
            service_predefined_res = service_predefined_mongo.find(query_dict=dict(hostip=hostip),
                                                                   fileds={"_id": 0})
            # 系统预定义服务映射集
            service_predefined_map = dict()
            if service_predefined_res:
                for _service_predefined in service_predefined_res:
                    if _service_predefined['name'] in service_predefined_map.keys():
                        service_predefined_map[_service_predefined['name']].append(
                            _service_predefined)
                    else:
                        service_predefined_map[_service_predefined['name']] = [
                            _service_predefined]
            # 地址数据映射集
            address_map = dict()
            address_res = address_mongo.find(
                query_dict=dict(hostip=hostip), fileds={"_id": 0})
            if address_res:
                for _addr in address_res:
                    if _addr['name'] in address_map.keys():
                        address_map[_addr['name']].append(_addr)
                    else:
                        address_map[_addr['name']] = [_addr]
            # 服务组数据映射集 假设服务组不存在重名，直接map映射进字典
            servgroup_map = dict()
            servgroup_res = servgroup_mongo.find(
                query_dict=dict(hostip=hostip), fileds={"_id": 0})
            if servgroup_res:
                for _sergroup in servgroup_res:
                    servgroup_map[_sergroup['servgroup']
                    ] = _sergroup['services']
            # 服务对象数据映射集 假设服务不存在重名，直接map映射进字典
            service_map = dict()
            service_res = service_mongo.find(
                query_dict=dict(hostip=hostip), fileds={"_id": 0})
            if service_res:
                for _service in service_res:
                    service_map[_service['name']] = _service['items']
            # SLB对象映射集
            slb_map = dict()
            slb_res = slb_server_mongo.find(
                query_dict=dict(
                    hostip=hostip), fileds={
                    "_id": 0})
            if slb_res:
                for _slb in slb_res:
                    if _slb['POOLNAME'] in slb_map.keys():
                        slb_map[_slb['POOLNAME']].append(_slb)
                    else:
                        slb_map[_slb['POOLNAME']] = [_slb]
            for i in dnat_res:
                if i['RULESTATE'] == 'disable':
                    continue
                # print(i)
                i['hostip'] = hostip
                # 变量初始化定义 start
                local_ip = []
                global_ip = []
                global_ip_range = []
                global_port = []
                local_port = []
                # 变量初始化定义 end
                if i['TO_IP'] in address_map.keys():
                    try:
                        global_ip = [dict(start=i['TO_IP'],
                                          end=i['TO_IP'],
                                          start_int=netaddr.IPAddress(
                                              i['TO_IP']).value,
                                          end_int=netaddr.IPAddress(
                                              i['TO_IP']).value,
                                          result=i['TO_IP'])]
                    except Exception as e:
                        pass
                        # send_msg_netops
                        # "设备:{} 山石防火墙DNAT解析 TO_IP 字段不是纯IP：{}".format(
                        #     i['TO_IP'], hostip))
                        global_ip = [
                            dict(
                                start=i['TO_IP'],
                                end=i['TO_IP'],
                                result=i['TO_IP'])]
                elif i['TO'] in address_map.keys():
                    _global_ip_query = address_map[i['TO']]
                    # print('_global_ip', _global_ip)
                    # _global_ip = _global_ip[0]
                    _global_ip_list = [x for x in _global_ip_query if x.get('ip') or x.get('range')]
                    # global_ip_list = [x['ip'] for x in _global_ip['ip'] if _global_ip.get('ip')]
                    for _global_ip in _global_ip_list:
                        if _global_ip.get('ip'):
                            global_ip += list([dict(start=x['ip'],
                                                    end=x['ip'],
                                                    start_int=netaddr.IPNetwork(
                                                        x['ip']).first,
                                                    end_int=netaddr.IPNetwork(
                                                        x['ip']).last,
                                                    result=x['ip']) for x in _global_ip['ip']])
                        if _global_ip.get('range'):
                            global_ip_range += list([dict(start=x['start'],
                                                          end=x['end'],
                                                          start_int=netaddr.IPAddress(
                                                              x['start']).value,
                                                          end_int=netaddr.IPAddress(
                                                              x['end']).value,
                                                          result=x['start'] +
                                                                 '-' + x['end']
                                                          ) for x in _global_ip['range']])
                        global_ip = global_ip + global_ip_range
                elif i['TO_IP']:
                    try:
                        if i['TO_IP'].find('/') != -1:
                            global_ip = [dict(start=i['TO_IP'],
                                              end=i['TO_IP'],
                                              start_int=netaddr.IPNetwork(
                                                  i['TO_IP']).first,
                                              end_int=netaddr.IPNetwork(
                                                  i['TO_IP']).last,
                                              result=i['TO_IP'])]
                        else:
                            global_ip = [dict(start=i['TO_IP'],
                                              end=i['TO_IP'],
                                              start_int=netaddr.IPAddress(
                                                  i['TO_IP']).value,
                                              end_int=netaddr.IPAddress(
                                                  i['TO_IP']).value,
                                              result=i['TO_IP'])]
                    except Exception as e:
                        global_ip = [
                            dict(
                                start=i['TO_IP'],
                                end=i['TO_IP'],
                                result=i['TO_IP'])]
                else:
                    try:
                        if i['TO'].find('/') != -1:
                            global_ip = [dict(start=i['TO'],
                                              end=i['TO'],
                                              start_int=netaddr.IPNetwork(
                                                  i['TO']).first,
                                              end_int=netaddr.IPNetwork(
                                                  i['TO']).last,
                                              result=i['TO'])]
                        else:
                            global_ip = [dict(start=i['TO'],
                                              end=i['TO'],
                                              start_int=netaddr.IPAddress(
                                                  i['TO']).value,
                                              end_int=netaddr.IPAddress(
                                                  i['TO']).value,
                                              result=i['TO'])]
                    except Exception as e:
                        global_ip = [
                            dict(
                                start=i['TO'],
                                end=i['TO'],
                                result=i['TO'])]
                # 判断是否系统预定义服务
                if i['SERVICE'] in service_predefined_map.keys():
                    _global_port = service_predefined_map[i['SERVICE']]
                    for _sub_global_port in _global_port:
                        try:
                            global_port.append(dict(start=int(_sub_global_port['dstport']),
                                                    end=int(
                                                        _sub_global_port['dstport']),
                                                    protocol=_sub_global_port['protocol'],
                                                    result=str(
                                                        _sub_global_port['dstport'])
                                                    ))
                        except BaseException:
                            global_port.append(dict(start=_sub_global_port['dstport'],
                                                    end=_sub_global_port['dstport'],
                                                    protocol=_sub_global_port['protocol'],
                                                    result=str(
                                                        _sub_global_port['dstport'])
                                                    ))
                # 判断是否服务组
                elif i['SERVICE'] in servgroup_map.keys():
                    _servgroup = servgroup_map[i['SERVICE']]
                    # _portlist = []
                    for _ser_port in _servgroup:
                        # _tmp = service_mongo.find(
                        #     query_dict=dict(hostip=hostip, service=str(_ser_port['Service'])),
                        #     fileds={"_id": 0, 'Port': 1, 'Protocol': 1})
                        if _ser_port['service'] in service_predefined_map.keys():
                            _tmp = service_predefined_map[_ser_port['service']]
                            for _sub_global_port in _tmp:
                                try:
                                    global_port.append(dict(start=int(_sub_global_port['dstport']),
                                                            end=int(
                                                                _sub_global_port['dstport']),
                                                            protocol=_sub_global_port['protocol'],
                                                            result=str(_sub_global_port['dstport'])))
                                except BaseException:
                                    global_port.append(dict(start=_sub_global_port['dstport'],
                                                            end=_sub_global_port['dstport'],
                                                            protocol=_sub_global_port['protocol'],
                                                            result=str(
                                                                _sub_global_port['dstport'])
                                                            ))
                        elif _ser_port['service'] in service_map.keys():
                            _tmp = service_map[_ser_port['service']]
                            for _tmp_port in _tmp:
                                if all(k in _tmp_port for k in (
                                        "dst-port-min", "dst-port-max")):
                                    # _portlist.append(_tmp_port['Port'])
                                    # _global_protocol.append(_tmp_port['protocol'])
                                    global_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                            end=int(
                                                                _tmp_port['dst-port-max']),
                                                            protocol=_tmp_port['protocol'],
                                                            result=str(_tmp_port['dst-port-min']) + '-' + str(
                                                                _tmp_port['dst-port-max'])
                                                            ))
                                elif 'dst-port-min' in _tmp_port.keys():
                                    # _portlist.append(_tmp_port['Port'])
                                    # _global_protocol.append(_tmp_port['protocol'])
                                    global_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                            end=int(
                                                                _tmp_port['dst-port-min']),
                                                            protocol=_tmp_port['protocol'],
                                                            result=str(
                                                                _tmp_port['dst-port-min'])
                                                            ))
                        else:
                            global_port.append(dict(start=_ser_port['service'],
                                                    end=_ser_port['service'],
                                                    protocol=_ser_port['service'],
                                                    result=_ser_port['service']
                                                    ))
                            # _portlist.append(str(_ser_port['service']))
                            # _global_protocol.append(_ser_port['service'])
                    # 统一转str格式
                    # global_port = list([str(x) for x in _portlist])
                    # _global_protocol = list([str(x) for x in _global_protocol])
                    # global_port = ','.join(global_port)
                    # global_protocol = ','.join(_global_protocol)
                # 判断是否服务
                elif i['SERVICE'] in service_map.keys():
                    # _global_port = service_mongo.find(query_dict=dict(hostip=hostip, service=str(i['SERVICE'])),
                    # fileds={"_id": 0, 'Port': 1, 'Protocol': 1})
                    _tmp = service_map[i['SERVICE']]
                    for _tmp_port in _tmp:
                        if all(k in _tmp_port for k in (
                                "dst-port-min", "dst-port-max")):
                            # _portlist.append(_tmp_port['Port'])
                            # _global_protocol.append(_tmp_port['protocol'])
                            global_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                    end=int(
                                                        _tmp_port['dst-port-max']),
                                                    protocol=_tmp_port['protocol'],
                                                    result=str(_tmp_port['dst-port-min']) + '-' + str(
                                                        _tmp_port['dst-port-max'])))
                        elif 'dst-port-min' in _tmp_port.keys():
                            # _portlist.append(_tmp_port['Port'])
                            # _global_protocol.append(_tmp_port['protocol'])
                            global_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                    end=int(
                                                        _tmp_port['dst-port-min']),
                                                    protocol=_tmp_port['protocol'],
                                                    result=str(
                                                        _tmp_port['dst-port-min'])
                                                    ))
                        # _global_port = service_map[i['SERVICE']]
                        # global_port = list([str(x['Port']) for x in _global_port])
                        # _global_protocol = list(set([str(x['Protocol']) for x in _global_port]))
                        # _global_protocol = list([str(x['Protocol']) for x in _global_port])
                        # global_port = ','.join(global_port)
                        # global_protocol = ','.join(_global_protocol)
                else:
                    global_port.append(dict(start=i['SERVICE'],
                                            end=i['SERVICE'],
                                            protocol=i['SERVICE'],
                                            result=i['SERVICE']))
                if i['TRANSTO_IP'] and i['TRANSTO_IP'] != '':
                    try:
                        local_ip = [dict(start=i['TRANSTO_IP'],
                                         end=i['TRANSTO_IP'],
                                         start_int=netaddr.IPAddress(
                                             i['TRANSTO_IP']).value,
                                         end_int=netaddr.IPAddress(
                                             i['TRANSTO_IP']).value,
                                         result=i['TRANSTO_IP'])]
                    except Exception as e:
                        local_ip = [
                            dict(
                                start=i['TRANSTO_IP'],
                                end=i['TRANSTO_IP'],
                                result=i['TRANSTO_IP'])]
                elif i['TRANSTO']:
                    if i['TRANSTO'] in address_map.keys():
                        _local_ip = address_map[i['TRANSTO']]
                        _local_ip = _local_ip[0]
                        if _local_ip.get('ip'):
                            local_ip = list([dict(start=x['ip'],
                                                  end=x['ip'],
                                                  start_int=netaddr.IPNetwork(
                                                      x['ip']).first,
                                                  end_int=netaddr.IPNetwork(
                                                      x['ip']).last,
                                                  result=x['ip']
                                                  ) for x in _local_ip['ip']])
                        local_ip_range = []
                        if _local_ip.get('range'):
                            local_ip_range = list([dict(start=x['start'],
                                                        end=x['end'],
                                                        start_int=netaddr.IPAddress(
                                                            x['start']).value,
                                                        end_int=netaddr.IPAddress(
                                                            x['end']).value,
                                                        result=x['start'] +
                                                               '-' + x['end']
                                                        ) for x in _local_ip['range']])
                        local_ip = local_ip + local_ip_range
                    else:
                        try:
                            local_ip = [dict(start=i['TRANSTO'],
                                             end=i['TRANSTO'],
                                             start_int=netaddr.IPAddress(
                                                 i['TRANSTO']).value,
                                             end_int=netaddr.IPAddress(
                                                 i['TRANSTO']).value,
                                             result=i['TRANSTO']
                                             )]
                        except Exception as e:
                            local_ip = [
                                dict(
                                    start=i['TRANSTO'],
                                    end=i['TRANSTO'],
                                    result=i['TRANSTO'])]
                elif i['POOLNAME']:
                    # PODNAME
                    if i['POOLNAME'] in slb_map.keys():
                        _res = slb_map[i['POOLNAME']]
                        for _ip in _res:
                            if _ip['ADDRTYPE'] == 'ip':
                                local_ip.append(dict(start=_ip['SERVERIP'],
                                                     end=_ip['SERVERIP'],
                                                     start_int=netaddr.IPNetwork(
                                                         _ip['SERVERIP']).first,
                                                     end_int=netaddr.IPNetwork(
                                                         _ip['SERVERIP']).last,
                                                     result=_ip['SERVERIP']))
                            if _ip['ADDRTYPE'] == 'ip-range':
                                tmp = _ip['SERVERIP'].split()
                                local_ip.append(dict(start=tmp[0],
                                                     end=tmp[1],
                                                     start_int=netaddr.IPAddress(
                                                         tmp[0]).value,
                                                     end_int=netaddr.IPAddress(
                                                         tmp[1]).value,
                                                     result=tmp[0] + '-' + tmp[1]))
                else:
                    try:
                        local_ip = [dict(start=i['POOLNAME'],
                                         end=i['POOLNAME'],
                                         start_int=netaddr.IPAddress(
                                             i['POOLNAME']).value,
                                         end_int=netaddr.IPAddress(
                                             i['POOLNAME']).value,
                                         result=i['POOLNAME'])]
                    except Exception as e:
                        local_ip = [
                            dict(
                                start=i['POOLNAME'],
                                end=i['POOLNAME'],
                                result=i['POOLNAME'])]
                port_regex = re.compile('^\\d+$')
                if i['PORT'] in service_map.keys():
                    _tmp = service_map[i['PORT']]
                    for _tmp_port in _tmp:
                        if all(k in _tmp_port for k in (
                                "dst-port-min", "dst-port-max")):
                            local_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                   end=int(
                                                       _tmp_port['dst-port-max']),
                                                   protocol=_tmp_port['protocol'],
                                                   result=str(_tmp_port['dst-port-min']) + '-' + str(
                                                       _tmp_port['dst-port-max'])))
                        elif 'dst-port-min' in _tmp_port.keys():
                            local_port.append(dict(start=int(_tmp_port['dst-port-min']),
                                                   end=int(
                                                       _tmp_port['dst-port-min']),
                                                   protocol=_tmp_port['protocol'],
                                                   result=str(_tmp_port['dst-port-min'])))
                    else:
                        local_port.append(dict(start=i['PORT'],
                                               end=i['PORT'],
                                               protocol=i['PORT'],
                                               result=i['PORT']))
                elif port_regex.search(i['PORT']):
                    local_port = [dict(start=int(i['PORT']),
                                       end=int(i['PORT']),
                                       protocol=global_port[0]['protocol'],
                                       result=i['PORT']
                                       )]
                else:
                    local_port = global_port
                dnat_result.append(i)  # 存储原始数据信息
                tmp = dict(
                    rule_id=i['ID'],
                    hostip=hostip,
                    global_ip=global_ip,
                    global_port=global_port,
                    local_ip=local_ip,
                    local_port=local_port,
                )
                dnat_data.append(tmp)  # 存储格式化后的数据信息
            if dnat_data:
                # AutomationMongo.insert_table('Automation', hostip, dnat_data, 'DNAT')
                AutomationMongo.dnat_ops(hostip, dnat_data)
            if dnat_result:
                AutomationMongo.insert_table(
                    'Automation', hostip, dnat_result, 'hillstone_dnat')
        except Exception as e:
            print(traceback.print_exc())
            print('山石配置文件DNAT拼接解析异常', str(e))
            AutomationMongo.failed_log(
                ip=hostip,
                fsm_flag='hillstone',
                cmd='dnat',
                version=str(
                    traceback.print_exc()))

    @staticmethod
    def hillstone_service_predefined(res, hostip):
        service_predefined_res = []
        for i in res:
            i['hostip'] = hostip
            if re.match("^\\d+-\\d+", i['dstport']):
                """
                参考10.254.12.251
                配置文件摘要如下：
                AFS                               TCP         7002-7009                 -        -
                需要识别出端口范围并生成range遍历添加
                {'name': 'AFS', 'protocol': 'TCP', 'dstport': ['7002', '7003', '7004', '7005', '7006', '7007', '7008', '7009'], 'srcport': '-', 'timeout': '-'}
                """
                dstport_start = int(i['dstport'].split('-')[0])
                dstport_end = int(i['dstport'].split('-')[1])
                service_list = [str(item) for item in
                                range(dstport_start, dstport_end + 1)]
                for _tmp_service in service_list:
                    service_predefined_res.append(dict(
                        name=i['name'],
                        protocol=i['protocol'].lower(),
                        dstport=_tmp_service,
                        srcport=i['srcport'],
                        timeout=i['timeout'],
                        dstport_start=dstport_start,
                        dstport_end=dstport_end,
                        hostip=hostip
                    ))
            else:
                service_predefined_res.append(i)
        if service_predefined_res:
            service_predefined_mongo = MongoOps(
                db='Automation', coll='hillstone_service_predefined')
            service_predefined_mongo.delete_many(query=dict(hostip=hostip))
            service_predefined_mongo.insert_many(service_predefined_res)
        return

    @staticmethod
    def h3cv5_dev_man(res, hostip):
        # 设备信息处理
        if isinstance(res, dict):
            """
            单台：
            {'chassis_id': '', 'slot_type': 'Slot', 'slot_id': '1', 'device_name': 'S5120-48P-EI',
             'device_serial_number': '210235A0BKH145000294', 'manufacturing_date': '2014-05-19',
              'vendor_name': 'H3C', 'mac_address': '70F9-6D46-3E40'}
            """
            serial_num = res['device_serial_number']
            slot = res['slot_id']
            NetworkDevice.objects.filter(
                manage_ip=hostip,
                serial_num=serial_num).update(
                slot=int(slot))
        elif isinstance(res, list):
            """
            堆叠  S12508以4.250为例：
            [{'chassis_id': '1', 'slot_type': 'Chassis', 'slot_id': 'self', 'device_name': 'LST2Z12508AC', 'device_serial_number': '210235A0E6X145000006', 'manufacturing_date': '2014-05-15', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '0', 'device_name': 'LST1MRPNC1', 'device_serial_number': '210231A968H145000086', 'manufacturing_date': '2014-05-18', 'vendor_name': 'H3C', 'mac_address': '70F9-6D47-E600'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '1', 'device_name': 'LST1MRPNC1', 'device_serial_number': '210231A968H145000059', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': '70F9-6D47-B000'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '2', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH144000007', 'manufacturing_date': '2014-04-17', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '3', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH12A000033', 'manufacturing_date': '2015-01-17', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '4', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH144000004', 'manufacturing_date': '2014-05-20', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '5', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH168000006', 'manufacturing_date': '2016-08-13', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '10', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000072', 'manufacturing_date': '2014-05-04', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '11', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000050', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '12', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000037', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '13', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000068', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '14', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000004', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '15', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000019', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '16', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000013', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Slot', 'slot_id': '17', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000040', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '1', 'slot_type': 'Power', 'slot_id': '1', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000854', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '1', 'slot_type': 'Power', 'slot_id': '2', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000985', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '1', 'slot_type': 'Power', 'slot_id': '3', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000973', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '1', 'slot_type': 'Fan', 'slot_id': '1', 'device_name': 'LSTM2FANH', 'device_serial_number': '210231A98GN145000036', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '1', 'slot_type': 'Fan', 'slot_id': '2', 'device_name': 'LSTM2FANH', 'device_serial_number': '210231A98GN145000019', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Chassis', 'slot_id': 'self', 'device_name': 'LST2Z12508AC', 'device_serial_number': '210235A0E6X145000004', 'manufacturing_date': '2014-05-09', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '0', 'device_name': 'LST1MRPNC1', 'device_serial_number': '210231A968H145000067', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': '70F9-6D47-BE00'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '1', 'device_name': 'LST1MRPNC1', 'device_serial_number': '210231A968H145000075', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': '70F9-6D47-D000'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '2', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH144000002', 'manufacturing_date': '2014-05-31', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '3', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH146000019', 'manufacturing_date': '2014-06-07', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '4', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH125000003', 'manufacturing_date': '2015-11-13', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '5', 'device_name': 'LST2XP32REB1', 'device_serial_number': '210231A0QCH168000001', 'manufacturing_date': '2016-08-13', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '10', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000006', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '11', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000030', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '12', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000041', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '13', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85N0108000042', 'manufacturing_date': '2016-07-11', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '14', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000071', 'manufacturing_date': '2014-05-03', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '15', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000039', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '16', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85NH144000021', 'manufacturing_date': '2014-04-29', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Slot', 'slot_id': '17', 'device_name': 'LST1SF08B1', 'device_serial_number': '210231A85N010A000187', 'manufacturing_date': '2016-07-18', 'vendor_name': 'H3C', 'mac_address': 'NONE'}
            {'chassis_id': '2', 'slot_type': 'Power', 'slot_id': '1', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000818', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Power', 'slot_id': '2', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000906', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Power', 'slot_id': '3', 'device_name': 'LSTM2PSRA', 'device_serial_number': '210231A0HHH145000810', 'manufacturing_date': '2014-05-23', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Fan', 'slot_id': '1', 'device_name': 'LSTM2FANH', 'device_serial_number': '210231A98GN145000033', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': ''}
            {'chassis_id': '2', 'slot_type': 'Fan', 'slot_id': '2', 'device_name': 'LSTM2FANH', 'device_serial_number': '210231A98GN145000008', 'manufacturing_date': '2014-05-12', 'vendor_name': 'H3C', 'mac_address': ''}]

            """
            update_flag = 0  # 先匹配框式，再匹配盒式
            for i in res:
                if i['slot_type'] == 'Chassis':
                    update_flag = 1
                    serial_num = i['device_serial_number']
                    chassis = int(i['chassis_id'])
                    # slot = int(i['slot_id'])
                    slot = 1
                    NetworkDevice.objects.filter(
                        serial_num=serial_num).update(
                        slot=slot, chassis=chassis)
            if update_flag == 0:
                for i in res:
                    if i['slot_type'] == 'Slot':
                        # update_flag = 1
                        serial_num = i['device_serial_number']
                        slot = int(i['slot_id'])
                        NetworkDevice.objects.filter(
                            serial_num=serial_num).update(
                            slot=slot)

    @staticmethod
    def h3cv5_irf(res, hostip):
        # irf信息处理
        if isinstance(res, dict):
            """
            10.254.7.54为例  独立设备
            {'chassisid': '', 'memberid': '1', 'role': 'Master', 'priority': '1', 'mac': '0cda-41c2-8d5b'}

            """
            if res['role'] == 'Master' and res['memberid'] != '0':
                NetworkDevice.objects.filter(
                    manage_ip=hostip, slot=int(
                        res['memberid'])).update(
                    ha_status=0)
            elif res['role'] == 'Slave' and res['memberid'] != '0':
                NetworkDevice.objects.filter(
                    manage_ip=hostip, slot=int(
                        res['memberid'])).update(
                    ha_status=0)

        elif isinstance(res, list):
            """
            堆叠，以4.250为例 
            {'chassisid': '1', 'memberid': '0', 'role': 'Master', 'priority': '32', 'mac': ''}
            {'chassisid': '1', 'memberid': '1', 'role': 'Slave', 'priority': '32', 'mac': ''}
            {'chassisid': '2', 'memberid': '0', 'role': 'Slave', 'priority': '31', 'mac': ''}
            {'chassisid': '2', 'memberid': '1', 'role': 'Slave', 'priority': '31', 'mac': ''}
            也有单设备
            """
            if len(res) > 1:
                # master 集合
                master = [x for x in res if x['role'] == 'Master']
                # master 对应的chassis id
                master_chassisid = master[0]['chassisid']
                # slave集合 并排除 master的 chassis id
                slave = [x for x in res if x['role'] == 'Slave' and x['chassisid'] != master_chassisid]
                for i in master:
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, chassis=int(
                            i['chassisid'])).update(
                        ha_status=1)
                    break
                for i in slave:
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, chassis=int(
                            i['chassisid'])).update(
                        ha_status=2)
                    break
            elif len(res) == 1:
                if res[0]['role'] == 'Master' and res[0]['memberid'] != '0':
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            res[0]['memberid'])).update(
                        ha_status=0)
                elif res[0]['role'] == 'Slave' and res[0]['memberid'] != '0':
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            res[0]['memberid'])).update(
                        ha_status=0)

    @staticmethod
    def ruijie_version(res, hostip):
        # version信息处理
        if isinstance(res, dict):
            """
            {'member': '1', 'serialnum': 'G1GC10V000176'}
            """
            NetworkDevice.objects.filter(
                manage_ip=hostip,
                serial_num=res['serialnum']).update(
                slot=int(
                    res['member']))
        elif isinstance(res, list):
            """
            [{'member': '1', 'serialnum': 'G1GC10V000176'}
            {'member': '2', 'serialnum': 'G1GC10V000134'}]
            """
            for i in res:
                NetworkDevice.objects.filter(
                    manage_ip=hostip,
                    serial_num=i['serialnum']).update(
                    slot=int(
                        i['member']))

    @staticmethod
    def ruijie_member(res, hostip):
        # 锐捷堆叠处理
        if isinstance(res, dict):
            """
            {'member': '1', 'priority': '120', 'macaddr': '1414.4b74.d658', 'softver': ''}
            {'member': '2', 'priority': '100', 'macaddr': '1414.4b74.d658', 'softver': ''}
            """
            # if int(res['priority']) > 100:
            NetworkDevice.objects.filter(
                manage_ip=hostip, slot=int(
                    res['member'])).update(
                ha_status=1)
            # elif int(res['priority']) <= 100:
            #     NetworkDevice.objects.filter(manage_ip=hostip, slot=int(res['member'])).update(ha_status=2)
        elif isinstance(res, list):
            # 172.17.1.2 的堆叠 priority 都是120，会导致判断错误
            tmp_priority = list(set([int(x['priority']) for x in res]))
            if len(tmp_priority) == 1:
                return
            for i in res:
                if int(i['priority']) == max(tmp_priority):
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            i['member'])).update(
                        ha_status=1)
                elif int(i['priority']) == min(tmp_priority):
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            i['member'])).update(
                        ha_status=2)

    @staticmethod
    def ruijie_switch_virtual(res, hostip):
        """
        res
        [{'member': '1', 'domain': '1', 'priority': '120', 'position': 'LOCAL', 'status': 'OK', 'role': 'ACTIVE'}
        {'member': '2', 'domain': '1', 'priority': '100', 'position': 'REMOTE', 'status': 'OK', 'role': 'STANDBY'}]
        :param res:
        :param hostip:
        :return:
        """
        if isinstance(res, dict):
            if res['role'] == 'ACTIVE':
                NetworkDevice.objects.filter(
                    manage_ip=hostip, slot=int(
                        res['member'])).update(
                    ha_status=1)
            elif res['role'] == 'STANDBY':
                NetworkDevice.objects.filter(
                    manage_ip=hostip, slot=int(
                        res['member'])).update(
                    ha_status=2)
        elif isinstance(res, list):
            for i in res:
                if i['role'] == 'ACTIVE':
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            i['member'])).update(
                        ha_status=1)
                elif i['role'] == 'STANDBY':
                    NetworkDevice.objects.filter(
                        manage_ip=hostip, slot=int(
                            i['member'])).update(
                        ha_status=2)

    # 华为usg防火墙安全策略写入mongo
    @staticmethod
    def huawei_usg_sec_policy(host, datas):
        """
        name: 'shipinghuiyi-deny',
        'source-zone': 'untrust',
        'destination-zone': 'trust',
        'destination-ip': {
            'address-set': 'shipinghuiyi'
        },
        service: {
            'service-object': 'tcp22'
        },
        enable: 'true',
        action: 'false',
        hostip: '172.21.250.251'
        :param host:
        :param datas:
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='sec_policy')
        my_mongo.delete_many(query=dict(hostip=host))
        address_mongo = MongoOps(db='NETCONF', coll='huawei_usg_address_set')
        results = []
        action = 'Deny'
        for i in datas:
            if i['action']:
                action = 'Permit'
            tmp = dict()
            src_addr = []
            dst_addr = []
            service = []
            tmp['src_ip_split'] = []
            tmp['dst_ip_split'] = []
            tmp['vendor'] = 'huawei_usg'
            tmp['hostip'] = host
            tmp['id'] = ''
            tmp['name'] = i['name']
            tmp['description'] = i.get('desc')
            tmp['action'] = action.lower()
            tmp['enable'] = i['enable']
            tmp['src_zone'] = i.get('source-zone')
            tmp['dst_zone'] = i.get('destination-zone')
            # tmp['service'] = i.get('service')
            if i.get('source-ip'):
                # 纯IP地址 点分十进制格式， 与掩码之间使用“/”区分，掩码使用 0- 32 的整数表示，如
                # 192.168.1.0/24。
                if 'address-ipv4' in i['source-ip'].keys():
                    if isinstance(i['source-ip']['address-ipv4'], list):
                        for element in i['source-ip']['address-ipv4']:
                            src_addr.append(dict(ip=element))
                            tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(element).first,
                                                            end=netaddr.IPNetwork(element).last))
                    elif isinstance(i['source-ip']['address-ipv4'], str):
                        src_addr.append(
                            dict(ip=i['source-ip']['address-ipv4']))
                        tmp['src_ip_split'].append(dict(start=netaddr.IPNetwork(i['source-ip']['address-ipv4']).first,
                                                        end=netaddr.IPNetwork(i['source-ip']['address-ipv4']).last))
                # address-ipv4-range 表示 IPv4 地址段节点，仅用于容纳子节 点，自身无数据含义
                if 'address-ipv4-range' in i['source-ip'].keys():
                    if isinstance(i['source-ip']['address-ipv4-range'], list):
                        for element in i['source-ip']['address-ipv4-range']:
                            start_ip = element['start-ipv4']
                            end_ip = element['end-ipv4']
                            src_addr.append(
                                dict(range=start_ip + '-' + end_ip))
                            tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                            end=netaddr.IPAddress(end_ip).value))
                    elif isinstance(i['source-ip']['address-ipv4-range'], dict):
                        start_ip = i['source-ip']['address-ipv4-range']['start-ipv4']
                        end_ip = i['source-ip']['address-ipv4-range']['end-ipv4']
                        src_addr.append(dict(range=start_ip + '-' + end_ip))
                        tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                        end=netaddr.IPAddress(end_ip).value))
                # 表示源地址引用的地址(组)对象的名称
                if 'address-set' in i['source-ip'].keys():
                    if isinstance(i['source-ip']['address-set'], str):
                        src_addr.append(
                            dict(object=i['source-ip']['address-set']))
                        _tmp = address_mongo.find(query_dict=dict(hostip=host, name=i['source-ip']['address-set']),
                                                  fileds={'_id': 0, 'elements': 1})
                        if _tmp:
                            for element in _tmp:
                                if isinstance(element['elements'], dict):
                                    if 'address-ipv4' in element['elements'].keys():
                                        tmp['src_ip_split'].append(
                                            dict(start=netaddr.IPNetwork(element['elements']['address-ipv4']).first,
                                                 end=netaddr.IPNetwork(element['elements']['address-ipv4']).last))
                                    if 'start-ipv4' and 'end-ipv4' in element['elements'].keys(
                                    ):
                                        start_ip = element['elements']['start-ipv4']
                                        end_ip = element['elements']['end-ipv4']
                                        tmp['src_ip_split'].append(
                                            dict(start=netaddr.IPAddress(start_ip).value,
                                                 end=netaddr.IPAddress(end_ip).value))
                                if isinstance(element['elements'], list):
                                    for ele_sub in element['elements']:
                                        if 'address-ipv4' in ele_sub.keys():
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(ele_sub['address-ipv4']).first,
                                                     end=netaddr.IPNetwork(ele_sub['address-ipv4']).last))
                                        if 'start-ipv4' and 'end-ipv4' in ele_sub.keys():
                                            start_ip = ele_sub['start-ipv4']
                                            end_ip = ele_sub['end-ipv4']
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPAddress(start_ip).value,
                                                     end=netaddr.IPAddress(end_ip).value))
                    elif isinstance(i['source-ip']['address-set'], list):
                        src_addr += [{'object': x}
                                     for x in i['source-ip']['address-set']]
                        for add_set in i['source-ip']['address-set']:
                            _tmp = address_mongo.find(query_dict=dict(hostip=host, name=add_set),
                                                      fileds={'_id': 0, 'elements': 1})
                            if _tmp:
                                for element in _tmp:
                                    if isinstance(element['elements'], dict):
                                        if 'address-ipv4' in element['elements'].keys():
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(element['address-ipv4']).first,
                                                     end=netaddr.IPNetwork(element['address-ipv4']).last))
                                        elif 'start-ipv4' and 'end-ipv4' in element['elements'].keys():
                                            start_ip = element['elements']['start-ipv4']
                                            end_ip = element['elements']['end-ipv4']
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPAddress(start_ip).value,
                                                     end=netaddr.IPAddress(end_ip).value))
                                    if isinstance(element['elements'], list):
                                        for ele_sub in element['elements']:
                                            if 'address-ipv4' in ele_sub.keys():
                                                tmp['src_ip_split'].append(
                                                    dict(start=netaddr.IPNetwork(ele_sub['address-ipv4']).first,
                                                         end=netaddr.IPNetwork(ele_sub['address-ipv4']).last))
                                            elif 'start-ipv4' and 'end-ipv4' in ele_sub.keys():
                                                start_ip = ele_sub['start-ipv4']
                                                end_ip = ele_sub['end-ipv4']
                                                tmp['src_ip_split'].append(
                                                    dict(start=netaddr.IPAddress(start_ip).value,
                                                         end=netaddr.IPAddress(end_ip).value))
            if i.get('destination-ip'):
                # 纯IP地址 点分十进制格式， 与掩码之间使用“/”区分，掩码使用 0- 32 的整数表示，如
                # 192.168.1.0/24。
                if 'address-ipv4' in i['destination-ip'].keys():
                    if isinstance(i['destination-ip']['address-ipv4'], list):
                        for element in i['destination-ip']['address-ipv4']:
                            dst_addr.append(dict(ip=element))
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPNetwork(element).first,
                                                            end=netaddr.IPNetwork(element).last))
                    elif isinstance(i['destination-ip']['address-ipv4'], str):
                        dst_addr.append(
                            dict(ip=i['destination-ip']['address-ipv4']))
                        tmp['dst_ip_split'].append(
                            dict(start=netaddr.IPNetwork(i['destination-ip']['address-ipv4']).first,
                                 end=netaddr.IPNetwork(i['destination-ip']['address-ipv4']).last))
                # address-ipv4-range 表示 IPv4 地址段节点，仅用于容纳子节 点，自身无数据含义
                if 'address-ipv4-range' in i['destination-ip'].keys():
                    if isinstance(i['destination-ip']
                                  ['address-ipv4-range'], list):
                        for element in i['destination-ip']['address-ipv4-range']:
                            start_ip = element['start-ipv4']
                            end_ip = element['end-ipv4']
                            dst_addr.append(
                                dict(range=start_ip + '-' + end_ip))
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                            end=netaddr.IPAddress(end_ip).value))
                    elif isinstance(i['destination-ip']['address-ipv4-range'], dict):
                        start_ip = i['destination-ip']['address-ipv4-range']['start-ipv4']
                        end_ip = i['destination-ip']['address-ipv4-range']['end-ipv4']
                        dst_addr.append(dict(range=start_ip + '-' + end_ip))
                        tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                        end=netaddr.IPAddress(end_ip).value))
                # 表示源地址引用的地址(组)对象的名称
                if 'address-set' in i['destination-ip'].keys():
                    if isinstance(i['destination-ip']['address-set'], str):
                        dst_addr.append(
                            dict(object=i['destination-ip']['address-set']))
                        _tmp = address_mongo.find(query_dict=dict(hostip=host, name=i['destination-ip']['address-set']),
                                                  fileds={'_id': 0, 'elements': 1})
                        if _tmp:
                            for element in _tmp:
                                if isinstance(element['elements'], dict):
                                    if 'address-ipv4' in element['elements'].keys():
                                        tmp['src_ip_split'].append(
                                            dict(start=netaddr.IPNetwork(element['elements']['address-ipv4']).first,
                                                 end=netaddr.IPNetwork(element['elements']['address-ipv4']).last))
                                    if 'start-ipv4' and 'end-ipv4' in element['elements'].keys(
                                    ):
                                        start_ip = element['elements']['start-ipv4']
                                        end_ip = element['elements']['end-ipv4']
                                        tmp['dst_ip_split'].append(
                                            dict(start=netaddr.IPAddress(start_ip).value,
                                                 end=netaddr.IPAddress(end_ip).value))
                                if isinstance(element['elements'], list):
                                    for ele_sub in element['elements']:
                                        if 'address-ipv4' in ele_sub.keys():
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(ele_sub['address-ipv4']).first,
                                                     end=netaddr.IPNetwork(ele_sub['address-ipv4']).last))
                                        if 'start-ipv4' and 'end-ipv4' in ele_sub.keys():
                                            start_ip = ele_sub['start-ipv4']
                                            end_ip = ele_sub['end-ipv4']
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPAddress(start_ip).value,
                                                     end=netaddr.IPAddress(end_ip).value))
                    elif isinstance(i['destination-ip']['address-set'], list):
                        dst_addr += [{'object': x}
                                     for x in i['destination-ip']['address-set']]
                        for add_set in i['destination-ip']['address-set']:
                            _tmp = address_mongo.find(query_dict=dict(hostip=host, name=add_set),
                                                      fileds={'_id': 0, 'elements': 1})
                            if _tmp:
                                for element in _tmp:
                                    if isinstance(element['elements'], dict):
                                        if 'address-ipv4' in element['elements'].keys():
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(element['address-ipv4']).first,
                                                     end=netaddr.IPNetwork(element['address-ipv4']).last))
                                        elif 'start-ipv4' and 'end-ipv4' in element['elements'].keys():
                                            start_ip = element['elements']['start-ipv4']
                                            end_ip = element['elements']['end-ipv4']
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPAddress(start_ip).value,
                                                     end=netaddr.IPAddress(end_ip).value))
                                    if isinstance(element['elements'], list):
                                        for ele_sub in element['elements']:
                                            if 'address-ipv4' in ele_sub.keys():
                                                tmp['dst_ip_split'].append(
                                                    dict(start=netaddr.IPNetwork(ele_sub['address-ipv4']).first,
                                                         end=netaddr.IPNetwork(ele_sub['address-ipv4']).last))
                                            elif 'start-ipv4' and 'end-ipv4' in ele_sub.keys():
                                                start_ip = ele_sub['start-ipv4']
                                                end_ip = ele_sub['end-ipv4']
                                                tmp['dst_ip_split'].append(
                                                    dict(start=netaddr.IPAddress(start_ip).value,
                                                         end=netaddr.IPAddress(end_ip).value))
            if i.get('service'):
                if 'service-object' in i['service'].keys():
                    if isinstance(i['service']['service-object'], str):
                        service.append(
                            dict(object=i['service']['service-object']))
                    elif isinstance(i['service']['service-object'], list):
                        service += [{'object': x}
                                    for x in i['service']['service-object']]
                if 'service-items' in i['service'].keys():
                    if isinstance(i['service']['service-items'], dict):
                        for key in i['service']['service-items'].keys():
                            if key in ['tcp', 'udp']:
                                if isinstance(
                                        i['service']['service-items'][key], list):
                                    for item in i['service']['service-items'][key]:
                                        _src_port = item['source-port']
                                        _dst_port = item['dest-port']
                                        if _src_port.find('to') != -1:
                                            _src_port = _src_port.split('to')
                                        if _dst_port.find('to') != -1:
                                            _dst_port = _dst_port.split('to')
                                        service.append(dict(item={
                                            "Type": key,
                                            "StartSrcPort": _src_port[0].strip() if isinstance(_src_port,
                                                                                               list) else _src_port,
                                            "EndSrcPort": _src_port[1].strip() if isinstance(_src_port,
                                                                                             list) else _src_port,
                                            "StartDestPort": _dst_port[1].strip() if isinstance(_dst_port,
                                                                                                list) else _dst_port,
                                            "EndDestPort": _dst_port[1].strip() if isinstance(_dst_port,
                                                                                              list) else _dst_port,
                                        }))
                                elif isinstance(i['service']['service-items'][key], dict):
                                    _src_port = i['service']['service-items'][key]['source-port']
                                    _dst_port = i['service']['service-items'][key]['dest-port']
                                    if _src_port.find('to') != -1:
                                        _src_port = _src_port.split('to')
                                    if _dst_port.find('to') != -1:
                                        _dst_port = _dst_port.split('to')
                                    service.append(dict(item={
                                        "Type": key,
                                        "StartSrcPort": _src_port[0].strip() if isinstance(_src_port,
                                                                                           list) else _src_port,
                                        "EndSrcPort": _src_port[1].strip() if isinstance(_src_port,
                                                                                         list) else _src_port,
                                        "StartDestPort": _dst_port[1].strip() if isinstance(_dst_port,
                                                                                            list) else _dst_port,
                                        "EndDestPort": _dst_port[1].strip() if isinstance(_dst_port,
                                                                                          list) else _dst_port,
                                    }))
                            if key == 'icmp-item':
                                if isinstance(
                                        i['service']['service-items'][key], list):
                                    for item in i['service']['service-items'][key]:
                                        service.append(dict(item={
                                            "Type": "icmp",
                                        }))
                                elif isinstance(i['service']['service-items'][key], dict):
                                    service.append(dict(item={
                                        "Type": "icmp",
                                    }))
                        # 'ServObjList': {'ServObjItem': '{ "Type": "0", "StartSrcPort": "0", "EndSrcPort": "65535", "StartDestPort": "80", "EndDestPort": "80" }'},
                    # todo 继续拆解 {'tcp': {'source-port': '0 to 65535',
                    # 'dest-port': '80'}}}
            tmp['service'] = service
            tmp['src_addr'] = src_addr
            tmp['dst_addr'] = dst_addr
            results.append(tmp)
        my_mongo.insert_many(results)
        return

    # 华三防火墙安全策略写入mongo
    @staticmethod
    def h3c_secpath_sec_policy(host, datas):
        """
        Type: '1',
        ID: '0',
        Action: '2',
        SrcZoneList: {
            SrcZoneItem: 'aa'
        },
        DestZoneList: {
            DestZoneItem: 'aa'
        },
        DestAddrList: {
            DestAddrItem: 'Server-AIaaS'
        },
        ServGrpList: {
            ServGrpItem: 'Services-AIaaS'
        },
        Enable: 'true',
        Log: 'false',
        Counting: 'true',
        Count: '27349857740',
        Byte: '36160694587021',
        SessAgingTimeSw: 'false',
        SessPersistAgingTimeSw: 'false',
        AllRulesCount: '3',
        hostip: '10.254.12.70'
        :param host:
        :param datas:
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='sec_policy')
        my_mongo.delete_many(query=dict(hostip=host))
        address_mongo = MongoOps(db='NETCONF', coll='h3c_address_set')
        results = []
        for i in datas:
            # print(i)
            tmp = dict()
            tmp['src_ip_split'] = []
            tmp['dst_ip_split'] = []
            service = []
            if i.get('ServGrpList'):
                if isinstance(i['ServGrpList']['ServGrpItem'], str):
                    service.append(
                        dict(
                            object=i['ServGrpList']['ServGrpItem']))
                elif isinstance(i['ServGrpList']['ServGrpItem'], list):
                    service += [{'object': x}
                                for x in i['ServGrpList']['ServGrpItem']]
            if i.get('ServObjList'):
                type_map = {
                    "0": "tcp",
                    "1": "udp",
                    "2": "icmp"
                }
                if isinstance(i['ServObjList']['ServObjItem'], str):
                    item = json.loads(i['ServObjList']['ServObjItem'])
                    item['Type'] = type_map[item['Type']]
                    service.append(dict(item=item))
                elif isinstance(i['ServObjList']['ServObjItem'], list):
                    for x in i['ServObjList']['ServObjItem']:
                        _tmp = json.loads(x)
                        _tmp['Type'] = type_map[_tmp['Type']]
                        service.append(dict(item=_tmp))
                    # service += [{'item': json.loads(x)} for x in i['ServObjList']['ServObjItem']]
            # 'ServObjList': {'ServObjItem': '{ "Type": "0", "StartSrcPort": "0", "EndSrcPort": "65535", "StartDestPort": "80", "EndDestPort": "80" }'},
            # 子网IP匹配正则
            ipaddr_regex = re.compile('^\\d+.\\d+.\\d+.\\d+/\\d+$')
            # 主机IP地址匹配正则
            host_ip_regex = re.compile('^\\d+.\\d+.\\d+.\\d+$')
            src_addr = []
            # 源地址对象组
            if i.get('SrcAddrList'):
                if isinstance(i['SrcAddrList']['SrcAddrItem'], list):
                    for src_item in i['SrcAddrList']['SrcAddrItem']:
                        src_addr.append(dict(object=src_item))
                        src_addr_res = address_mongo.find(
                            query_dict=dict(hostip=host, Name=src_item),
                            fileds={'_id': 0, 'elements': 1})
                        if src_addr_res:
                            for _src_addr in src_addr_res:
                                if 'elements' not in _src_addr.keys():
                                    continue
                                for _sub_addr in _src_addr['elements']:
                                    # 子网
                                    if _sub_addr['Type'] == 'subnet':
                                        if all(k in _sub_addr for k in (
                                                "SubnetIPv4Address", "IPv4Mask")):
                                            _tmp_subnet = _sub_addr['SubnetIPv4Address'] + \
                                                          '/' + _sub_addr['IPv4Mask']
                                            tmp['src_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(_tmp_subnet).first,
                                                     end=netaddr.IPNetwork(_tmp_subnet).last))
                                    # 范围
                                    if _sub_addr['Type'] == 'range':
                                        if all(k in _sub_addr for k in (
                                                "StartIPv4Address", "EndIPv4Address")):
                                            start_ip = _sub_addr['StartIPv4Address']
                                            end_ip = _sub_addr['EndIPv4Address']
                                            tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                            end=netaddr.IPAddress(end_ip).value))
                                    # 主机地址
                                    if _sub_addr['Type'] == 'ip' and _src_addr.get(
                                            'HostIPv4Address'):
                                        start_ip = _sub_addr['HostIPv4Address']
                                        end_ip = _sub_addr['HostIPv4Address']
                                        tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                        end=netaddr.IPAddress(end_ip).value))
                        elif ipaddr_regex.search(src_item):
                            tmp['src_ip_split'].append(
                                dict(start=netaddr.IPNetwork(src_item).first,
                                     end=netaddr.IPNetwork(src_item).last))
                elif isinstance(i['SrcAddrList']['SrcAddrItem'], str):
                    src_addr.append(
                        dict(object=i['SrcAddrList']['SrcAddrItem']))
                    src_addr_res = address_mongo.find(
                        query_dict=dict(
                            hostip=host, Name=i['SrcAddrList']['SrcAddrItem']),
                        fileds={'_id': 0, 'elements': 1})
                    if src_addr_res:
                        for _src_addr in src_addr_res:
                            if 'elements' not in _src_addr.keys():
                                continue
                            for _sub_addr in _src_addr['elements']:
                                # 子网
                                if _sub_addr['Type'] == 'subnet':
                                    if all(k in _sub_addr for k in (
                                            "SubnetIPv4Address", "IPv4Mask")):
                                        _tmp_subnet = _sub_addr['SubnetIPv4Address'] + \
                                                      '/' + _sub_addr['IPv4Mask']
                                        tmp['src_ip_split'].append(
                                            dict(start=netaddr.IPNetwork(_tmp_subnet).first,
                                                 end=netaddr.IPNetwork(_tmp_subnet).last))
                                # 范围
                                if _sub_addr['Type'] == 'range':
                                    if all(k in _sub_addr for k in (
                                            "StartIPv4Address", "EndIPv4Address")):
                                        start_ip = _sub_addr['StartIPv4Address']
                                        end_ip = _sub_addr['EndIPv4Address']
                                        tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                        end=netaddr.IPAddress(end_ip).value))
                                # 主机地址
                                if _sub_addr['Type'] == 'ip' and _src_addr.get(
                                        'HostIPv4Address'):
                                    start_ip = _sub_addr['HostIPv4Address']
                                    end_ip = _sub_addr['HostIPv4Address']
                                    tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                    end=netaddr.IPAddress(end_ip).value))
                    elif ipaddr_regex.search(i['SrcAddrList']['SrcAddrItem']):
                        tmp['src_ip_split'].append(
                            dict(start=netaddr.IPNetwork(i['SrcAddrList']['SrcAddrItem']).first,
                                 end=netaddr.IPNetwork(i['SrcAddrList']['SrcAddrItem']).last))
            dst_addr = []
            # 目的地址对象组
            if i.get('DestAddrList'):
                if isinstance(i['DestAddrList']['DestAddrItem'], list):
                    for dst_item in i['DestAddrList']['DestAddrItem']:
                        dst_addr.append(dict(object=dst_item))
                        dst_addr_res = address_mongo.find(
                            query_dict=dict(hostip=host, Name=dst_item),
                            fileds={'_id': 0, 'elements': 1})
                        if dst_addr_res:
                            for _dst_addr in dst_addr_res:
                                if 'elements' not in _dst_addr.keys():
                                    continue
                                for _sub_addr in _dst_addr['elements']:
                                    # 子网
                                    if _sub_addr['Type'] == 'subnet':
                                        if all(k in _sub_addr for k in (
                                                "SubnetIPv4Address", "IPv4Mask")):
                                            _tmp_subnet = _sub_addr['SubnetIPv4Address'] + \
                                                          '/' + _sub_addr['IPv4Mask']
                                            tmp['dst_ip_split'].append(
                                                dict(start=netaddr.IPNetwork(_tmp_subnet).first,
                                                     end=netaddr.IPNetwork(_tmp_subnet).last))
                                    # 范围
                                    if _sub_addr['Type'] == 'range':
                                        if all(k in _sub_addr for k in (
                                                "StartIPv4Address", "EndIPv4Address")):
                                            start_ip = _sub_addr['StartIPv4Address']
                                            end_ip = _sub_addr['EndIPv4Address']
                                            tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                            end=netaddr.IPAddress(end_ip).value))
                                    # 主机地址
                                    if _sub_addr['Type'] == 'ip' and _sub_addr.get(
                                            'HostIPv4Address'):
                                        start_ip = _sub_addr['HostIPv4Address']
                                        end_ip = _sub_addr['HostIPv4Address']
                                        tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                        end=netaddr.IPAddress(end_ip).value))
                        elif ipaddr_regex.search(dst_item):
                            tmp['dst_ip_split'].append(
                                dict(start=netaddr.IPNetwork(dst_item).first,
                                     end=netaddr.IPNetwork(dst_item).last))
                elif isinstance(i['DestAddrList']['DestAddrItem'], str):
                    dst_addr.append(
                        dict(object=i['DestAddrList']['DestAddrItem']))
                    dst_addr_res = address_mongo.find(
                        query_dict=dict(
                            hostip=host, Name=i['DestAddrList']['DestAddrItem']),
                        fileds={'_id': 0, 'elements': 1})
                    if dst_addr_res:
                        for _dst_addr in dst_addr_res:
                            if 'elements' not in _dst_addr.keys():
                                continue
                            for _sub_addr in _dst_addr['elements']:
                                # 子网
                                if _sub_addr['Type'] == 'subnet':
                                    if all(k in _sub_addr for k in (
                                            "SubnetIPv4Address", "IPv4Mask")):
                                        _tmp_subnet = _sub_addr['SubnetIPv4Address'] + \
                                                      '/' + _sub_addr['IPv4Mask']
                                        tmp['dst_ip_split'].append(
                                            dict(start=netaddr.IPNetwork(_tmp_subnet).first,
                                                 end=netaddr.IPNetwork(_tmp_subnet).last))
                                # 范围
                                if _sub_addr['Type'] == 'range':
                                    if all(k in _sub_addr for k in (
                                            "StartIPv4Address", "EndIPv4Address")):
                                        start_ip = _sub_addr['StartIPv4Address']
                                        end_ip = _sub_addr['EndIPv4Address']
                                        tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                        end=netaddr.IPAddress(end_ip).value))
                                # 主机地址
                                if _sub_addr['Type'] == 'ip' and _dst_addr.get(
                                        'HostIPv4Address'):
                                    start_ip = _sub_addr['HostIPv4Address']
                                    end_ip = _sub_addr['HostIPv4Address']
                                    tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                    end=netaddr.IPAddress(end_ip).value))
                    elif ipaddr_regex.search(i['DestAddrList']['DestAddrItem']):
                        tmp['dst_ip_split'].append(
                            dict(start=netaddr.IPNetwork(i['DestAddrList']['DestAddrItem']).first,
                                 end=netaddr.IPNetwork(i['DestAddrList']['DestAddrItem']).last))
            # 自定义源地址
            if i.get('SrcSimpleAddrList'):
                if 'SrcSimpleAddrItem' in i['SrcSimpleAddrList'].keys():
                    if isinstance(i['SrcSimpleAddrList']
                                  ['SrcSimpleAddrItem'], list):
                        for _src_simple in i['SrcSimpleAddrList']['SrcSimpleAddrItem']:
                            if _src_simple.find('-') != -1:  # range
                                src_addr.append(dict(range=_src_simple))
                                start_ip = _src_simple.split('-')[0]
                                end_ip = _src_simple.split('-')[1]
                                tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                end=netaddr.IPAddress(end_ip).value))
                            elif ipaddr_regex.search(_src_simple):  # subnet
                                src_addr.append(dict(ip=_src_simple))
                                tmp['src_ip_split'].append(
                                    dict(start=netaddr.IPNetwork(_src_simple).first,
                                         end=netaddr.IPNetwork(_src_simple).last))
                            elif host_ip_regex.search(_src_simple):  # host ip
                                src_addr.append(dict(ip=_src_simple))
                                tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(_src_simple).value,
                                                                end=netaddr.IPAddress(_src_simple).value))

                    elif isinstance(i['SrcSimpleAddrList']['SrcSimpleAddrItem'], str):
                        _src_simple = i['SrcSimpleAddrList']['SrcSimpleAddrItem']
                        if _src_simple.find('-') != -1:  # range
                            src_addr.append(dict(range=_src_simple))
                            start_ip = _src_simple.split('-')[0]
                            end_ip = _src_simple.split('-')[1]
                            tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                            end=netaddr.IPAddress(end_ip).value))
                        elif ipaddr_regex.search(_src_simple):  # subnet
                            src_addr.append(dict(ip=_src_simple))
                            tmp['src_ip_split'].append(
                                dict(start=netaddr.IPNetwork(_src_simple).first,
                                     end=netaddr.IPNetwork(_src_simple).last))
                        elif host_ip_regex.search(_src_simple):  # host ip
                            src_addr.append(dict(ip=_src_simple))
                            tmp['src_ip_split'].append(dict(start=netaddr.IPAddress(_src_simple).value,
                                                            end=netaddr.IPAddress(_src_simple).value))
            # 自定义目的地址
            if i.get('DestSimpleAddrList'):
                if 'DestSimpleAddrItem' in i['DestSimpleAddrList'].keys():
                    if isinstance(i['DestSimpleAddrList']
                                  ['DestSimpleAddrItem'], list):
                        for _dst_simple in i['DestSimpleAddrList']['DestSimpleAddrItem']:
                            if _dst_simple.find('-') != -1:  # range
                                dst_addr.append(dict(range=_dst_simple))
                                start_ip = _dst_simple.split('-')[0]
                                end_ip = _dst_simple.split('-')[1]
                                tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                                end=netaddr.IPAddress(end_ip).value))
                            elif ipaddr_regex.search(_dst_simple):  # subnet
                                dst_addr.append(dict(ip=_dst_simple))
                                tmp['dst_ip_split'].append(
                                    dict(start=netaddr.IPNetwork(_dst_simple).first,
                                         end=netaddr.IPNetwork(_dst_simple).last))
                            elif host_ip_regex.search(_dst_simple):  # host ip
                                dst_addr.append(dict(ip=_dst_simple))
                                tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(_dst_simple).value,
                                                                end=netaddr.IPAddress(_dst_simple).value))
                    elif isinstance(i['DestSimpleAddrList']['DestSimpleAddrItem'], str):
                        _dst_simple = i['DestSimpleAddrList']['DestSimpleAddrItem']
                        if _dst_simple.find('-') != -1:  # range
                            dst_addr.append(dict(range=_dst_simple))
                            start_ip = _dst_simple.split('-')[0]
                            end_ip = _dst_simple.split('-')[1]
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(start_ip).value,
                                                            end=netaddr.IPAddress(end_ip).value))
                        elif ipaddr_regex.search(_dst_simple):  # subnet
                            dst_addr.append(dict(ip=_dst_simple))
                            tmp['dst_ip_split'].append(
                                dict(start=netaddr.IPNetwork(_dst_simple).first,
                                     end=netaddr.IPNetwork(_dst_simple).last))
                        elif host_ip_regex.search(_dst_simple):  # host ip
                            dst_addr.append(dict(ip=_dst_simple))
                            tmp['dst_ip_split'].append(dict(start=netaddr.IPAddress(_dst_simple).value,
                                                            end=netaddr.IPAddress(_dst_simple).value))
            src_zone = ''
            if i.get('SrcZoneList'):
                src_zone = i['SrcZoneList']['SrcZoneItem']
            dst_zone = ''
            if i.get('DestZoneList'):
                dst_zone = i['DestZoneList']['DestZoneItem']
            tmp['vendor'] = 'H3C'
            tmp['hostip'] = i['hostip']
            tmp['id'] = i.get('ID')
            tmp['name'] = i.get('Name')
            tmp['action'] = str(i.get('Action')).lower()
            tmp['enable'] = i.get('Enable')
            tmp['src_zone'] = src_zone
            tmp['dst_zone'] = dst_zone
            tmp['service'] = service
            tmp['src_addr'] = src_addr  # 地址组
            tmp['dst_addr'] = dst_addr  # 地址组
            tmp['src_ip'] = ''  # 单IP列表
            tmp['dst_ip'] = ''  # 单IP列表
            tmp['log'] = i['Log']
            tmp['description'] = i.get('Comment')
            results.append(tmp)
        my_mongo.insert_many(results)
        return
