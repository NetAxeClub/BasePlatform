# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:
   Author:          Lijiamin
   date：           2023/11/15 09:51
-------------------------------------------------
   Change Activity:
                    2023/11/15 09:51
-------------------------------------------------
"""
# -*- coding: utf-8 -*-
# @Time    : 2023/11/15 10:01
# @Author  : LiJiaMin
# @Site    :
# @File    : tasks.py
# @Software: PyCharm
from __future__ import absolute_import, unicode_literals

import copy
import json
import time
# from copy import deepcopy
from datetime import datetime
from functools import wraps
import logging
import jinja2
import requests
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.core.cache import cache
# from NetOpsV1.settings import BASE_DIR
# from django.db.models import Q
# from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from django.core.files.storage import default_storage
from netaddr import IPNetwork, IPAddress

from netaxe.celery import AxeTask
from netaxe.settings import DEBUG
from apps.asset.models import NetworkDevice
from apps.automation.tools.hillstone import HillstoneProc
from apps.automation.firewall.h3c import H3cFirewall
from apps.automation.firewall.hillstone import HillstoneBase
from apps.automation.firewall.huawei import HuaweiUsgSecPolicyConf
from apps.automation.models import AutomationInventory, AutoFlow, Tasks as AutoFlowTasks, AutoEvent
from apps.automation.tasks import StandardFSMAnalysis, AutomationMongo
from utils.connect_layer.auto_main import BatManMain, HillstoneFsm
from apps.automation.tools.model_api import get_device_info_v2
from utils.connect_layer.NETCONF.h3c_netconf import H3CinfoCollection, H3CSecPath
from utils.connect_layer.NETCONF.huawei_netconf import HuaweiUSG
from utils.db.mongo_ops import MongoOps, MongoNetOps

channel_layer = get_channel_layer()
cmdb_mongo = MongoOps(db='XunMiData', coll='networkdevice')
dnat_mongo = MongoOps(db='Automation', coll='hillstone_dnat')
snat_mongo = MongoOps(db='Automation', coll='hillstone_snat')
address_mongo = MongoOps(db='Automation', coll='hillstone_address')
service_mongo = MongoOps(db='Automation', coll='hillstone_service')
servgroup_mongo = MongoOps(db='Automation', coll='hillstone_servgroup')
# 系统预定义服务
predefined_mongo = MongoOps(db='Automation', coll='hillstone_service_predefined')
if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config_backup'
log = logging.getLogger(__name__)


# 发送websocket消息
def send_ws_msg(group_name, data):
    # group_name = "sec_device"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'sec_device_message',
            'message': data
        }
    )
    return


def send_msg_sec_manage(msg):
    log.info(msg)


# ws装饰器
class WebSocket(object):
    def __init__(self):
        pass

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            room_group_name = kwargs.get('room_group_name')
            if room_group_name is not None:
                send_ws_msg(group_name=room_group_name,
                            data=dict(method='run', data='开始执行……\n', hostip=kwargs['hostip'], status='info'))
            func(*args, **kwargs)
            # print('Ending')
            if room_group_name is not None:
                send_ws_msg(group_name=room_group_name,
                            data=dict(method='closed', data='执行完成……\n', hostip=kwargs['hostip'], status='success'))

        return wrapper

    def notify(self):
        # logit只打日志，不做别的
        pass


# 比较两个字典差
class CompareTwoDict(object):
    """比较两个字典差异"""

    def __init__(self, dict1, dict2):
        self.dict1 = dict1
        self.dict2 = dict2
        self.key_list = self.keys(dict1, dict2)
        self.result = {}
        # 值相等
        self.EQUAL = '='
        # 值不等
        self.DIFF = '!'
        # 独有key
        self.MORE = '+'
        # 缺失key
        self.LACK = '-'

    def compare(self, key):
        """比较一个key"""
        # 这里默认value不是None
        v1 = self.dict1.get(key)
        v2 = self.dict2.get(key)
        # 如果都是字典继续深入比较
        if (isinstance(v1, dict)) and (isinstance(v2, dict)):
            self.result[key] = CompareTwoDict(v1, v2).main()
        else:
            self.result[key] = self.different(v1, v2)

    def different(self, v1, v2):
        """比较value差异"""
        if (v1 is not None) and (v2 is not None):
            if v1 == v2:
                return self.EQUAL
            else:
                return self.DIFF
        elif v1 is not None:
            return self.MORE
        else:
            return self.LACK

    def keys(self, dict1, dict2):
        """获取所有key"""
        return list(set(list(dict1.keys()) + list(dict2.keys())))

    def main(self):

        for k in self.key_list:
            self.compare(k)

        return self.result


def get_list_diff(old, new):
    del_more1 = []
    add_more2 = []
    dic_result = {}
    for str_1 in old:
        dic_result[str(str_1)] = 1

    for str_2 in new:
        if dic_result.get(str(str_2)):
            dic_result[str(str_2)] = 2
        else:
            add_more2.append(str_2)

    for key, val in dic_result.items():
        if val == 1:
            del_more1.append(key)
    # print('old比new多的内容为:', del_more1)
    # print('new比old多的内容为:', add_more2)
    return add_more2, del_more1


def get_host_info(host):
    dev_infos = get_device_info_v2(manage_ip=host)
    if dev_infos:
        if 'netconf' in dev_infos[0]['protocol']:
            dev_info = {
                'device_type': 'h3c',
                'ip': host,
                'port': dev_infos[0]['netconf_port'],
                'username': dev_infos[0]['netconf_username'],
                'password': dev_infos[0]['netconf_password'],
                'timeout': 200,  # float，连接超时时间，默认为100
                'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                'hostname': dev_infos[0]['name'],
                'idc_name': dev_infos[0].get('idc__name'),
                'chassis': dev_infos[0]['chassis'],
                'slot': dev_infos[0]['slot']
            }
            return dev_info
    return {}


# 安全纳管回调函数
def sec_callback(flow_record_id):
    flow_record = AutoFlow.objects.filter(id=flow_record_id).values().first()
    if flow_record['commit_user'] == 'sbzhang7':
        url = "http://sparta.iflytek.com/api/work/info/update_dnat_id.action"
        response = requests.post(url, data=flow_record)
    return


# 下发SSH执行动作
def run_cmd_config(*cmds, **dev_info):
    """
    这里只能看到命令是否发送到设备上运行
    :param cmds:
    :param dev_info:
    :return:
    """
    count = 0
    while True:
        if not cache.get('automation_' + dev_info['ip']):
            cache.set('automation_' + dev_info['ip'], '1')
            res, path, error = BatManMain.hillstone_config_v2(*cmds, **dev_info)
            # res booleam  True  False
            # paths list  config file path
            cache.delete('automation_' + dev_info['ip'])
            return res, path, error
        else:
            count += 1
            if count > 3:
                break
            time.sleep(30)
    return False, '', '等待设备锁释放超时(90秒),请勿短时间内反复操作这台设备'


# 下发Netconf执行动作 xml 放在 dev_info['cmds']中
def run_netconf_config(**dev_info):
    """
    这里只能看到命令是否发送到设备上运行
    :param cmds:
    :param dev_info:
    :return:
    """
    count = 0
    while True:
        if not cache.get('automation_' + dev_info['ip']):
            cache.set('automation_' + dev_info['ip'], '1')
            print('开始执行配置下发')
            try:
                if dev_info['port'] == 830 and dev_info['device_type'] in ['h3c', 'hpcomware']:
                    device = H3CSecPath(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'],
                                        timeout=600, device_params=dev_info['device_type'])
                    # 判断具体要调用那个方法，采用方法映射关系
                    class_method = getattr(H3CSecPath, dev_info['class_method'], None)
                    if class_method:
                        # 适配分段下发 华三dnat有用到
                        if isinstance(dev_info['cmd'], list):
                            # 默认下发成功，如果默认False，则后面即使是True， 与运算也会是False
                            res = True
                            info = ''
                            for _cmd in dev_info['cmd']:
                                _res, _info = class_method(device, _cmd)
                                print("run_netconf_config ==> _res", _res)
                                print("run_netconf_config ==> _info", _info)
                                res = res and _res
                                info = info + str(_info)
                            device.closed()
                            cache.delete('automation_' + dev_info['ip'])
                            return res, info
                        else:
                            # getattr 获取到的方法，第一个参数是self，传入device即可 而且方法必须有两个返回值
                            res, info = class_method(device, dev_info['cmd'])
                            print("run_netconf_config ==> res", res)
                            print("run_netconf_config ==> info", info)
                            device.closed()
                            cache.delete('automation_' + dev_info['ip'])
                            return res, info
                elif dev_info['port'] == 830 and dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(
                        host=dev_info['ip'],
                        user=dev_info['username'],
                        password=dev_info['password'],
                        timeout=600)
                    # 判断具体要调用那个方法，采用方法映射关系
                    class_method = getattr(HuaweiUSG, dev_info['class_method'], None)
                    if class_method:
                        # getattr 获取到的方法，第一个参数是self，传入device即可 而且方法必须有两个返回值
                        res, info = class_method(device, dev_info['cmd'])
                        print("run_netconf_config ==> res", res)
                        print("run_netconf_config ==> info", info)
                        device.closed()
                        cache.delete('automation_' + dev_info['ip'])
                        return res, info
                else:
                    cache.delete('automation_' + dev_info['ip'])
                    raise ValueError("run_netconf_config 匹配未知参数")
                # res booleam  True  False
                # paths list  config file path
            except Exception as e:
                cache.delete('automation_' + dev_info['ip'])
                print(e)
                # print(traceback.print_exc())
                return False, '执行下netconf发动作失败'
            cache.delete('automation_' + dev_info['ip'])
        else:
            count += 1
            if count > 3:
                break
            print('等待30s……')
            time.sleep(30)
    return False, '等待设备锁释放超时'


# 防火墙统一处理 集中在此处理或调度
class FirewallMain(object):
    def __init__(self, host):
        """
        统一登陆设备信息获取方法
        :param host:
        """
        # 下发命令
        self.cmds = []
        # 回退命令
        self.back_off_cmds = []
        self.host = host
        self.dev_infos = get_device_info_v2(manage_ip=host)
        if isinstance(self.dev_infos, list) and len(self.dev_infos) > 0:
            self.dev_infos = self.dev_infos[0]
            if 'netconf' in self.dev_infos['protocol']:
                if self.dev_infos['vendor__alias'] == 'H3C' and self.dev_infos['category__name'] == '防火墙':
                    self.dev_info = {
                        'device_type': 'h3c',
                        'ip': self.dev_infos.get('bind_ip__ipaddr') if self.dev_infos.get('bind_ip__ipaddr') else host,
                        'port': self.dev_infos['netconf']['port'],
                        'username': self.dev_infos['netconf']['username'],
                        'password': self.dev_infos['netconf']['password'],
                        'timeout': 200,  # float，连接超时时间，默认为100
                        'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                        'patch_version': self.dev_infos.get('patch_version'),
                        'hostname': self.dev_infos['name'],
                        'idc_name': self.dev_infos.get('idc__name'),
                        'chassis': self.dev_infos['chassis'],
                        'slot': self.dev_infos['slot'],
                        'serial_num': self.dev_infos['serial_num'],
                        'category__name': self.dev_infos.get('category__name')
                    }
                elif self.dev_infos['vendor__alias'] == 'Huawei' and self.dev_infos['category__name'] == '防火墙':
                    self.dev_info = {
                        'device_type': 'huawei_usg',
                        'ip': self.dev_infos['bind_ip__ipaddr'],  # 华为防火墙必须走专用netconf地址
                        'port': self.dev_infos['netconf_port'],
                        'username': self.dev_infos['netconf_username'],
                        'password': self.dev_infos['netconf_password'],
                        'timeout': 200,  # float，连接超时时间，默认为100
                        'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                        'hostname': self.dev_infos['name'],
                        'idc_name': self.dev_infos.get('idc__name'),
                        'chassis': self.dev_infos['chassis'],
                        'slot': self.dev_infos['slot'],
                        'manage_ip': self.dev_infos['manage_ip']
                    }
                else:
                    raise ValueError("netconf 初始化未知失败")
            else:
                # self.cmds = ['configure']
                # self.back_off_cmds = ['configure']
                # 默认带 configure  后续根据版本再反向判断哪些不需要带 configure
                # if self.dev_infos['soft_version'].find('SG6000-M-2-5.5R2P17-v6') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-5.0R4P3.4.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find(
                #         'Version 5.5 SG6000-M-2-5.5R2P6.5-v6.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-5.0R4P14.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-5.0R3P5.bin') != -1:  # Version 5.5
                # #     self.cmds = []
                # #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-5.0R4P5.6.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-2-5.0R3P2.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-5.0R4P3.4.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # elif self.dev_infos['soft_version'].find('Version 5.5 SG6000-M-5.5R5.bin') != -1:  # Version 5.5
                #     self.cmds = []
                #     self.back_off_cmds = []
                # if self.dev_infos['soft_version'].find('5.5R6') != -1:  # Version 5.5
                #     self.cmds = ['configure']
                #     self.back_off_cmds = ['configure']
                # elif self.dev_infos['soft_version'].find('SG6000-X7180-5.5R2P7') != -1:  # 10.254.3.102
                #     self.cmds = ['configure']
                #     self.back_off_cmds = ['configure']
                self.dev_info = {
                    'device_type': 'hillstone_telnet' if 'telnet' in self.dev_infos['protocol'] else 'hillstone',
                    'ip': host,
                    'port': self.dev_infos['ssh']['port'],
                    'username': self.dev_infos['ssh']['username'],
                    'password': self.dev_infos['ssh']['password'],
                    'timeout': 100,  # float，连接超时时间，默认为100
                    'session_timeout': 60,  # float，每个请求的超时时间，默认为60，
                    'encoding': 'utf-8'
                }
                if self.dev_infos.get('bind_ip__ipaddr'):
                    self.dev_infos['ip'] = self.dev_infos['bind_ip__ipaddr']
        else:
            raise ValueError("FirewallMain初始化未获取到设备CMDB信息")

    # 流程引擎操作
    def flow_engine(self, *args, **kwargs):
        # 下发命令， 回退命令， 对应类方法
        cmds, back_off_cmds, class_method = args
        flag = kwargs.get('flag')
        if kwargs.get('event_id'):
            event_id = kwargs.get('event_id')
            kwargs['event'] = AutoEvent.objects.get(id=event_id)
            kwargs.pop('event_id')
        if isinstance(flag, bool):
            kwargs.pop('flag')
        # 获取设备实例
        _device = NetworkDevice.objects.get(id=kwargs['device_id'])
        # 验证通过  创建流程
        flow_record = AutoFlow.objects.create(**kwargs)
        # 批准执行
        netmiko_error = ''
        netconf_error = ''
        path = ''
        flow_record.approve()
        if class_method != 'Hillstone':
            # 将类方法传入参数，只对netconf操作才需要传入, netmiko不能传，否则会出现netmiko不识别导致任务失败
            self.dev_info['class_method'] = class_method
            # 开始执行NETCONF配置下发动作 很关键
            self.dev_info['cmd'] = cmds
            res, netconf_error = run_netconf_config(**self.dev_info)
        else:
            print('开始执行SSH配置下发动作 ')
            log.info('开始执行SSH配置下发动作 ')
            # 开始执行SSH配置下发动作 很关键
            res, path, netmiko_error = run_cmd_config(*cmds, **self.dev_info)
            if res:
                data_to_parse = default_storage.open(path).read()
                flow_record.task_result = data_to_parse.decode('utf-8')
        # 设置发布生效 后面根据配置结果，判断是否需要迁移到 失败
        flow_record.publish()
        if res:
            # 只有类方法是Hillstone才会用到TTP解析
            # class_method 设计初衷是给华三华为做类方法映射用的，山石默认就是Hillstone
            _ttp_info = ''  # 存储ttp解析的错误结果内容
            if class_method == 'Hillstone':
                ttp_method = HillstoneFsm.get_map("standard")
                if ttp_method:
                    ttp_res = ttp_method(path=path)  # 此处是方法的实例
                    if isinstance(ttp_res, dict):
                        # 目前山石网科的三种命令执行中的错误提示 捕获
                        if 'unrecognized' in ttp_res.keys():
                            flow_record.failed()
                            if isinstance(ttp_res['unrecognized'], dict):
                                if 'unrecognized' in ttp_res['unrecognized'].keys():
                                    if isinstance(ttp_res['unrecognized']['unrecognized'], str):
                                        _ttp_info = 'unrecognized: ' + ttp_res['unrecognized'][
                                            'unrecognized']
                                    elif isinstance(ttp_res['unrecognized']['unrecognized'], list):
                                        _ttp_info = 'unrecognized: ' + ' '.join(
                                            ttp_res['unrecognized']['unrecognized'])
                                    else:
                                        _ttp_info = 'unrecognized: ' + str(
                                            ttp_res['unrecognized']['unrecognized'])
                            elif isinstance(ttp_res['unrecognized'], list):
                                _ttp_info = 'unrecognized: ' + '\n'.join(
                                    [x['unrecognized'] for x in ttp_res['unrecognized']])
                        elif 'errors' in ttp_res.keys():
                            flow_record.failed()
                            if isinstance(ttp_res['errors'], dict):
                                _ttp_info = 'error: ' + ttp_res['errors']['error']
                            elif isinstance(ttp_res['errors'], list):
                                _info = '\n'.join(list(set([x['error'] for x in ttp_res['errors']])))
                                _ttp_info = 'error: ' + _info
                            else:
                                _ttp_info = 'error: ' + str(ttp_res['errors']['error'])
                        elif 'warning' in ttp_res.keys():
                            flow_record.failed()
                            _ttp_info = 'warning: ' + ttp_res['errors']['error']
                    flow_record.ttp = json.dumps(ttp_res)
            flow_record.save()
            # 判断状态迁移到失败以后的state值
            if flow_record.state == 'Failed':
                # TODO(): 关联工单推进到人工审核
                # if flow_record.order_code is not None:
                #     sd_params = dict(code_id=flow_record.order_code,
                #                      status=False, user=flow_record.commit_user)
                #     service_desk_ops.apply_async(kwargs=sd_params)
                msg = "[操作{}失败]\n用户:{}\n设备:{}\n状态:{}\n错误:{}\n==========".format(
                    kwargs['task'], kwargs['commit_user'], kwargs['device'], flow_record.state, _ttp_info)
            # 判断状态迁移到成功以后的state值
            elif flow_record.state == 'Published':
                # TODO(): 关联工单推进用户确认
                # if flow_record.order_code is not None:
                #     sd_params = dict(code_id=flow_record.order_code,
                #                      status=True, user=flow_record.commit_user)
                #     service_desk_ops.apply_async(kwargs=sd_params)
                msg = "[操作{}成功]\n用户:{}\n设备:{}\n状态:{}\n==========".format(
                    kwargs['task'], kwargs['commit_user'], kwargs['device'], '发布生产')
            else:
                msg = "[操作{}]\n用户:{}\n设备:{}\n状态:{}\n未能获取到状态信息\n==========".format(
                    kwargs['task'], kwargs['commit_user'], kwargs['device'], flow_record.state)
            send_msg_sec_manage(msg)
        else:
            # 执行失败 一般执行失败，也会有配置过程，不是单纯的失败
            # flow_record.task_result = str(path)
            flow_record.failed()
            # if len(flow_record.order_code) > 2:
            #     sd_params = dict(code_id=flow_record.order_code, status=False,
            #                      user=flow_record.commit_user)
            #     service_desk_ops.apply_async(kwargs=sd_params)
            flow_record.task_result = str(netconf_error)
            flow_record.save()
            if class_method != 'Hillstone':
                msg = "[操作{}失败]\n用户:{}\n设备:{}\n状态:发布失败\n错误:{}\n==========".format(
                    kwargs['task'], kwargs['commit_user'], kwargs['device'], netconf_error)
            else:
                msg = "[操作{}失败]\n用户:{}\n设备:{}\n状态:发布失败\n错误:{}\n==========".format(
                    kwargs['task'], kwargs['commit_user'], kwargs['device'], netmiko_error)
            send_msg_sec_manage(msg)
        # 回调
        sec_callback(flow_record.id)
        return

    # 山石地址对象操作V2
    def hillstone_address_detail(self, **kwargs):
        """
        "vendor": "hillstone",
        "add_detail": true,
        "ip_mask": "1.1.1.1/32",
        "ip_type": "ip_mask",
        "name": "AIYL_white_list",
        "range_end": "",
        "range_start": "",
        "hostip": "10.254.3.102"
        "cmds" 初始化命令
        "dev_info" 设备登陆参数
        :param kwargs:
        :return: True, 'path', ttp_res
        """
        # host = kwargs['hostip']
        name = 'address ' + kwargs['name']
        if kwargs.get('add_detail_ip'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ip in kwargs['ip_mask']:
                self.cmds += ['ip ' + _ip]
                self.back_off_cmds += ['no ip ' + _ip]
        elif kwargs.get('add_detail_exclude_ip'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ip in kwargs['ip_mask']:
                self.cmds += ['exclude ip ' + _ip]
                self.back_off_cmds += ['no exclude ip ' + _ip]
        elif kwargs.get('del_detail_ip'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ip in kwargs['ip_mask']:
                self.cmds += ['no ip ' + _ip]
                self.back_off_cmds += ['ip ' + _ip]
        elif kwargs.get('del_detail_exclude_ip'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ip in kwargs['ip_mask']:
                self.cmds += ['no exclude ip ' + _ip]
                self.back_off_cmds += ['exclude ip ' + _ip]
        elif kwargs.get('add_detail_range'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            self.cmds += ['range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
            self.back_off_cmds += ['no range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
        elif kwargs.get('add_detail_exclude_range'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            self.cmds += ['exclude range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
            self.back_off_cmds += ['no exclude range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
        elif kwargs.get('del_detail_range'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            self.cmds += ['no range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
            self.back_off_cmds += ['range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
        elif kwargs.get('del_detail_exclude_range'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            self.cmds += ['no exclude range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
            self.back_off_cmds += ['exclude range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
        elif kwargs.get('add_object'):
            self.cmds += [name]
            self.back_off_cmds += ['no address ' + kwargs['name']]
            if kwargs.get('ip_mask'):
                for _ip in kwargs['ip_mask']:
                    self.cmds += ['ip ' + _ip]
            if kwargs.get('range_start') and kwargs.get('range_end'):
                self.cmds += ['range ' + kwargs['range_start'] + ' ' + kwargs['range_end']]
        elif kwargs.get('del_object'):
            self.cmds += ['no address ' + kwargs['name']]
            self.back_off_cmds += ['address ' + kwargs['name']]
            res = address_mongo.find(query_dict=dict(hostip=kwargs['hostip'], name=kwargs['name']), fileds={'_id': 0})
            if not res:
                raise RuntimeError("hillstone_address_detail" + ' 未获取到现有的配置，无法生成回退命令')
            for i in res:
                if i.get('ip'):
                    if i['ip']:
                        for _ip in i['ip']:
                            self.back_off_cmds += ['ip ' + _ip['ip']]
                if i.get('range'):
                    if i['range']:
                        for _range in i['range']:
                            self.back_off_cmds += ['range ' + _range['start'] + ' ' + _range['end']]
        elif kwargs.get('add_detail_hybrid'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ip in kwargs['ip_mask']:
                if _ip.find('-') != -1:
                    self.cmds += ["range " + ' '.join(_ip.split('-'))]
                    self.back_off_cmds += ["no range " + ' '.join(_ip.split('-'))]
                else:
                    self.cmds += ['ip ' + _ip]
                    self.back_off_cmds += ['no ip ' + _ip]
        return self.cmds, self.back_off_cmds

    # 山石SLB对象操作v2
    def hillstone_slb_detail(self, **kwargs):
        """
        新建和编辑SLB
        slb-server-pool {pool-name}
        server ip 172.31.6.74/32 | ip-range 1.1.1.1 1.1.1.2 port 9000 weight-per-server 100
        max-connection-per-server 65535
        :param kwargs:
        :return:
        """
        slb_name = kwargs['name']
        # 增加对象
        if kwargs.get('add_object'):
            self.back_off_cmds += ['no slb-server-pool ' + slb_name]
            _HillstoneBase = HillstoneBase(self.cmds, self.dev_info, self.dev_infos)
            config_cmds = _HillstoneBase.config_slb_pool(**kwargs)
            if config_cmds:
                self.cmds += config_cmds
                return self.cmds, self.back_off_cmds
            raise RuntimeError("hillstone_slb删除对象失败:未能生成新建配置命令")
        # 删除对象
        elif kwargs.get('del_object'):
            before_cmds = ['show configuration | begin slb-server-pool']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_slb_config_before(slb_name=slb_name, path=paths[0])
                if "before_config" in before_ttp_res.keys():
                    self.back_off_cmds += ['slb-server-pool ' + slb_name] + before_ttp_res['before_config']
                    self.cmds += ['no slb-server-pool ' + slb_name]
                    return self.cmds, self.back_off_cmds
            raise RuntimeError("hillstone_slb删除对象失败:未能生成回退命令")
        # TODO(jmli12):编辑对象 #生成配置，再根据配置生成回退命令有待验证
        elif kwargs.get('edit_object'):
            before_cmds = ['show configuration | begin slb-server-pool']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_slb_config_before(slb_name=slb_name, path=paths[0])
                if "before_config" in before_ttp_res.keys():
                    self.back_off_cmds += ['slb-server-pool ' + slb_name] + before_ttp_res['before_config']
                    _HillstoneBase = HillstoneBase(self.cmds, self.dev_info, self.dev_infos)
                    config_cmds = _HillstoneBase.config_slb_pool(**kwargs)
                    if config_cmds:
                        self.cmds += config_cmds
                        return self.cmds, self.back_off_cmds
                    else:
                        raise RuntimeError("hillstone_slb 未能生成下发配置")
            raise RuntimeError("hillstone_slb删除对象失败:未能生成回退命令")
        else:
            raise RuntimeError("hillstone_slb未能获取到对应的操作标记")

    # 华三地址对象操作V2
    def h3c_address_detail(self, **kwargs):
        """
        # 前期只能返回配置命令，ID是配置后随即分配的，回退命令需要等配置下发后二次采集获得
        ===============
        "user": "jmli8",
        "vendor": "H3C",
        "add_detail_ip": true,
        "ip_mask": ["1.1.1.1/32"],
        "name": "12.101测试",
        "id": "1", # 新增不需要，删除需要
        "hostip": "10.254.12.101"
        =================
        "vendor": "Hillstone",
        "add_detail_range": true,
        "range_start": "1.1.1.1/32",
        "range_end": "1.1.1.2",
        "name": "7",
        "hostip": "10.254.12.16",
        "hostid": 2494
        """
        if kwargs['method'] == 'create':
            oms = {
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'Obj': []
                    }
            }
            back_oms = {
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'Obj': []
                    }
            }
            if kwargs.get('add_detail_ip'):
                for _tmp in kwargs['ip_mask']:
                    _tmp_ip = IPNetwork(_tmp)  # demo: 10.254.0.1/24
                    oms['IPv4Objs']['Obj'].append(
                        {
                            "Group": kwargs['name'],
                            "ID": '4294967295',  # 固定值 代表系统自动分配
                            "Type": '1',
                            "SubnetIPv4Address": _tmp_ip.network.format(),
                            "IPv4Mask": _tmp_ip.netmask.format()
                        }
                    )
                    back_oms['IPv4Objs']['Obj'].append(
                        {
                            "Group": kwargs['name'],
                            "ID": '',  # 预留，下发后回填
                        }
                    )
            elif kwargs.get('add_detail_hostip'):
                for _tmp in kwargs['hostipv4addr']:
                    _tmp_ip = IPAddress(_tmp)  # demo: 10.254.0.1/24
                    oms['IPv4Objs']['Obj'].append(
                        {
                            "Group": kwargs['name'],
                            "ID": '4294967295',  # 固定值 代表系统自动分配
                            "Type": '3',
                            "HostIPv4Address": _tmp_ip.format(),
                        }
                    )
                    back_oms['IPv4Objs']['Obj'].append(
                        {
                            "Group": kwargs['name'],
                            "ID": '',  # 预留，下发后回填
                        }
                    )
            if kwargs.get('add_detail_range'):
                oms['IPv4Objs']['Obj'].append(
                    {
                        "Group": kwargs['name'],
                        "ID": '4294967295',  # 固定值 代表系统自动分配
                        "Type": '2',
                        "StartIPv4Address": kwargs['range_start'],
                        "EndIPv4Address": kwargs['range_end']
                    }
                )
                back_oms['IPv4Objs']['Obj'].append(
                    {
                        "Group": kwargs['name'],
                        "ID": '',  # 预留，下发后回填
                    }
                )
            return True, oms, back_oms
        elif kwargs['method'] == 'remove':
            oms = {
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'Obj': []
                    }
            }
            back_oms = {
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'Obj': []
                    }
            }
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            if kwargs.get('del_detail_ip'):
                for _tmp in kwargs['ip_mask']:
                    _tmp_ip = IPNetwork(_tmp)  # demo: 10.254.0.1/24
                    # 先查询IP/MASK
                    try:
                        _tmp_id = device.get_ipv4_objs(name=kwargs['name'],
                                                       SubnetIPv4Address=_tmp_ip.network.format(),
                                                       IPv4Mask=_tmp_ip.netmask.format())
                        if not _tmp_id:
                            # 如果查询不到，查询主机IP  hostip
                            _tmp_id = device.get_ipv4_objs(name=kwargs['name'],
                                                           HostIPv4Address=_tmp_ip.network.format())
                        if _tmp_id:
                            oms['IPv4Objs']['Obj'].append(
                                {
                                    "Group": kwargs['name'],
                                    "ID": str(_tmp_id[0]['ID'])
                                }
                            )
                            back_oms['IPv4Objs']['Obj'].append(
                                _tmp_id[0]
                            )

                    except Exception as e:
                        # 如果查询失败，查询主机IP  hostip
                        try:
                            # 华三这个兼容没做好，删除有可能是删除的主机IP，但是在这里没有做好区分
                            _tmp_id = device.get_ipv4_objs(name=kwargs['name'],
                                                           HostIPv4Address=_tmp_ip.network.format())
                            if _tmp_id:
                                oms['IPv4Objs']['Obj'].append(
                                    {
                                        "Group": kwargs['name'],
                                        "ID": str(_tmp_id[0]['ID'])
                                    }
                                )
                                back_oms['IPv4Objs']['Obj'].append(
                                    _tmp_id[0]
                                )
                        except Exception as e:
                            # 如果依然没查询到，则地址对象不包含该条目
                            raise ValueError("h3c_address_detail执行del_detail_ip错误，地址对象中不包含该条目")
                    # else:
                    #     raise ValueError("h3c_address_detail执行del_detail_ip错误")

            elif kwargs.get('del_detail_hostip'):
                for _tmp in kwargs['hostipv4addr']:
                    _tmp_ip = IPAddress(_tmp)  # demo: 10.254.0.1/24
                    _tmp_id = device.get_ipv4_objs(name=kwargs['name'],
                                                   HostIPv4Address=_tmp_ip.format())
                    if _tmp_id:
                        oms['IPv4Objs']['Obj'].append(
                            {
                                "Group": kwargs['name'],
                                "ID": str(_tmp_id[0]['ID'])
                            }
                        )
                        back_oms['IPv4Objs']['Obj'].append(
                            _tmp_id[0]
                        )
                    else:
                        raise ValueError("h3c_address_detail执行del_detail_hostip错误")
            elif kwargs.get('del_detail_range'):
                _tmp_id = device.get_ipv4_objs(name=kwargs['name'],
                                               StartIPv4Address=kwargs['range_start'],
                                               EndIPv4Address=kwargs['range_end'])
                if _tmp_id:
                    oms['IPv4Objs']['Obj'].append(
                        {
                            "Group": kwargs['name'],
                            "ID": str(_tmp_id[0]['ID'])
                        }
                    )
                    back_oms['IPv4Objs']['Obj'].append(
                        _tmp_id[0]
                    )
                else:
                    raise ValueError("del_detail_range")
            device.closed()
            if len(oms['IPv4Objs']['Obj']) == 0:
                return False, oms, back_oms
            return True, oms, back_oms
        elif kwargs['method'] == 'object':
            if kwargs.get('add_object'):
                Obj = []
                if kwargs.get('ip_mask'):
                    for _tmp in kwargs['ip_mask']:
                        _tmp_ip = IPNetwork(_tmp)  # demo: 10.254.0.1/24
                        Obj.append(
                            {
                                "Group": kwargs['name'],
                                "ID": '4294967295',  # 固定值 代表系统自动分配
                                "Type": '1',
                                "SubnetIPv4Address": _tmp_ip.network.format(),
                                "IPv4Mask": _tmp_ip.netmask.format()
                            }
                        )
                if kwargs.get('range_start') and kwargs.get('range_end'):
                    Obj.append(
                        {
                            "Group": kwargs['name'],
                            "ID": '4294967295',  # 固定值 代表系统自动分配
                            "Type": '2',
                            "StartIPv4Address": kwargs['range_start'],
                            "EndIPv4Address": kwargs['range_end']
                        }
                    )
                # 新建地址组对象需要分两段下发，第一次建组，第二次创建组成员
                oms = [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'IPv4Groups': {
                            'Group':
                                {
                                    'Name': kwargs['name']
                                }
                        }
                    },
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'IPv4Objs': {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'Obj': Obj
                        }
                    }
                ]
                if kwargs.get('description'):
                    oms[0]['IPv4Groups']['Group']['Description'] = kwargs['description']
                back_oms = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'remove',
                    'IPv4Groups': {
                        'Group':
                            {
                                'Name': kwargs['name']
                            }
                    },
                }
                return True, oms, back_oms
            elif kwargs.get('del_object'):
                device = H3CSecPath(host=self.dev_info['ip'],
                                    user=self.dev_info['username'], password=self.dev_info['password'],
                                    timeout=600, device_params=self.dev_info['device_type'])
                OMS = {
                    'IPv4Groups': {
                        'Group': {
                            'Name': kwargs['name'],
                            'Description': None
                        }
                    },
                    'IPv4Objs':
                        {
                            'Obj': {
                                'Group': kwargs['name'],
                                'ID': None,
                                'Type': None,
                                'SubnetIPv4Address': None,
                                'IPv4Mask': None,
                                'StartIPv4Address': None,
                                'EndIPv4Address': None,
                                'HostIPv4Address': None,
                                'HostName': None,
                                'NestedGroup': None
                            }
                        }
                }
                back_oms = device.get_oms_objs(OMS)
                # 把ID字段置换成系统识别的自动分配专用ID
                if back_oms:
                    if back_oms['IPv4Objs']['Obj']:
                        for i in back_oms['IPv4Objs']['Obj']:
                            i['ID'] = '4294967295'
                oms = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'remove',
                    'IPv4Groups': {
                        'Group':
                            {
                                'Name': kwargs['name']
                            }
                    },
                }
                device.closed()
                return True, oms, back_oms
        raise RuntimeError("FirewallMain.h3c_address_detail 未匹配到method参数")

    # 华为地址对象操作V2
    def huawei_address_detail(self, **kwargs):
        device = HuaweiUSG(host=self.dev_info['ip'], user=self.dev_info['username'], password=self.dev_info['password'])
        res = device.get_address_set()
        device.closed()
        count_flag = 0
        back_oms = {'vsys': 'public', 'name': kwargs['name'], 'desc': kwargs.get('description'),
                    'elements': []}
        if not res:
            raise ValueError("huawei_address_detail未获取到现有配置")
        for i in res:
            if i['name'] == kwargs['name']:
                back_oms = copy.deepcopy(i)
                # {'vsys': 'public', 'name': 'test1', 'desc': 'test_desc',
                # 'elements': [{'elem-id': '0', 'address-ipv4': '1.1.1.1/32'},
                # {'elem-id': '1', 'address-ipv4': '2.2.2.2/32'},
                # {'elem-id': '2', 'start-ipv4': '3.3.3.1', 'end-ipv4': '3.3.3.3'}]}
                # description = i.get('desc')
        if back_oms['elements']:
            # elements id填充计数器
            count_flag = max([int(x.get('elem-id')) for x in back_oms['elements'] if x.get('elem-id')])
        if kwargs.get('add_detail_ip'):
            oms = copy.deepcopy(back_oms)
            # 先检查是否有重复条目
            for _cmd in kwargs['ip_mask']:
                # if _cmd['type'] == 'subnet':
                _tmp_ip = IPNetwork(_cmd)  # demo: 10.254.0.1/24
                tmp_ip = _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                for elem in oms['elements']:
                    if elem.get('address-ipv4') == tmp_ip:
                        kwargs['ip_mask'].remove(_cmd)
                        # raise RuntimeError("安全纳管-华为-地址组-增加IP条目，不允许重复条目")
            # 继续执行拼接
            for _cmd in kwargs['ip_mask']:
                # 计数器提前+1 等于现有配置的末尾追加
                count_flag += 1
                _tmp_ip = IPNetwork(_cmd)  # demo: 10.254.0.1/24
                oms['elements'].append({
                    "elem-id": str(count_flag),
                    "address-ipv4": _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                })
            oms['@nc:operation'] = 'replace'
            back_oms['@nc:operation'] = 'replace'
            return oms, back_oms
        elif kwargs.get('add_detail_range'):
            oms = copy.deepcopy(back_oms)
            # 先检查是否有重复条目
            for elem in oms['elements']:
                if elem.get('start-ipv4') == kwargs['range_start'] and elem.get('end-ipv4') == kwargs['range_end']:
                    raise RuntimeError("安全纳管-华为-地址组-增加range条目，不允许重复条目")
            # 继续执行拼接
            count_flag += 1
            oms['elements'].append({
                "elem-id": str(count_flag),
                "start-ipv4": kwargs['range_start'],
                "end-ipv4": kwargs['range_end']
            })
            oms['@nc:operation'] = 'replace'
            back_oms['@nc:operation'] = 'replace'
            return oms, back_oms
        elif kwargs.get('del_detail_ip'):
            oms = copy.deepcopy(back_oms)
            for _cmd in kwargs['ip_mask']:
                # if _cmd['type'] == 'subnet':
                _tmp_ip = IPNetwork(_cmd)  # demo: 10.254.0.1/24
                tmp_ip = _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                for elem in oms['elements']:
                    if elem.get('address-ipv4') == tmp_ip:
                        oms['elements'].remove(elem)
            # 重新排列一次elem-id
            count_flag = 0
            for elem in oms['elements']:
                elem['elem-id'] = count_flag
                count_flag += 1
            oms['@nc:operation'] = 'replace'
            back_oms['@nc:operation'] = 'replace'
            return oms, back_oms
        elif kwargs.get('del_detail_range'):
            oms = copy.deepcopy(back_oms)
            for elem in oms['elements']:
                if elem.get('start-ipv4') == kwargs['range_start'] and elem.get('end-ipv4') == kwargs['range_end']:
                    oms['elements'].remove(elem)
            # 重新排列一次elem-id
            count_flag = 0
            for elem in oms['elements']:
                elem['elem-id'] = count_flag
                count_flag += 1
            oms['@nc:operation'] = 'replace'
            back_oms['@nc:operation'] = 'replace'
            return oms, back_oms
        elif kwargs.get('add_object'):
            count_flag = 0
            oms = {'vsys': 'public', 'name': kwargs['name'], 'desc': kwargs.get('description'),
                   'elements': []}
            if kwargs.get('ip_mask'):
                for _cmd in kwargs['ip_mask']:
                    _tmp_ip = IPNetwork(_cmd)  # demo: 10.254.0.1/24
                    oms['elements'].append({
                        "elem-id": str(count_flag),
                        "address-ipv4": _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                    })
                    # 计数器后+1 从0开始计数，用于新建
                    count_flag += 1
            if kwargs.get('range_start'):
                count_flag += 1
                oms['elements'].append({
                    "elem-id": str(count_flag),
                    "start-ipv4": kwargs['range_start'],
                    "end-ipv4": kwargs['range_end']
                })
            oms['@nc:operation'] = 'create'
            back_oms['@nc:operation'] = 'delete'
            return oms, back_oms
        elif kwargs.get('del_object'):
            oms = copy.deepcopy(back_oms)
            oms['@nc:operation'] = 'delete'
            back_oms['@nc:operation'] = 'create'
            return oms, back_oms
        return [], []

    # 山石服务对象操作V2
    def hillstone_service_detail(self, **kwargs):
        """
        ICMP TYPE
          3 Dest-Unreachable
          4 Source Quench
          5 Redirect
          8 Echo
          11 Time Exceeded
          12 Parameter Problem
          13 Timestamp
          15 information
          any Only used to config timeout for predefined service "ICMP"
        """
        name = F"service {kwargs['name']}"
        # 新增服务对象
        if kwargs.get('add_object'):
            self.cmds += [name]
            self.back_off_cmds += [F"no {name}"]
            for _ser in kwargs['objects']:
                """
                [
                    {
                        "add_detail":true,
                        "protocol":"TCP", 
                        "start_src_port":1, 
                        "end_src_port":65535,
                        "start_dst_port":8443,
                        "end_dst_port":8443,
                    }
                ]
                """
                if _ser.get('add_detail'):
                    if _ser['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    elif _ser['start_src_port'] == 1 and _ser['end_src_port'] == 65535:
                        self.cmds += [
                            F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} {_ser['end_dst_port']}"]
                    else:
                        self.cmds += [
                            F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} {_ser['end_dst_port']} "
                            F"src-port {_ser['start_src_port']} {_ser['end_src_port']}"]
        # 编辑
        elif kwargs.get('edit_object'):
            self.cmds += [name]
            self.back_off_cmds += [name]
            for _ser in kwargs['objects']:
                """
                [
                    {
                        "add_detail":true,
                        "protocol":"TCP", 
                        "start_src_port":1, 
                        "end_src_port":65535,
                        "start_dst_port":8443,
                        "end_dst_port":8443,
                    }
                ]
                """
                if _ser.get('add_detail'):
                    if _ser['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                        self.back_off_cmds += ["no icmp type any"]
                    elif _ser['start_src_port'] == 1 and _ser['end_src_port'] == 65535:
                        self.cmds += [F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                      F"{_ser['end_dst_port']}"]
                        self.back_off_cmds += [F"no {_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                               F"{_ser['end_dst_port']}"]
                    else:
                        self.cmds += [F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                      F"{_ser['end_dst_port']} "
                                      F"src-port {_ser['start_src_port']} {_ser['end_src_port']}"]
                        self.back_off_cmds += [F"no {_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                               F"{_ser['end_dst_port']} src-port {_ser['start_src_port']} "
                                               F"{_ser['end_src_port']}"]
                elif _ser.get('del_detail'):
                    if _ser['protocol'] == 'ICMP':
                        self.cmds += ["no icmp type 8"]
                        self.back_off_cmds += ["icmp type 8"]
                    elif _ser['start_src_port'] == 1 and _ser['end_src_port'] == 65535:
                        self.cmds += [F"no {_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                      F"{_ser['end_dst_port']}"]
                        self.back_off_cmds += [F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                               F"{_ser['end_dst_port']}"]
                    else:
                        self.cmds += [F"no {_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                      F"{_ser['end_dst_port']} "
                                      F"src-port {_ser['start_src_port']} {_ser['end_src_port']}"]
                        self.back_off_cmds += [F"{_ser['protocol'].lower()} dst-port {_ser['start_dst_port']} "
                                               F"{_ser['end_dst_port']} src-port {_ser['start_src_port']} "
                                               F"{_ser['end_src_port']}"]
        # 删除
        elif kwargs.get('del_object'):
            self.cmds += [F"no {name}"]
            self.back_off_cmds += [F"{name}"]
            res = service_mongo.find(query_dict=dict(hostip=kwargs['hostip'], name=kwargs['name']), fileds={'_id': 0})
            if not res:
                raise RuntimeError("hillstone_service_detail" + ' 未获取到现有的配置，无法生成回退命令')
            for i in res[0]['items']:
                if all(k in i for k in ("src-port-max", "src-port-min", "dst-port-max", "dst-port-min")):
                    self.back_off_cmds += [F"{i['protocol']} dst-port {i['dst-port-min']} {i['dst-port-max']} "
                                           F"src-port {i['src-port-min']} {i['src-port-max']}"]
                elif all(k in i for k in ("src-port-min", "dst-port-max", "dst-port-min")):
                    self.back_off_cmds += [F"{i['protocol']} dst-port {i['dst-port-min']} {i['dst-port-max']} "
                                           F"src-port {i['src-port-min']}"]
                elif all(k in i for k in ("dst-port-max", "dst-port-min")):
                    self.back_off_cmds += [F"{i['protocol']} dst-port {i['dst-port-min']} {i['dst-port-max']}"]
                elif "dst-port-min" in i.keys():
                    self.back_off_cmds += [F"{i['protocol']} dst-port {i['dst-port-min']}"]
        else:
            raise RuntimeError("FirewallMain.hillstone_service_detail 未匹配到method参数")
        return self.cmds, self.back_off_cmds

    # 华三服务对象操作V2
    def h3c_service_detail(self, **kwargs):
        name = kwargs['name']
        # 新建服务对象
        # 新建服务对象需要分两段下发，第一次建组，第二次创建组成员
        if kwargs.get('add_object'):
            Obj = []
            for _ser in kwargs['objects']:
                """
                [
                    {
                        "add_detail":true,
                        "protocol":"TCP", 
                        "start_src_port":1, 
                        "end_src_port":65535,
                        "start_dst_port":8443,
                        "end_dst_port":8443,
                    }
                ]
                """
                if _ser.get('add_detail'):
                    if _ser['protocol'] == 'ICMP':
                        Obj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='2',  # ICMP ANY
                        ))
                    elif _ser['protocol'] == 'TCP':
                        Obj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='3',
                            StartSrcPort=_ser['start_src_port'],
                            EndSrcPort=_ser['end_src_port'],
                            StartDestPort=_ser['start_dst_port'],
                            EndDestPort=_ser['end_dst_port'],
                        ))
                    elif _ser['protocol'] == 'UDP':
                        Obj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='4',
                            StartSrcPort=_ser['start_src_port'],
                            EndSrcPort=_ser['end_src_port'],
                            StartDestPort=_ser['start_dst_port'],
                            EndDestPort=_ser['end_dst_port'],
                        ))
            oms = [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'ServGroups': {
                        'Group':
                            {
                                'Name': kwargs['name']
                            }
                    }
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'ServObjs':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'Obj': Obj
                        }
                }
            ]
            if kwargs.get('description'):
                oms[0]['ServObjs']['Group']['Description'] = kwargs['description']
            # 新增服务对象对应回退操作是删除服务对象，无需关心包含条目变动
            back_oms = {
                'ServObjs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'Obj': Obj
                    }
            }
            return oms, back_oms
        # 编辑
        elif kwargs.get('edit_object'):
            addObj = []  # 新增条目
            # back_addObj = []  # 回退新增条目
            delObj = []  # 删除
            back_delObj = []  # 回退删除条目
            oms = []  # 请求体
            back_oms = []
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            for _ser in kwargs['objects']:
                """
                [
                    {
                        "add_detail":true,
                        "protocol":"TCP", 
                        "start_src_port":1, 
                        "end_src_port":65535,
                        "start_dst_port":8443,
                        "end_dst_port":8443,
                    }
                ]
                """
                if _ser.get('add_detail'):
                    if _ser['protocol'] == 'ICMP':
                        addObj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='2',  # ICMP ANY
                        ))
                    elif _ser['protocol'] == 'TCP':
                        addObj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='3',
                            StartSrcPort=_ser['start_src_port'],
                            EndSrcPort=_ser['end_src_port'],
                            StartDestPort=_ser['start_dst_port'],
                            EndDestPort=_ser['end_dst_port'],
                        ))
                    elif _ser['protocol'] == 'UDP':
                        addObj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='4',
                            StartSrcPort=_ser['start_src_port'],
                            EndSrcPort=_ser['end_src_port'],
                            StartDestPort=_ser['start_dst_port'],
                            EndDestPort=_ser['end_dst_port'],
                        ))
                if _ser.get('del_detail'):
                    if _ser.get('ID'):
                        _OMS = {
                            'ServObjs':
                                {
                                    'Obj':
                                        {
                                            'Group': name,
                                            'ID': _ser['ID'],
                                            'Type': None,
                                            'Protocol': None,
                                            'StartSrcPort': None,
                                            'StartDestPort': None,
                                            'EndDestPort': None,
                                            'ICMPType': None,
                                            'ICMPCode': None,
                                            'NestedGroup': None
                                        }
                                }
                        }
                        del_oms = device.get_oms_objs(_OMS)
                        if del_oms:
                            if del_oms['ServObjs']['Obj']:
                                for i in del_oms['ServObjs']['Obj']:
                                    delObj.append(dict(
                                        Group=name,
                                        ID=i['ID'],
                                    ))
                                    # 回退对应新增，但此处暂时没改ID为自动分配
                                    back_delObj.append(i)
                        # 此处改ID为自动分配
                        for x in back_delObj:
                            x['ID'] = '4294967295'
            device.closed()
            if addObj:
                oms.append({
                    'ServObjs':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'Obj': addObj
                        }
                })
            if delObj:
                oms.append({
                    'ServObjs':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'remove',
                            'Obj': delObj
                        }
                })
            return oms, back_oms
        # 删除
        elif kwargs.get('del_object'):
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            OMS = {
                'ServGroups': {
                    'Group': {
                        'Name': kwargs['name'],
                        'Description': None
                    }
                },
                'ServObjs':
                    {
                        'Obj': {
                            'Group': kwargs['name'],
                            'ID': None,
                            'Type': None,
                            'StartSrcPort': None,
                            'EndSrcPort': None,
                            'StartDestPort': None,
                            'EndDestPort': None,
                        }
                    }
            }
            back_oms = device.get_oms_objs(OMS)
            # 把ID字段置换成系统识别的自动分配专用ID
            if back_oms:
                if back_oms['ServObjs']['Obj']:
                    for i in back_oms['ServObjs']['Obj']:
                        i['ID'] = '4294967295'
            oms = {
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'remove',
                'ServGroups': {
                    'Group':
                        {
                            'Name': kwargs['name']
                        }
                },
            }
            device.closed()
            return oms, back_oms
        raise RuntimeError("FirewallMain.h3c_service_detail 未匹配到method参数")

    # 华为服务对象操作V2
    def huawei_service_detail(self, **kwargs):
        name = kwargs['name']
        description = kwargs.get('description')
        # 新建
        if kwargs.get('add_object'):
            Obj = []
            count_flag = 0  # elements id填充计数器
            for _ser in kwargs['objects']:
                """
                [
                    {
                        "add_detail":true,
                        "protocol":"TCP", 
                        "start_src_port":1, 
                        "end_src_port":65535,
                        "start_dst_port":8443,
                        "end_dst_port":8443,
                    }
                ]
                """
                if _ser.get('add_detail'):
                    if _ser['protocol'] in ['TCP', 'UDP']:
                        Obj.append({
                            "id": str(count_flag),
                            _ser['protocol'].lower(): {
                                'source-port': {'start': str(_ser['start_src_port']), 'end': str(_ser['end_src_port'])},
                                'dest-port': {'start': str(_ser['start_dst_port']), 'end': str(_ser['end_dst_port'])}
                            }
                        })
                    elif _ser['protocol'] == 'ICMP':
                        Obj.append({
                            "id": str(count_flag),
                            "icmp-name": "echo"
                        })
                        count_flag += 1
                        Obj.append({
                            "id": str(count_flag),
                            "icmp-name": "echo-reply"
                        })
                    count_flag += 1
            if Obj:
                oms = {
                    '@nc:operation': 'create',
                    'vsys': 'public',
                    'name': name,
                    'items': Obj
                }
                back_oms = {
                    '@nc:operation': 'delete',
                    'vsys': 'public',
                    'name': name,
                    'items': Obj,
                }
                if description is not None:
                    oms['desc'] = description
                    back_oms['desc'] = description
                return oms, back_oms
        # 编辑
        elif kwargs.get('edit_object'):
            oms = []
            back_oms = []
            addObj = []
            delObj = []
            count_flag = 1  # elements id填充计数器 次数设为1 方便后面max取当前最大再相加
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _service_req = device.get_service_set()
            device.closed()
            if _service_req:
                _service_res = [x for x in _service_req if x['name'] == name]
                _service_res = _service_res[0]
                back_oms = copy.deepcopy(_service_res)
                back_oms['@nc:operation'] = 'replace'
                # 当服务对象条目只有一条时，items字段会是dict，大于1条就是list
                # 这里需要强制统一类型
                if isinstance(_service_res['items'], dict):
                    addObj += [_service_res['items']]
                else:
                    addObj += _service_res['items']
                for _ser in kwargs['objects']:
                    # 增加条目
                    if _ser.get('add_detail'):
                        # 求最大id编号
                        count_flag += max([x['id'] for x in addObj])
                        if _ser['protocol'] in ['TCP', 'UDP']:
                            addObj.append({
                                "id": str(count_flag),
                                _ser['protocol'].lower(): {
                                    'source-port': {'start': str(_ser['start_src_port']),
                                                    'end': str(_ser['end_src_port'])},
                                    'dest-port': {'start': str(_ser['start_dst_port']),
                                                  'end': str(_ser['end_dst_port'])}
                                }
                            })
                        elif _ser['protocol'] == 'ICMP':
                            addObj.append({
                                "id": str(count_flag),
                                "icmp-name": "echo"
                            })
                            count_flag += 1
                            addObj.append({
                                "id": str(count_flag),
                                "icmp-name": "echo-reply"
                            })
                    # 删除条目
                    if _ser.get('del_detail'):
                        if _ser.get('ID'):
                            for obj in addObj:
                                if obj['id'] == _ser['ID']:
                                    delObj.append(obj)
                if addObj:
                    _tmp = {
                        '@nc:operation': 'replace',
                        'vsys': 'public',
                        'name': name,
                        'items': addObj
                    }
                    if description is not None:
                        _tmp['desc'] = description
                    oms.append(_tmp)
                if delObj:
                    _tmp = {
                        '@nc:operation': 'delete',
                        'vsys': 'public',
                        'name': name,
                        'items': delObj
                    }
                    if description is not None:
                        _tmp['desc'] = description
                    oms.append(_tmp)
                return oms, back_oms
            else:
                raise RuntimeError("FirewallMain.huawei_service_detail 没能获取到待编辑的对象")
        # 删除
        elif kwargs.get('del_object'):
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _service_req = device.get_service_set()
            device.closed()
            if _service_req:
                _service_res = [x for x in _service_req if x['name'] == name]
                oms = _service_res[0]
                oms['@nc:operation'] = 'delete'
                back_oms = copy.deepcopy(oms)
                back_oms['@nc:operation'] = 'create'
                return oms, back_oms
            else:
                raise RuntimeError("FirewallMain.huawei_service_detail 没能获取到待删除的对象")

    # 山石DNAT操作V2
    def hillstone_dnat_detail(self, **kwargs):
        # Version 5.5 SG6000-X7180-5.5R6P15-v6.bin 2021/01/15 18:55:45 这个版本from 和 to 需要指定address-book 和 ip
        soft_version = ''
        if self.dev_infos['soft_version'].find('5.5R6') != -1:
            soft_version = '5.5R6'
        elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-2-5.0R3P9.bin') != -1:
            soft_version = 'Version 5.0 SG6000-M-2-5.0R3P9.bin'
        # 新增DNAT规则
        if kwargs.get('add_object'):
            service = kwargs['service']
            trans_to = kwargs['trans_to']
            if 'custom_slb' in trans_to.keys():
                self.back_off_cmds += ['no slb-server-pool ' + kwargs['name']]
                _vars = {
                    "slb_name": kwargs['name'],
                    "hostip": kwargs['hostip'],
                    "objects": trans_to['custom_slb'],  # list
                    "monitor": "track-tcp",
                    "load_balance": "weighted-least-connection sticky",
                    'soft_version': soft_version
                }
                path = 'config_templates/hillstone/slb_server_pool.j2'
                data_to_parse = default_storage.open(path).read().decode('utf-8')
                template = jinja2.Template(data_to_parse)
                tmp_commands = template.render(_vars)
                # 去除空字符串命令
                self.cmds += [x.lstrip() for x in tmp_commands.split('\n') if len(x.strip()) != 0]
            # 直接引用服务名
            if 'name' in service.keys():
                _service = service['name']
            elif 'multi' in service.keys():
                # 服务名
                # _service = "SD_multi_{protocol}_{start_port}_{end_port}".format(
                #     protocol=service['multi'][0]['protocol'].upper(),
                #     start_port=str(service['multi'][0]['start_port']),
                #     end_port=str(service['multi'][0]['end_port'])
                # )
                _service = "auto_{}".format(str(int(time.time())))
                self.cmds += [F"service {_service}"]
                self.back_off_cmds += [F"no service {_service}"]
                for _sub_ser in service['multi']:
                    if all(k in _sub_ser for k in ("protocol", "start_port", "end_port")):
                        if _sub_ser['protocol'] == 'ICMP':
                            self.cmds += ["icmp type 8"]
                        else:
                            self.cmds += [
                                F"{_sub_ser['protocol'].lower()} dst-port {_sub_ser['start_port']} {_sub_ser['end_port']}"]
                self.cmds += ["exit"]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                _query_service = MongoNetOps.hillstone_service_query(hostip=self.dev_info['ip'],
                                                                     protocol=service['protocol'],
                                                                     start_port=service['start_port'],
                                                                     end_port=service['end_port'])
                _service = None
                # 如果查询到系统中已经存在的服务，如果系统有匹配服务，则引用并且不要写入回退命令，防止回退操作删除服务
                if _query_service:
                    if 'items' in _query_service.keys():
                        # 必须唯一匹配，有的现有的服务，也是一个集合(定义了多个协议端口)，但我们需要仅仅匹配一个
                        if len(_query_service['items']) == 1:
                            print('_service赋值', _service)
                            _service = _query_service['name']
                if _service is None:
                    # 服务名
                    _service = "auto_{}_{}_{}".format(str(service['start_port']), str(service['end_port']),
                                                      str(int(time.time())))
                    self.cmds += [F"service {_service}"]
                    self.back_off_cmds += [F"no service {_service}"]
                    if service['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    else:
                        self.cmds += [
                            F"{service['protocol'].lower()} dst-port {service['start_port']} {service['end_port']}"]
                    self.cmds += ["exit"]
            else:
                raise ValueError("service不符合格式，山石service字段只支持name")
            # 不允许公网服务端口是范围且同时指定内网端口的情况
            if all(k in service for k in ("protocol", "start_port", "end_port")) and kwargs.get('port') is not None:
                if service['start_port'] != service['end_port']:
                    raise RuntimeError('山石网科，公网发布，不允许公网服务端口是范围且同时指定内网端口的情况')
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs.get('id'),  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'ingress_interface': kwargs.get('ingress_interface'),  # 指定匹配该 dnat 规则的入接口
                'insert': kwargs.get('insert'),  # [before id | after id | top]
                'from': kwargs.get('from'),  # {'address_book': 'address-book'} | {'ip':'A.B.C.D '} | {'any': True}
                'to': kwargs['to'],  # {'object': 'address-book'} | {'ip':'A.B.C.D'}
                'service': _service,  # 服务对象名
                'trans_to': kwargs.get('trans_to'),
                # {'ip':'A.B.C.D '}|{'slb_server_pool':'slbname'}|{'address_book':'10.103.65.100'}
                'port': kwargs.get('port'),  # 映射端口
                'load_balance': kwargs.get('load_balance'),  # 是否启用，boolean
                'log': kwargs.get('log'),  # log  # 是否启用，boolean
                'soft_version': soft_version,  # 版本区分
                'track_tcp': kwargs.get('track_tcp'),  # tcp 监测
                'track_ping': kwargs.get('track_ping'),  # ping 监测
                # 'group': '',  # 待定，默认为HA组0
                # 'disable': '',  # 5.0不支持
                # 'description': ''  # 5.0不支持
            }
            if 'custom_slb' in trans_to.keys():
                _vars['slb_name'] = kwargs['name']
            # print('_vars', _vars)
            path = 'config_templates/hillstone/hillstone_dnat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            self.cmds += [' '.join(tmp_commands)]
            return self.cmds, self.back_off_cmds
        # 编辑DNAT规则
        elif kwargs.get('edit_object'):
            service = kwargs['service']
            if 'name' in service.keys():
                service = service['name']
            else:
                raise ValueError("service不符合格式，山石service字段只支持name")
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs.get('id'),  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'ingress_interface': kwargs.get('ingress_interface'),  # 指定匹配该 dnat 规则的入接口
                'insert': kwargs.get('insert'),  # [before id | after id | top]
                'from': kwargs.get('from'),  # {'address-book': 'address-book'} | {'ip':'A.B.C.D/M '} | {'any': True}
                'to': kwargs['to'],  # {'object': 'address-book'} | {'ip':'A.B.C.D/M' A.B.C.D}
                'service': service,  # 服务对象名
                'trans_to': kwargs.get('trans_to'),
                # {'ip':'A.B.C.D '}|{'slb_server_pool':'slbname'}|{'address_book':'10.103.65.100'}
                'port': kwargs.get('port'),  # 映射端口
                'load_balance': kwargs.get('load_balance'),  # 是否启用，boolean
                'log': kwargs.get('log'),  # log  # 是否启用，boolean
                'soft_version': soft_version,  # 版本区分
                'track_tcp': kwargs.get('track_tcp'),  # tcp 监测
                'track_ping': kwargs.get('track_ping'),  # ping 监测
                # 'group': '',  # 待定，默认为HA组0
                # 'disable': '',  # 5.0不支持
                # 'description': '' # 5.0不支持
            }
            path = 'config_templates/hillstone/hillstone_dnat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            self.cmds += ' '.join(tmp_commands)
            before_cmds = ['show configuration | begin dnatrule']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_dnat_config_before(rule_id=kwargs['id'], path=paths[0])
                if "command" in before_ttp_res.keys():
                    self.back_off_cmds += [before_ttp_res['command']]
                    self.cmds += ['no dnatrule id ' + kwargs['id']]
                    return self.cmds, self.back_off_cmds
                else:
                    raise RuntimeError("hillstone_dnat编辑对象失败:未能生成回退命令,ttp解析失败")
        # 删除DNAT规则
        elif kwargs.get('del_object'):
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            before_cmds = ['show configuration | begin dnatrule']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_dnat_config_before(rule_id=kwargs['id'], path=paths[0])
                if "command" in before_ttp_res.keys():
                    self.back_off_cmds += [before_ttp_res['command']]
                    self.cmds += ['no dnatrule id ' + kwargs['id']]
                    return self.cmds, self.back_off_cmds
                else:
                    raise RuntimeError("hillstone_dnat删除对象失败:未能生成回退命令,ttp解析失败")
        # 移动DNAT规则
        elif kwargs.get('sort_object'):
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs['id'],  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'insert': kwargs['insert']  # before id | after id | top | bottom
            }
            print('_vars', _vars)
            path = 'config_templates/hillstone/move_dnat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            self.cmds += [template.render(_vars)]
            self.back_off_cmds += ['dnatrule move {} bottom'.format(kwargs['id'])]
            return self.cmds, self.back_off_cmds
        else:
            raise RuntimeError("FirewallMain.hillstone_dnat_detail 未匹配到method参数")

    # 山石SNAT操作V2
    def hillstone_snat_detail(self, **kwargs):
        # Version 5.5 SG6000-X7180-5.5R6P15-v6.bin 2021/01/15 18:55:45 这个版本from 和 to 需要指定address-book 和 ip
        soft_version = ''
        if self.dev_infos['soft_version'].find('5.5R6') != -1:
            soft_version = '5.5R6'
        elif self.dev_infos['soft_version'].find('Version 5.5 SG6000') != -1:
            soft_version = '5.5R6'
        elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-2-5.0R3P9.bin') != -1:
            soft_version = 'Version 5.0 SG6000-M-2-5.0R3P9.bin'
        # 新增SNAT规则
        if kwargs.get('add_object'):
            service = kwargs['service']
            # 直接引用服务名
            if 'name' in service.keys():
                _service = service['name']
            elif 'multi' in service.keys():
                # 服务名
                # _service = "SD_multi_{protocol}_{start_port}_{end_port}".format(
                #     protocol=service['multi'][0]['protocol'].upper(),
                #     start_port=str(service['multi'][0]['start_port']),
                #     end_port=str(service['multi'][0]['end_port'])
                # )
                _service = "auto_{}".format(str(int(time.time())))
                self.cmds += [F"service {_service}"]
                self.back_off_cmds += [F"no service {_service}"]
                for _sub_ser in service['multi']:
                    if all(k in _sub_ser for k in ("protocol", "start_port", "end_port")):
                        if _sub_ser['protocol'] == 'ICMP':
                            self.cmds += ["icmp type 8"]
                        else:
                            self.cmds += [
                                F"{_sub_ser['protocol'].lower()} dst-port {_sub_ser['start_port']} {_sub_ser['end_port']}"]
                self.cmds += ["exit"]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                _query_service = MongoNetOps.hillstone_service_query(hostip=self.dev_info['ip'],
                                                                     protocol=service['protocol'],
                                                                     start_port=service['start_port'],
                                                                     end_port=service['end_port'])
                _service = None
                # 如果查询到系统中已经存在的服务，如果系统有匹配服务，则引用并且不要写入回退命令，防止回退操作删除服务
                if _query_service:
                    if 'items' in _query_service.keys():
                        # 必须唯一匹配，有的现有的服务，也是一个集合(定义了多个协议端口)，但我们需要仅仅匹配一个
                        if len(_query_service['items']) == 1:
                            print('_service赋值', _service)
                            _service = _query_service['name']
                if _service is None:
                    # 服务名
                    _service = "auto_{}_{}_{}".format(str(service['start_port']), str(service['end_port']),
                                                      str(int(time.time())))
                    self.cmds += [F"service {_service}"]
                    self.back_off_cmds += [F"no service {_service}"]
                    if service['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    else:
                        self.cmds += [
                            F"{service['protocol'].lower()} dst-port {service['start_port']} {service['end_port']}"]
                    self.cmds += ["exit"]
            else:
                raise ValueError("service不符合格式，山石service字段只支持name和定义服务对象")
            # 不允许公网服务端口是范围且同时指定内网端口的情况
            if all(k in service for k in ("protocol", "start_port", "end_port")) and kwargs.get('port') is not None:
                if service['start_port'] != service['end_port']:
                    raise RuntimeError('山石网科，公网发布，不允许公网服务端口是范围且同时指定内网端口的情况')
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs.get('id'),  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'ingress_interface': kwargs['ingress']['name'],  # 指定匹配该 snat 规则的入接口
                'insert': kwargs.get('insert', ''),  # [before id | after id | top]
                'from': kwargs.get('from', ''),  # {'object': 'address-book'} | {'ip':'A.B.C.D '} | {'any': True}
                'to': kwargs.get('to', ''),  # {'object': 'address-book'} | {'ip':'A.B.C.D'}
                'service': _service,  # 服务对象名
                'trans_to': kwargs.get('trans_to', ''),
                'egress_interface': kwargs['egress']['name'],
                'nat_mode': kwargs.get('nat_mode'),  # static|dynamicip|dynamicport[sticky]
                'log': kwargs.get('log'),  # log  # 是否启用，boolean
                'soft_version': soft_version,  # 版本区分
                'track_tcp': kwargs.get('track_tcp'),  # tcp 监测
                'track_ping': kwargs.get('track_ping'),  # ping 监测
                # 'group': '',  # 待定，默认为HA组0
                # 'disable': '',  # 5.0不支持
                # 'description': ''  # 5.0不支持
            }
            print('_vars', _vars)
            path = 'config_templates/hillstone/hillstone_snat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            self.cmds += [' '.join(tmp_commands)]
            return self.cmds, self.back_off_cmds
        # 编辑SNAT规则
        elif kwargs.get('edit_object'):
            service = kwargs['service']
            # 直接引用服务名
            if 'name' in service.keys():
                _service = service['name']
            elif 'multi' in service.keys():
                # 服务名
                # _service = "SD_multi_{protocol}_{start_port}_{end_port}".format(
                #     protocol=service['multi'][0]['protocol'].upper(),
                #     start_port=str(service['multi'][0]['start_port']),
                #     end_port=str(service['multi'][0]['end_port'])
                # )
                _service = "auto_{}".format(str(int(time.time())))
                self.cmds += [F"service {_service}"]
                self.back_off_cmds += [F"no service {_service}"]
                for _sub_ser in service['multi']:
                    if all(k in _sub_ser for k in ("protocol", "start_port", "end_port")):
                        if _sub_ser['protocol'] == 'ICMP':
                            self.cmds += ["icmp type 8"]
                        else:
                            self.cmds += [
                                F"{_sub_ser['protocol'].lower()} dst-port {_sub_ser['start_port']} {_sub_ser['end_port']}"]
                self.cmds += ["exit"]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                _query_service = MongoNetOps.hillstone_service_query(hostip=self.dev_info['ip'],
                                                                     protocol=service['protocol'],
                                                                     start_port=service['start_port'],
                                                                     end_port=service['end_port'])
                _service = None
                # 如果查询到系统中已经存在的服务，如果系统有匹配服务，则引用并且不要写入回退命令，防止回退操作删除服务
                if _query_service:
                    if 'items' in _query_service.keys():
                        # 必须唯一匹配，有的现有的服务，也是一个集合(定义了多个协议端口)，但我们需要仅仅匹配一个
                        if len(_query_service['items']) == 1:
                            print('_service赋值', _service)
                            _service = _query_service['name']
                if _service is None:
                    # 服务名
                    _service = "auto_{}_{}_{}".format(str(service['start_port']), str(service['end_port']),
                                                      str(int(time.time())))
                    self.cmds += [F"service {_service}"]
                    self.back_off_cmds += [F"no service {_service}"]
                    if service['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    else:
                        self.cmds += [
                            F"{service['protocol'].lower()} dst-port {service['start_port']} {service['end_port']}"]
                    self.cmds += ["exit"]
            else:
                raise ValueError("service不符合格式，山石service字段只支持name和定义服务对象")
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs.get('id'),  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'ingress_interface': kwargs['ingress']['name'],  # 指定匹配该 snat 规则的入接口
                'insert': kwargs.get('insert', ''),  # [before id | after id | top]
                'from': kwargs.get('from', ''),  # {'address_book': 'address-book'} | {'ip':'A.B.C.D '} | {'any': True}
                'to': kwargs.get('to', ''),  # {'object': 'address-book'} | {'ip':'A.B.C.D'}
                'service': _service,  # 服务对象名
                'trans_to': kwargs.get('trans_to', ''),
                'egress_interface': kwargs['egress']['name'],
                'nat_mode': kwargs.get('nat_mode'),  # static|dynamicip|dynamicport[sticky]
                'log': kwargs.get('log'),  # log  # 是否启用，boolean
                'soft_version': soft_version,  # 版本区分
                'track_tcp': kwargs.get('track_tcp'),  # tcp 监测
                'track_ping': kwargs.get('track_ping'),  # ping 监测
                # 'group': '',  # 待定，默认为HA组0
                # 'disable': '',  # 5.0不支持
                # 'description': ''  # 5.0不支持
            }
            path = 'config_templates/hillstone/hillstone_dnat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            self.cmds += ' '.join(tmp_commands)
            before_cmds = ['show configuration | begin snat']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_snat_config_before(rule_id=kwargs['id'], path=paths[0])
                if "command" in before_ttp_res.keys():
                    self.back_off_cmds += [before_ttp_res['command']]
                    # self.back_off_cmds += ['no snatrule id ' + kwargs['id']]
                    return self.cmds, self.back_off_cmds
                else:
                    raise RuntimeError("hillstone_dnat删除对象失败:未能生成回退命令,ttp解析失败")
        # 删除SNAT规则
        elif kwargs.get('del_object'):
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            before_cmds = ['show configuration | begin snat']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_snat_config_before(rule_id=kwargs['id'], path=paths[0])
                if "command" in before_ttp_res.keys():
                    self.back_off_cmds += [before_ttp_res['command']]
                    self.cmds += ['no snatrule id ' + kwargs['id']]
                    return self.cmds, self.back_off_cmds
                else:
                    raise RuntimeError("hillstone_snat删除对象失败:未能生成回退命令,ttp解析失败")
        # 移动SNAT规则
        elif kwargs.get('sort_object'):
            self.cmds += ['ip vrouter trust-vr']
            self.back_off_cmds += ['ip vrouter trust-vr']
            _vars = {
                'id': kwargs['id'],  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
                'insert': kwargs['insert']  # before id | after id | top | bottom
            }
            print('_vars', _vars)
            path = 'config_templates/hillstone/move_snat.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            self.cmds += [template.render(_vars)]
            self.back_off_cmds += ['snatrule move {} bottom'.format(kwargs['id'])]
            return self.cmds, self.back_off_cmds
        else:
            raise RuntimeError("FirewallMain.hillstone_snat_detail 未匹配到method参数")

    # 山石安全策略操作V2
    def hillstone_sec_policy_detail(self, **kwargs):
        soft_version = ''
        if self.dev_infos['soft_version'].find('5.5R6') != -1:
            soft_version = '5.5R6'
        # elif self.dev_infos['soft_version'].find('Version 5.5 SG6000') != -1:
        #     soft_version = '5.5R6'
        elif self.dev_infos['soft_version'].find('Version 5.0 SG6000-M-2-5.0R3P9.bin') != -1:
            soft_version = 'Version 5.0 SG6000-M-2-5.0R3P9.bin'
        self.cmds += ['policy-global']
        self.back_off_cmds += ['policy-global']
        # 新增
        if kwargs.get('add_object'):
            service_res = []
            service = kwargs['service']
            # 直接引用服务名
            if 'name' in service.keys():
                service_res += service['name']
            elif 'multi' in service.keys():
                # 服务名
                _service = "auto_{}".format(str(int(time.time())))
                self.cmds += [F"service {_service}"]
                self.back_off_cmds += [F"no service {_service}"]
                for _sub_ser in service['multi']:
                    if all(k in _sub_ser for k in ("protocol", "start_port", "end_port")):
                        if _sub_ser['protocol'] == 'ICMP':
                            self.cmds += ["icmp type 8"]
                        else:
                            self.cmds += [
                                F"{_sub_ser['protocol'].lower()} dst-port {_sub_ser['start_port']} {_sub_ser['end_port']}"]
                self.cmds += ["exit"]
                service_res += [_service]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                _query_service = MongoNetOps.hillstone_service_query(hostip=self.dev_info['ip'],
                                                                     protocol=service['protocol'],
                                                                     start_port=service['start_port'],
                                                                     end_port=service['end_port'])
                _service = None
                # 如果查询到系统中已经存在的服务，如果系统有匹配服务，则引用并且不要写入回退命令，防止回退操作删除服务
                if _query_service:
                    if 'items' in _query_service.keys():
                        # 必须唯一匹配，有的现有的服务，也是一个集合(定义了多个协议端口)，但我们需要仅仅匹配一个
                        if len(_query_service['items']) == 1:
                            print('_service赋值', _service)
                            _service = _query_service['name']
                if _service is None:
                    # 服务名
                    _service = "auto_{}_{}_{}".format(str(service['start_port']), str(service['end_port']),
                                                      str(int(time.time())))
                    self.cmds += [F"service {_service}"]
                    self.back_off_cmds += [F"no service {_service}"]
                    if service['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    else:
                        self.cmds += [
                            F"{service['protocol'].lower()} dst-port {service['start_port']} {service['end_port']}"]
                    self.cmds += ["exit"]
            else:
                raise ValueError("service不符合格式，山石service字段只支持name和定义服务对象")
            _vars = {
                'ops': 'create',
                'id': kwargs.get('id'),  # 如果不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID为已有的规则的ID，已有的规则会被覆盖。
                'name': kwargs['name'],  # 低版本不支持name
                'insert': kwargs.get('insert', ''),  # [before id | after id | top]
                'from': kwargs['from'],  # {'object': 'address-book'} | {'ip':'A.B.C.D '} | {'any': True}
                'to': kwargs['to'],  # {'object': 'address-book'} | {'ip':'A.B.C.D'}
                'service': service_res,  # 服务对象名
                'from_addr': kwargs['from_addr'],
                'to_addr': kwargs['to_addr'],
                'soft_version': soft_version,  # 版本区分
                'action': kwargs['action']
            }
            print('_vars', _vars)
            path = 'config_templates/hillstone/hillstone_sec_policy.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            self.cmds += [' '.join(tmp_commands)]
            return self.cmds, self.back_off_cmds
        elif kwargs.get('edit_object'):
            service = kwargs['service']
            # 直接引用服务名
            if 'name' in service.keys():
                _service = service['name']
            elif 'multi' in service.keys():
                # 服务名
                _service = "auto_{}".format(str(int(time.time())))
                self.cmds += [F"service {_service}"]
                self.back_off_cmds += [F"no service {_service}"]
                for _sub_ser in service['multi']:
                    if all(k in _sub_ser for k in ("protocol", "start_port", "end_port")):
                        if _sub_ser['protocol'] == 'ICMP':
                            self.cmds += ["icmp type 8"]
                        else:
                            self.cmds += [
                                F"{_sub_ser['protocol'].lower()} dst-port {_sub_ser['start_port']} {_sub_ser['end_port']}"]
                self.cmds += ["exit"]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                _query_service = MongoNetOps.hillstone_service_query(hostip=self.dev_info['ip'],
                                                                     protocol=service['protocol'],
                                                                     start_port=service['start_port'],
                                                                     end_port=service['end_port'])
                _service = None
                # 如果查询到系统中已经存在的服务，如果系统有匹配服务，则引用并且不要写入回退命令，防止回退操作删除服务
                if _query_service:
                    if 'items' in _query_service.keys():
                        # 必须唯一匹配，有的现有的服务，也是一个集合(定义了多个协议端口)，但我们需要仅仅匹配一个
                        if len(_query_service['items']) == 1:
                            print('_service赋值', _service)
                            _service = _query_service['name']
                if _service is None:
                    # 服务名
                    _service = "auto_{}_{}_{}".format(str(service['start_port']), str(service['end_port']),
                                                      str(int(time.time())))
                    self.cmds += [F"service {_service}"]
                    self.back_off_cmds += [F"no service {_service}"]
                    if service['protocol'] == 'ICMP':
                        self.cmds += ["icmp type 8"]
                    else:
                        self.cmds += [
                            F"{service['protocol'].lower()} dst-port {service['start_port']} {service['end_port']}"]
                    self.cmds += ["exit"]
            else:
                raise ValueError("service不符合格式，山石service字段只支持name和定义服务对象")
            _vars = {
                'ops': 'edit',
                'id': kwargs['id'],  # 如果不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID为已有的规则的ID，已有的规则会被覆盖。
                'name': kwargs['name'],  # 低版本不支持name
                'insert': kwargs.get('insert', ''),  # [before id | after id | top]
                'from': kwargs['from'],  # {'object': 'address-book'} | {'ip':'A.B.C.D '} | {'any': True}
                'to': kwargs['to'],  # {'object': 'address-book'} | {'ip':'A.B.C.D'}
                'service': _service,  # 服务对象名
                'from_addr': kwargs['from_addr'],
                'to_addr': kwargs['to_addr'],
                'soft_version': soft_version,  # 版本区分
                'action': kwargs['action']
            }
            print('_vars', _vars)
            path = 'config_templates/hillstone/hillstone_sec_policy.j2'
            data_to_parse = default_storage.open(path).read().decode('utf-8')
            template = jinja2.Template(data_to_parse)
            tmp_commands = template.render(_vars)
            tmp_commands = tmp_commands.split('\n')
            print([x.strip() for x in tmp_commands])
            self.cmds += [x.strip() for x in tmp_commands]
            before_cmds = ['show configuration policy']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_sec_policy_config_before(rule_id=kwargs['id'], path=paths[0])
                self.back_off_cmds += ["rule id {}".format(kwargs['id'])]
                self.back_off_cmds += before_ttp_res
                return self.cmds, self.back_off_cmds
            return self.cmds, self.back_off_cmds
        elif kwargs.get('del_object'):
            self.cmds += ["no rule id {}".format(kwargs['id'])]
            before_cmds = ['show configuration policy']
            paths = BatManMain.hillstone_send_cmds(*before_cmds, **self.dev_info)
            if isinstance(paths, list):
                before_ttp_res = HillstoneFsm.check_sec_policy_config_before(rule_id=kwargs['id'], path=paths[0])
                self.back_off_cmds += ["rule id {}".format(kwargs['id'])]
                self.back_off_cmds += before_ttp_res
                return self.cmds, self.back_off_cmds
            return self.cmds, self.back_off_cmds

    # 华三DNAT操作V2
    def h3c_dnat_detail(self, **kwargs):
        name = kwargs['name']
        # 新建DNAT规则
        if kwargs.get('add_object'):
            description = kwargs.get('description')
            service = kwargs['service']
            to = kwargs['to']
            trans_to = kwargs['trans_to']
            trans_port = kwargs.get('port')
            # 目的地址
            GlobalPolicyRuleDstObj = []
            oms = []
            back_oms = []
            _service_name = ''
            # 直接引用服务名
            if 'name' in service.keys():
                _service_name = service['name']
            elif 'multi' in service.keys():
                # 服务名
                # _service_name = "SD_multi_{protocol}_{start_port}_{end_port}".format(
                #     protocol=service['multi'][0]['protocol'].upper(),
                #     start_port=str(service['multi'][0]['start_port']),
                #     end_port=str(service['multi'][0]['end_port'])
                # )
                _service_name = "auto_{}".format(str(int(time.time())))
                Obj = []
                for _sub_ser in service['multi']:
                    if _sub_ser['protocol'] == 'TCP':
                        Obj.append(dict(
                            Group=_service_name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='3',
                            StartSrcPort='0',
                            EndSrcPort='65535',
                            StartDestPort=_sub_ser['start_port'],
                            EndDestPort=_sub_ser['end_port'],
                        ))
                    elif _sub_ser['protocol'] == 'UDP':
                        Obj.append(dict(
                            Group=_service_name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='4',
                            StartSrcPort='0',
                            EndSrcPort='65535',
                            StartDestPort=_sub_ser['start_port'],
                            EndDestPort=_sub_ser['end_port'],
                        ))
                oms += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'ServGroups': {
                                'Group':
                                    {
                                        'Name': _service_name
                                    }
                            }
                        },
                    },
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'ServObjs':
                                {
                                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                                    '@xc:operation': 'create',
                                    'Obj': Obj
                                }
                        }
                    }

                ]
                # 新增服务对象对应回退操作是删除服务对象，无需关心包含条目变动
                back_oms += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            'ServObjs':
                                {
                                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                                    '@xc:operation': 'remove',
                                    'Obj': Obj
                                }
                        }
                    }
                ]
            # 创建服务对象 判断系统预定义服务和已经定义的服务
            elif all(k in service for k in ("protocol", "start_port", "end_port")):
                Obj = []
                # 服务名
                # _service_name = "SD_multi_{protocol}_{start_port}_{end_port}".format(
                #     protocol=service['multi'][0]['protocol'].upper(),
                #     start_port=str(service['multi'][0]['start_port']),
                #     end_port=str(service['multi'][0]['end_port'])
                # )
                _service_name = "auto_{}".format(str(int(time.time())))
                if service['protocol'] == 'TCP':
                    Obj.append(dict(
                        Group=_service_name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='3',
                        StartSrcPort='0',
                        EndSrcPort='65535',
                        StartDestPort=service['start_port'],
                        EndDestPort=service['end_port'],
                    ))
                elif service['protocol'] == 'UDP':
                    Obj.append(dict(
                        Group=_service_name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='4',
                        StartSrcPort='0',
                        EndSrcPort='65535',
                        StartDestPort=service['start_port'],
                        EndDestPort=service['end_port'],
                    ))
                oms += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'ServGroups': {
                                'Group':
                                    {
                                        'Name': _service_name
                                    }
                            }
                        },
                    },
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'create',
                            'ServObjs':
                                {
                                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                                    '@xc:operation': 'create',
                                    'Obj': Obj
                                }
                        }
                    }

                ]
                # 新增服务对象对应回退操作是删除服务对象，无需关心包含条目变动
                back_oms += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        'OMS': {
                            'ServObjs':
                                {
                                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                                    '@xc:operation': 'remove',
                                    'Obj': Obj
                                }
                        }
                    }
                ]
            else:
                raise RuntimeError("service不符合格式，key name not match name or protocol")
            if 'object' in to.keys():
                GlobalPolicyRuleDstObj += [{
                    'RuleName': name,
                    'DstAddrType': '0',
                    'DstObjGrpList': {'DstIpObj': to['object']}
                }]
            elif 'ip' in to.keys():
                GlobalPolicyRuleDstObj += [{
                    'RuleName': name,
                    'DstAddrType': '1',
                    'DstIPList': {'DstIP': [to['ip']]}
                }]
            else:
                raise ValueError("to不符合格式，key name not match object or ip")
            # 转换后的内网地址
            TransDstIP = ''
            if 'ip' in trans_to.keys():
                TransDstIP = trans_to['ip']
            else:
                raise RuntimeError("trans_to不符合格式，华三trans_to字段只支持ip，不支持地址对象和SLB")
            GlobalPolicyRuleMembers = {
                'Rule': {
                    'RuleName': name,
                    'TransMode': '1',
                    'SrcZoneList': {'SrcZone': 'Untrust'},  # 源安全域
                    'TransDstType': '0',
                    'TransDstIP': TransDstIP,
                    'Disable': False,
                    'Counting': True
                }
            }
            if description:
                GlobalPolicyRuleMembers['Rule']['Description'] = description
            if isinstance(trans_port, int):
                GlobalPolicyRuleMembers['Rule']['TransDstPort'] = trans_port
            config_data = [
                {
                    'GlobalPolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                },
                {
                    'GlobalPolicyRuleMembers': GlobalPolicyRuleMembers
                },
                {
                    'GlobalPolicyRuleDstObj': {
                        'Rule': GlobalPolicyRuleDstObj
                    }
                },
                {
                    'GlobalPolicyRuleSrvObj':
                        {
                            'Rule':
                                {
                                    'RuleName': name,
                                    'SrvAddrType': '0',
                                    'SrvObjGrpList': {'SrvObj': _service_name}
                                }
                        }
                }
            ]
            oms += [{
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'create',
                'NAT': config_data
            }]
            back_oms += [{
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'remove',
                'NAT': {
                    'GlobalPolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                }
            }]
            return oms, back_oms
        # 编辑DNAT规则
        elif kwargs.get('edit_object'):
            description = kwargs.get('description')
            service = kwargs['service']
            to = kwargs['to']
            trans_to = kwargs['trans_to']
            trans_port = kwargs.get('port')
            if 'name' in service.keys():
                service = service['name']
            else:
                raise ValueError("service不符合格式，华三service字段只支持name")
            # 目的地址
            GlobalPolicyRuleDstObj = []
            if 'object' in to.keys():
                GlobalPolicyRuleDstObj += [{
                    'RuleName': name,
                    'DstAddrType': '0',
                    'DstObjGrpList': {'DstIpObj': to['object']}
                }]
            elif 'ip' in to.keys():
                GlobalPolicyRuleDstObj += [{
                    'RuleName': name,
                    'DstAddrType': '1',
                    'DstIPList': {'DstIP': [to['ip']]}
                }]
            else:
                raise ValueError("to不符合格式，key name not match object or ip")
            device = H3CSecPath(host=self.dev_info['ip'], user=self.dev_info['username'],
                                password=self.dev_info['password'])
            before = device.get_global_nat_policy(mode='DNAT', name=name)
            device.closed()
            if len(before) > 0:
                # 转换后的内网地址
                TransDstIP = ''
                if 'ip' in trans_to.keys():
                    TransDstIP = trans_to['ip']
                else:
                    raise RuntimeError("trans_to不符合格式，华三trans_to字段只支持ip，不支持地址对象和SLB")
                GlobalPolicyRuleMembers = {
                    '@xc:operation': 'replace',
                    'Rule': {
                        'RuleName': name,
                        'Description': description,
                        'TransMode': '1',
                        'SrcZoneList': {
                            'SrcZone': 'Untrust'
                        },
                        'TransDstType': '0',
                        'TransDstIP': TransDstIP,
                        'Disable': False,
                        'Counting': True
                    }
                }
                if isinstance(trans_port, int):
                    GlobalPolicyRuleMembers['Rule']['TransDstPort'] = trans_port
                config_data = [
                    {
                        'GlobalPolicyRuleMembers': GlobalPolicyRuleMembers
                    },
                    {
                        'GlobalPolicyRuleDstObj': {
                            '@xc:operation': 'replace',
                            'Rule': GlobalPolicyRuleDstObj,
                        },
                    },
                    {
                        'GlobalPolicyRuleSrvObj':
                            {
                                '@xc:operation': 'replace',
                                'Rule':
                                    {
                                        'RuleName': name,
                                        'SrvAddrType': '0',
                                        'SrvObjGrpList': {'SrvObj': service}
                                    }
                            }
                    }
                ]
                self.cmds = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'merge',
                    'NAT': config_data
                }
                self.back_off_cmds = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'merge',
                    'NAT': before
                }
                return self.cmds, self.back_off_cmds
            else:
                raise RuntimeError("h3c_dnat_detail，编辑DNAT策略，未获取到待编辑的策略")
        # 删除DNAT规则
        elif kwargs.get('del_object'):
            device = H3CSecPath(host=self.dev_info['ip'], user=self.dev_info['username'],
                                password=self.dev_info['password'])
            before = device.get_global_nat_policy(mode='DNAT', name=name)
            device.closed()
            self.back_off_cmds = {
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'create',
                'NAT': before
            }
            self.cmds = {
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'remove',
                'NAT': {
                    'GlobalPolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                }
            }
            return self.cmds, self.back_off_cmds
        else:
            raise RuntimeError("FirewallMain.h3c_dnat_detail 未匹配到method参数")

    # 华三SNAT操作V2
    def h3c_snat_detail(self, **kwargs):
        """
        <NAT>
        <PolicyRuleMembers web:operation='replace'>
        <Rule>
            <RuleName>WANAccess</RuleName>
            <Description></Description>
            <AddrGroupNumber></AddrGroupNumber>
            <AddrGroupName></AddrGroupName>
            <OutboundInterface>159</OutboundInterface>
            <Action>2</Action>
            <Reversible>false</Reversible>  反向转换
            <PortPreserved>true</PortPreserved>
            <Disable>false</Disable>
            <Counting>false</Counting>
        </Rule>
        </PolicyRuleMembers>
        </NAT>
        Action: 0 no pat 1 pat 2 easyip 3 no nat
        <top xmlns='http://www.h3c.com/netconf/config:1.0' web:operation='create'>
        <NAT>
        <PolicyRules web:operation='create'>
        <Rule>
        <RuleName>test123</RuleName>
        </Rule>
        </PolicyRules>
        </NAT>
        <NAT>
        <PolicyRuleMembers web:operation='create'>
        <Rule>
        <RuleName>test123</RuleName>
        <Description>test123</Description>
        <OutboundInterface>159</OutboundInterface>
        <Action>1</Action>
        <AddrGroupNumber>10</AddrGroupNumber>
        <Reversible>false</Reversible>
        <PortPreserved>true</PortPreserved>
        <Disable>false</Disable>
        </Rule>
        </PolicyRuleMembers>
        </NAT>
        <NAT>
        <PolicyRuleMemberSrcObj web:operation='merge'>
        <Rule>
        <RuleName>test123</RuleName>
        <SrcObjGrpList>
        <SrcIpObj>test1</SrcIpObj>
        </SrcObjGrpList>
        </Rule>
        </PolicyRuleMemberSrcObj>
        </NAT>
        <NAT>
        <PolicyRuleMemberDstObj web:operation='merge'>
        <Rule>
        <RuleName>test123</RuleName>
        <DstObjGrpList>
        <DstIpObj>223.244.84.112</DstIpObj>
        </DstObjGrpList>
        </Rule>
        </PolicyRuleMemberDstObj>
        </NAT>
        <NAT>
        <PolicyRuleMemberSrvObj web:operation='merge'>
        <Rule><RuleName>test123</RuleName>
        <SrvObjGrpList>
        <SrvObj>tcp-8443</SrvObj>
        </SrvObjGrpList>
        </Rule>
        </PolicyRuleMemberSrvObj>
        </NAT>
        </top>
        :param kwargs:
        :return:
        """
        name = kwargs['name']
        # egress
        if kwargs['egress']['type'] != 'interface':
            raise RuntimeError("")
        # 新建SNAT规则
        if kwargs.get('add_object'):
            _from = kwargs['from']
            _to = kwargs.get('to', {})
            trans_to = kwargs['trans_to']  # address_book、eif_ip、ip
            service = kwargs['service']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', True)
            # 主内容
            PolicyRuleMembers = {
                '@xc:operation': 'create',
                'Rule': {
                    'RuleName': name,
                    'OutboundInterface': kwargs['egress']['name'],
                    'Reversible': False,
                    'PortPreserved': True,
                    'Disable': True if disable else False,
                }
            }
            # 是否增加该段配置的标记，默认False 不插入
            PolicyRuleMemberSrcObjFlag = False
            PolicyRuleMemberDstObjFlag = False
            PolicyRuleMemberSrvObjFlag = False
            # from 源地址
            PolicyRuleMemberSrcObj = {
                '@xc:operation': 'merge',
                'Rule': {
                    'RuleName': name,
                    'SrcObjGrpList': {
                    }
                }
            }
            if 'object' in _from.keys():
                PolicyRuleMemberSrcObj['Rule']['SrcObjGrpList']['SrcIpObj'] = _from['object']
                PolicyRuleMemberSrcObjFlag = True
            elif 'ip' in _from.keys():
                raise RuntimeError("")
            # to 限定目的地址
            PolicyRuleMemberDstObj = {
                '@xc:operation': 'merge',
                'Rule': {
                    'RuleName': name,
                    'DstObjGrpList': {
                    }
                }
            }
            if 'object' in _to.keys():
                PolicyRuleMemberDstObj['Rule']['DstObjGrpList']['DstIpObj'] = _to['object']
                PolicyRuleMemberDstObjFlag = True
            elif 'ip' in _to.keys():
                raise RuntimeError("")
            # service 制定服务
            PolicyRuleMemberSrvObj = {
                '@xc:operation': 'merge',
                'Rule': {
                    'RuleName': name,
                    'SrvObjGrpList': {
                    }
                }
            }
            if 'name' in service.keys():
                PolicyRuleMemberSrvObj['Rule']['SrvObjGrpList']['SrvObj'] = service['name']  # 服务对象名
                PolicyRuleMemberSrvObjFlag = True
            elif 'start_port' in service.keys() or 'multi' in service.keys():
                raise RuntimeError("")
            if description:
                PolicyRuleMembers['Rule']['Description'] = description
            if 'eif_ip' in trans_to.keys():
                PolicyRuleMembers['Rule']['Action'] = '2'
            elif 'address_book' in trans_to.keys():
                PolicyRuleMembers['Rule']['Action'] = '1'
                # 地址组名称即可
                PolicyRuleMembers['Rule']['AddrGroupNumber'] = trans_to['address_book']
            config_data = [
                {
                    'PolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                },
                {'PolicyRuleMembers': PolicyRuleMembers},
            ]
            if PolicyRuleMemberSrcObjFlag:
                config_data.append({'PolicyRuleMemberSrcObj': PolicyRuleMemberSrcObj})
            if PolicyRuleMemberDstObjFlag:
                config_data.append({'PolicyRuleMemberDstObj': PolicyRuleMemberDstObj})
            if PolicyRuleMemberSrvObjFlag:
                config_data.append({'PolicyRuleMemberSrvObj': PolicyRuleMemberSrvObj})
            self.cmds += [{
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'create',
                'NAT': config_data
            }]
            self.back_off_cmds += [{
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'remove',
                'NAT': {
                    'PolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                }
            }]
            return self.cmds, self.back_off_cmds

    # 华三安全策略操作V2
    def h3c_sec_policy_detail(self, **kwargs):
        name = kwargs['name']
        action_map = {
            "deny": "1",
            "permit": "2"
        }
        if 'add_object' in kwargs.keys():
            _from = kwargs['from']
            _to = kwargs['to']
            # 服务是列表，支持多服务对象
            service_obj = []
            service_multi = []
            service_dict = kwargs['service']
            if 'name' in service_dict.keys():
                service_obj += service_dict['name']
            if 'multi' in service_dict.keys():
                service_multi += service_dict['multi']
            if not service_obj:
                service_obj += ['Any']
            from_addr = []
            from_obj = []
            from_addr_dict = kwargs.get('from_addr', {})
            if 'object' in from_addr_dict.keys():
                from_obj += from_addr_dict['object']
            if 'iplist' in from_addr_dict.keys():
                from_addr += from_addr_dict['iplist']
            to_addr = []
            to_obj = []
            to_addr_dict = kwargs.get('to_addr', {})
            if 'object' in to_addr_dict.keys():
                to_obj += to_addr_dict['object']
            if 'iplist' in to_addr_dict.keys():
                to_addr += to_addr_dict['iplist']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', True)
            log = kwargs.get('log', False)
            vrf = kwargs.get('vrf', '')
            counting = kwargs.get('counting', False)
            action = action_map[kwargs['action']]
            # 华三这个比较恶心，新建安全策略要分两步，一步建规则，一步关联源目参数，并且ID不回传，需要提前查一下当前策略
            # 把所有当前策略ID取出来，新建策略的时候自己指定一个不冲突的固定ID，如果用自动ID，在实际下发的时候还是需要捕获规则ID
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            rules = device.get_sec_policy()
            device.closed()
            rule_id = 50
            rule_id_list = []
            if isinstance(rules, list):
                rule_id_list += [int(x['ID']) for x in rules]
                rule_id = max(rule_id_list) + 1
            # print('rule_id', rule_id)
            # 先建基本策略
            IPv4Rules = {
                'IPv4Rules': {
                    'Rule': {
                        'ID': rule_id,
                        'RuleName': name,
                        'Action': action,
                        'Enable': not disable,
                        'Log': log,
                        'Counting': counting,
                        'SessAgingTimeSw': False,
                        'SessPersistAgingTimeSw': False,
                    }
                }}
            if vrf:
                IPv4Rules['IPv4Rules']['Rule']['VRF'] = vrf
            if description:
                IPv4Rules['IPv4Rules']['Rule']['Comment'] = description
            SecZone = {}
            if 'zone' in _from.keys():
                if _from['zone'].lower() != 'any':
                    IPv4SrcSecZone = {
                        '@xc:operation': 'merge',
                        'SrcSecZone': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': _from['zone']}],
                        }
                    }

                    SecZone['IPv4SrcSecZone'] = IPv4SrcSecZone
            if 'zone' in _to.keys():
                if _to['zone'].lower() != 'any':
                    IPv4DestSecZone = {
                        '@xc:operation': 'merge',
                        'DestSecZone': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': _to['zone']}],
                        }
                    }

                    SecZone['IPv4DestSecZone'] = IPv4DestSecZone
            if SecZone == {}:
                raise RuntimeError("华三防火墙安全策略必须指定一个源或者目的")
            self.cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': IPv4Rules
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': SecZone
                },
            ]
            if service_obj and 'Any' not in service_obj:
                IPv4ServGrp = {
                    'IPv4ServGrp': {
                        '@xc:operation': 'merge',
                        'ServGrp': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in service_obj]},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServGrp
                    },
                ]
            # 指定了自定义协议端口
            if service_multi:
                type_map = {
                    "tcp": "0",
                    "udp": "1",
                    "icmp": "2"
                }
                ServObjItem = []
                for _manual_service in service_multi:
                    if _manual_service['protocol'].lower() in ['tcp', 'udp']:
                        _tmp_obj = {
                            "Type": type_map[_manual_service['protocol'].lower()],
                            "StartSrcPort": '0',
                            "EndSrcPort": '65535',
                            "StartDestPort": str(_manual_service['start_port']),
                            "EndDestPort": str(_manual_service['end_port']),
                        }
                        ServObjItem.append(json.dumps(_tmp_obj))
                    elif _manual_service['protocol'].lower() == 'icmp':
                        _tmp_obj = {
                            "Type": type_map[_manual_service['type']]
                        }
                        ServObjItem.append(json.dumps(_tmp_obj))
                IPv4ServObj = {
                    'IPv4ServObj': {
                        '@xc:operation': 'merge',
                        'ServObj': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'ServObjList': {'ServObjItem': ServObjItem},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServObj
                    },
                ]
            # 指定了源IP地址对象
            if from_obj and 'Any' not in from_obj:
                IPv4SrcAddr = {
                    'IPv4SrcAddr': {
                        '@xc:operation': 'merge',
                        'SrcAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in from_obj]},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4SrcAddr
                    },
                ]
            # 指定了目的IP地址对象
            if to_obj and 'Any' not in to_obj:
                IPv4DestAddr = {
                    'IPv4DestAddr': {
                        '@xc:operation': 'merge',
                        'DestAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in to_obj]},
                        }
                    }

                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4DestAddr
                    },
                ]
            # 指定了源IP列表
            if from_addr:
                IPv4SrcSimpleAddr = {
                    'IPv4SrcSimpleAddr': {
                        '@xc:operation': 'merge',
                        'SrcSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': [x for x in from_addr]}],
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4SrcSimpleAddr
                    },
                ]
            # 指定了目的IP列表
            if to_addr:
                IPv4DestSimpleAddr = {
                    'IPv4DestSimpleAddr': {
                        '@xc:operation': 'merge',
                        'DestSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': [x for x in to_addr]}],
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4DestSimpleAddr
                    },
                ]
            self.back_off_cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'remove',
                    'SecurityPolicies': {
                        'IPv4Rules': {
                            'Rule': {
                                'ID': rule_id,
                            }
                        }
                    }
                },
            ]
            return self.cmds, self.back_off_cmds
        elif 'edit_object' in kwargs.keys():
            """
            1. 先生成主策略
            2. 通过查询现有策略的逻辑，将回退指令同时生成一份删除remove指令，不判断具体差异
            3. 再按新建元素根据新建逻辑新建元素
            """
            # 新建逻辑参数获取start
            _from = kwargs['from']
            _to = kwargs['to']
            # 服务是列表，支持多服务对象
            service_obj = []
            service_multi = []
            service_dict = kwargs['service']
            if 'name' in service_dict.keys():
                service_obj += service_dict['name']
            if 'multi' in service_dict.keys():
                service_multi += service_dict['multi']
            if not service_obj:
                service_obj += ['Any']
            from_addr = []
            from_obj = []
            from_addr_dict = kwargs.get('from_addr', {})
            if 'object' in from_addr_dict.keys():
                from_obj += from_addr_dict['object']
            if 'iplist' in from_addr_dict.keys():
                from_addr += from_addr_dict['iplist']
            to_addr = []
            to_obj = []
            to_addr_dict = kwargs.get('to_addr', {})
            if 'object' in to_addr_dict.keys():
                to_obj += to_addr_dict['object']
            if 'iplist' in to_addr_dict.keys():
                to_addr += to_addr_dict['iplist']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', True)
            log = kwargs.get('log', False)
            vrf = kwargs.get('vrf', '')
            counting = kwargs.get('counting', False)
            action = action_map[kwargs['action']]
            rule_id = kwargs['id']
            # 用新建的逻辑参数获取end
            # 开始根据当前策略的配置，生成回退的配置，同时生成一份remove  start---
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            rules = device.get_sec_policy_id(rule_id=rule_id)
            device.closed()
            if not rules:
                raise RuntimeError("华三防火墙安全策略未获取到需要编辑的策略信息")
            IPv4Rules = {
                'IPv4Rules': {
                    'Rule': {
                        'ID': rule_id,
                        'RuleName': name,
                        'Action': rules['Action'],
                        'Enable': rules['Enable'],
                        'Log': rules['Log'],
                        'Counting': rules['Counting'],
                        'SessAgingTimeSw': rules['SessAgingTimeSw'],
                        'SessPersistAgingTimeSw': rules['SessPersistAgingTimeSw'],
                    }
                }}
            if vrf:
                IPv4Rules['IPv4Rules']['Rule']['VRF'] = vrf
            if description:
                IPv4Rules['IPv4Rules']['Rule']['Comment'] = description
            BackSecZone = {}
            SecZone = {}
            if 'SrcZoneList' in rules.keys():
                BackIPv4SrcSecZone = {
                    '@xc:operation': 'merge',
                    'SrcSecZone': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': False,
                        'NameList': [{'NameItem': rules['SrcZoneList']['SrcZoneItem']}],
                    }
                }
                IPv4SrcSecZone = {
                    '@xc:operation': 'remove',
                    'SrcSecZone': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'NameList': [{'NameItem': None}],
                    }
                }
                BackSecZone['IPv4SrcSecZone'] = BackIPv4SrcSecZone
                SecZone['IPv4SrcSecZone'] = IPv4SrcSecZone
            if 'DestZoneList' in rules.keys():
                BackIPv4DestSecZone = {
                    '@xc:operation': 'merge',
                    'DestSecZone': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': False,
                        'NameList': [{'NameItem': rules['DestZoneList']['DestZoneItem']}],
                    }
                }
                IPv4DestSecZone = {
                    '@xc:operation': 'remove',
                    'DestSecZone': {'ID': rule_id, 'SeqNum': None, 'NameList': {'NameItem': None}}
                }
                SecZone['IPv4DestSecZone'] = IPv4DestSecZone
                BackSecZone['IPv4DestSecZone'] = BackIPv4DestSecZone
            # 先建基本策略
            BackIPv4Rules = {
                'IPv4Rules': {
                    'Rule': {
                        'ID': rule_id,
                        'RuleName': name,
                        'Action': action,
                        'Enable': not disable,
                        'Log': log,
                        'Counting': counting,
                        'SessAgingTimeSw': False,
                        'SessPersistAgingTimeSw': False,
                    }
                }}
            if vrf:
                IPv4Rules['IPv4Rules']['Rule']['VRF'] = vrf
            if description:
                IPv4Rules['IPv4Rules']['Rule']['Comment'] = description
            NewSecZone = {}
            if 'zone' in _from.keys():
                if _from['zone'].lower() != 'any':
                    IPv4SrcSecZone = {
                        '@xc:operation': 'merge',
                        'SrcSecZone': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': _from['zone']}],
                        }
                    }

                    NewSecZone['IPv4SrcSecZone'] = IPv4SrcSecZone
            if 'zone' in _to.keys():
                if _to['zone'].lower() != 'any':
                    IPv4DestSecZone = {
                        '@xc:operation': 'merge',
                        'DestSecZone': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': _to['zone']}],
                        },
                    }

                    NewSecZone['IPv4DestSecZone'] = IPv4DestSecZone
            if NewSecZone == {}:
                raise RuntimeError("华三防火墙安全策略必须指定一个源或者目的")
            # 关联具体源目
            self.cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'merge',
                    'SecurityPolicies': IPv4Rules
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'remove',
                    'SecurityPolicies': SecZone
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'merge',
                    'SecurityPolicies': NewSecZone
                },
            ]
            self.back_off_cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': BackIPv4Rules
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': BackSecZone
                },
            ]
            if 'SrcAddrList' in rules.keys():
                BackIPv4SrcAddr = {
                    'IPv4SrcAddr': {
                        '@xc:operation': 'merge',
                        'SrcAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': rules['SrcAddrList']['SrcAddrItem']}],
                        }
                    }
                }
                IPv4SrcAddr = {
                    'IPv4SrcAddr': {
                        '@xc:operation': 'remove',
                        'SrcAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'NameList': [{'NameItem': None}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4SrcAddr
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4SrcAddr
                    },
                ]
            if 'DestAddrList' in rules.keys():
                BackIPv4DestAddr = {
                    'IPv4DestAddr': {
                        '@xc:operation': 'merge',
                        'DestAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': rules['DestAddrList']['DestAddrItem']}],
                        }
                    }
                }
                IPv4DestAddr = {
                    'IPv4DestAddr': {
                        '@xc:operation': 'remove',
                        'DestAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'NameList': [{'NameItem': None}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4DestAddr
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4DestAddr
                    },
                ]
            if 'SrcSimpleAddrList' in rules.keys():
                BackIPv4SrcSimpleAddr = {
                    'IPv4SrcSimpleAddr': {
                        '@xc:operation': 'merge',
                        'SrcSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': rules['SrcSimpleAddrList']['SrcSimpleAddrItem']}],
                        }
                    }
                }
                IPv4SrcSimpleAddr = {
                    'IPv4SrcSimpleAddr': {
                        '@xc:operation': 'remove',
                        'SrcSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'SimpleAddrList': [{'SimpleAddrItem': None}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4SrcSimpleAddr
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4SrcSimpleAddr
                    },
                ]
            if 'DestSimpleAddrList' in rules.keys():
                BackIPv4DestSimpleAddr = {
                    'IPv4DestSimpleAddr': {
                        '@xc:operation': 'merge',
                        'DestSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': rules['DestSimpleAddrList']['DestSimpleAddrItem']}],
                        }
                    }
                }
                IPv4DestSimpleAddr = {
                    'IPv4DestSimpleAddr': {
                        '@xc:operation': 'remove',
                        'DestSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'SimpleAddrList': [{'SimpleAddrItem': None}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4DestSimpleAddr
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4DestSimpleAddr
                    },
                ]
            if 'ServGrpList' in rules.keys():
                BackIPv4ServGrp = {
                    'IPv4ServGrp': {
                        '@xc:operation': 'merge',
                        'ServGrp': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': rules['ServGrpList']['ServGrpItem']},
                        }
                    }
                }
                IPv4ServGrp = {
                    'IPv4ServGrp': {
                        '@xc:operation': 'remove',
                        'ServGrp': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'NameList': {'NameItem': None},
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4ServGrp
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4ServGrp
                    },
                ]
            if 'ServObjList' in rules.keys():
                BackIPv4ServObj = {
                    'IPv4ServObj': {
                        '@xc:operation': 'merge',
                        'ServObj': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'ServObjList': {'ServObjItem': rules['ServObjList']['ServObjItem']},
                        }
                    }
                }
                IPv4ServObj = {
                    'IPv4ServObj': {
                        '@xc:operation': 'remove',
                        'ServObj': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'ServObjList': {'ServObjItem': None},
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': BackIPv4ServObj
                    },
                ]
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'SecurityPolicies': IPv4ServObj
                    },
                ]
            # 开始根据当前策略的配置，生成回退的配置，同时生成一份remove end---
            # 开始按规则生成具体配置项
            # 关联具体源目
            if service_obj and 'Any' not in service_obj:
                IPv4ServGrp = {
                    'IPv4ServGrp': {
                        '@xc:operation': 'merge',
                        'ServGrp': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in service_obj]},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServGrp
                    },
                ]
            # 指定了自定义协议端口
            if service_multi:
                type_map = {
                    "tcp": "0",
                    "udp": "1",
                    "icmp": "2"
                }
                ServObjItem = []
                for _manual_service in service_multi:
                    if _manual_service['protocol'].lower() in ['tcp', 'udp']:
                        _tmp_obj = {
                            "Type": type_map[_manual_service['protocol'].lower()],
                            "StartSrcPort": '0',
                            "EndSrcPort": '65535',
                            "StartDestPort": str(_manual_service['start_port']),
                            "EndDestPort": str(_manual_service['end_port']),
                        }
                        ServObjItem.append(json.dumps(_tmp_obj))
                    elif _manual_service['protocol'].lower() == 'icmp':
                        _tmp_obj = {
                            "Type": type_map[_manual_service['type']]
                        }
                        ServObjItem.append(json.dumps(_tmp_obj))
                IPv4ServObj = {
                    'IPv4ServObj': {
                        '@xc:operation': 'merge',
                        'ServObj': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'ServObjList': {'ServObjItem': ServObjItem},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServObj
                    },
                ]
            # 指定了源IP地址对象
            if from_obj and 'Any' not in from_obj:
                IPv4SrcAddr = {
                    'IPv4SrcAddr': {
                        '@xc:operation': 'merge',
                        'SrcAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in from_obj]},
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4SrcAddr
                    },
                ]
            # 指定了目的IP地址对象
            if to_obj and 'Any' not in to_obj:
                IPv4DestAddr = {
                    'IPv4DestAddr': {
                        '@xc:operation': 'merge',
                        'DestAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': [x for x in to_obj]},
                        }
                    }

                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4DestAddr
                    },
                ]
            # 指定了源IP列表
            if from_addr:
                IPv4SrcSimpleAddr = {
                    'IPv4SrcSimpleAddr': {
                        '@xc:operation': 'merge',
                        'SrcSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': [x for x in from_addr]}],
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4SrcSimpleAddr
                    },
                ]
            # 指定了目的IP列表
            if to_addr:
                IPv4DestSimpleAddr = {
                    'IPv4DestSimpleAddr': {
                        '@xc:operation': 'merge',
                        'DestSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': [x for x in to_addr]}],
                        }
                    }
                }
                self.cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4DestSimpleAddr
                    },
                ]
            return self.cmds, self.back_off_cmds
        elif 'del_object' in kwargs.keys():
            rule_id = kwargs['id']
            device = H3CSecPath(host=self.dev_info['ip'],
                                user=self.dev_info['username'], password=self.dev_info['password'],
                                timeout=600, device_params=self.dev_info['device_type'])
            rules = device.get_sec_policy_id(rule_id=rule_id)
            device.closed()
            if not rules:
                raise RuntimeError("华三防火墙安全策略未获取到需要删除的策略信息")
            IPv4Rules = {
                'IPv4Rules': {
                    'Rule': {
                        'ID': rule_id,
                        'RuleName': name,
                        'Action': rules['Action'],
                        'Enable': rules['Enable'],
                        'Log': rules['Log'],
                        'Counting': rules['Counting'],
                        'SessAgingTimeSw': rules['SessAgingTimeSw'],
                        'SessPersistAgingTimeSw': rules['SessPersistAgingTimeSw'],
                    }
                }}
            SecZone = {}
            if 'SrcZoneList' in rules.keys():
                IPv4SrcSecZone = {
                    '@xc:operation': 'merge',
                    'SrcSecZone': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': False,
                        'NameList': [{'NameItem': rules['SrcZoneList']['SrcZoneItem']}],
                    }
                }
                SecZone['IPv4SrcSecZone'] = IPv4SrcSecZone
            if 'DestZoneList' in rules.keys():
                IPv4DestSecZone = {
                    '@xc:operation': 'merge',
                    'DestSecZone': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': False,
                        'NameList': [{'NameItem': rules['DestZoneList']['DestZoneItem']}],
                    },
                }
                SecZone['IPv4DestSecZone'] = IPv4DestSecZone
            self.back_off_cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': IPv4Rules
                },
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'SecurityPolicies': SecZone
                },
            ]
            if 'SrcAddrList' in rules.keys():
                IPv4SrcAddr = {
                    'IPv4SrcAddr': {
                        '@xc:operation': 'merge',
                        'SrcAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': rules['SrcAddrList']['SrcAddrItem']}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'SecurityPolicies': IPv4SrcAddr
                    },
                ]
            if 'DestAddrList' in rules.keys():
                IPv4DestAddr = {
                    'IPv4DestAddr': {
                        '@xc:operation': 'merge',
                        'DestAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': [{'NameItem': rules['DestAddrList']['DestAddrItem']}],
                        }
                    }

                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'SecurityPolicies': IPv4DestAddr
                    },
                ]
            if 'SrcSimpleAddrList' in rules.keys():
                IPv4SrcSimpleAddr = {
                    'IPv4SrcSimpleAddr': {
                        '@xc:operation': 'merge',
                        'SrcSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': rules['SrcSimpleAddrList']['SrcSimpleAddrItem']}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4SrcSimpleAddr
                    },
                ]
            if 'DestSimpleAddrList' in rules.keys():
                IPv4DestSimpleAddr = {
                    'IPv4DestSimpleAddr': {
                        '@xc:operation': 'merge',
                        'DestSimpleAddr': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'SimpleAddrList': [{'SimpleAddrItem': rules['DestSimpleAddrList']['DestSimpleAddrItem']}],
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4DestSimpleAddr
                    },
                ]
            if 'ServGrpList' in rules.keys():
                IPv4ServGrp = {
                    'IPv4ServGrp': {
                        '@xc:operation': 'merge',
                        'ServGrp': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'NameList': {'NameItem': rules['ServGrpList']['ServGrpItem']},
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServGrp
                    },
                ]
            if 'ServObjList' in rules.keys():
                IPv4ServObj = {
                    'IPv4ServObj': {
                        '@xc:operation': 'merge',
                        'ServObj': {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': False,
                            'ServObjList': {'ServObjItem': rules['ServObjList']['ServObjItem']},
                        }
                    }
                }
                self.back_off_cmds += [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'merge',
                        'SecurityPolicies': IPv4ServObj
                    },
                ]
            self.cmds += [
                {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'remove',
                    'SecurityPolicies': {
                        'IPv4Rules': {
                            'Rule': {
                                'ID': rule_id,
                            }
                        }
                    }
                },
            ]
            return self.cmds, self.back_off_cmds
        elif 'sort_object' in kwargs.keys():
            insert = kwargs['insert']  # ^(before\s\d|after\s\d|top)
            rule_id = kwargs['id']
            type_map = {
                'top': 1,  # 华三翻译过来是head，这里为了统一，用top
                'before': 2,
                'after': 3,
                'tail': 4,  # 暂时不用
            }
            if insert == 'top':
                self.cmds = [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/action:1.0',
                        'SecurityPolicies':
                            {
                                'MoveIPv4Rule':
                                    {
                                        'Rule': {'ID': rule_id, 'MoveType': type_map[insert]}
                                    }
                            }
                    }
                ]
            else:
                self.cmds = [
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/action:1.0',
                        'SecurityPolicies':
                            {
                                'MoveIPv4Rule':
                                    {
                                        'Rule': {
                                            'ID': rule_id,
                                            'MoveType': type_map[insert.split()[0]],
                                            'DestID': insert.split()[1]
                                        }
                                    }
                            }
                    }
                ]
            self.back_off_cmds = [
                {
                    'top': {
                        '@xmlns': 'http://www.h3c.com/netconf/action:1.0',
                        'SecurityPolicies':
                            {
                                'MoveIPv4Rule':
                                    {
                                        'Rule': {'ID': rule_id, 'MoveType': 4}
                                    }
                            }
                    }
                }
            ]
            return self.cmds, self.back_off_cmds

    # 华为DNAT操作V2
    def huawei_dnat_detail(self, **kwargs):
        name = kwargs['name']
        protocol_map = {"TCP": '6', "UDP": '17', "ICMP": '1'}
        to = kwargs['to']
        trans_to = kwargs['trans_to']
        trans_port = kwargs.get('port')
        # 新建DNAT规则
        if kwargs.get('add_object'):
            service = kwargs['service']
            if 'protocol' in service.keys():
                if 'ip' in trans_to.keys():
                    TransDstIP = trans_to['ip']
                else:
                    raise RuntimeError("trans_to不符合格式，华为trans_to字段只支持ip，不支持地址对象和SLB")
                if 'ip' in to.keys():
                    global_ip = to['ip']
                else:
                    raise ValueError("to不符合格式，华为to字段只支持ip，不支持地址对象和SLB")
                protocol = protocol_map[service['protocol']]
                if protocol == '1':
                    oms = {
                        '@nc:operation': 'create',
                        'name': name,
                        'vsys': 'public',
                        'global-zone': 'untrust',
                        'protocol': '1',
                        'global': {'start-ip': global_ip},
                        'inside': {'start-ip': TransDstIP},
                        'no-reverse': 'true'
                    }
                    back_oms = {
                        '@nc:operation': 'delete',
                        'name': name,
                        'vsys': 'public',
                    }
                    return oms, back_oms
                else:
                    oms = []
                    back_oms = []
                    # 端口范围映射  比如 8001 - 8003  到内网主机的  8001-8003
                    if service['start_port'] != service['end_port']:
                        for _sub_port in range(service['start_port'], service['end_port']):
                            _sub_name = "{name}_{protocol}_{start_port}_{end_port}".format(
                                name=name,
                                protocol=service['multi']['protocol'].upper(),
                                start_port=str(_sub_port),
                                end_port=str(_sub_port)
                            )
                            oms.append(
                                {
                                    '@nc:operation': 'create',
                                    'name': _sub_name,
                                    'vsys': 'public',
                                    'global-zone': 'untrust',
                                    'protocol': protocol,
                                    'global': {'start-ip': global_ip},
                                    'global-port': {'start-port': str(_sub_port)},
                                    'inside': {'start-ip': TransDstIP},
                                    'inside-port': {'start-port': str(_sub_port)},
                                    'no-reverse': 'true'
                                }
                            )
                            back_oms.append(
                                {
                                    '@nc:operation': 'delete',
                                    'name': _sub_name,
                                    'vsys': 'public',
                                }
                            )
                    # 单端口映射
                    elif service['start_port'] == service['end_port']:
                        oms.append(
                            {
                                '@nc:operation': 'create',
                                'name': name,
                                'vsys': 'public',
                                'global-zone': 'untrust',
                                'protocol': protocol,
                                'global': {'start-ip': global_ip},
                                'global-port': {'start-port': str(service['start_port'])},
                                'inside': {'start-ip': TransDstIP},
                                'inside-port': {'start-port': str(trans_port)},
                                'no-reverse': 'true'
                            }
                        )
                        back_oms.append(
                            {
                                '@nc:operation': 'delete',
                                'name': name,
                                'vsys': 'public',
                            }
                        )
                    return oms, back_oms
            elif 'multi' in service.keys():
                oms = []
                back_oms = []
                for _sub_ser in service['multi']:
                    if 'ip' in trans_to.keys():
                        TransDstIP = trans_to['ip']
                    else:
                        raise RuntimeError("trans_to不符合格式，华为trans_to字段只支持ip，不支持地址对象和SLB")
                    if 'ip' in to.keys():
                        global_ip = to['ip']
                    else:
                        raise ValueError("to不符合格式，华为to字段只支持ip，不支持地址对象和SLB")
                    protocol = protocol_map[_sub_ser['protocol']]
                    sub_name = "{name}_{protocol}_{start_port}_{end_port}".format(
                        name=name,
                        protocol=_sub_ser['protocol'].upper(),
                        start_port=str(_sub_ser['start_port']),
                        end_port=str(_sub_ser['end_port'])
                    )
                    if protocol == '1':
                        oms.append({
                            '@nc:operation': 'create',
                            'name': sub_name,
                            'vsys': 'public',
                            'global-zone': 'untrust',
                            'protocol': protocol,
                            'global': {'start-ip': global_ip},
                            'inside': {'start-ip': TransDstIP},
                            'no-reverse': 'true'
                        })
                        back_oms.append({
                            '@nc:operation': 'delete',
                            'name': sub_name,
                            'vsys': 'public',
                        })
                    else:
                        # 端口范围映射  比如 8001 - 8003  到内网主机的  8001-8003
                        if _sub_ser['start_port'] != _sub_ser['end_port']:
                            for _sub_port in range(_sub_ser['start_port'], _sub_ser['end_port']):
                                _sub_name = "{name}_{protocol}_{start_port}_{end_port}".format(
                                    name=name,
                                    protocol=_sub_ser['protocol'].upper(),
                                    start_port=str(_sub_port),
                                    end_port=str(_sub_port)
                                )
                                oms.append(
                                    {
                                        '@nc:operation': 'create',
                                        'name': _sub_name,
                                        'vsys': 'public',
                                        'global-zone': 'untrust',
                                        'protocol': protocol,
                                        'global': {'start-ip': global_ip},
                                        'global-port': {'start-port': str(_sub_port)},
                                        'inside': {'start-ip': TransDstIP},
                                        'inside-port': {
                                            'start-port': str(trans_port) if trans_port is not None else str(
                                                _sub_ser['start_port'])},
                                        'no-reverse': 'true'
                                    }
                                )
                                back_oms.append(
                                    {
                                        '@nc:operation': 'delete',
                                        'name': sub_name,
                                        'vsys': 'public',
                                    }
                                )
                        # 单端口映射
                        elif _sub_ser['start_port'] == _sub_ser['end_port']:
                            _sub_name = "{name}_{protocol}_{start_port}_{end_port}".format(
                                name=name,
                                protocol=_sub_ser['protocol'].upper(),
                                start_port=str(_sub_ser['start_port']),
                                end_port=str(_sub_ser['end_port'])
                            )
                            oms.append(
                                {
                                    '@nc:operation': 'create',
                                    'name': _sub_name,
                                    'vsys': 'public',
                                    'global-zone': 'untrust',
                                    'protocol': protocol,
                                    'global': {'start-ip': global_ip},
                                    'global-port': {'start-port': str(_sub_ser['start_port'])},
                                    'inside': {'start-ip': TransDstIP},
                                    'inside-port': {
                                        'start-port': str(trans_port) if trans_port is not None else str(
                                            _sub_ser['start_port'])},
                                    'no-reverse': 'true'
                                }
                            )
                            back_oms.append(
                                {
                                    '@nc:operation': 'delete',
                                    'name': name,
                                    'vsys': 'public',
                                }
                            )
                return oms, back_oms
            else:
                raise ValueError("service不符合格式，华为只支持自定义协议和端口，不支持引用服务对象")

        # 编辑DNAT规则
        elif kwargs.get('edit_object'):
            service = kwargs['service']
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _dnat_req = device.get_nat_server()
            device.closed()
            if _dnat_req:
                _dnat_res = [x for x in _dnat_req if x['name'] == name]
                back_oms = copy.deepcopy(_dnat_res[0])
                back_oms['@nc:operation'] = 'replace'
            else:
                raise RuntimeError("FirewallMain.huawei_dnat_detail 没能获取到待编辑的对象")

            if 'protocol' in service.keys():
                if 'ip' in trans_to.keys():
                    TransDstIP = trans_to['ip']
                else:
                    raise RuntimeError("trans_to不符合格式，华为trans_to字段只支持ip，不支持地址对象和SLB")
                if 'ip' in to.keys():
                    global_ip = to['ip']
                else:
                    raise ValueError("to不符合格式，华为to字段只支持ip，不支持地址对象和SLB")
                protocol = protocol_map[service['protocol']]
                if protocol == '1':
                    oms = {
                        '@nc:operation': 'replace',
                        'name': name,
                        'vsys': 'public',
                        'global-zone': 'untrust',
                        'protocol': '1',
                        'global': {'start-ip': global_ip},
                        'inside': {'start-ip': TransDstIP},
                        'no-reverse': 'true'
                    }
                    return oms, back_oms
                else:
                    if 'global_port' in service.keys():
                        global_port = service['global_port']
                    else:
                        raise RuntimeError("global_port不符合格式，华为DNAT配置TCP/UDP需要global_port和protocol")
                    oms = {
                        '@nc:operation': 'replace',
                        'name': name,
                        'vsys': 'public',
                        'global-zone': 'untrust',
                        'protocol': protocol,
                        'global': {'start-ip': global_ip},
                        'global-port': {'start-port': str(global_port)},
                        'inside': {'start-ip': TransDstIP},
                        'inside-port': {'start-port': str(trans_port)},
                        'no-reverse': 'true'
                    }
                    return oms, back_oms
            else:
                raise ValueError("FirewallMain.huawei_dnat_detail service不符合格式，华为只支持自定义协议和端口，不支持引用服务对象")
        # 删除DANT规则
        elif kwargs.get('del_object'):
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _dnat_req = device.get_nat_server()
            device.closed()
            if _dnat_req:
                _dnat_res = [x for x in _dnat_req if x['name'] == name]
                back_oms = copy.deepcopy(_dnat_res[0])
                back_oms['@nc:operation'] = 'create'
                oms = {
                    '@nc:operation': 'delete',
                    'name': name,
                    'vsys': 'public',
                }
                return oms, back_oms
        else:
            raise RuntimeError("FirewallMain.huawei_dnat_detail 未匹配到method参数")

    # 华为SNAT操作V2
    def huawei_snat_detail(self, **kwargs):
        name = kwargs['name']
        # 新建SNAT规则
        if kwargs.get('add_object'):
            _from = kwargs['from']
            _to = kwargs.get('to', {})
            trans_to = kwargs['trans_to']  # address_book、eif_ip、ip
            service = kwargs['service']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', True)
            config_obj = {
                '@nc:operation': 'create',
                'nat-type': 'nat',
                'name': "{}_{}".format(name, str(int(time.time()))),
            }
            if 'address_book' in trans_to.keys():
                config_obj['action'] = 'nat-address-group'
                config_obj['nat-address-group'] = trans_to['address_book']
            elif 'eif_ip' in trans_to.keys():
                config_obj['action'] = 'easyip'
            else:
                raise RuntimeError("华为USG防火墙/SNAT/新建/tran_to不支持指定单IP")
            if disable:
                config_obj['enable'] = False
            if description != '':
                config_obj['description'] = description
            if kwargs['ingress']['type'] == 'zone':
                config_obj['source-zone'] = kwargs['ingress']['name'].lower()
            else:
                raise RuntimeError("华为USG防火墙/SNAT/不支持入方向为设备接口的逻辑")
            if kwargs['egress']['type'] == 'zone':
                config_obj['destination-zone'] = kwargs['egress']['name'].lower()
            elif kwargs['egress']['type'] == 'interface':
                config_obj['egress-interface'] = kwargs['egress']['name']
            config_obj['@nc:operation'] = 'create'
            if 'ip' in _to.keys():
                config_obj['destination-ip'] = {'address-ipv4': _to['ip']}
            elif 'object' in _to.keys():
                config_obj['destination-ip'] = {'address-set': _to['object']}
            if 'ip' in _from.keys():
                config_obj['source-ip'] = {'address-ipv4': _from['ip']}
            elif 'object' in _from.keys():
                config_obj['source-ip'] = {'address-set': _from['object']}
            # 指定单个协议端口
            if 'protocol' in service.keys():
                if service['start_port'] == service['end_port']:
                    config_obj['service'] = {
                        service['protocol'].lower: {
                            'dest-port': service['start_port']
                        }
                    }
                else:
                    config_obj['service'] = {
                        service['protocol'].lower: {
                            'dest-port': service['start_port'] + ' to ' + service['end_port']
                        }
                    }
            # 混合多个协议端口
            elif 'multi' in service.keys():
                config_obj['service'] = []
                for _sub_ser in service['multi']:
                    if 'protocol' in _sub_ser.keys():
                        if _sub_ser['start_port'] == _sub_ser['end_port']:
                            config_obj['service'] += [{
                                _sub_ser['protocol'].lower: {
                                    'dest-port': _sub_ser['start_port']
                                }
                            }]
                        else:
                            config_obj['service'] += [{
                                _sub_ser['protocol'].lower: {
                                    'dest-port': _sub_ser['start_port'] + ' to ' + _sub_ser['end_port']
                                }
                            }]
                    elif 'name' in _sub_ser.keys():
                        config_obj['service'] += [{'service-object': _sub_ser['name']}]
                return
            # 指定单个服务对象名
            elif 'name' in service.keys():
                config_obj['service'] = {'service-object': service['name']}
            else:
                raise ValueError("service不符合格式，华为只支持自定义协议和端口，不支持引用服务对象")
            oms = {
                'name': 'public',
                'rule': config_obj
            }
            back_config_obj = copy.deepcopy(config_obj)
            back_config_obj['@nc:operation'] = 'delete'
            back_oms = {
                'name': 'public',
                'rule': back_config_obj
            }
            return oms, back_oms
        # 编辑SNAT规则
        elif kwargs.get('edit_object'):
            _from = kwargs['from']
            _to = kwargs.get('to', {})
            trans_to = kwargs['trans_to']  # address_book、eif_ip、ip
            service = kwargs['service']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', False)
            config_obj = {
                '@nc:operation': 'replace',
                'nat-type': 'nat',
                'name': name,
            }
            if 'address_book' in trans_to.keys():
                config_obj['action'] = 'nat-address-group'
            elif 'eif_ip' in trans_to.keys():
                config_obj['action'] = 'easyip'
            else:
                raise RuntimeError("华为USG防火墙/SNAT/编辑/tran_to不支持指定单IP")
            if disable:
                config_obj['enable'] = False
            if description != '':
                config_obj['description'] = description
            if kwargs['ingress']['type'] == 'zone':
                config_obj['source-zone'] = kwargs['ingress']['name'].lower()
            else:
                raise RuntimeError("华为USG防火墙/SNAT/不支持入方向为设备接口的逻辑")
            if kwargs['egress']['type'] == 'zone':
                config_obj['destination-zone'] = kwargs['egress']['name'].lower()
            elif kwargs['egress']['type'] == 'interface':
                config_obj['egress-interfac'] = kwargs['egress']['name']
            if 'ip' in _to.keys():
                config_obj['destination-ip'] = {'address-ipv4': _to['ip']}
            elif 'object' in _to.keys():
                config_obj['destination-ip'] = {'address-set': _to['object']}
            if 'ip' in _from.keys():
                config_obj['source-ip'] = {'address-ipv4': _from['ip']}
            elif 'object' in _from.keys():
                config_obj['source-ip'] = {'address-set': _from['object']}
            # 指定单个协议端口
            if 'protocol' in service.keys():
                if service['start_port'] == service['end_port']:
                    config_obj['service'] = {
                        service['protocol'].lower: {
                            'dest-port': service['start_port']
                        }
                    }
                else:
                    config_obj['service'] = {
                        service['protocol'].lower: {
                            'dest-port': service['start_port'] + ' to ' + service['end_port']
                        }
                    }
            # 混合多个协议端口
            elif 'multi' in service.keys():
                config_obj['service'] = []
                for _sub_ser in service['multi']:
                    if 'protocol' in _sub_ser.keys():
                        if _sub_ser['start_port'] == _sub_ser['end_port']:
                            config_obj['service'] += [{
                                _sub_ser['protocol'].lower: {
                                    'dest-port': _sub_ser['start_port']
                                }
                            }]
                        else:
                            config_obj['service'] += [{
                                _sub_ser['protocol'].lower: {
                                    'dest-port': _sub_ser['start_port'] + ' to ' + _sub_ser['end_port']
                                }
                            }]
                    elif 'name' in _sub_ser.keys():
                        config_obj['service'] += [{'service-object': _sub_ser['name']}]
                return
            # 指定单个服务对象名
            elif 'name' in service.keys():
                config_obj['service'] = {'service-object': service['name']}
            else:
                raise ValueError("service不符合格式，华为只支持自定义协议和端口，不支持引用服务对象")
            oms = {
                'name': 'public',
                'rule': config_obj
            }
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _dnat_req = device.get_nat_policy()
            device.closed()
            _dnat_res = [x for x in _dnat_req[0]['rule'] if x['name'] == name]
            back_config_obj = copy.deepcopy(_dnat_res[0])
            back_config_obj['@nc:operation'] = 'replace'
            back_oms = {
                'name': 'public',
                'rule': back_config_obj
            }
            return oms, back_oms
        # 删除SANT规则
        elif kwargs.get('del_object'):
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _dnat_req = device.get_nat_policy()
            device.closed()
            if _dnat_req:
                _dnat_res = [x for x in _dnat_req[0]['rule'] if x['name'] == name]
                config_obj = copy.deepcopy(_dnat_res[0])
                config_obj['@nc:operation'] = 'delete'
                back_config_obj = copy.deepcopy(_dnat_res[0])
                back_config_obj['@nc:operation'] = 'create'
                oms = {
                    'name': 'public',
                    'rule': config_obj
                }
                back_oms = {
                    'name': 'public',
                    'rule': back_config_obj
                }
                return oms, back_oms
        else:
            raise RuntimeError("FirewallMain.huawei_dnat_detail 未匹配到method参数")

    # 华为安全策略V2
    def huawei_sec_policy(self, **kwargs):
        name = kwargs['name']
        action_map = {
            "deny": "false",
            "permit": "true"
        }
        if 'add_object' in kwargs.keys() or 'edit_object' in kwargs.keys():
            _from = kwargs['from']
            _to = kwargs['to']
            # 服务是列表，支持多服务对象
            service_obj = []
            service_multi = []
            service_dict = kwargs['service']
            if 'name' in service_dict.keys():
                service_obj += service_dict['name']
            if 'multi' in service_dict.keys():
                service_multi += service_dict['multi']
            if not service_obj:
                service_obj += ['Any']
            from_addr = []
            from_obj = []
            from_addr_dict = kwargs.get('from_addr', {})
            if 'object' in from_addr_dict.keys():
                from_obj += from_addr_dict['object']
            if 'iplist' in from_addr_dict.keys():
                from_addr += from_addr_dict['iplist']
            to_addr = []
            to_obj = []
            to_addr_dict = kwargs.get('to_addr', {})
            if 'object' in to_addr_dict.keys():
                to_obj += to_addr_dict['object']
            if 'iplist' in to_addr_dict.keys():
                to_addr += to_addr_dict['iplist']
            description = kwargs.get('description', '')
            disable = kwargs.get('disable', True)
            log = kwargs.get('log', False)
            vrf = kwargs.get('vrf', '')
            counting = kwargs.get('counting', False)
            action = action_map[kwargs['action']]
            # 如果安全域为any 则 'source-zone'或者'destination-zone'不需要携带
            policy_data = {
                'rule':
                    {
                        '@nc:operation': 'create',
                        'name': name,
                        'source-ip': {},
                        'destination-ip': {},
                        'service': {},
                        'action': action,
                        'enable': str(not disable).lower(),
                        'session-log': str(log).lower(),
                    }
            }
            if 'edit_object' in kwargs.keys():
                policy_data['rule']['@nc:operation'] = 'replace'
            self.back_off_cmds = {}
            if description:
                policy_data['rule']['desc'] = description
            if 'zone' in _from.keys():
                if _from['zone'].lower() != 'any':
                    policy_data['rule']['source-zone'] = _from['zone']
            if 'zone' in _to.keys():
                if _to['zone'].lower() != 'any':
                    policy_data['rule']['destination-zone'] = _to['zone']
            if from_obj and 'Any' not in from_obj:
                policy_data['rule']['source-ip']['address-set'] = [x for x in from_obj]
            if from_addr:
                for _sub_from_addr in from_addr:
                    if _sub_from_addr.lower() == 'any':
                        continue
                    if _sub_from_addr.find('-') != -1:
                        if 'address-ipv4-range' not in policy_data['rule']['source-ip'].keys():
                            policy_data['rule']['source-ip']['address-ipv4-range'] = [{
                                'start-ipv4': _sub_from_addr.split('-')[0],
                                'end-ipv4': _sub_from_addr.split('-')[1]}]
                        else:
                            policy_data['rule']['source-ip']['address-ipv4-range'] += [{
                                'start-ipv4': _sub_from_addr.split('-')[0],
                                'end-ipv4': _sub_from_addr.split('-')[1]}]
                    elif _sub_from_addr.find('/') != -1:
                        if 'address-ipv4' not in policy_data['rule']['source-ip'].keys():
                            policy_data['rule']['source-ip']['address-ipv4'] = [_sub_from_addr]
                        else:
                            policy_data['rule']['source-ip']['address-ipv4'] += [_sub_from_addr]
                    else:
                        if 'address-ipv4' not in policy_data['rule']['source-ip'].keys():
                            policy_data['rule']['source-ip']['address-ipv4'] = ["{}/32".format(_sub_from_addr)]
                        else:
                            policy_data['rule']['source-ip']['address-ipv4'] += ["{}/32".format(_sub_from_addr)]
            if to_addr:
                for _sub_to_addr in to_addr:
                    if _sub_to_addr.lower() == 'any':
                        continue
                    if _sub_to_addr.find('-') != -1:
                        if 'address-ipv4-range' not in policy_data['rule']['destination-ip'].keys():
                            policy_data['rule']['destination-ip']['address-ipv4-range'] = [
                                {'start-ipv4': _sub_to_addr.split('-')[0],
                                 'end-ipv4': _sub_to_addr.split('-')[1]}]
                        else:
                            policy_data['rule']['destination-ip']['address-ipv4-range'] += [
                                {'start-ipv4': _sub_to_addr,
                                 'end-ipv4': _sub_to_addr}]
                    elif _sub_to_addr.find('/') != -1:
                        if 'address-ipv4' not in policy_data['rule']['destination-ip'].keys():
                            policy_data['rule']['destination-ip']['address-ipv4'] = [_sub_to_addr]
                        else:
                            policy_data['rule']['destination-ip']['address-ipv4'] += [_sub_to_addr]
                    else:
                        if 'address-ipv4' not in policy_data['rule']['destination-ip'].keys():
                            policy_data['rule']['destination-ip']['address-ipv4'] = ["{}/32".format(_sub_to_addr)]
                        else:
                            policy_data['rule']['destination-ip']['address-ipv4'] += ["{}/32".format(_sub_to_addr)]
            if to_obj and 'Any' not in to_obj:
                policy_data['rule']['destination-ip']['address-set'] = [x for x in to_obj]
            if service_obj and 'Any' not in service_obj:
                if 'service-object' not in policy_data['rule']['service'].keys():
                    policy_data['rule']['service']['service-object'] = [x for x in service_obj]
                else:
                    policy_data['rule']['service']['service-object'] += [x for x in service_obj]
            if service_multi:
                policy_data['rule']['service']['service-items'] = dict()
                for _m_service in service_multi:
                    if _m_service['protocol'].lower() in ['tcp', 'udp']:
                        if _m_service['protocol'] not in policy_data['rule']['service']['service-items'].keys():
                            policy_data['rule']['service']['service-items'][_m_service['protocol']] = []
                        policy_data['rule']['service']['service-items'][_m_service['type']].append(
                            {'source-port': '{} to {}'.format('0', '65535'),
                             'dest-port': '{} to {}'.format(str(_m_service['start_port']),
                                                            str(_m_service['end_port']))})
                    elif _m_service['protocol'] == 'icmp':
                        policy_data['rule']['service']['service-items']['icmp-item'] = [{'icmp-name': 'echo'},
                                                                                        {'icmp-name': 'echo-reply'}]
            back_config_obj = copy.deepcopy(policy_data)
            back_config_obj['rule']['@nc:operation'] = 'delete'
            return policy_data, back_config_obj
        elif 'del_object' in kwargs.keys():
            rule_name = kwargs['name']
            device = HuaweiUSG(host=self.dev_info['ip'],
                               user=self.dev_info['username'],
                               password=self.dev_info['password'])
            _rule_req = device.get_sec_policy_single(rule_name=rule_name)
            device.closed()
            if _rule_req:
                self.cmds = _rule_req['static-policy']
                self.cmds['rule']['@nc:operation'] = 'delete'
                self.back_off_cmds = copy.deepcopy(self.cmds)
                self.back_off_cmds['@nc:operation'] = 'create'
                return self.cmds, self.back_off_cmds
            raise RuntimeError("DCS:未查询到指定安全策略:{}".format(rule_name))
        elif 'sort_object' in kwargs.keys():
            # 等测试环境设备到货后再测试
            pass
        raise RuntimeError("DCS:未查询到安全策略的动作")

    # 华三获取SNAT表项
    def get_h3c_snat(self, **kwargs):
        # get_source_nat
        try:
            device = H3CSecPath(host=self.host, user=self.dev_info['username'], password=self.dev_info['password'])

            try:
                snat_res = device.get_source_nat()
                if snat_res:
                    for i in snat_res:
                        i['hostip'] = self.host
                device.closed()
                return snat_res
            except Exception as e:
                device.closed()
                # print(traceback.print_exc())
                send_msg_sec_manage("安全纳管操作华三防火墙 {} 获取SNAT数据失败:{}".format(self.host, str(e)))
            device.closed()
            return True
        except Exception as e:
            send_msg_sec_manage("安全纳管华三防火墙 {} NETCONF初始化失败:{}".format(self.host, str(e)))
            return False

    # 华为获取全局NAT策略 用于SNAT
    def get_huawei_nat_policy(self, **kwargs):
        # get_nat_policy
        device = HuaweiUSG(host=self.dev_info['ip'],
                           user=self.dev_info['username'], password=self.dev_info['password'])
        try:
            nat_policy = device.get_nat_policy()
            if nat_policy:
                for i in nat_policy:
                    i['hostip'] = self.dev_info['manage_ip']
            device.closed()
            return nat_policy
        except Exception as e:
            send_msg_sec_manage("[安全纳管]操作华为防火墙 设备 {} 获取NAT策略表项异常：{}".format(self.host, str(e)))
            device.closed()
            return []

    # 获取华三单个设备地址组对象列表V2
    def get_h3c_address_obj(self, **kwargs):
        try:
            device = H3CSecPath(host=self.host, user=self.dev_info['username'], password=self.dev_info['password'])

            try:
                ipv4_group = device.get_ipv4_paging()
                if ipv4_group:
                    for i in ipv4_group:
                        i['hostip'] = self.host
                device.closed()
                return ipv4_group
            except Exception as e:
                device.closed()
                # print(traceback.print_exc())
                send_msg_sec_manage("安全纳管操作华三防火墙 {} 获取地址组数据失败:{}".format(self.host, str(e)))
            device.closed()
            return True
        except Exception as e:
            send_msg_sec_manage("安全纳管华三防火墙 {} NETCONF初始化失败:{}".format(self.host, str(e)))
            return False

    # 获取华为单个设备地址组对象列表V2
    def get_huawei_address_obj(self, **kwargs):
        device = HuaweiUSG(host=self.dev_info['ip'], user=self.dev_info['username'], password=self.dev_info['password'])
        try:
            address_ser = device.get_address_set()
            if address_ser:
                for i in address_ser:
                    i['hostip'] = self.dev_info['manage_ip']
            device.closed()
            return address_ser
        except Exception as e:
            # print(traceback.print_exc())
            send_msg_sec_manage("[安全纳管]操作华为防火墙 设备 {} 地址组对象采集异常：{}".format(self.host, str(e)))
            device.closed()
            return False

    # 获取华三单个设备服务对象列表V2
    def get_h3c_service_obj(self, **kwargs):
        try:
            device = H3CinfoCollection(host=self.host,
                                       user=self.dev_info['username'], password=self.dev_info['password'])
            try:
                service_set = device.get_server_groups()
                if service_set:
                    for i in service_set:
                        i['hostip'] = self.host
                    return service_set
            except Exception as e:
                # print(traceback.print_exc())
                send_msg_sec_manage("[安全纳管]操作华三防火墙 {} 获取服务组对象数据失败:{}".format(self.host, str(e)))
            device.closed()
        except Exception as e:
            send_msg_sec_manage("[安全纳管]华三防火墙 {} 获取华三单个设备服务组对象列表失败:{}".format(self.host, str(e)))
            return False

    # 获取华为单个设备服务对象列表V2
    def get_huawei_service_obj(self, **kwargs):
        device = HuaweiUSG(host=self.dev_info['ip'],
                           user=self.dev_info['username'], password=self.dev_info['password'])
        try:
            service_set = device.get_service_set()
            if service_set:
                for i in service_set:
                    i['hostip'] = self.dev_info['manage_ip']
            device.closed()
            return service_set
        except Exception as e:
            send_msg_sec_manage("[安全纳管]操作华为防火墙 设备 {} 获取服务组组对象异常：{}".format(self.host, str(e)))
            device.closed()
            return False

    # 获取华为单个设备安全策略
    def get_huawei_sec_policy(self, **kwargs):
        device = HuaweiUSG(host=self.dev_info['ip'],
                           user=self.dev_info['username'], password=self.dev_info['password'])
        try:
            policy_set = device.get_sec_policy()
            if policy_set:
                for i in policy_set['static-policy']['rule']:
                    i['hostip'] = self.dev_info['manage_ip']
            device.closed()
            return policy_set['static-policy']['rule']
        except Exception as e:
            send_msg_sec_manage("[安全纳管]操作华为防火墙 设备 {} 获取安全策略异常：{}".format(self.host, str(e)))
            device.closed()
            return False

    # 获取华三全局DNAT表项
    def get_h3c_global_dnat(self, **kwargs):
        try:
            device = H3CSecPath(host=self.host, user=self.dev_info['username'], password=self.dev_info['password'])

            try:
                nat_res = device.get_global_nat_policy()
                if nat_res:
                    for i in nat_res:
                        i['hostip'] = self.host
                device.closed()
                return nat_res
            except Exception as e:
                device.closed()
                # print(traceback.print_exc())
                send_msg_sec_manage("安全纳管操作华三防火墙 {} 获取DNAT数据失败:{}".format(self.host, str(e)))
            device.closed()
            return []
        except Exception as e:
            send_msg_sec_manage("安全纳管华三防火墙 {} NETCONF初始化失败:{}".format(self.host, str(e)))
            return []

    # 获取华为全局DNAT表项(NAT SERVER)
    def get_huawei_nat_server(self, **kwargs):
        device = HuaweiUSG(host=self.dev_info['ip'],
                           user=self.dev_info['username'], password=self.dev_info['password'])
        try:
            nat_server = device.get_nat_server()
            if nat_server:
                for i in nat_server:
                    i['hostip'] = self.dev_info['manage_ip']
            device.closed()
            return nat_server
        except Exception as e:
            send_msg_sec_manage("[安全纳管]操作华为防火墙 设备 {} 获取全局DNAT表项异常：{}".format(self.host, str(e)))
            device.closed()
            return []

    # 华三配置DNAT操作
    def config_h3c_dnat(self, **kwargs):
        """
        字段合法性检查前置
        :param kwargs:
        :return:
        """
        name = kwargs['name']
        description = kwargs.get('description')
        service = kwargs['service']
        to = kwargs['to']
        trans_to = kwargs['trans_to']
        port = kwargs['port']
        method = 'create'  # 默认方法动作 新建
        device = H3CSecPath(host=self.dev_info['ip'], user=self.dev_info['username'],
                            password=self.dev_info['password'])
        before = device.get_global_nat_policy(mode='DNAT', name=name)
        # 公网地址对象
        GlobalPolicyRuleDstObj = {}
        if 'object' in to.keys():
            GlobalPolicyRuleDstObj = {
                'RuleName': name,
                'DstAddrType': '0',
                'DstObjGrpList': {'DstIpObj': to['object']}
            }

        elif 'ip' in to.keys():
            if to['ip'].find('/') != -1:
                raise ValueError("to不符合格式，只支持单个IP地址，不支持CIDR格式")
            GlobalPolicyRuleDstObj = {
                'RuleName': name,
                'DstAddrType': '1',
                'DstIPList': {'DstIP': [to['ip']]}
            }

        else:
            raise ValueError("to不符合格式，key name not match object or ip")
        # 转换后的内网地址
        TransDstIP = ''
        if 'ip' in trans_to.keys():
            TransDstIP = trans_to['ip']
        else:
            raise ValueError("trans_to不符合格式，key name not match object or ip")
        # 编辑规则
        if len(before) > 0:
            method = 'merge'
            data = [
                {
                    'GlobalPolicyRuleMembers': {
                        '@xc:operation': 'replace',
                        'Rule': {
                            'RuleName': name,
                            'Description': description,
                            'TransMode': '1',
                            'SrcZoneList': {
                                'SrcZone': 'Untrust'
                            },
                            'TransDstType': '0',
                            'TransDstIP': TransDstIP,
                            'Disable': 'false',
                            'Counting': 'true'
                        }
                    }
                },
                {
                    'GlobalPolicyRuleDstObj': {
                        '@xc:operation': 'replace',
                        'Rule': GlobalPolicyRuleDstObj,
                    },
                },
                {
                    'GlobalPolicyRuleSrvObj':
                        {
                            '@xc:operation': 'replace',
                            'Rule':
                                {
                                    'RuleName': name,
                                    'SrvAddrType': '0',
                                    'SrvObjGrpList': {'SrvObj': service}
                                }
                        }
                }
            ]
        # 新建规则
        else:
            method = 'create'
            data = [
                {
                    'GlobalPolicyRules': {
                        'Rule': {
                            'RuleName': name
                        }
                    }
                },
                {
                    'GlobalPolicyRuleMembers': {
                        'Rule': {
                            'RuleName': name,
                            'Description': description,
                            'TransMode': '1',
                            'SrcZoneList': {'SrcZone': 'Untrust'},
                            'TransDstType': '0',
                            'TransDstIP': TransDstIP,
                            'Disable': 'false',
                            'Counting': 'true'
                        }
                    }
                },
                {
                    'GlobalPolicyRuleDstObj': {
                        'Rule': GlobalPolicyRuleDstObj
                    }
                },
                {
                    'GlobalPolicyRuleSrvObj':
                        {
                            'Rule':
                                {
                                    'RuleName': name,
                                    'SrvAddrType': '0',
                                    'SrvObjGrpList': {'SrvObj': service}
                                }
                        }
                }
            ]
        res = device.config_nat_server(data, method=method)
        device.closed()
        return before, data, res

    # 更新单个山石防火墙nat信息
    def refresh_hillstone_configuration(self, **kwargs):
        _HillstoneProc = HillstoneProc(**self.dev_infos)
        _HillstoneProc.manual_cmd_run(*['show configuration'])
        return {'code': 200}

    # 获取华三安全域列表
    def get_h3c_sec_zone(self, **kwargs):
        try:
            device = H3CSecPath(host=self.host, user=self.dev_info['username'], password=self.dev_info['password'])

            try:
                nat_res = device.get_sec_zone()
                if nat_res:
                    for i in nat_res:
                        i['hostip'] = self.host
                device.closed()
                return nat_res
            except Exception as e:
                device.closed()
                # print(traceback.print_exc())
                send_msg_sec_manage("安全纳管操作华三防火墙 {} 获取安全域列表失败:{}".format(self.host, str(e)))
            device.closed()
            return []
        except Exception as e:
            send_msg_sec_manage("安全纳管华三防火墙 {} NETCONF初始化失败:{}".format(self.host, str(e)))
            return []

    # 获取华三安全策略
    def get_h3c_sec_policy(self, **kwargs):
        try:
            device = H3CSecPath(host=self.host, user=self.dev_info['username'],
                                password=self.dev_info['password'])

            try:
                nat_res = device.get_sec_policy()
                if nat_res:
                    for i in nat_res:
                        i['hostip'] = self.host
                device.closed()
                return nat_res
            except Exception as e:
                device.closed()
                # print(traceback.print_exc())
                send_msg_sec_manage("安全纳管操作华三防火墙 {} 获取安全策略失败:{}".format(self.host, str(e)))
            device.closed()
            return []
        except Exception as e:
            send_msg_sec_manage("安全纳管华三防火墙 {} NETCONF初始化失败:{}".format(self.host, str(e)))
            return []

    def get_hillstone_address_obj(self, **kwargs):
        res = MongoOps(db='Automation', coll='hillstone_address') \
            .find(query_dict=dict(hostip=self.host), fileds={'_id': 0})
        return res


class SecPolicyMain(object):

    # 更新单个山石设备安全策略  ssh方式
    @staticmethod
    def get_single_hillstone(host):
        """
        更新单个山石防火墙的安全策略配置数据
        5.0版本的不支持  show configuration policy
        :param host:
        :return:
        """
        cmds = ['show configuration policy']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            username = dev_infos[0]['username']  # 用户名
            password = dev_infos[0]['password']  # 密码
            port = dev_infos[0]['port']
            if dev_infos[0]['soft_version'].startswith('Version 5.0'):
                cmds = ['show configuration']
            device_ios = 'ruijie_os'
            # device_ios = 'cisco_ios'
            if 'telnet' in dev_infos[0]['protocol']:
                device_ios = 'ruijie_os_telnet'
            # fsm_flag = 'hillstone'  # 解析器标识
            dev_info = {
                'device_type': device_ios,
                'ip': host,
                'port': port,
                'username': username,
                'password': password,
                'timeout': 200,  # float，连接超时时间，默认为100
                'session_timeout': 100,  # float，每个请求的超时时间，默认为60
            }
            paths = BatManMain.send_cmds(*cmds, **dev_info)
            if paths and isinstance(paths, list):
                sec_policy_res = HillstoneFsm.sec_policy(path=paths[0])
                if isinstance(sec_policy_res, list):
                    sec_policy_result = []
                    if sec_policy_res:
                        for i in sec_policy_res:
                            i['hostip'] = host
                            sec_policy_result.append(i)
                    if sec_policy_result:
                        StandardFSMAnalysis.hillstone_sec_policy(host=host, datas=sec_policy_result)
                        # sec_policy_mongo.delete_many(query=dict(hostip=host))
                        # sec_policy_mongo.insert_many(sec_policy_result)
                        return True
            else:
                print(paths)
                return False
        return False

    # 更新单个华三设备安全策略  netconf方式
    @staticmethod
    def get_single_h3c(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    device = H3CSecPath(host=host, user=dev_info['username'], password=dev_info['password'])
                    if dev_info['category__name'] == '防火墙':
                        # 安全策略
                        try:
                            sec_policy_res = device.get_sec_policy()
                            device.closed()
                            sec_policy_result = []
                            if sec_policy_res:
                                for i in sec_policy_res:
                                    i['hostip'] = host
                                    sec_policy_result.append(i)
                            if sec_policy_result:
                                StandardFSMAnalysis.h3c_secpath_sec_policy(host, sec_policy_result)
                                return True
                        except Exception as e:
                            device.closed()
                            # print(traceback.print_exc())
                            # send_msg_sec_manage("华三防火墙 {} 获取安全策略失败:{}".format(host, str(e)))
                            return False
                except Exception as e:
                    # print(traceback.print_exc())
                    send_msg_sec_manage("运营平台接口华三防火墙 {} NETCONF初始化失败:{}".format(host, str(e)))
                    return False
        return False

    # 更新单个华为设备安全策略  netconf方式
    @staticmethod
    def get_single_huawei(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'huawei_usg',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'manage_ip': dev_infos[0]['manage_ip']
                }
                # if bind_ipaddress:
                #     dev_info['ip'] = bind_ipaddress['ipaddr']
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                if dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
                    try:
                        sec_policy_res = device.get_sec_policy()
                        if sec_policy_res:
                            sec_policy_rule = sec_policy_res['static-policy']['rule']
                            sec_policy_result = []
                            if sec_policy_rule:
                                for i in sec_policy_rule:
                                    i['hostip'] = dev_info['manage_ip']
                                    sec_policy_result.append(i)
                            if sec_policy_result:
                                # 格式化落库
                                StandardFSMAnalysis.huawei_usg_sec_policy(dev_info['manage_ip'], sec_policy_result)
                                # 原始数据格式落库
                                AutomationMongo.insert_table(db='NETCONF', hostip=dev_info['manage_ip'],
                                                             datas=sec_policy_result, tablename='huawei_sec_policy')
                                # AutomationMongo.insert_table(db='NETCONF', hostip=host, datas=sec_policy_result,
                                #                              tablename='huawei_sec_policy')
                                return True
                    except Exception as e:
                        # print(traceback.print_exc())
                        send_msg_sec_manage("华为防火墙 设备 {} 安全策略采集异常：{}".format(host, str(e)))
                        return False
                    device.closed()
        return False

    # 更新单个山石设备地址组、服务组
    @staticmethod
    def update_hillstone_addr_service(host):
        cmds = ['show configuration']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            username = dev_infos[0]['username']  # 用户名
            password = dev_infos[0]['password']  # 密码
            port = dev_infos[0]['port']
            if dev_infos[0]['soft_version'].startswith('Version 5.0'):
                cmds = ['show configuration']
            device_ios = 'ruijie_os'
            # device_ios = 'cisco_ios'
            if 'telnet' in dev_infos[0]['protocol']:
                device_ios = 'ruijie_os_telnet'
            # fsm_flag = 'hillstone'  # 解析器标识
            dev_info = {
                'device_type': device_ios,
                'ip': host,
                'port': port,
                'username': username,
                'password': password,
                'timeout': 200,  # float，连接超时时间，默认为100
                'session_timeout': 100,  # float，每个请求的超时时间，默认为60
            }
            paths = BatManMain.send_cmds(*cmds, **dev_info)
            if paths and isinstance(paths, list):
                address_mongo = MongoOps(db='Automation', coll='hillstone_address')
                service_mongo = MongoOps(db='Automation', coll='hillstone_service')
                servgroup_mongo = MongoOps(db='Automation', coll='hillstone_servgroup')
                # 地址组
                try:
                    address_res = HillstoneFsm.address_group(path=paths[0])
                    address_result = []
                    for i in address_res:
                        i['hostip'] = host
                        address_result.append(i)
                    if address_result:
                        address_mongo.delete_many(query=dict(hostip=host))
                        address_mongo.insert_many(address_result)
                except Exception as e:
                    AutomationMongo.failed_log(ip=host, fsm_flag='hillstone', cmd='address', version=str(e))
                # 服务
                try:
                    service_res = HillstoneFsm.service_proc(path=paths[0])
                    service_result = []
                    for i in service_res:
                        """
                        {'items': [{'dst-port-min': 7093, 'protocol': 'tcp', 'src-port-max': 65535, 'src-port-min': 0}, 
                        {'dst-port-min': 7096, 'protocol': 'tcp', 'src-port-max': 65535, 'src-port-min': 0}], 'name': '7093/6'}
                        """
                        i['hostip'] = host
                        # if len(i['Port'].split()) > 1:
                        #     """
                        #     参考10.254.12.252
                        #     配置文件摘要如下：
                        #     service "20190714"
                        #       tcp dst-port 10001
                        #       tcp dst-port 12003 12004
                        #     需要识别出端口范围并生成range遍历添加
                        #     {'service': '223.244.84.16_1_0_10000_20000', 'Protocol': 'tcp', 'Method': 'dst-port', 'Port': ['10000', '20000']}
                        #     """
                        #     service_list = [str(item) for item in
                        #                     range(int(i['Port'].split()[0]), int(i['Port'].split()[1]) + 1)]
                        #     for _tmp_service in service_list:
                        #         service_result.append(dict(
                        #             service=i['service'],
                        #             Protocol=i['Protocol'],
                        #             Method=i['Method'],
                        #             Port=_tmp_service,
                        #             hostip=host
                        #         ))
                        # else:
                        service_result.append(i)
                    if service_result:
                        service_mongo.delete_many(query=dict(hostip=host))
                        service_mongo.insert_many(service_result)
                except Exception as e:
                    AutomationMongo.failed_log(ip=host, fsm_flag='hillstone', cmd='service', version=str(e))
                # 服务组
                try:
                    servgroup_res = HillstoneFsm.servgroup_proc(path=paths[0])
                    servgroup_result = []
                    for i in servgroup_res:
                        i['hostip'] = host
                        """
                        {'servgroup': '75.28', 'services': [{'service': '1936'}, {'service': '8083'}, 
                        {'service': '8086'}, {'service': '7093/6'}]}
                        """
                        # if i['Service'] == 'FTP':
                        #     i['Service'] = '21'
                        # elif i['Service'] == 'HTTP':
                        #     i['Service'] = '80'
                        # elif i['Service'] == 'HTTPS':
                        #     i['Service'] = '443'
                        servgroup_result.append(i)
                    if servgroup_result:
                        servgroup_mongo.delete_many(query=dict(hostip=host))
                        servgroup_mongo.insert_many(servgroup_result)
                except Exception as e:
                    AutomationMongo.failed_log(ip=host, fsm_flag='hillstone', cmd='servgroup', version=str(e))
                # StandardFSMAnalysis.hillstone_configfile(path=paths[0], hostip=host)
                return True
            else:
                return False
        return False

    # 更新单个华三设备地址组
    @staticmethod
    def update_single_h3c_address(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    device = H3CinfoCollection(host=host, user=dev_info['username'], password=dev_info['password'])
                    if dev_info['category__name'] == '防火墙':
                        try:
                            address_set = device.get_ipv4_paging()
                            device.closed()
                            # res = device.move_ipv4_rule(id='2', dest_id='3', type='2')
                            # print(res)
                            # address_set = []
                            # result = dict()
                            # for i in ipv4_groups:
                            #     result[i['Name']] = i
                            # for i in ipv4_objs:
                            #     if i['Group'] in result.keys():
                            #         if result[i['Group']].get('elements'):
                            #             result[i['Group']]['elements'].append(i)
                            #         else:
                            #             result[i['Group']]['elements'] = [i]
                            # for i in result.keys():
                            #     # if 'elements' not in result[i].keys():
                            #     #     print(result[i])
                            #     address_set.append(result[i])

                            if address_set:
                                for i in address_set:
                                    print(i)
                                    i['hostip'] = host
                                AutomationMongo.insert_table(db='NETCONF', hostip=host, datas=address_set,
                                                             tablename='h3c_address_set')
                            return True
                        except Exception as e:
                            device.closed()
                            send_msg_sec_manage("运营平台操作华三防火墙 {} 拼接地址组对象数据失败:{}".format(host, str(e)))
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} NETCONF初始化失败:{}".format(host, str(e)))
                    return False
        return False

    # 更新单个华三设备服务组
    @staticmethod
    def update_single_h3c_service(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    device = H3CinfoCollection(host=host, user=dev_info['username'], password=dev_info['password'])
                    if dev_info['category__name'] == '防火墙':
                        try:
                            service_set = device.get_server_groups()
                            device.closed()
                            if service_set:
                                for i in service_set:
                                    i['hostip'] = host
                                AutomationMongo.insert_table(db='NETCONF', hostip=host, datas=service_set,
                                                             tablename='h3c_service_set')
                            return True
                        except Exception as e:
                            device.closed()
                            # print(traceback.print_exc())
                            # send_msg_sec_manage("运营平台操作华三防火墙 {} 拼接服务组对象数据失败:{}".format(host, str(e)))
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} NETCONF初始化失败:{}".format(host, str(e)))
                    return False
        return False

    # 更新单个华为防火墙地址组
    @staticmethod
    def update_single_huawei_address(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'huawei_usg',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'manage_ip': dev_infos[0]['manage_ip']
                }
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                if dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
                    try:
                        address_set = device.get_address_set()
                        if address_set:
                            for i in address_set:
                                i['hostip'] = host
                            AutomationMongo.insert_table(db='NETCONF', hostip=host, datas=address_set,
                                                         tablename='huawei_usg_address_set')
                            return True
                    except Exception as e:
                        send_msg_sec_manage("运营平台操作华为防火墙 设备 {} 地址组对象采集异常：{}".format(host, str(e)))
                        return False
                    device.closed()
        return False

    # 更新单个华为防火墙服务组
    @staticmethod
    def update_single_huawei_service(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'huawei_usg',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'manage_ip': dev_infos[0]['manage_ip']
                }
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                if dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
                    try:
                        service_set = device.get_service_set()
                        if service_set:
                            for i in service_set:
                                i['hostip'] = host
                            AutomationMongo.insert_table(db='NETCONF', hostip=host, datas=service_set,
                                                         tablename='huawei_usg_service_set')
                            return True
                    except Exception as e:
                        send_msg_sec_manage("运营平台操作华为防火墙 设备 {} 服务组组对象采集异常：{}".format(host, str(e)))
                        return False
                    device.closed()
        return False

    # 获取华三单个设备安全域列表
    @staticmethod
    def get_h3c_sec_zone(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    device = H3CinfoCollection(host=host, user=dev_info['username'], password=dev_info['password'])
                    if dev_info['category__name'] == '防火墙':
                        try:
                            serv_groups = device.get_sec_zone()
                            device.closed()
                            return serv_groups
                        except Exception as e:
                            device.closed()
                            # print(traceback.print_exc())
                            send_msg_sec_manage("运营平台操作华三防火墙 {} 获取安全域数据失败:{}".format(host, str(e)))
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} NETCONF初始化失败:{}".format(host, str(e)))
                    return False
        return False

    # 获取华为单个设备安全域列表
    @staticmethod
    def get_huawei_sec_zone(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'huawei_usg',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'manage_ip': dev_infos[0]['manage_ip']
                }
                # if bind_ipaddress:
                #     dev_info['ip'] = bind_ipaddress['ipaddr']
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                if dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
                    try:
                        sec_policy_res = device.get_sec_zone()
                        device.closed()
                        return sec_policy_res
                    except Exception as e:
                        # print(traceback.print_exc())
                        send_msg_sec_manage("运营平台操作华为防火墙 设备 {} 安全域采集异常：{}".format(host, str(e)))
                        device.closed()
                        return False

        return False

    # 获取华三单个设备服务组对象列表
    @staticmethod
    def get_h3c_service_obj(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    device = H3CinfoCollection(host=host, user=dev_info['username'], password=dev_info['password'])
                    if dev_info['category__name'] == '防火墙':
                        try:
                            service_set = device.get_server_groups()
                            device.closed()
                            if service_set:
                                for i in service_set:
                                    i['hostip'] = host
                                return service_set
                        except Exception as e:
                            device.closed()
                            # print(traceback.print_exc())
                            send_msg_sec_manage("运营平台操作华三防火墙 {} 获取服务组对象数据失败:{}".format(host, str(e)))
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 获取华三单个设备服务组对象列表失败:{}".format(host, str(e)))
                    return False
        return False

    # 获取华为单个设备服务组组对象列表
    @staticmethod
    def get_huawei_service_obj(host):
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'huawei_usg',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'manage_ip': dev_infos[0]['manage_ip']
                }
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                if dev_info['device_type'] == 'huawei_usg':
                    device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
                    try:
                        service_set = device.get_service_set()
                        if service_set:
                            for i in service_set:
                                i['hostip'] = dev_info['manage_ip']
                        device.closed()
                        return service_set
                    except Exception as e:
                        send_msg_sec_manage("运营平台操作华为防火墙 设备 {} 获取服务组组对象异常：{}".format(host, str(e)))
                        device.closed()
                        return False

        return False

    @staticmethod
    def move_h3c_sec_policy(**kwargs):
        host = kwargs['hostip']
        insert = kwargs.get('insert')
        rule_id = kwargs.get('current_id')
        target_id = kwargs.get('target_id')
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    if insert in ['first', 'last']:
                        res = _H3cFirewall.move(insert=insert)
                        return res
                    else:
                        res = _H3cFirewall.move(hostip=host,
                                                rule_id=rule_id,
                                                target_id=target_id,
                                                insert=insert)
                        return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 移动安全策略失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def del_h3c_sec_policy(**kwargs):
        host = kwargs['hostip']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.delete_sec_policy(hostip=host, rule_id=kwargs['delete_rule_id'])
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 删除安全策略失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def create_h3c_address(**kwargs):
        host = kwargs['hostip']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.create_address(**kwargs)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 删除地址对象失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def edit_h3c_address(**kwargs):
        host = kwargs['hostip']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.edit_address(**kwargs)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 删除地址对象失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def del_h3c_address(**kwargs):
        host = kwargs['hostip']
        name = kwargs['delete_address_obj']['name']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.delete_address(name)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 删除地址对象失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def create_h3c_service(**kwargs):
        host = kwargs['hostip']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.create_service(**kwargs)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 新建服务对象失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def edit_h3c_service(**kwargs):
        host = kwargs['hostip']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.edit_service(**kwargs)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 编辑服务对象失败:{}".format(host, str(e)))
                    return False
        return False

    @staticmethod
    def del_h3c_service(**kwargs):
        host = kwargs['hostip']
        name = kwargs['delete_service_obj']['name']
        dev_infos = get_device_info_v2(manage_ip=host)
        if dev_infos:
            if 'netconf' in dev_infos[0]['protocol']:
                dev_info = {
                    'device_type': 'h3c',
                    'ip': host,
                    'port': dev_infos[0]['netconf_port'],
                    'username': dev_infos[0]['netconf_username'],
                    'password': dev_infos[0]['netconf_password'],
                    'timeout': 200,  # float，连接超时时间，默认为100
                    'session_timeout': 100,  # float，每个请求的超时时间，默认为60
                    'patch_version': dev_infos[0].get('patch_version'),
                    'hostname': dev_infos[0]['name'],
                    'idc_name': dev_infos[0].get('idc__name'),
                    'chassis': dev_infos[0]['chassis'],
                    'slot': dev_infos[0]['slot'],
                    'serial_num': dev_infos[0]['serial_num'],
                    'category__name': dev_infos[0].get('category__name')
                }
                try:
                    _H3cFirewall = H3cFirewall(host=host, username=dev_info['username'], password=dev_info['password'])
                    res = _H3cFirewall.delete_service(name)
                    return res
                except Exception as e:
                    send_msg_sec_manage("华三防火墙 {} 删除地址对象失败:{}".format(host, str(e)))
                    return False
        return False


