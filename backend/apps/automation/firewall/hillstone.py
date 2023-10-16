# -*- coding: utf-8 -*-
# @Time    : 2021/5/12 10:45
# @Author  : LiJiaMin
# @Site    : 
# @File    : hillstone.py
# @Software: PyCharm
import copy
import json
import os

import jinja2
from django.core.files.storage import default_storage
from netaddr import IPNetwork

from apps.automation.tools.model_api import get_device_info_v2
# from apps.automation.utils.auto_main import BatManMain, HillstoneFsm
# from apps.automation.utils.model_api import get_device_info_v2

from utils.connect_layer.auto_main import BatManMain, HillstoneFsm
from utils.db.mongo_ops import MongoOps

package_dir = os.path.dirname(__file__)


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
        if (type(v1) == dict) and (type(v2) == dict):
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


# 山石Base 防火墙统一处理由SecPolicyMain
class HillstoneBase(object):

    def __init__(self, cmds: list, dev_info: dict, dev_infos: dict):
        self.cmds = cmds
        self.dev_info = dev_info,
        self.dev_infos = dev_infos

    # 比较列表差异
    @staticmethod
    def get_list_diff(old, new) -> [list, list]:
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

    # 获取设备信息
    @staticmethod
    def get_host_info(host) -> [list, dict]:
        dev_infos = get_device_info_v2(manage_ip=host)
        cmds = []
        if dev_infos:
            username = dev_infos[0]['username']  # 用户名
            password = dev_infos[0]['password']  # 密码
            port = dev_infos[0]['port']
            if dev_infos[0]['soft_version'].find('5.5R6') != -1:
                cmds = ['configure']
            # if dev_infos[0]['soft_version'].startswith('Version 5.0') and 'ssh' in dev_infos[0]['protocol']:
            #     cmds = ['configure']
            # elif host in ['10.254.3.102', '10.254.5.68', '10.254.12.242',
            #               '172.16.73.250', '172.22.170.1', '103.108.2.242',
            #               '172.16.73.249', '172.22.57.203', '172.17.1.41']:
            # cmds = ['configure']
            device_ios = 'hillstone'
            # device_ios = 'juniper'
            # device_ios = 'juniper_junos'
            # device_ios = 'cisco_ios'
            if 'telnet' in dev_infos[0]['protocol']:
                device_ios = 'hillstone_telnet'
            # fsm_flag = 'hillstone'  # 解析器标识
            dev_info = {
                'device_type': device_ios,
                'ip': host,
                'port': port,
                'username': username,
                'password': password,
                'timeout': 100,  # float，连接超时时间，默认为100
                'session_timeout': 100,  # float，每个请求的超时时间，默认为60，
                'encoding': 'utf-8'
            }
            if dev_infos[0].get('bind_ip__ipaddr'):
                dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
            return cmds, dev_info, dev_infos[0]
        return cmds, {}, {}

    # 新建地址组
    @staticmethod
    def create_address(**kwargs):
        """
        {'vendor': 'hillstone',
         'create_address_obj': {'name': 'hillstone', 'description': 'miaoshu',
         'object':
         [{'content': '10.254.0.1/24', 'type': 'subnet', 'id': 'F7zK7SmT4Z'},
         {'content': '{"start_ip":"10.254.0.2","end_ip":"10.254.0.3"}', 'type': 'range', 'id': 'mWQCmPS3pB'}]}}
        :param kwargs:
        :return:
        """
        host = kwargs['hostip']
        # 获取设备信息和命令前缀，v5.0需要手动加config进入配置模式
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        mongo_data = dict()
        if dev_info:
            name = kwargs['create_address_obj']['name']
            cmds += ['address ' + name]
            if kwargs['create_address_obj'].get('description'):
                description = 'description ' + kwargs['create_address_obj']['description']
                cmds += [description]
            contents = kwargs['create_address_obj']['object']
            mongo_data['hostip'] = host
            mongo_data['name'] = kwargs['create_address_obj']['name']
            mongo_data['description'] = kwargs['create_address_obj'].get('description')
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'subnet':
                        # 标准格式化 192.168.1.1/24 -> 192.168.1.0/24
                        _ip = IPNetwork(_cmd['content']).network.format() + '/' + str(IPNetwork(
                            _cmd['content']).netmask.netmask_bits())
                        cmds += ['ip ' + _ip]
                        if 'ip' in mongo_data.keys():
                            mongo_data['ip'].append(dict(ip=_ip))
                        else:
                            mongo_data['ip'] = [dict(ip=_ip)]
                    if _cmd['type'] == 'host':
                        # host "ifconfig.me"
                        # host "*.cip.cc"
                        # host "*.ubuntu.com"
                        cmds += ['host ' + _cmd['content']]
                        if 'host' in mongo_data.keys():
                            mongo_data['host'].append(dict(host=_cmd['content']))
                        else:
                            mongo_data['host'] = [dict(host=_cmd['content'])]
                    if _cmd['type'] == 'range':
                        _tmp = json.loads(_cmd['content'])
                        if 'range' in mongo_data.keys():
                            mongo_data['range'].append(dict(start=_tmp['start_ip'], end=_tmp['end_ip']))
                        else:
                            mongo_data['range'] = [dict(start=_tmp['start_ip'], end=_tmp['end_ip'])]
                        cmds += ['range ' + _tmp['start_ip'] + ' ' + _tmp['end_ip']]
                paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
                if paths:
                    MongoOps(db='Automation', coll='hillstone_address').insert(mongo_data)
                if isinstance(paths, list):
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
                    return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
                elif isinstance(paths, bool):
                    return False, []
                return paths[0], []
        return '', []

    # 删除地址组
    @staticmethod
    def delete_address(**kwargs):
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            name = 'no address ' + kwargs['delete_address_obj']['name']
            cmds += [name]
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
                """
                [
                    {
                        "results": {
                            "create": {
                                "rule_id": "4"
                            },
                            "unrecognized": {
                                "unrecognized": "configure"
                            }
                        }
                    }
                ]
                """
                return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
            return paths[0], []
        return '', []

    # 编辑地址组(旧)
    @staticmethod
    def edit_address(**kwargs):
        host = kwargs['hostip']
        name = kwargs['edit_address_obj']['name']
        old_res = MongoOps(db='Automation', coll='hillstone_address').find(query_dict=dict(hostip=host, name=name),
                                                                           fileds={'_id': 0})
        if old_res:
            old_res = old_res[0]
            # print('old_res', old_res)
            new_data = dict()
            new_data['hostip'] = host
            new_data['name'] = kwargs['edit_address_obj']['name']
            new_data['description'] = kwargs['edit_address_obj'].get('description')
            contents = kwargs['edit_address_obj']['object']
            for _cmd in contents:
                if _cmd['type'] == 'subnet':
                    _ip = IPNetwork(_cmd['content']).network.format() + '/' + str(IPNetwork(
                        _cmd['content']).netmask.netmask_bits())
                    if 'ip' in new_data.keys():
                        new_data['ip'].append(dict(ip=_ip))
                    else:
                        new_data['ip'] = [dict(ip=_ip)]
                if _cmd['type'] == 'host':
                    # host "ifconfig.me"
                    # host "*.cip.cc"
                    # host "*.ubuntu.com"
                    if 'host' in new_data.keys():
                        new_data['host'].append(dict(host=_cmd['content']))
                    else:
                        new_data['host'] = [dict(host=_cmd['content'])]
                if _cmd['type'] == 'range':
                    # _tmp = json.loads(_cmd['content'])  # 前端传递是json格式 需要再次解开
                    # _tmp = _cmd['content']
                    _tmp = json.loads(_cmd['content'])
                    if 'range' in new_data.keys():
                        new_data['range'].append(dict(start=_tmp['start_ip'], end=_tmp['end_ip']))
                    else:
                        new_data['range'] = [dict(start=_tmp['start_ip'], end=_tmp['end_ip'])]
            # print('new_data', new_data)
            cmp = CompareTwoDict(new_data, old_res)
            # print('差异配置如下')
            # print(cmp.main())
            res = cmp.main()
            # 归集IP 和range 集合
            old_ip = []
            old_range = []
            old_host = []
            new_ip = []
            new_range = []
            new_host = []
            # 归集差异比较结果
            cmd_ip_add = []
            cmd_ip_del = []
            cmd_range_add = []
            cmd_range_del = []
            cmd_host_add = []
            cmd_host_del = []
            if res.get('ip') != '=':
                if 'ip' in old_res.keys():
                    old_ip = [x['ip'] for x in old_res['ip']]
                if 'ip' in new_data.keys():
                    new_ip = [x['ip'] for x in new_data['ip']]
                cmd_ip_add, cmd_ip_del = HillstoneSecPolicyConf.get_list_diff(old_ip, new_ip)
                # print('新增IP', cmd_ip_add)
                # print('删除IP', cmd_ip_del)
            if res.get('range') != '=':
                if 'range' in old_res.keys():
                    old_range = [x['start'] + '-' + x['end'] for x in old_res['range']]
                if 'range' in new_data.keys():
                    new_range = [x['start'] + '-' + x['end'] for x in new_data['range']]
                cmd_range_add, cmd_range_del = HillstoneSecPolicyConf.get_list_diff(old_range, new_range)
                # print('新增range', cmd_range_add)
                # print('删除range', cmd_range_del)
            if res.get('host') != '=':
                if 'host' in old_res.keys():
                    old_host = [x['host'] for x in old_res['host']]
                if 'host' in new_data.keys():
                    new_host = [x['host'] for x in new_data['host']]
                cmd_host_add, cmd_host_del = HillstoneSecPolicyConf.get_list_diff(old_host, new_host)
                # print('新增host', cmd_host_add)
                # print('删除host', cmd_host_del)
            if not res.get('ip') and not res.get('range') and not res.get('host'):
                return '', '当前没有任何修改!'
            cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
            if dev_info:
                name = 'address ' + kwargs['edit_address_obj']['name']
                cmds += [name]
                # print('new_data', new_data)
                # print('old_res', old_res)
                if new_data['description'] != old_res.get('description'):
                    description = 'description ' + kwargs['edit_address_obj']['description']
                    cmds += [description]
                if cmd_ip_add:
                    cmds += ['ip ' + x for x in cmd_ip_add]
                if cmd_ip_del:
                    cmds += ['no ip ' + x for x in cmd_ip_add]
                if cmd_host_add:
                    cmds += ['host ' + x for x in cmd_host_add]
                if cmd_host_del:
                    cmds += ['no host ' + x for x in cmd_host_del]
                if cmd_range_add:
                    cmds += ['range ' + ' '.join(x.split('-')) for x in cmd_range_add]
                if cmd_range_del:
                    cmds += ['no range ' + ' '.join(x.split('-')) for x in cmd_range_del]
            # print('cmds', cmds)
            if len(cmds) >= 2:
                paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
                if paths:
                    my_mongo = MongoOps(db='Automation', coll='hillstone_address')
                    # print('new_data', new_data)
                    my_mongo.delete_many(query=dict(hostip=host, name=kwargs['edit_address_obj']['name']))
                    my_mongo.insert(new_data)
                if isinstance(paths, list):
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
                    return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
                elif isinstance(paths, bool):
                    return False, []
                return paths[0], []
            else:
                return '', '当前没有任何修改!'
        return '', []

    # 新建服务组
    @staticmethod
    def create_service(**kwargs):
        """
        {
            "vendor": "hillstone",
            "create_service_obj": {
                "description": "jmli12_test",
                "name": "test_addr",
                "object": [
                    {
                        "type": "tcp",
                        "src_port_start": "0",
                        "src_port_end": "65535",
                        "dst_port_start": "80",
                        "dst_port_end": "80",
                    },
                    {
                        "type": "icmp",
                    }
                ]
            },
            "hostip": "10.254.12.16"
        }
        """
        host = kwargs['hostip']
        no_save = kwargs.get('no_save')
        # 获取设备信息和命令前缀，v5.0需要手动加config进入配置模式
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        mongo_data = dict()
        if dev_info:
            name = 'service ' + kwargs['create_service_obj']['name']
            cmds += [name]
            if kwargs['create_service_obj'].get('description'):
                description = 'description ' + kwargs['create_service_obj']['description']
                cmds += [description]
            contents = kwargs['create_service_obj']['object']
            mongo_data['hostip'] = host
            mongo_data['name'] = kwargs['create_service_obj']['name']
            mongo_data['description'] = kwargs['create_service_obj'].get('description')
            mongo_data['items'] = []
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'tcp' or _cmd['type'] == 'udp':
                        if _cmd['src_port_start'] == '0' and _cmd['src_port_end'] == '65535':
                            cmds += ['{} dst-port {} {}'.format(_cmd['type'],
                                                                _cmd['dst_port_start'],
                                                                _cmd['dst_port_end'])]
                            mongo_data['items'].append({
                                'dst-port-min': int(_cmd['dst_port_start']),
                                'dst-port-max': int(_cmd['dst_port_end']),
                                'protocol': 'tcp' if _cmd['type'] == 'tcp' else 'udp'
                            })
                        else:
                            cmds += ['{} dst-port {} {} src-port {} {}'.format(_cmd['type'],
                                                                               _cmd['dst_port_start'],
                                                                               _cmd['dst_port_end'],
                                                                               _cmd['src_port_start'],
                                                                               _cmd['src_port_end'])]
                            mongo_data['items'].append({
                                'dst-port-min': int(_cmd['dst_port_start']),
                                'dst-port-max': int(_cmd['dst_port_end']),
                                'src-port-min': int(_cmd['src_port_start']),
                                'src-port-max': int(_cmd['src_port_end']),
                                'protocol': 'tcp' if _cmd['type'] == 'tcp' else 'udp'
                            })
                    elif _cmd['type'] == 'icmp':
                        """
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
                        cmds += ['icmp type 8']
                        mongo_data['items'].append({
                            'protocol': 'icmp'
                        })
                error = ''
                if no_save:
                    paths, error = BatManMain.hillstone_config_cmds_no_save(*cmds, **dev_info)
                else:
                    paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
                if paths:
                    MongoOps(db='Automation', coll='hillstone_service').insert(mongo_data)
                if isinstance(paths, list):
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
                    return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
                elif isinstance(paths, bool):
                    return False, []
                return paths[0], []
        return '', []

    # 删除服务组
    @staticmethod
    def delete_service(**kwargs):
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            name = kwargs['delete_service_obj']['name']
            cmds += ['no service ' + name]
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
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
                my_mongo = MongoOps(db='Automation', coll='hillstone_service')
                my_mongo.delete_many(query=dict(hostip=host, name=name))
                return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
            return paths[0], []
        return '', []

    # 编辑服务组
    @staticmethod
    def edit_service(**kwargs):
        host = kwargs['hostip']
        name = kwargs['edit_service_obj']['name']
        old_service_res = MongoOps(db='Automation', coll='hillstone_service') \
            .find(query_dict=dict(hostip=host, name=name), fileds={'_id': 0})
        # print('old_service_res', old_service_res)
        if old_service_res:
            old_service_res = old_service_res[0]
            # print('old_res', old_res)
            new_service_res = dict()
            new_service_res['hostip'] = host
            new_service_res['name'] = kwargs['edit_service_obj']['name']
            new_service_res['description'] = kwargs['edit_service_obj'].get('description')
            new_service_res['items'] = copy.deepcopy(old_service_res['items'])
            contents = kwargs['edit_service_obj']['object']
            # 归集IP 和range 集合
            cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
            if dev_info:
                cmds += ['service ' + name]
                if kwargs['edit_service_obj']['description'] != old_service_res['description']:
                    cmds += ['description ' + kwargs['edit_service_obj']['description']]
                addCmd = []  # 增加命令
                delCmd = []  # 删除命令
                for _cmd in contents:
                    if _cmd['type'] == 'tcp' or _cmd['type'] == 'udp':
                        add_tcp_udp = True
                        for old in old_service_res['items']:
                            # print(old['protocol'], _cmd['type'])
                            # print(old, _cmd)
                            if old['protocol'] == _cmd['type']:
                                if str(old.get('src-port-min')) == _cmd['src_port_start'] and \
                                        str(old.get('src-port-max')) == _cmd['src_port_end'] and \
                                        str(old['dst-port-min']) == _cmd['dst_port_start'] and \
                                        str(old['dst-port-max']) == _cmd['dst_port_end']:
                                    add_tcp_udp = False
                                elif str(old['dst-port-min']) == _cmd['dst_port_start'] and \
                                        str(old['dst-port-max']) == _cmd['dst_port_end']:
                                    add_tcp_udp = False
                        if add_tcp_udp:
                            if _cmd['src_port_start'] == '0' and _cmd['src_port_end'] == '65535':
                                addCmd += ['{} dst-port {} {}'.format(_cmd['type'],
                                                                      _cmd['dst_port_start'],
                                                                      _cmd['dst_port_end'])]
                                new_service_res['items'].append({
                                    'dst-port-min': int(_cmd['dst_port_start']),
                                    'dst-port-max': int(_cmd['dst_port_end']),
                                    'protocol': 'tcp' if _cmd['type'] == 'tcp' else 'udp'
                                })
                            elif _cmd['dst_port_start'] and _cmd['dst_port_end']:
                                addCmd += ['{} dst-port {} {} src-port {} {}'.format(_cmd['type'],
                                                                                     _cmd['dst_port_start'],
                                                                                     _cmd['dst_port_end'],
                                                                                     _cmd['src_port_start'],
                                                                                     _cmd['src_port_end'])]
                                new_service_res['items'].append({
                                    'dst-port-min': int(_cmd['dst_port_start']),
                                    'dst-port-max': int(_cmd['dst_port_end']),
                                    'src-port-min': int(_cmd['src_port_start']),
                                    'src-port-max': int(_cmd['src_port_end']),
                                    'protocol': 'tcp' if _cmd['type'] == 'tcp' else 'udp'
                                })

                    elif _cmd['type'] == 'icmp':
                        add_icmp = True
                        for old in old_service_res['items']:
                            if old['protocol'] == 'icmp':
                                add_icmp = False
                        if add_icmp:
                            addCmd += ['icmp type 8']
                            new_service_res['items'].append({
                                'protocol': 'icmp'
                            })
                for old in old_service_res['items']:
                    if old['protocol'] == 'tcp' or old['protocol'] == 'udp':
                        del_tcp_udp = True
                        for _cmd in contents:
                            if old['protocol'] == _cmd['type']:
                                if str(old.get('src-port-min')) == _cmd['src_port_start'] and \
                                        str(old.get('src-port-max')) == _cmd['src_port_end'] and \
                                        str(old['dst-port-min']) == _cmd['dst_port_start'] and \
                                        str(old['dst-port-max']) == _cmd['dst_port_end']:
                                    del_tcp_udp = False
                                elif str(old['dst-port-min']) == _cmd['dst_port_start'] and \
                                        str(old['dst-port-max']) == _cmd['dst_port_end']:
                                    del_tcp_udp = False
                        if del_tcp_udp:
                            if all(k in old for k in ("src-port-min", "src-port-max", "dst-port-min", "dst-port-max")):
                                delCmd += ['no {} dst-port {} {} src-port {} {}'.format(old['protocol'],
                                                                                        str(old['dst-port-min']),
                                                                                        str(old['dst-port-max']),
                                                                                        str(old['src-port-min']),
                                                                                        str(old['src-port-max']))]

                            elif all(k in old for k in ("dst-port-min", "dst-port-max")):
                                delCmd += ['no {} dst-port {} {}'.format(str(old['protocol']),
                                                                         str(old['dst-port-min']),
                                                                         str(old['dst-port-max']))]
                            new_service_res['items'].remove(old)
                    elif old['protocol'] == 'icmp':
                        del_icmp = True
                        for _cmd in contents:
                            if _cmd['type'] == 'icmp':
                                del_icmp = False
                        if del_icmp:
                            new_service_res['items'].remove(old)
                            delCmd += ['no icmp type 8']
                # print('addCmd', addCmd)
                # print('delCmd', delCmd)
                # print('new_service_res', new_service_res)
                if delCmd:
                    cmds += delCmd
                if addCmd:
                    cmds += addCmd
                # print('cmds', cmds)
                if len(cmds) >= 2:
                    paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
                    if paths:
                        server_mongo = MongoOps(db='Automation', coll='hillstone_service')
                        server_mongo.delete_many(query=dict(hostip=host, name=name))
                        server_mongo.insert_many([new_service_res])
                    if isinstance(paths, list):
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
                        return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
                    elif isinstance(paths, bool):
                        return False, []
                    return paths[0], []
        return '', []

    # 配置slb-server-pool
    def config_slb_pool(self, **kwargs):
        """
        新建和编辑SLB
        slb-server-pool {pool-name}
        server ip 172.31.6.74/32 | ip-range 1.1.1.1 1.1.1.2 port 9000 weight-per-server 100 max-connection-per-server 65535
        :param kwargs:
        :return:
        """
        soft_version = ''
        # soft_version 判断
        if self.dev_infos['soft_version'].find('5.5R6') != -1:
            soft_version = '5.5R6'
        _vars = {
            "slb_name": kwargs['name'],
            "hostip": kwargs['hostip'],
            "description": kwargs['description'] if 'description' in kwargs.keys() else '',
            "monitor": kwargs['monitor'],
            "load_balance": kwargs['load_balance'],
            "monitor_threshold": kwargs['monitor_threshold'],
            "objects": kwargs['objects'],  # list
            'soft_version': soft_version
        }
        jinja_file = package_dir + '/slb_server_pool.j2'
        with open(jinja_file) as f:
            template = jinja2.Template(f.read())
        tmp_commands = template.render(_vars)
        # 去除空字符串命令
        res = [x for x in tmp_commands.split('\n') if len(x.strip()) != 0]
        return res

    # 测试发送中文
    @staticmethod
    def test_zh(**kwargs):
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            #  hostip=post_param['hostip'],
            name = str(kwargs['test_address_obj']['name']).encode(encoding='UTF-8').decode(encoding='UTF-8')
            cmds += ['address ' + name]
            if kwargs['test_address_obj'].get('description'):
                cmds += ['description ' + kwargs['test_address_obj']['description']]
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
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
                return paths[0], HillstoneFsm.standard_ttp(path=paths[0])
            elif isinstance(paths, bool):
                return False, []
            return paths[0], []
        return '', []


# 山石防火墙安全策略配置
class HillstoneSecPolicyConf(HillstoneBase):

    # # 比较列表差异
    # @staticmethod
    # def get_list_diff(old, new):
    #     del_more1 = []
    #     add_more2 = []
    #     dic_result = {}
    #     for str_1 in old:
    #         dic_result[str(str_1)] = 1
    #
    #     for str_2 in new:
    #         if dic_result.get(str(str_2)):
    #             dic_result[str(str_2)] = 2
    #         else:
    #             add_more2.append(str_2)
    #
    #     for key, val in dic_result.items():
    #         if val == 1:
    #             del_more1.append(key)
    #     # print('old比new多的内容为:', del_more1)
    #     # print('new比old多的内容为:', add_more2)
    #     return add_more2, del_more1
    #
    # @staticmethod
    # def get_host_info(host):
    #     dev_infos = get_device_info_v2(host)
    #     cmds = []
    #     if dev_infos:
    #         username = dev_infos[0]['username']  # 用户名
    #         password = dev_infos[0]['password']  # 密码
    #         port = dev_infos[0]['port']
    #         # if dev_infos[0]['soft_version'].startswith('Version 5.0') and 'ssh' in dev_infos[0]['protocol']:
    #         #     cmds = ['configure']
    #         # elif host in ['10.254.3.102', '10.254.5.68', '10.254.12.242',
    #         #               '172.16.73.250', '172.22.170.1', '103.108.2.242',
    #         #               '172.16.73.249', '172.22.57.203', '172.17.1.41']:
    #         cmds = ['configure']
    #         device_ios = 'ruijie_os'
    #         # device_ios = 'juniper'
    #         # device_ios = 'juniper_junos'
    #         # device_ios = 'cisco_ios'
    #         if 'telnet' in dev_infos[0]['protocol']:
    #             device_ios = 'ruijie_os_telnet'
    #         # fsm_flag = 'hillstone'  # 解析器标识
    #         dev_info = {
    #             'device_type': device_ios,
    #             'ip': host,
    #             'port': port,
    #             'username': username,
    #             'password': password,
    #             'timeout': 100,  # float，连接超时时间，默认为100
    #             'session_timeout': 100,  # float，每个请求的超时时间，默认为60，
    #             'encoding': 'utf-8'
    #         }
    #         if dev_infos[0].get('bind_ip__ipaddr'):
    #             dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
    #         return cmds, dev_info
    #     return cmds, {}

    # 配置一条安全策略
    # @staticmethod
    # def config(**kwargs):
    #     cmds, dev_info = HillstoneSecPolicyConf.get_host_info(kwargs['host'])
    #     if dev_info:
    #         # cmds = ['policy-global', 'move 5 before 4']  # 移动规则
    #         # cmds += ['policy-global', 'rule from any to any service icmp permit']  # 新建一条规则，并捕获rule id
    #         # cmds = ['policy-global', 'rule from any to any service icmp permit'] # 新建一条规则，并捕获rule id
    #         cmds += ['no rule id 4']  # 新建一条规则，并捕获rule id
    #         paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
    #         if isinstance(paths, list):
    #             """
    #             [
    #                 {
    #                     "results": {
    #                         "create": {
    #                             "rule_id": "4"
    #                         },
    #                         "unrecognized": {
    #                             "unrecognized": "configure"
    #                         }
    #                     }
    #                 }
    #             ]
    #                             """
    #             return HillstoneFsm.config_sec_policy(path=paths[0])
    #         return paths
    #     # if all(k in kwargs for k in ("rule_id", "before")):
    #     #     if isinstance(kwargs['rule_id'], int) and isinstance(kwargs['before'], int):
    #     #         cmds = ['configure', 'policy-global', 'move 4 before 5']
    #     #         paths = BatManMain.config_cmds(cmds, **dev_info)
    #     #         print(paths)
    #     #         return paths
    #     # if all(k in kwargs for k in ("rule_id", "after")):
    #     #     pass
    #     # if all(k in kwargs for k in ("rule_id", "top")):
    #     #     pass
    #     # if all(k in kwargs for k in ("rule_id", "bottom")):
    #     #     pass
    #     return False

    # 移动安全策略
    @staticmethod
    def move(**kwargs) -> [str, list]:
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            #  hostip=post_param['hostip'],
            current_id = kwargs['current_id']
            target_id = kwargs.get('target_id')
            insert = kwargs['insert']
            cmds += ['policy-global']
            if insert == 'first':
                cmds += ['move ' + current_id + ' top']
            elif insert == 'last':
                cmds += ['move ' + current_id + ' bottom']
            elif insert == 'before' and target_id:
                cmds += ['move ' + current_id + ' before ' + target_id]
            elif insert == 'after' and target_id:
                cmds += ['move ' + current_id + ' after ' + target_id]
            # cmds = ['policy-global', 'move 5 before 4']  # 移动规则
            # cmds += ['policy-global', 'rule from any to any service icmp permit']  # 新建一条规则，并捕获rule id
            # cmds = ['policy-global', 'rule from any to any service icmp permit'] # 新建一条规则，并捕获rule id
            # cmds = ['no rule id 4']  # 新建一条规则，并捕获rule id
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
                """
                [
                    {
                        "results": {
                            "create": {
                                "rule_id": "4"
                            },
                            "unrecognized": {
                                "unrecognized": "configure"
                            }
                        }
                    }
                ]
                                """
                return paths[0], HillstoneFsm.config_sec_policy(path=paths[0])
            return paths[0], []
        return '', []

    # 禁用启用安全策略
    @staticmethod
    def on_off(**kwargs) -> [str, list]:
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            #  hostip=post_param['hostip'],
            current_id = kwargs['current_id']
            enable = kwargs['enable']
            if enable == 'on':
                cmds += ['rule id ' + str(current_id), 'enable']
            elif enable == 'off':
                cmds += ['rule id ' + str(current_id), 'disable']
            else:
                return '', []
            # cmds = ['policy-global', 'move 5 before 4']  # 移动规则
            # cmds += ['policy-global', 'rule from any to any service icmp permit']  # 新建一条规则，并捕获rule id
            # cmds = ['policy-global', 'rule from any to any service icmp permit'] # 新建一条规则，并捕获rule id
            # cmds = ['no rule id 4']  # 新建一条规则，并捕获rule id
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
                """
                [
                    {
                        "results": {
                            "create": {
                                "rule_id": "4"
                            },
                            "unrecognized": {
                                "unrecognized": "configure"
                            }
                        }
                    }
                ]
                                """
                return paths[0], HillstoneFsm.config_sec_policy(path=paths[0])
            return paths[0], []
        return '', []


    @staticmethod
    def delete_poilcy(host, rule_id):
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        if dev_info:
            if isinstance(rule_id, list):
                for _rule in rule_id:
                    cmds += ['no rule id ' + _rule]  # 删除一条规则
            paths = BatManMain.hillstone_config_cmds(*cmds, **dev_info)
            if isinstance(paths, list):
                """
                [
                    {
                        "results": {
                            "create": {
                                "rule_id": "4"
                            },
                            "unrecognized": {
                                "unrecognized": "configure"
                            }
                        }
                    }
                ]
                """
                if paths:
                    my_mongo = MongoOps(db='Automation', coll='sec_policy')
                    my_mongo.delete_many(query=dict(hostip=host, id=rule_id))
                return paths[0], HillstoneFsm.config_sec_policy(path=paths[0])
            return paths[0], []
        return '', []


