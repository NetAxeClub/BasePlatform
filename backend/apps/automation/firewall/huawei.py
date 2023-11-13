# -*- coding: utf-8 -*-
# @Time    : 2021/5/12 11:11
# @Author  : LiJiaMin
# @Site    : 
# @File    : huawei.py
# @Software: PyCharm
# from apps.automation.utils.model_api import get_device_info_v2
from apps.automation.tools.model_api import get_device_info_v2
from utils.connect_layer.NETCONF.huawei_netconf import HuaweiUSG
from apps.automation.tasks import StandardFSMAnalysis, AutomationMongo
from utils.wechat_api import send_msg_netops
from utils.db.mongo_ops import MongoOps
from netaddr import IPNetwork
import json


# 华为防火墙安全策略配置
class HuaweiUsgSecPolicyConf(object):

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.device = HuaweiUSG(host=self.host, user=self.username, password=self.password)

    @staticmethod
    def get_host_info(host):
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
                    'slot': dev_infos[0]['slot']
                }
                # if bind_ipaddress:
                #     dev_info['ip'] = bind_ipaddress['ipaddr']
                if dev_infos[0].get('bind_ip__ipaddr'):
                    dev_info['ip'] = dev_infos[0]['bind_ip__ipaddr']
                    return dev_info
        return {}

    def config(self, host, rule, top):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(host)
        content = ''
        if dev_info['device_type'] == 'huawei_usg':
            # device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            res, content = self.device.config_sec_policy(rule=rule)
            if res and top:
                sec_policy_move = self.device.move_sec_policy(rule_name=rule['rule']['name'], insert='first')
                if not sec_policy_move:
                    content = '移动策略失败'
                    # print('config')
            # print(res, content)
            if res:
                sec_policy_res = self.device.get_sec_policy()
                if sec_policy_res:
                    sec_policy_rule = sec_policy_res['static-policy']['rule']
                    sec_policy_result = []
                    if sec_policy_rule:
                        for i in sec_policy_rule:
                            i['hostip'] = host
                            sec_policy_result.append(i)
                    if sec_policy_result:
                        # 格式化落库
                        StandardFSMAnalysis.huawei_usg_sec_policy(host, sec_policy_result)
                        # 原始数据格式落库
                        AutomationMongo.insert_table(db='NETCONF', hostip=host,
                                                     datas=sec_policy_result, tablename='huawei_sec_policy')
                        return True, content
            return res, content
        return False, '未获取到设备信息'

    # 移动安全策略
    @staticmethod
    def move(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            try:
                sec_policy_move = device.move_sec_policy(**kwargs)
                if sec_policy_move:
                    return True
            except Exception as e:
                #send_msg_netops"华为防火墙 设备 {} 移动安全策略异常：{}".format(kwargs['hostip'], str(e)))
                return False
        return False

    # 编辑安全策略
    @staticmethod
    def modify():
        pass

    # 新建地址组
    @staticmethod
    def create_address(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            name = kwargs['create_address_obj']['name']
            description = ''
            if kwargs['create_address_obj'].get('description'):
                description = kwargs['create_address_obj']['description']
            contents = kwargs['create_address_obj']['object']
            Obj = []
            count_flag = 1  # elements id填充计数器
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'subnet':
                        _tmp_ip = IPNetwork(_cmd['content'])  # demo: 10.254.0.1/24
                        Obj.append({
                            "elem-id": str(count_flag),
                            "address-ipv4": _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                        })
                        count_flag += 1
                    elif _cmd['type'] == 'range':
                        _tmp = json.loads(_cmd['content'])  # 再解一次
                        Obj.append({
                            "elem-id": str(count_flag),
                            "start-ipv4": _tmp['start_ip'],
                            "end-ipv4": _tmp['end_ip']
                        })
                        count_flag += 1
            if Obj:
                # 准备插入mongo的数据
                insert_mongo_datas = {
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj,
                    'hostip': kwargs['hostip']
                }
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'create',
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj
                }
                res = device.config_address(addr_object=netconf_data)
                if res:
                    addr_mongo = MongoOps(db='NETCONF', coll='huawei_usg_address_set')
                    addr_mongo.insert(insert_mongo_datas)
                    return True
        return False

    # 编辑地址组
    @staticmethod
    def edit_address(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            name = kwargs['edit_address_obj']['name']
            description = ''
            if kwargs['edit_address_obj'].get('description'):
                description = kwargs['edit_address_obj']['description']
            contents = kwargs['edit_address_obj']['object']
            Obj = []
            count_flag = 1  # elements id填充计数器
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'subnet':
                        _tmp_ip = IPNetwork(_cmd['content'])  # demo: 10.254.0.1/24
                        Obj.append({
                            "elem-id": str(count_flag),
                            "address-ipv4": _tmp_ip.network.format() + '/' + str(_tmp_ip.netmask.netmask_bits())
                        })
                        count_flag += 1
                    elif _cmd['type'] == 'range':
                        _tmp = json.loads(_cmd['content'])  # 再解一次
                        Obj.append({
                            "elem-id": str(count_flag),
                            "start-ipv4": _tmp['start_ip'],
                            "end-ipv4": _tmp['end_ip']
                        })
                        count_flag += 1
            if Obj:
                # 准备插入mongo的数据
                insert_mongo_datas = {
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj,
                    'hostip': kwargs['hostip']
                }
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'replace',
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj
                }
                res = device.config_address(addr_object=netconf_data)
                if res:
                    addr_mongo = MongoOps(db='NETCONF', coll='huawei_usg_address_set')
                    addr_mongo.delete_many(query=dict(hostip=kwargs['hostip'], name=name))
                    addr_mongo.insert(insert_mongo_datas)
                    return True
        return False

    # 删除地址组
    @staticmethod
    def delete_address(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            addr_mongo = MongoOps(db='NETCONF', coll='huawei_usg_address_set')
            _res = addr_mongo.find(query_dict=dict(hostip=kwargs['hostip'],
                                                   name=kwargs['delete_address_obj']['name']),
                                   fileds={'_id': 0})
            if _res:
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'delete',
                    'vsys': _res[0]['vsys'],
                    'name': _res[0]['name'],
                    'desc': _res[0]['desc'],
                    'elements': _res[0]['elements'],
                }
                res = device.config_address(addr_object=netconf_data)
                if res:
                    addr_mongo = MongoOps(db='NETCONF', coll='huawei_usg_address_set')
                    addr_mongo.delete_many(query=dict(hostip=kwargs['hostip'],
                                                      name=kwargs['delete_address_obj']['name']))
                    return True
        return False

    # 新建服务组
    @staticmethod
    def create_service(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            name = kwargs['create_service_obj']['name']
            description = ''
            if kwargs['create_service_obj'].get('description'):
                description = kwargs['create_service_obj']['description']
            contents = kwargs['create_service_obj']['object']
            Obj = []
            count_flag = 1  # elements id填充计数器
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'tcp' or _cmd['type'] == 'udp':
                        Obj.append({
                            "id": str(count_flag),
                            _cmd['type']: {
                                'source-port': {'start': str(_cmd['src_port_start']), 'end': str(_cmd['src_port_end'])},
                                'dest-port': {'start': str(_cmd['dst_port_start']), 'end': str(_cmd['dst_port_end'])}
                            }
                        })
                        count_flag += 1
                    elif _cmd['type'] == 'icmp':
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
                # 准备插入mongo的数据
                insert_mongo_datas = {
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj,
                    'hostip': kwargs['hostip']
                }
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'create',
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'items': Obj
                }
                res = device.config_service(service_object=netconf_data)
                if res:
                    service_mongo = MongoOps(db='NETCONF', coll='huawei_usg_service_set')
                    service_mongo.insert_many([insert_mongo_datas])
                    return True
        return False

    # 编辑服务组
    @staticmethod
    def edit_service(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            name = kwargs['edit_service_obj']['name']
            description = ''
            if kwargs['edit_service_obj'].get('description'):
                description = kwargs['edit_service_obj']['description']
            contents = kwargs['edit_service_obj']['object']
            Obj = []
            count_flag = 1  # elements id填充计数器
            if contents:
                for _cmd in contents:
                    if _cmd['type'] == 'tcp' or _cmd['type'] == 'udp':
                        Obj.append({
                            "id": str(count_flag),
                            _cmd['type']: {
                                'source-port': {'start': str(_cmd['src_port_start']),
                                                'end': str(_cmd['src_port_end'])},
                                'dest-port': {'start': str(_cmd['dst_port_start']),
                                              'end': str(_cmd['dst_port_end'])}
                            }
                        })
                        count_flag += 1
                    elif _cmd['type'] == 'icmp':
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
                # 准备插入mongo的数据
                insert_mongo_datas = {
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'elements': Obj,
                    'hostip': kwargs['hostip']
                }
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'replace',
                    'vsys': 'public',
                    'name': name,
                    'desc': description,
                    'items': Obj
                }
                res = device.config_service(service_object=netconf_data)
                if res:
                    service_mongo = MongoOps(db='NETCONF', coll='huawei_usg_service_set')
                    service_mongo.insert(insert_mongo_datas)
                    return True
        return False

    # 删除服务组
    @staticmethod
    def delete_service(**kwargs):
        dev_info = HuaweiUsgSecPolicyConf.get_host_info(kwargs['hostip'])
        if dev_info['device_type'] == 'huawei_usg':
            device = HuaweiUSG(host=dev_info['ip'], user=dev_info['username'], password=dev_info['password'])
            service_mongo = MongoOps(db='NETCONF', coll='huawei_usg_service_set')
            _res = service_mongo.find(query_dict=dict(hostip=kwargs['hostip'],
                                                      name=kwargs['delete_service_obj']['name']),
                                      fileds={'_id': 0})
            if _res:
                # 最终提交到设备的netconf数据
                netconf_data = {
                    '@nc:operation': 'delete',
                    'vsys': _res[0]['vsys'],
                    'name': _res[0]['name'],
                    'desc': _res[0]['desc'],
                    'items': _res[0]['elements'],
                }
                res = device.config_service(service_object=netconf_data)
                if res:
                    addr_mongo = MongoOps(db='NETCONF', coll='huawei_usg_service_set')
                    addr_mongo.delete_many(query=dict(hostip=kwargs['hostip'],
                                                      name=kwargs['delete_service_obj']['name']))
                    return True
        return False