def edit_sec_policy(**kwargs):
    print(kwargs['device_object'])
    print(kwargs['policy_object'])
    room_group_name = kwargs['room_group_name']
    device = kwargs['device_object']
    hostip = device['manage_ip']
    """
    'manage_ip': '10.254.5.68',
    'name': 'DZ.AD.IN.FW.001',
    'vendor__name': '山石网科'
    """
    if device['vendor__name'] == '山石网科':
        try:
            insert_mongo_datas = dict()  # 最终更新到monggo数据库
            insert_mongo_datas['hostip'] = device['manage_ip']
            policy_object = kwargs['policy_object']
            rule_id = policy_object['id']
            name = policy_object.get('name')
            is_top = policy_object['is_top']
            # 山石网科老设备不支持name，统一不下发name
            # if policy_object['is_auto_name']:
            #     name = 'auto_' + datetime.strftime(datetime.now(), '%Y_%m_%d_%H_%M')
            if not name:  # name 提前预测可能为空的情况下
                name = 'auto_' + datetime.strftime(datetime.now(), '%Y_%m_%d_%H_%M')
            cmds, dev_info = HillstoneBase.get_host_info(device['manage_ip'])
            # 置顶操作
            if is_top:
                cmds += ['policy-global', 'move ' + rule_id + ' top']
            old_sec_policy = MongoOps(db='Automation', coll='sec_policy').find(
                query_dict=dict(hostip=hostip, id=rule_id),
                fileds={'_id': 0})
            """
            old_sec_policy 数据大致如下：
            vendor: 'hillstone',
            hostip: '10.254.12.16',
            id: '2',
            name: null,
            action: 'permit',
            enable: true,
            src_zone: 'dmz',
            dst_zone: 'Any',
            service: [{'object': 'TeamView防御'}]
            src_addr: [
                {
                    ip: '10.254.254.0/24'
                },
                {
                    ip: '10.254.253.0/24'
                }
            ],
            dst_addr: [
                {
                    object: 'Any'
                }
            ],
            log: '',
            description: null

            """
            if old_sec_policy:
                old_sec_policy = old_sec_policy[0]
            else:
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='Failed', content='未检索到待编辑策略数据！进程退出……'))
                return

            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='连接成功……'))
            send_ws_msg(group_name=room_group_name,
                        data=dict(device=device, result='OK', content='开始编辑, rule id ' + rule_id))
            insert_mongo_datas['id'] = rule_id
            insert_mongo_datas['vendor'] = old_sec_policy['vendor']
            action = policy_object['action']
            description = policy_object['description'] or ''
            insert_mongo_datas['description'] = description
            src_zone_object = policy_object.get('src_zone_object') or 'Any'
            dst_zone_object = policy_object.get('dst_zone_object') or 'Any'
            src_addr_info = policy_object['src_addr_info']
            dst_addr_info = policy_object['dst_addr_info']
            manual_src_addr = policy_object['manual_src_addr']
            manual_dst_addr = policy_object['manual_dst_addr']
            service_info = policy_object['service_info']
            manual_service_info = policy_object['manual_service_info']
            service_path = ''
            cmds += ['rule id ' + rule_id]
            if description != old_sec_policy['description']:
                cmds += ['description ' + description]
            else:
                insert_mongo_datas['description'] = old_sec_policy['description']
            if action != old_sec_policy['action']:
                cmds += ['action ' + action.lower()]
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='OK', content='策略改变识别……{}……OK!'.format(action)))
                insert_mongo_datas['action'] = action
            else:
                insert_mongo_datas['action'] = old_sec_policy['action']
            # 新增自定义协议端口 转 服务对象  山石在这一步不需要判断差异
            if manual_service_info:
                # 服务需要预先新建
                # 需要新建服务组 service  服务名跟安全策略ID一致 调用已有方法新建服务
                # service "20"
                #   tcp dst-port 20 application "FTP" timeout 1800
                service_data = {
                    "vendor": "hillstone",
                    "create_service_obj": {
                        "name": name,
                        "object": manual_service_info
                    },
                    "hostip": device['manage_ip'],
                    "no_save": True
                }
                service_path, service_ttp = HillstoneBase.create_service(**service_data)
                print('service_path, service_ttp ', service_path, service_ttp)
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义服务识别……OK!'))
            if service_path:
                service_content = default_storage.open(service_path).read().decode('utf-8')
                for _content in service_content.split('\n'):
                    ws_data = dict(device=device, result='OK', content=_content)
                    # print('ws_data')
                    # print(ws_data)
                    send_ws_msg(group_name=room_group_name, data=ws_data)
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='新建服务成功……'))
                cmds += ['service ' + name]
                if isinstance(insert_mongo_datas.get('service'), list):
                    insert_mongo_datas['service'] += [{'object': name}]
                else:
                    insert_mongo_datas['service'] = [{'object': name}]
            # 如果安全域为any 则 'source-zone'或者'destination-zone'不需要携带
            if isinstance(src_zone_object, dict):
                if src_zone_object['name'] != old_sec_policy['src_zone']:
                    cmds += ['src-zone ' + src_zone_object['name']]
                    insert_mongo_datas['src_zone'] = src_zone_object['name']
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='源安全域识别……OK!'))
                else:
                    insert_mongo_datas['src_zone'] = old_sec_policy['src_zone']
            else:
                cmds += ['no src-zone']
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源安全域识别Any……OK!'))
                insert_mongo_datas['src_zone'] = 'Any'
            if isinstance(dst_zone_object, dict):
                if dst_zone_object['name'] != old_sec_policy['dst_zone']:
                    cmds += ['dst-zone ' + dst_zone_object['name']]
                    insert_mongo_datas['dst_zone'] = dst_zone_object['name']
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='目的安全域识别……OK!'))
                else:
                    insert_mongo_datas['dst_zone'] = old_sec_policy['dst_zone']
            else:
                cmds += ['no dst-zone']
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='OK', content='目的安全域识别Any……OK!'))
                insert_mongo_datas['dst-zone'] = 'Any'
            insert_mongo_datas['src_addr'] = []
            insert_mongo_datas['dst_addr'] = []
            # 指定地址对象
            print("old_sec_policy['src_addr']")
            print(old_sec_policy['src_addr'])
            # old_src_addr = [x.get('object') for x in old_sec_policy['src_addr']]
            if old_sec_policy['src_addr']:
                old_src_addr = [item_dict.get(type_name) for item_dict in old_sec_policy['src_addr']
                                for type_name in item_dict if type_name == "object"]
            else:
                old_src_addr = []
            if src_addr_info and isinstance(src_addr_info, list) and len(src_addr_info) > 0:
                new_src_addr = [x['name'] for x in src_addr_info]
                print('新源地址对象', new_src_addr)
                print('旧源地址对象', old_src_addr)
                # 归集差异比较结果
                cmd_src_addr_add, cmd_src_addr_del = HillstoneBase.get_list_diff(old_src_addr, new_src_addr)
                print('cmd_src_addr_add')
                print(cmd_src_addr_add)
                print('cmd_src_addr_del')
                print(cmd_src_addr_del)
                if cmd_src_addr_add:
                    cmds += ['src-addr ' + x for x in cmd_src_addr_add]
                if cmd_src_addr_del:
                    cmds += ['no src-addr ' + x for x in cmd_src_addr_del]
                insert_mongo_datas['src_addr'] += [{'object': x['name']} for x in src_addr_info]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源地址对象识别……OK!'))
            else:
                print('old_src_addr')
                print(old_src_addr)
                if old_src_addr:
                    cmds += ['no src-addr ' + x for x in old_src_addr]
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='源地址对象识别……OK!'))
            # old_dst_addr = [x.get('object') for x in old_sec_policy['dst_addr']]
            if old_sec_policy['dst_addr']:
                old_dst_addr = [item_dict.get(type_name) for item_dict in old_sec_policy['dst_addr']
                                for type_name in item_dict if type_name == "object"]
            else:
                old_dst_addr = []
            if dst_addr_info and isinstance(dst_addr_info, list) and len(dst_addr_info) > 0:
                new_dst_addr = [x['name'] for x in dst_addr_info]
                # 归集差异比较结果
                cmd_dst_addr_add, cmd_dst_addr_del = HillstoneBase.get_list_diff(old_dst_addr, new_dst_addr)
                if cmd_dst_addr_add:
                    cmds += ['dst-addr ' + x for x in cmd_dst_addr_add]
                if cmd_dst_addr_del:
                    cmds += ['no dst-addr ' + x for x in cmd_dst_addr_del]
                insert_mongo_datas['dst_addr'] += [{'object': x['name']} for x in dst_addr_info]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='目的地址对象识别……OK!'))
            else:
                if old_dst_addr:
                    cmds += ['no dst-addr ' + x for x in old_dst_addr]
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='目的地址对象识别……OK!'))
            # 指定服务对象
            # old_ser = [x.get('object') for x in old_sec_policy['service']]
            if old_sec_policy['service']:
                old_ser = [item_dict.get(type_name) for item_dict in old_sec_policy['service']
                           for type_name in item_dict if type_name == "object"]
            else:
                old_ser = []
            if service_info and isinstance(service_info, list) and len(service_info) > 0:
                new_ser = [x['name'] for x in service_info]
                if old_sec_policy['service']:
                    old_ser = [x.get('object') for x in old_sec_policy['service']]
                else:
                    old_ser = []
                # 归集差异比较结果
                new_ser_add, new_ser_del = HillstoneBase.get_list_diff(old_ser, new_ser)
                if new_ser_add:
                    cmds += ['service ' + x for x in new_ser_add]
                if new_ser_del:
                    cmds += ['no service ' + x for x in new_ser_del]
                if isinstance(insert_mongo_datas.get('service'), list):
                    insert_mongo_datas['service'] += [{'object': x['name']} for x in service_info]
                else:
                    insert_mongo_datas['service'] = [{'object': x['name']} for x in service_info]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='服务对象识别……OK!'))
            else:
                if old_ser:
                    cmds += ['no service ' + x for x in old_ser]
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='服务对象识别……OK!'))
            # 自定义源地址
            # old_src_ip = [x.get('ip') for x in old_sec_policy['src_addr']]
            if old_sec_policy['src_addr']:
                old_src_ip = [item_dict.get(type_name) for item_dict in old_sec_policy['src_addr']
                              for type_name in item_dict if type_name == "ip"]
            else:
                old_src_ip = []
            # old_src_range = [x.get('range') for x in old_sec_policy['src_addr']]
            if old_sec_policy['src_addr']:
                old_src_range = [item_dict.get(type_name) for item_dict in old_sec_policy['src_addr']
                                 for type_name in item_dict if type_name == "range"]
            else:
                old_src_range = []
            if manual_src_addr:
                new_src_ip = []
                new_src_range = []
                for src_addr in manual_src_addr:
                    if src_addr['type'] == 'subnet':
                        new_src_ip.append(src_addr['content'])
                        insert_mongo_datas['src_addr'].append({'ip': src_addr['content']})
                    elif src_addr['type'] == 'range':
                        _content = json.loads(src_addr['content'])
                        new_src_range.append(_content['start_ip'] + ' ' + _content['end_ip'])
                        insert_mongo_datas['src_addr'].append(
                            {'range': _content['start_ip'] + ' ' + _content['end_ip']})
                # 归集差异比较结果
                src_ip_add, src_ip_del = HillstoneBase.get_list_diff(old_src_ip, new_src_ip)
                print('src_ip_add, src_ip_del', src_ip_add, src_ip_del)
                src_range_add, src_range_del = HillstoneBase.get_list_diff(old_src_range, new_src_range)
                if src_ip_add:
                    cmds += ['src-ip ' + x for x in src_ip_add]
                if src_ip_del:
                    cmds += ['no src-ip ' + x for x in src_ip_del]
                if src_range_add:
                    cmds += ['src-range ' + x for x in src_range_add]
                if src_range_del:
                    cmds += ['no src-range ' + x for x in src_range_del]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义源地址识别……OK!'))
            else:
                if old_src_ip:
                    cmds += ['no src-ip ' + x for x in old_src_ip]
                if old_src_range:
                    cmds += ['no src-range ' + x for x in old_src_range]
            # 自定义目的地址
            # old_dst_ip = [x.get('ip') for x in old_sec_policy['dst_addr']]
            if old_sec_policy['dst_addr']:
                old_dst_ip = [item_dict.get(type_name) for item_dict in old_sec_policy['dst_addr']
                              for type_name in item_dict if type_name == "ip"]
                # old_dst_range = [x.get('range') for x in old_sec_policy['dst_addr']]
            else:
                old_dst_ip = []
            if old_sec_policy['dst_addr']:
                old_dst_range = [item_dict.get(type_name) for item_dict in old_sec_policy['dst_addr']
                                 for type_name in item_dict if type_name == "range"]
            else:
                old_dst_range = []
            if manual_dst_addr:
                new_dst_ip = []
                new_dst_range = []
                for dst_addr in manual_dst_addr:
                    if dst_addr['type'] == 'subnet':
                        new_dst_ip.append(dst_addr['content'])
                        insert_mongo_datas['dst_addr'].append({'ip': dst_addr['content']})
                    elif dst_addr['type'] == 'range':
                        _content = json.loads(dst_addr['content'])
                        new_dst_range.append(_content['start_ip'] + ' ' + _content['end_ip'])
                        insert_mongo_datas['dst_addr'].append(
                            {'range': _content['start_ip'] + ' ' + _content['end_ip']})
                # 归集差异比较结果
                dst_ip_add, dst_ip_del = HillstoneBase.get_list_diff(old_dst_ip, new_dst_ip)
                dst_range_add, dst_range_del = HillstoneBase.get_list_diff(old_dst_range, new_dst_range)
                if dst_ip_add:
                    cmds += ['dst-ip ' + x for x in dst_ip_add]
                if dst_ip_del:
                    print('dst_ip_del', dst_ip_del)
                    cmds += ['no dst-ip ' + x for x in dst_ip_del]
                if dst_range_add:
                    cmds += ['dst-range ' + x for x in dst_range_add]
                if dst_range_del:
                    cmds += ['no dst-range ' + x for x in dst_range_del]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义目的地址识别……OK!'))
            else:
                if old_dst_ip:
                    cmds += ['no dst-ip ' + x for x in old_dst_ip]
                if old_dst_range:
                    cmds += ['no dst-range ' + x for x in old_dst_range]
            print('cmds', cmds)
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='开始下发配置……'))
            final_paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(final_paths, list):
                """
                [
                    {
                        "results": {
                            "unrecognized": {
                                "unrecognized": "configure"
                            }
                        }
                    }
                ]
                """
                if final_paths:
                    content = default_storage.open(final_paths[0]).read().decode('utf-8')
                    # print('content', content)
                    for _content in content.split('\n'):
                        ws_data = dict(device=device, result='OK', content=_content)
                        # print('ws_data')
                        # print(ws_data)
                        send_ws_msg(group_name=room_group_name, data=ws_data)
                    send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='编辑策略成功!'))
                    MongoOps(db='Automation', coll='sec_policy').delete_many(query=dict(hostip=hostip, id=rule_id))
                    print('insert_mongo_datas')
                    print(insert_mongo_datas)
                    my_mongo = MongoOps(db='Automation', coll='sec_policy')
                    my_mongo.delete_single(query=dict(hostip=hostip, id=rule_id))
                    # my_mongo.update(filter=dict(hostip=hostip, id=rule_id), update={"$set": insert_mongo_datas})
                    my_mongo.insert(insert_mongo_datas)
                    # StandardFSMAnalysis.hillstone_sec_policy(host=device['manage_ip'],
                    #                                          datas=[insert_mongo_datas],
                    #                                          method='insert')
                    return
                else:
                    ws_data = dict(device=device, result='Failed', content='')
                    # print('ws_data')
                    # print(ws_data)
                    send_ws_msg(group_name=room_group_name, data=ws_data)
                    return
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='Failed', content='编辑策略异常, 进程退出'))
        except Exception as e:
            print(str(e))
            # print(traceback.print_exc())
    elif device['vendor__name'] == '华为':
        # send_ws_msg('华为')
        policy_object = kwargs['policy_object']
        name = policy_object['name']
        # if policy_object['is_auto_name']:
        #     name = 'auto_' + datetime.strftime(datetime.now(), '%Y_%m_%d_%H_%M')
        action = policy_object['action']
        description = policy_object.get('description') or ''
        src_zone_object = policy_object['src_zone_object'] or 'any'
        dst_zone_object = policy_object['dst_zone_object'] or 'any'
        src_addr_info = policy_object['src_addr_info']
        dst_addr_info = policy_object['dst_addr_info']
        manual_src_addr = policy_object['manual_src_addr']
        manual_dst_addr = policy_object['manual_dst_addr']
        service_info = policy_object['service_info']
        manual_service_info = policy_object['manual_service_info']
        is_top = policy_object['is_top']
        # 如果安全域为any 则 'source-zone'或者'destination-zone'不需要携带
        policy_data = {
            'rule':
                {
                    '@nc:operation': 'replace',
                    'name': name,
                    # 'desc': 'just for test',
                    # 'source-zone': 'trust',
                    # 'destination-zone': 'untrust',
                    'source-ip': {},
                    'destination-ip': {},
                    'service': {},
                    'action': 'true'
                }
        }
        if src_zone_object:
            if isinstance(src_zone_object, dict):
                policy_data['rule']['source-zone'] = src_zone_object['name']
            elif isinstance(src_zone_object, list):
                policy_data['rule']['source-zone'] = [x['name'] for x in src_zone_object]
            else:
                policy_data['rule']['source-zone'] = src_zone_object
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源安全域识别……OK!'))
        if dst_zone_object:
            if isinstance(dst_zone_object, dict):
                policy_data['rule']['destination-zone'] = dst_zone_object['name']
            elif isinstance(dst_zone_object, list):
                policy_data['rule']['destination-zone'] = [x['name'] for x in dst_zone_object]
            else:
                policy_data['rule']['destination-zone'] = dst_zone_object
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='目的安全域识别……OK!'))
        if description:
            policy_data['rule']['desc'] = description
        if action == 'permit':
            policy_data['rule']['action'] = 'true'
        else:
            policy_data['rule']['action'] = 'false'
        send_ws_msg(group_name=room_group_name,
                    data=dict(device=device, result='OK', content='策略规则识别……{}……OK!'.format(action)))
        if src_addr_info:
            if 'address-set' not in policy_data['rule']['source-ip'].keys():
                #
                policy_data['rule']['source-ip']['address-set'] = [x['name'] for x in src_addr_info]
            else:
                policy_data['rule']['source-ip']['address-set'] += [x['name'] for x in src_addr_info]
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源地址对象识别……OK!'))
        if dst_addr_info:
            if 'address-set' not in policy_data['rule']['destination-ip'].keys():
                #
                policy_data['rule']['destination-ip']['address-set'] = [x['name'] for x in dst_addr_info]
            else:
                policy_data['rule']['destination-ip']['address-set'] += [x['name'] for x in dst_addr_info]
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='目的地址对象识别……OK!'))
        if service_info:
            if 'service-object' not in policy_data['rule']['service'].keys():
                #
                policy_data['rule']['service']['service-object'] = [x['name'] for x in service_info]
            else:
                policy_data['rule']['service']['service-object'] += [x['name'] for x in service_info]
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='服务对象识别……OK!'))
        if manual_src_addr:
            if 'address-ipv4' not in policy_data['rule']['source-ip'].keys():
                policy_data['rule']['source-ip'] = {}
            for src_addr in manual_src_addr:
                if src_addr['type'] == 'subnet':
                    if 'address-ipv4' not in policy_data['rule']['source-ip'].keys():
                        policy_data['rule']['source-ip']['address-ipv4'] = [src_addr['content']]
                    else:
                        policy_data['rule']['source-ip']['address-ipv4'] += [src_addr['content']]
                elif src_addr['type'] == 'range':
                    _content = json.loads(src_addr['content'])
                    if 'address-ipv4-range' not in policy_data['rule']['source-ip'].keys():
                        policy_data['rule']['source-ip']['address-ipv4-range'] = [{
                            'start-ipv4': _content['start_ip'],
                            'end-ipv4': _content['end_ip']}]
                    else:
                        policy_data['rule']['source-ip']['address-ipv4-range'] += [{
                            'start-ipv4': _content['start_ip'],
                            'end-ipv4': _content['end_ip']}]
                    # policy_data['rule']['source-ip']['address-ipv4-range'].append()
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义源地址识别……OK!'))
        if manual_dst_addr:
            if 'address-ipv4' not in policy_data['rule']['destination-ip'].keys():
                policy_data['rule']['destination-ip'] = {}
            for dst_addr in manual_dst_addr:
                if dst_addr['type'] == 'subnet':
                    if 'address-ipv4' not in policy_data['rule']['destination-ip'].keys():
                        policy_data['rule']['destination-ip']['address-ipv4'] = [dst_addr['content']]
                    else:
                        policy_data['rule']['destination-ip']['address-ipv4'] += [dst_addr['content']]

                elif dst_addr['type'] == 'range':
                    _content = json.loads(dst_addr['content'])
                    if 'address-ipv4-range' not in policy_data['rule']['destination-ip'].keys():
                        policy_data['rule']['destination-ip']['address-ipv4-range'] = [
                            {'start-ipv4': _content['start_ip'],
                             'end-ipv4': _content['end_ip']}]
                    else:
                        policy_data['rule']['destination-ip']['address-ipv4-range'] += [
                            {'start-ipv4': _content['start_ip'],
                             'end-ipv4': _content['end_ip']}]
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义目的地址识别……OK!'))
        if manual_service_info:
            if 'service-items' not in policy_data['rule']['service'].keys():
                policy_data['rule']['service']['service-items'] = dict()
            for _manual_service in manual_service_info:
                if _manual_service['type'] in ['tcp', 'udp']:
                    # {
                    #  'type': 'tcp',
                    #  'src_port_start': 0,
                    #  'src_port_end': 65535,
                    #  'dst_port_start': 0,
                    #  'dst_port_end': 65535,
                    #  'content': '源端口0 - 65535,目的端口0 - 65535'
                    #
                    #  },
                    if _manual_service['type'] not in policy_data['rule']['service']['service-items'].keys():
                        policy_data['rule']['service']['service-items'][_manual_service['type']] = []
                    policy_data['rule']['service']['service-items'][_manual_service['type']].append(
                        {'source-port': '{} to {}'.format(str(_manual_service['src_port_start']),
                                                          str(_manual_service['src_port_end'])),
                         'dest-port': '{} to {}'.format(str(_manual_service['dst_port_start']),
                                                        str(_manual_service['dst_port_end']))})
                elif _manual_service['type'] == 'icmp':
                    policy_data['rule']['service']['service-items']['icmp-item'] = [{'icmp-name': 'echo'},
                                                                                    {'icmp-name': 'echo-reply'}]
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='自定义服务识别……OK!'))
        print('policy_data', policy_data)
        send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='开始编辑安全策略规则……!'))
        print(device['manage_ip'])
        if is_top:
            res, content = HuaweiUsgSecPolicyConf.config(host=device['manage_ip'], rule=policy_data, top=True)
        else:
            res, content = HuaweiUsgSecPolicyConf.config(host=device['manage_ip'], rule=policy_data, top=False)
        print('res', 'content')
        print(res, content)
        SecPolicyMain.get_single_huawei(host=device['manage_ip'])
        if not content:
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='编辑策略成功!'))
        else:
            send_ws_msg(group_name=room_group_name,
                        data=dict(device=device, result='Failed', content='编辑安全策略失败:' + content))
    elif device['vendor__name'] == '华三':
        # send_ws_msg('华三')
        policy_object = kwargs['policy_object']
        name = policy_object['name']
        rule_id = policy_object['id']
        # if policy_object['is_auto_name']:
        #     name = 'auto_' + datetime.strftime(datetime.now(), '%Y_%m_%d_%H_%M')
        action = policy_object['action']
        description = policy_object['description'] or ''
        src_zone_object = policy_object['src_zone_object'] or 'Any'
        dst_zone_object = policy_object['dst_zone_object'] or 'Any'
        src_addr_info = policy_object['src_addr_info']
        dst_addr_info = policy_object['dst_addr_info']
        manual_src_addr = policy_object['manual_src_addr']
        manual_dst_addr = policy_object['manual_dst_addr']
        service_info = policy_object['service_info']
        manual_service_info = policy_object['manual_service_info']
        is_top = policy_object['is_top']
        action_map = {
            "deny": "1",
            "permit": "2"
        }
        rule_params = dict(
            method='replace',
            ID=rule_id,
            name=name,
            action=action_map[action],  # 'deny'  permit
            enable='true',  # 'true' 'false'
            log='false',
            counting='false',
            description=description
        )
        dev_info = get_host_info(device['manage_ip'])
        _H3cFirewall = H3cFirewall(dev_info['ip'], dev_info['username'], dev_info['password'])
        ipv4_rule_res, content = _H3cFirewall.config_ipv4_rule(rule=rule_params)

        print('ipv4_rule_res, content', ipv4_rule_res, content)
        if isinstance(ipv4_rule_res, dict):
            ws_data = dict(device=device, result='OK', content='初始化策略规则……OK!')
            send_ws_msg(group_name=room_group_name, data=ws_data)
            rule_id = ipv4_rule_res['ID']
            # 开始拼接具体规则
            data_dict = {
                'SecurityPolicies': [{}]
            }
            if src_zone_object != 'Any':
                if isinstance(src_zone_object, list):
                    src_zone_object = [x['name'] for x in src_zone_object]
                elif isinstance(src_zone_object, dict):
                    src_zone_object = src_zone_object['name']
                data_dict['SecurityPolicies'][0]['IPv4SrcSecZone'] = {
                    '@xc:operation': 'merge',
                    'SrcSecZone':
                        {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': 'false',
                            'NameList': {'NameItem': [src_zone_object]}
                        }
                }
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源安全域识别……OK!'))
            if dst_zone_object != 'Any':
                if isinstance(dst_zone_object, list):
                    dst_zone_object = [x['name'] for x in dst_zone_object]
                elif isinstance(dst_zone_object, dict):
                    dst_zone_object = dst_zone_object['name']
                data_dict['SecurityPolicies'][0]['IPv4DestSecZone'] = {
                    '@xc:operation': 'merge',
                    'DestSecZone':
                        {
                            'ID': rule_id,
                            'SeqNum': None,
                            'IsIncrement': 'false',
                            'NameList': {'NameItem': [dst_zone_object]}
                        }
                }
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='目的安全域识别……OK!'))
            if src_addr_info:
                if isinstance(src_addr_info, list):
                    src_addr_info = [x['name'] for x in src_addr_info]
                data_dict['SecurityPolicies'][0]['IPv4SrcAddr'] = {
                    '@xc:operation': 'merge',
                    'SrcAddr': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': 'false',
                        'NameList': {'NameItem': src_addr_info}}}
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='源地址对象识别……OK!'))
            if dst_addr_info:
                if isinstance(dst_addr_info, list):
                    dst_addr_info = [x['name'] for x in dst_addr_info]
                data_dict['SecurityPolicies'][0]['IPv4DestAddr'] = {
                    '@xc:operation': 'merge',
                    'DestAddr': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': 'false',
                        'NameList': {'NameItem': dst_addr_info}}}
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='目的地址对象识别……OK!'))
            if service_info:
                if isinstance(service_info, list):
                    service_info = [x['name'] for x in service_info]
                data_dict['SecurityPolicies'][0]['IPv4ServGrp'] = [{
                    '@xc:operation': 'merge',
                    'ServGrp': {
                        'ID': rule_id,
                        'SeqNum': None,
                        'IsIncrement': 'false',
                        'NameList': {'NameItem': service_info}
                    }}]
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='服务对象识别……OK!'))
            if manual_src_addr:
                _src_content = []
                if isinstance(manual_src_addr, list):
                    for _src_addr in manual_src_addr:
                        if _src_addr['type'] == 'subnet':
                            _src_content.append(_src_addr['content'])
                        elif _src_addr['type'] == 'range':
                            _content = json.loads(_src_addr['content'])
                            _src_content.append(_content['start_ip'] + '-' + _content['end_ip'])
                data_dict['SecurityPolicies'][0]['IPv4SrcSimpleAddr'] = {
                    '@xc:operation': 'merge',
                    'SrcSimpleAddr':
                        {
                            'ID': ipv4_rule_res['ID'],
                            'SeqNum': None,
                            'IsIncrement': 'false',
                            'SimpleAddrList':
                                {'SimpleAddrItem': [x for x in _src_content]}
                        }
                }
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='OK', content='自定义源地址对象识别……OK!'))
            if manual_dst_addr:
                _dst_content = []
                if isinstance(manual_dst_addr, list):
                    for _dst_addr in manual_dst_addr:
                        if _dst_addr['type'] == 'subnet':
                            _dst_content.append(_dst_addr['content'])
                        elif _dst_addr['type'] == 'range':
                            _content = json.loads(_dst_addr['content'])
                            _dst_content.append(_content['start_ip'] + '-' + _content['end_ip'])
                        print(_dst_content)
                data_dict['SecurityPolicies'][0]['IPv4DestSimpleAddr'] = {
                    '@xc:operation': 'merge',
                    'DestSimpleAddr':
                        {
                            'ID': ipv4_rule_res['ID'],
                            'SeqNum': None,
                            'IsIncrement': 'false',
                            'SimpleAddrList':
                                {'SimpleAddrItem': [x for x in _dst_content]}
                        }
                }
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='OK', content='自定义目的地址对象识别……OK!'))
            if manual_service_info:
                type_map = {
                    "tcp": "0",
                    "udp": "1",
                    "icmp": "2"
                }
                ServObjList = []
                for _manual_service in manual_service_info:
                    if _manual_service['type'] in ['tcp', 'udp']:
                        # {
                        #  'type': 'tcp',
                        #  'src_port_start': 0,
                        #  'src_port_end': 65535,
                        #  'dst_port_start': 0,
                        #  'dst_port_end': 65535,
                        #  'content': '源端口0 - 65535,目的端口0 - 65535'
                        # '{ "Type": "0", "StartSrcPort": "0", "EndSrcPort": "65535", "StartDestPort": "80", "EndDestPort": "80" }'
                        #  },
                        if _manual_service['type']:
                            _tmp_obj = {
                                "Type": type_map[_manual_service['type']],
                                "StartSrcPort": str(_manual_service['src_port_start']),
                                "EndSrcPort": str(_manual_service['src_port_end']),
                                "StartDestPort": str(_manual_service['dst_port_start']),
                                "EndDestPort": str(_manual_service['dst_port_end']),
                            }
                            ServObjList.append({'ServObjItem': json.dumps(_tmp_obj)})
                    elif _manual_service['type'] == 'icmp':
                        _tmp_obj = {
                            "Type": type_map[_manual_service['type']]
                        }
                        ServObjList.append({'ServObjItem': json.dumps(_tmp_obj)})
                if ServObjList:
                    # 定义 自定义服务的数据结构
                    data_dict['SecurityPolicies'][0]['IPv4ServObj'] = [
                        {
                            '@xc:operation': 'merge',
                            'ServObj':
                                {
                                    'ID': rule_id,
                                    'SeqNum': None,
                                    'IsIncrement': 'false',
                                    'ServObjList': ServObjList
                                }
                        }
                    ]
                    send_ws_msg(group_name=room_group_name,
                                data=dict(device=device, result='OK', content='自定义服务对象识别……OK!'))
            print('data_dict')
            print(data_dict)
            send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='开始编辑安全策略规则……!'))
            if is_top:
                config_policy_res, policy_content = _H3cFirewall.config_sec_policy(config_data=data_dict,
                                                                                   rule_id=rule_id, top=True)
            else:
                config_policy_res, policy_content = _H3cFirewall.config_sec_policy(config_data=data_dict,
                                                                                   rule_id=rule_id, top=False)
            print(config_policy_res, policy_content)
            SecPolicyMain.get_single_h3c(host=device['manage_ip'])
            if config_policy_res:
                send_ws_msg(group_name=room_group_name, data=dict(device=device, result='OK', content='编辑策略成功!'))
            else:
                send_ws_msg(group_name=room_group_name,
                            data=dict(device=device, result='Failed', content='新建安全策略失败:' + policy_content))

            return ipv4_rule_res, content
        else:
            ws_data = dict(device=device, result='Failed', content='初始化安全策略规则失败:' + content)
            send_ws_msg(group_name=room_group_name, data=ws_data)
            return '', []
    return '', []