# 山石防火墙NAT配置
class HillstoneNat(HillstoneBase):

    # 一对一静态映射
    @staticmethod
    def create_static():
        """
        bnatrule [id id] interface interface-name virtual {ip {A.B.C.D/M | X:X:X:X:X::X/M} | address-book address-name } real {ip {A.B.C.D | A.B.C.D/M | X:X:X:X:X::X/M} | address-book address-name }
        :return:
        """
        pass

    # dnat配置下发之前的配置校验
    @staticmethod
    def check_dnat_rule(**kwargs):
        host = kwargs['hostip']
        id = kwargs['id']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        cmds = ['show configuration | include dnatrule id ' + id]
        paths = BatManMain.hillstone_send_cmds(*cmds, **dev_info)
        if isinstance(paths, list):
            ttp_res = HillstoneFsm.check_dnat_config_before(rule_id=id, path=paths[0])  # {'rule_id': '654'}
            return ttp_res
        return {}

    # snat配置下发之前的配置校验
    @staticmethod
    def check_snat_rule(**kwargs):
        host = kwargs['hostip']
        id = kwargs['id']
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        cmds = ['show configuration | include snatrule id ' + id]
        paths = BatManMain.hillstone_send_cmds(*cmds, **dev_info)
        if isinstance(paths, list):
            ttp_res = HillstoneFsm.check_snat_config_before(rule_id=id, path=paths[0])  # {'rule_id': '654'}
            return ttp_res
        return {}

    # DNAT 创建和修改
    @staticmethod
    def config_dnat(**kwargs):
        """
        新建和编辑DNAT策略
        dnatrule [id id] [before id | after id | top] [ingress-interface interface]
        from src-address to dst-address [service service-name]
        trans-to trans-to-address [redirect] [port port] [load-balance] [track-tcp port] [track-ping]
        [log] [group group-id] [disable] [description description]
        5.5R6版本是新的DNAT命令，from和to需要指定类型
        :return:
        """
        host = kwargs['hostip']
        cmds, dev_info, dev_infos = HillstoneBase.get_host_info(host)
        # Version 5.5 SG6000-X7180-5.5R6P15-v6.bin 2021/01/15 18:55:45 这个版本from 和 to 需要指定address-book 和 ip
        soft_version = ''
        print(dev_infos['soft_version'])
        if dev_infos['soft_version'].find('5.5R6') != -1:
            soft_version = '5.5R6'
        cmds += ['ip vrouter trust-vr']
        _to = kwargs['to']
        if not _to.find ('/') != -1:
            _to = _to + '/32'
        _vars = {
            'id': kwargs.get('id'),  # 如果用户不指定，系绝会为觃则自劢生成一个 ID。如果指定的ID 为已有的 DNAT 规则的 ID，已有的规则会被覆盖。
            'ingress_interface': kwargs.get('ingress_interface'),  # 指定匹配该 dnat 规则的入接口
            'insert': kwargs.get('insert'),  # [before id | after id | top]
            'from': kwargs.get('from'),  # {'object': 'address-book'} | {'ip':'A.B.C.D/M '}
            'to': _to,  # {'object': 'address-book'} | {'ip':'A.B.C.D/M' A.B.C.D}
            'service': kwargs.get('service'),  # 服务对象名
            'trans_to': kwargs.get('trans_to'),  # {'ip':'A.B.C.D '}|{'slb_server_pool':'slbname'}|{'address_book':'10.103.65.100'}
            'port': kwargs.get('port'),  # 映射端口
            'load_balance': kwargs.get('load_balance'),  # 是否启用，非空即启用
            'log': kwargs.get('log'),  # log  # 是否启用，非空即启用
            'soft_version': soft_version,  # 版本区分
            'track_tcp': kwargs.get('track_tcp'),  # tcp 监测
            'track_ping': kwargs.get('track_ping'),  # ping 监测
            # 'group': '',  # 待定，默认为HA组0
            # 'disable': '',  # 5.0不支持
            # 'description': ''  # 5.0不支持
        }

        jinja_file = package_dir + '/hillstone_dnat.j2'
        before_commands = ''
        if kwargs.get('id'):
            before_commands = HillstoneNat.check_dnat_rule(**kwargs)
            before_commands = before_commands['command'] if 'command' in before_commands.keys() else '没有匹配'
        # print('before_commands', before_commands)
        # print(jinja_file)
        with open(jinja_file) as f:
            template = jinja2.Template(f.read())
        tmp_commands = template.render(_vars)
        tmp_commands = tmp_commands.split('\n')
        cmds.append(' '.join(tmp_commands))
        # print(cmds)
        path, error_info = BatManMain.hillstone_config_cmds_no_save(*cmds, **dev_info)
        # print(path)
        if error_info == '':
            # 解析配置下发过程中的config文件
            ttp_res = HillstoneFsm.config_dnat(path=path[0])  # {'config': {'rule_id': '654'}}
            return [path[0], ttp_res, cmds, error_info, before_commands]
        return [path[0], {}, cmds, error_info, before_commands]

    # DNAT 删除
    @staticmethod
    def delete_dnat(**kwargs):
        host = kwargs['hostip']
        rule_id = kwargs['id']
        commands = ['configure', 'ip vrouter trust-vr', 'no dnatrule id ' + rule_id]
        cmds, dev_info, dev_infos = HillstoneSecPolicyConf.get_host_info(host)
        path, error_info = BatManMain.hillstone_config_cmds_no_save(*cmds, **dev_info)
        return

    # SNAT 创建
    @staticmethod
    def config_snat():
        """
        snatrule [id id] [ingress-interface interface-name] [before id | after id | top] from src-address
        to dst-address [service service-name] [eif egress-interface | evr vrouter-name]
        trans-to {addressbook trans-to-address | eif-ip} mode {static | dynamicip | dynamicport [sticky]}
        [log] [group group-id] [disable] [ track track-name] [description description]
        :return:
        """
        _vars = {
            'id': 2,
            'ingress-interface': '',
            'insert': '',  # [before id | after id | top]
            'from': '',
            'to': '',
            'service': '',
            'eif': '',
            'trans-to': '',
            'mode': '',  # static | dynamicip | dynamicport [sticky]
            'log': '',  # log
            'disable': '',  # disable
            'track': '',
            'description': '',
        }