# 新建安全策略总任务
# def _bulk_sec_policy(**kwargs):
#     """
#     room_group_name consumers 自动分配
#     :param kwargs:
#     :return:
#     """
#     post_param = kwargs
#     # kwargs = json.loads(kwargs)
#     # post_param = kwargs['kwargs']
#     # print(post_param)
#     if isinstance(post_param['device_object'], dict):
#         post_param['device_object'] = [post_param['device_object']]
#     # 编辑
#     if 'edit_policy_object' in post_param.keys():
#         for device in post_param['device_object']:
#             params = {'device_object': device, 'policy_object': post_param['edit_policy_object'],
#                       'room_group_name': post_param['room_group_name']}
#             tmp = edit_sec_policy.apply_async(kwargs=params, queue='config_backup')
#     # 新建
#     elif 'policy_object' in post_param.keys():
#         for device in post_param['device_object']:
#             params = {'device_object': device, 'policy_object': post_param['policy_object'],
#                       'room_group_name': post_param['room_group_name']}
#             # print('params', params)
#             tmp = create_sec_policy_sub.apply_async(kwargs=params, queue='config_backup')
#             # tmp = create_sec_policy_sub.apply_async(kwargs=params)
#             # print('taskid', tmp)
#     return


# 配置地址组V2
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def address_set(self, **post_param):
    _FirewallMain = FirewallMain(post_param['hostip'])
    # "event_id": event_id.id,  # 关联事件
    event_id = post_param.get('event_id') or None
    # # 更新地址组
    # if all(k in post_param for k in ("vendor", "update_device")):
    #     if post_param['vendor'] == 'Hillstone':
    #         _FirewallMain.refresh_hillstone_configuration()
    #     return
    if post_param['vendor'] == 'H3C':
        # 首先判断具体操作
        """ 
            "user": "jmli8",
            "vendor": "H3C", 
            "add_detail_ip": true,
            "ip_mask": "1.1.1.1/32",
            "name": "12.101测试",
            "hostip": "10.254.12.101"
        """
        # 地址组条目操作
        if 'add_detail_ip' in post_param.keys() or 'add_detail_range' in post_param.keys():
            # step 1 生成netconf xml 配置
            post_param['method'] = 'create'
        # 地址组条目操作
        elif 'del_detail_ip' in post_param.keys() or 'del_detail_range' in post_param.keys():
            # step 1 生成netconf xml 配置
            post_param['method'] = 'remove'
        # 地址组条目操作
        elif 'del_detail_hostip' in post_param.keys():
            # step 1 生成netconf xml 配置
            post_param['method'] = 'remove'
        # 地址组对象操作
        elif 'add_object' in post_param.keys() or 'del_object' in post_param.keys():
            # step 1 生成netconf xml 配置
            post_param['method'] = 'object'
        else:
            raise ValueError("address_set 没有匹配到关键字")
        class_method = 'config_oms_objs'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        flag, cmds, back_off_cmds = _FirewallMain.h3c_address_detail(**post_param)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=post_param.get('task_id') or str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=post_param.get('task') or AutoFlowTasks.ADDRESS_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds),
            flag=flag,
            event_id=event_id,
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Huawei':
        class_method = 'config_address'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.huawei_address_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=post_param.get('task_id') or str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=post_param.get('task') or AutoFlowTasks.ADDRESS_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds),
            event_id=event_id,
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Hillstone':
        # 首先判断具体操作
        """ 
            "user": "jmli8",
            "vendor": "Hillstone", 
            "add_detail_ip": true,
            "ip_mask": "1.1.1.1/32",
            "name": "AIYL_white_list",
            "hostip": "10.254.3.102"
        """
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.hillstone_address_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=post_param.get('task_id') or str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param.get('user') or '',
            remote_ip=post_param.get('remote_ip'),
            task=post_param.get('task') or AutoFlowTasks.ADDRESS_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='SSH',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds),
            event_id=event_id,
        )
        # print(_data)
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    return


# 配置服务组V2
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def service_set(self, **post_param):
    _FirewallMain = FirewallMain(post_param['hostip'])
    # 更新服务组
    if all(k in post_param for k in ("vendor", "update_device")):
        if post_param['vendor'] == 'Hillstone':
            _FirewallMain.refresh_hillstone_configuration()
        return
    if post_param['vendor'] == 'H3C':
        # 首先判断具体操作
        class_method = 'config_oms_objs'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.h3c_service_detail(**post_param)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SERVICE_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Huawei':
        class_method = 'config_service'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.huawei_service_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SERVICE_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Hillstone':
        # 首先判断具体操作
        """ 
            "user": "jmli8",
            "add_object": true,
            "vendor":"Hillstone",
            "hostip":"10.254.12.16",
            "hostid": 2494,
            "name":"jmli12test",
            "objects":[
                {
                    "add_detail":true,
                    "protocol":"TCP", 
                    "start_src_port":1, 
                    "end_src_port":65535,
                    "start_dst_port":8443,
                    "end_dst_port":8443,
                }
            ]
        """
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.hillstone_service_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SERVICE_SET,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='SSH',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        print(_data)
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    return


# 配置SNAT
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def config_snat(self, **post_param):
    _FirewallMain = FirewallMain(post_param['hostip'])
    # 刷新配置
    if all(k in post_param for k in ("vendor", "update_device")):
        if post_param['vendor'] == 'Hillstone':
            _FirewallMain.refresh_hillstone_configuration()
        return
    if post_param['vendor'] == 'H3C':
        # 首先判断具体操作
        class_method = 'config_top'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.h3c_snat_detail(**post_param)
        print(cmds)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SNAT,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            class_method=class_method,
            method='NETCONF',
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Huawei':
        class_method = 'config_nat_policy'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.huawei_snat_detail(**post_param)
        print(cmds, back_off_cmds)
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SNAT,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Hillstone':
        # 首先判断具体操作
        """ 
        """
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        try:
            cmds, back_off_cmds = _FirewallMain.hillstone_snat_detail(**post_param)
            print(cmds, back_off_cmds)
            _data = dict(
                order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
                task_id=str(self.request.id),
                origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
                commit_user=post_param['user'],
                remote_ip=post_param.get('remote_ip'),
                task=AutoFlowTasks.SNAT,
                device=post_param['hostip'],
                device_id=post_param['hostid'],
                kwargs=json.dumps(post_param),
                commands=json.dumps(cmds),
                method='SSH',
                class_method=class_method,
                back_off_commands=json.dumps(back_off_cmds)
            )
            # print(_data)
            # _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
        except RuntimeError as e:
            send_msg_sec_manage("安全纳管引擎\n公网SNAT发布\n任务状态：失败\n原因:生成配置过程异常\n提示:{}".format(str(e)))
        except Exception as e:
            # print(traceback.print_exc())
            send_msg_sec_manage("安全纳管引擎\n公网SNAT发布\n任务状态：失败\n原因:生成配置过程异常\n提示:{}".format(str(e)))
    return