def test_slb():
    var = {'slb_name': 'jmli12test',
           'hostip': '10.254.12.16',
           'description': '',
           'monitor': 'track-ping',
           'load_balance': 'weighted-hash',
           'monitor_threshold': 99,
           'objects': [{'add_detail_ip': True, 'ip_mask': ['1.1.1.1/30'], 'port': 80, 'weight': 1,
                        'max_connection': 655350},
                       {'add_detail_range': True, 'range_start': '2.2.2.1', 'range_end': '2.2.2.2',
                        'port': 80, 'weight': 1, 'max_connection': 655350}], 'soft_version': ''}
    jinja_file = package_dir + '/slb_server_pool.j2'
    with open(jinja_file) as f:
        template = jinja2.Template(f.read())
    tmp_commands = template.render(var)
    return tmp_commands.split('\n')


def test_dnat():
    var = {'id': None,
           'ingress_interface': None,
           'insert': None,
           'from': {'any': True},
           'to': {'ip': '1.2.3.4'},
           'service': 'TCP-80',
           'trans_to': {'slb_server_pool': 'jmli12test'},
           'port': 80,
           'load_balance': False,
           'log': False,
           'soft_version': '',
           'track_tcp': None,
           'track_ping': False}
    # var = {'id': None, 'ingress_interface': None, 'insert': None, 'from': {'object': 'address-book'}, 'to': {'ip': '1.2.3.4/32'}, 'service': 'jmli8test', 'trans_to': {'slb_server_pool': '36.7.109.47_1_0_5556_5557'}, 'port': 80, 'load_balance': False, 'log': False, 'soft_version': '', 'track_tcp': None, 'track_ping': False}
    # jinja_file = package_dir + '/hillstone_dnat.j2'
    path = 'config_templates/hillstone/hillstone_dnat.j2'
    data_to_parse = default_storage.open(path).read().decode('utf-8')
    template = jinja2.Template(data_to_parse)
    # with open(jinja_file) as f:
    #     template = jinja2.Template(f.read())
    tmp_commands = template.render(var)
    return tmp_commands.split('\n')