# 配置DNATV2
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def config_dnat(self, **post_param):
    """

    :param self:
    :param kwargs:
    :return:
    """
    _FirewallMain = FirewallMain(post_param['hostip'])
    # 更新DNAT
    if all(k in post_param for k in ("vendor", "update_device")):
        if post_param['vendor'] == 'Hillstone':
            _FirewallMain.refresh_hillstone_configuration()
        return
    if post_param['vendor'] == 'H3C':
        # 首先判断具体操作
        class_method = 'config_top'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.h3c_dnat_detail(**post_param)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.DNAT,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            class_method=class_method,
            method='NETCONF',
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Huawei':
        class_method = 'config_dnat'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.huawei_dnat_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.DNAT,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='NETCONF',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param['vendor'] == 'Hillstone':
        # 首先判断具体操作
        """ 
            "user": "jmli8",
            "add_object": true,
            "vendor":"Hillstone",
            "hostip":"10.254.12.16",
            "hostid": 2494,
            "name":"jmli12test",
            "from": {"object": "address-book"},
            "to": {"ip":"1.2.3.4/32"},
            "service": "jmli8test",
            "trans_to": {"slb_server_pool":"36.7.109.47_1_0_5556_5557"},
            "port": 80,
            "load_balance": false,
            "log": false,
            "track_ping": false
        """
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        try:
            cmds, back_off_cmds = _FirewallMain.hillstone_dnat_detail(**post_param)
            _data = dict(
                order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
                task_id=str(self.request.id),
                origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
                commit_user=post_param['user'],
                remote_ip=post_param.get('remote_ip'),
                task=AutoFlowTasks.DNAT,
                device=post_param['hostip'],
                device_id=post_param['hostid'],
                kwargs=json.dumps(post_param),
                commands=json.dumps(cmds),
                method='SSH',
                class_method=class_method,
                back_off_commands=json.dumps(back_off_cmds)
            )
            # print(_data)
            _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
        except RuntimeError as e:
            send_msg_sec_manage("安全纳管引擎\n公网DNAT发布\n任务状态：失败\n原因:生成配置过程异常\n提示:{}".format(str(e)))
        except Exception as e:
            # print(traceback.print_exc())
            send_msg_sec_manage("安全纳管引擎\n公网DNAT发布\n任务状态：失败\n原因:生成配置过程异常\n提示:{}".format(str(e)))
    return


# 配置SLB负载均衡
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def config_slb(self, **post_param):
    _FirewallMain = FirewallMain(post_param['hostip'])
    if post_param.get('vendor') == 'H3C':
        pass
    elif post_param.get('vendor') == 'Huawei':
        pass
    elif post_param.get('vendor') == 'Hillstone':
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        cmds, back_off_cmds = _FirewallMain.hillstone_slb_detail(**post_param)
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SLB,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            method='SSH',
            class_method=class_method,
            back_off_commands=json.dumps(back_off_cmds)
        )
        print(_data)
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
        # path, ttp_res, cmds, error_info, before_cmds = HillstoneBase.config_slb_pool(**kwargs)
        # tmp = {
        #     "task_id": str(self.request.id),
        #     "author": kwargs.get('author'),
        #     "params": kwargs,
        #     "before_commands": before_cmds,
        #     "config_commands": cmds,
        #     "path": path,
        #     "result": ttp_res if ttp_res else 'SUCCESS',
        #     "error_info": error_info,
        #     "log_time": datetime.now()
        # }
        # slb_config_mongo.insert(tmp)
    else:
        return


# 配置安全策略V2
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
@WebSocket()
def config_sec_policy(self, **post_param):
    _FirewallMain = FirewallMain(post_param['hostip'])
    if post_param.get('vendor') == 'H3C':
        # 首先判断具体操作
        class_method = 'config_top'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        if 'sort_object' in post_param.keys():
            class_method = 'action_top'
        cmds, back_off_cmds = _FirewallMain.h3c_sec_policy_detail(**post_param)
        print(cmds)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SEC_POLICY,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            class_method=class_method,
            method='NETCONF',
            back_off_commands=json.dumps(back_off_cmds)
        )
        _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param.get('vendor') == 'Huawei':
        class_method = 'config_sec_policy'
        cmds, back_off_cmds = _FirewallMain.huawei_sec_policy(**post_param)
        print(cmds)
        # step 2 生成流程
        _data = dict(
            order_code=post_param.get('order_code'),
            task_id=str(self.request.id),
            origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
            commit_user=post_param['user'],
            remote_ip=post_param.get('remote_ip'),
            task=AutoFlowTasks.SEC_POLICY,
            device=post_param['hostip'],
            device_id=post_param['hostid'],
            kwargs=json.dumps(post_param),
            commands=json.dumps(cmds),
            class_method=class_method,
            method='NETCONF',
            back_off_commands=json.dumps(back_off_cmds)
        )
        send_msg_sec_manage("华为防火墙因为现网BUG问题")
        # _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
    elif post_param.get('vendor') == 'Hillstone':
        class_method = 'Hillstone'  # 类方法，山石直接下发命令，所以不需要，主要给华三华为对应对应类方法使用
        try:
            cmds, back_off_cmds = _FirewallMain.hillstone_sec_policy_detail(**post_param)
            # print(cmds, back_off_cmds)
            _data = dict(
                order_code=post_param.get('order_code') if post_param.get('order_code') else ' ',
                task_id=str(self.request.id),
                origin=post_param.get('origin') if post_param.get('origin') else '运维平台',
                commit_user=post_param['user'],
                remote_ip=post_param.get('remote_ip'),
                task=AutoFlowTasks.SEC_POLICY,
                device=post_param['hostip'],
                device_id=post_param['hostid'],
                kwargs=json.dumps(post_param),
                commands=json.dumps(cmds),
                method='SSH',
                class_method=class_method,
                back_off_commands=json.dumps(back_off_cmds)
            )
            # print(_data)
            _FirewallMain.flow_engine(*[cmds, back_off_cmds, class_method], **_data)
        except Exception as e:
            # print(traceback.print_exc())
            send_msg_sec_manage("安全纳管引擎\n公网DNAT发布\n任务状态：失败\n原因:生成配置过程异常\n提示:{}".format(str(e)))
    return


# 一键封堵V2/场景任务执行模块
@shared_task(base=AxeTask, once={'graceful': True}, bind=True)
def bulk_deny_by_address(self, **post_param):
    """
    hosts:
    {'ans_group_name': '护网行动', 'ans_group_hosts__ans_host': '10.254.4.204',
     'ans_group_hosts__ans_obj': 'wakuang_deny_ip',
     'ans_group_hosts__ans_memo': 'wakuang_deny_ip'},
     {'ans_group_name': '护网行动', 'ans_group_hosts__ans_host': '10.254.4.159',
     'ans_group_hosts__ans_obj': 'deny-hw', 'ans_group_hosts__ans_memo': 'deny-hw'}]
    :param self:
    :param post_param:
    :return:
    """
    hosts = post_param['inventory'][0]['ans_group_hosts']

    event_id = AutoEvent.objects.create(**dict(commit_user=post_param['user'],
                                               remote_ip=post_param['remote_ip'],
                                               task=AutoFlowTasks.DENY))
    for host in hosts:
        if post_param.get('ip_mask'):
            if post_param.get('add_detail_ip'):
                post_data = {
                    "origin": post_param['origin'],
                    "vendor": host['ans_vars']['vendor__alias'],
                    "add_detail_ip": True,
                    "ip_mask": post_param['ip_mask'],
                    "name": post_param['inventory'][0]['ans_obj'],
                    "hostip": post_param['inventory'][0]['ans_host'],  # 这个很重要，如果有绑定ip的话，是以绑定IP来下发配置
                    "hostid": host['ans_vars']['id'],
                    "user": post_param['user'],
                    "remote_ip": post_param['remote_ip'],
                    "room_group_name": post_param.get('room_group_name'),
                    "task_id": str(self.request.id),
                    "task": AutoFlowTasks.DENY,
                    "event_id": event_id.id,  # 关联事件
                }
                address_set.apply_async(kwargs=post_data, queue=CELERY_QUEUE,
                                        retry=True)  # config_backup
            elif post_param.get('del_detail_ip'):
                post_data = {
                    "origin": post_param['origin'],
                    "vendor": host['ans_vars']['vendor__alias'],
                    "del_detail_ip": True,
                    "ip_mask": post_param['ip_mask'],
                    "name": post_param['inventory'][0]['ans_obj'],
                    "hostip": post_param['inventory'][0]['ans_host'],
                    "hostid": host['ans_vars']['id'],
                    "user": post_param['user'],
                    "remote_ip": post_param['remote_ip'],
                    "room_group_name": post_param.get('room_group_name'),
                    "task_id": str(self.request.id),
                    "task": AutoFlowTasks.DENY,
                    "event_id": event_id.id,  # 关联事件
                }
                address_set.apply_async(kwargs=post_data, queue=CELERY_QUEUE,
                                        retry=True)  # config_backup
        if post_param.get('range_start') and post_param.get('range_end'):
            if post_param.get('add_detail_range'):
                post_data = {
                    "origin": post_param['origin'],
                    "vendor": host['ans_vars']['vendor__alias'],
                    "add_detail_range": True,
                    "range_start": post_param['range_start'],
                    "range_end": post_param['range_end'],
                    "name": post_param['inventory'][0]['ans_obj'],
                    "hostip": post_param['inventory'][0]['ans_host'],
                    "hostid": host['ans_vars']['id'],
                    "user": post_param['user'],
                    "remote_ip": post_param['remote_ip'],
                    "room_group_name": post_param.get('room_group_name'),
                    "task_id": str(self.request.id),
                    "task": AutoFlowTasks.DENY,
                    "event_id": event_id.id,  # 关联事件
                }
                address_set.apply_async(kwargs=post_data, queue=CELERY_QUEUE,
                                        retry=True)  # config_backup
            elif post_param.get('del_detail_range'):
                post_data = {
                    "origin": post_param['origin'],
                    "vendor": host['ans_vars']['vendor__alias'],
                    "del_detail_range": True,
                    "range_start": post_param['range_start'],
                    "range_end": post_param['range_end'],
                    "name": post_param['inventory'][0]['ans_obj'],
                    "hostip": post_param['inventory'][0]['ans_host'],
                    "hostid": host['ans_vars']['id'],
                    "user": post_param['user'],
                    "remote_ip": post_param['remote_ip'],
                    "room_group_name": post_param.get('room_group_name'),
                    "task_id": str(self.request.id),
                    "task": AutoFlowTasks.DENY,
                    "event_id": event_id.id,  # 关联事件
                }
                address_set.apply_async(kwargs=post_data, queue=CELERY_QUEUE,
                                        retry=True)  # config_backup
    return


if __name__ == '__main__':
    pass
    # import django
    # django.setup()
