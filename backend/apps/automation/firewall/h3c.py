# -*- coding: utf-8 -*-
# @Time    : 2021/5/12 11:10
# @Author  : LiJiaMin
# @Site    : 
# @File    : h3c.py
# @Software: PyCharm
from utils.connect_layer.NETCONF.h3c_netconf import H3CSecPath
from apps.automation.tasks import StandardFSMAnalysis, AutomationMongo
from utils.wechat_api import send_msg_netops
from netaddr import IPNetwork
import json
import copy


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


class H3cFirewall(object):
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.device = H3CSecPath(host=self.host, user=self.username,
                                 password=self.password, timeout=600, device_params='h3c')

    def config_ipv4_rule(self, rule: dict):
        try:
            res, content = self.device.config_ipv4_rule(**rule)
            if res:
                rule_res = self.device.get_sec_policy_name(name=rule['name'])
                self.device.closed()
                if isinstance(rule_res, dict):
                    return rule_res, content
                else:
                    return False, '新建rule成功，但没有查询新建的rule数据'
            return res, content
        except Exception as e:
            self.device.closed()
            #send_msg_netops"华三防火墙 设备 {} 配置安全策略异常：{}".format(self.host, str(e)))
            return False, ''

    def config_sec_policy(self, config_data: dict, rule_id: str, top: bool):

        try:
            res, content = self.device.config_sec_policy(config_data)
            if res and top:
                move_res = self.device.move_ipv4_rule(rule_id=rule_id, insert='first')
                if not move_res:
                    content = '移动策略失败'
            sec_policy_res = self.device.get_sec_policy()
            sec_policy_result = []
            if sec_policy_res:
                for i in sec_policy_res:
                    i['hostip'] = self.host
                    sec_policy_result.append(i)
            if sec_policy_result:
                StandardFSMAnalysis.h3c_secpath_sec_policy(self.host, sec_policy_result)
            self.device.closed()
            if res:
                return True, '配置成功'
            return res, content
        except Exception as e:
            self.device.closed()
            #send_msg_netops"华三防火墙 设备 {} 配置安全策略异常：{}".format(self.host, str(e)))
            return False, ''

    # 移动安全策略
    def move(self, **kwargs):
        try:
            sec_policy_move = self.device.move_ipv4_rule(**kwargs)
            self.device.closed()
            if sec_policy_move:
                return True
        except Exception as e:
            self.device.closed()
            #send_msg_netops"华三防火墙 设备 {} 移动安全策略异常：{}".format(kwargs['hostip'], str(e)))
            return False
        return False

    # 禁用启用安全策略
    def on_off(self, **kwargs):
        pass

    # 编辑安全策略
    def modify(self, **kwargs):
        pass

    # 删除安全策略
    def delete_sec_policy(self, **kwargs):
        result = []
        if isinstance(kwargs['rule_id'], list):
            for rule_id in kwargs['rule_id']:
                try:
                    rule_service_res = {}
                    # 先删除rule
                    res, content = self.device.delete_sec_policy(method='remove', rule_id=rule_id)
                    print('删除rule res, content', res, content)
                    result.append([self.host, rule_id, res, content])
                except Exception as e:
                    self.device.closed()
                    # print(traceback.print_exc())
                    #send_msg_netops"华三防火墙 设备 {} 删除安全策略异常：{}".format(self.host, str(e)))
                    return False
            # 最后同步安全策略数据
            sec_policy_res = self.device.get_sec_policy()
            sec_policy_result = []
            if sec_policy_res:
                for i in sec_policy_res:
                    i['hostip'] = self.host
                    sec_policy_result.append(i)
            if sec_policy_result:
                StandardFSMAnalysis.h3c_secpath_sec_policy(self.host, sec_policy_result)
            self.device.closed()
            return result
        self.device.closed()
        return False

    # 新建地址组
    def create_address(self, **kwargs):
        """
        {'vendor': 'H3C',
         'create_address_obj': {'name': 'test', 'description': 'miaoshu',
         'object':
         [{'content': '10.254.0.1/24', 'type': 'subnet', 'id': 'F7zK7SmT4Z'},
         {'content': '{"start_ip":"10.254.0.2","end_ip":"10.254.0.3"}', 'type': 'range', 'id': 'mWQCmPS3pB'}]}}
        :param kwargs:
        :return:
        """
        # type_map = {
        #     "subnet": "1",
        #     "range": "2",
        #     "ip": "3",
        # }
        name = kwargs['create_address_obj']['name']
        description = ''
        if kwargs['create_address_obj'].get('description'):
            description = kwargs['create_address_obj']['description']
        contents = kwargs['create_address_obj']['object']
        Obj = []
        if contents:
            for _cmd in contents:
                if _cmd['type'] == 'subnet':
                    _tmp_ip = IPNetwork(_cmd['content'])  # demo: 10.254.0.1/24
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='1',
                        SubnetIPv4Address=_tmp_ip.network.format(),  # demo: 10.254.0.1
                        IPv4Mask=_tmp_ip.netmask.format()  # demo: 255.255.255.0
                    ))
                if _cmd['type'] == 'range':
                    _tmp = json.loads(_cmd['content'])  # 再解一次
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='2',
                        StartIPv4Address=_tmp['start_ip'],  # demo: 10.254.0.1
                        EndIPv4Address=_tmp['end_ip']  # demo: 10.254.0.5
                    ))
                if _cmd['type'] == 'ip':
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='3',
                        HostIPv4Address=_cmd['content'],  # demo: 10.254.0.1
                    ))
        if Obj:
            group_res = self.device.create_ipv4_group(name=name, description=description)
            if group_res:
                # 生成OMS 下 IPv4Objs 的create方法
                OMS = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'IPv4Objs':
                        {
                            'Obj': Obj
                        }
                }
                res = self.device.config_oms_objs(OMS=OMS)
                if res:
                    address_set = self.device.get_ipv4_paging()
                    if address_set:
                        for i in address_set:
                            i['hostip'] = kwargs['hostip']
                        AutomationMongo.insert_table(db='NETCONF', hostip=kwargs['hostip'], datas=address_set,
                                                     tablename='h3c_address_set')
                return res
        self.device.closed()
        return False

    # 编辑地址组V2
    def edit_address_v2(self, **kwargs):
        pass

    # 编辑地址组
    def edit_address(self, **kwargs):
        old_group_res = self.device.get_ipv4_paging(name=kwargs['edit_address_obj']['name'], map=False)
        if not old_group_res:
            return False
        old_group_res = old_group_res[0]
        # {'Name': 'test_addr', 'Description': 'jmli12_test', 'ObjNum': '2', 'InUse': 'false', 'SecurityZone': None}
        # 安全域不在比较之列
        name = kwargs['edit_address_obj']['name']
        description = ''
        if kwargs['edit_address_obj'].get('description'):
            description = kwargs['edit_address_obj']['description']
        contents = kwargs['edit_address_obj']['object']
        new_group_res = copy.deepcopy(old_group_res)
        new_group_res['Name'] = name
        new_group_res['Description'] = description
        # 归集IP 和range 集合
        old_ip = []
        old_range = []
        new_ip = []
        new_range = []
        # 归集差异比较结果
        for _tmp in old_group_res['ObjList']:
            if _tmp.get('SubnetIPv4Address'):
                old_ip.append((_tmp['SubnetIPv4Address'] + '/' + _tmp['IPv4Mask']))
            if _tmp.get('StartIPv4Address'):
                old_range.append(_tmp['StartIPv4Address'] + '-' + _tmp['EndIPv4Address'])

        Obj = []
        if contents:
            for _cmd in contents:
                if _cmd['type'] == 'subnet':
                    _tmp_ip = IPNetwork(_cmd['content'])  # demo: 10.254.0.1/24
                    new_ip.append(_tmp_ip.network.format() + '/' + _tmp_ip.netmask.format())
                if _cmd['type'] == 'range':
                    _tmp = json.loads(_cmd['content'])  # 再解一次
                    new_range.append(_tmp['start_ip'] + '-' + _tmp['end_ip'])
                # if _cmd['type'] == 'ip':  # 主机地址暂时不参与比较
                #     Obj.append(dict(
                #         Group=name,
                #         ID='4294967295',  # 固定值，代表系统自动分配
                #         Type='3',
                #         HostIPv4Address=_cmd['content'],  # demo: 10.254.0.1
                #     ))
        new_group_res['ObjList'] = Obj
        cmp = CompareTwoDict(new_group_res, old_group_res)
        # print('差异配置如下')
        # print(cmp.main())
        res = cmp.main()
        if res.get('description') != '=' or res.get('Name') != '=':
            group_res = self.device.create_ipv4_group(method="replace", name=name, description=description)
        cmd_ip_add, cmd_ip_del = get_list_diff(old_ip, new_ip)
        cmd_range_add, cmd_range_del = get_list_diff(old_range, new_range)
        # print('新增IP', cmd_ip_add)
        # print('删除IP', cmd_ip_del)
        # print('新增range', cmd_range_add)
        # print('删除range', cmd_range_del)
        OMS = []
        addObj = []
        delObj = []
        if cmd_ip_add:
            for _ip in cmd_ip_add:
                _tmp_ip = IPNetwork(_ip)  # demo: 10.254.0.1/24
                new_ip.append(_tmp_ip.network.format() + '/' + _tmp_ip.netmask.format())
                addObj.append(dict(
                    Group=name,
                    ID='4294967295',  # 固定值，代表系统自动分配
                    Type='1',
                    SubnetIPv4Address=_tmp_ip.network.format(),  # demo: 10.254.0.1
                    IPv4Mask=_tmp_ip.netmask.format()  # demo: 255.255.255.0
                ))
        if cmd_range_add:
            for _ip in cmd_range_add:
                addObj.append(dict(
                    Group=name,
                    ID='4294967295',  # 固定值，代表系统自动分配
                    Type='2',
                    StartIPv4Address=_ip.split('-')[0],  # demo: 10.254.0.1
                    EndIPv4Address=_ip.split('-')[1]  # demo: 10.254.0.5
                ))
        if cmd_ip_add or cmd_range_add:
            OMS.append({
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'Obj': addObj
                    }
            })
        if cmd_ip_del:
            for _ip in cmd_ip_del:
                _tmp_ip = IPNetwork(_ip)  # demo: 10.254.0.1/24
                for x in old_group_res['ObjList']:
                    if x.get('SubnetIPv4Address'):
                        if x['SubnetIPv4Address'] == _tmp_ip.ip.format():
                            delObj.append(dict(Group=name, ID=x['ID']))
        if cmd_range_del:
            for _ip in cmd_range_del:
                for x in old_group_res['ObjList']:
                    if x.get('StartIPv4Address'):
                        if x['StartIPv4Address'] == _ip.split('-')[0]:
                            delObj.append(dict(Group=name, ID=x['ID']))

        if cmd_ip_del or cmd_range_del:
            OMS.append({
                'IPv4Objs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'Obj': delObj
                    }
            })
        if cmd_ip_add or cmd_ip_del or cmd_range_add or cmd_range_del:
            res = self.device.config_oms_objs(OMS=OMS)
            if res:
                address_set = self.device.get_ipv4_paging()
                if address_set:
                    for i in address_set:
                        i['hostip'] = kwargs['hostip']
                    AutomationMongo.insert_table(db='NETCONF', hostip=kwargs['hostip'], datas=address_set,
                                                 tablename='h3c_address_set')
            return res
        self.device.closed()
        return False

    # 删除地址组
    def delete_address(self, name):
        # name = kwargs['delete_address_obj']['name']
        res = self.device.delete_ipv4_group(name=name)
        if res:
            address_set = self.device.get_ipv4_paging()
            if address_set:
                for i in address_set:
                    i['hostip'] = self.host
                AutomationMongo.insert_table(db='NETCONF', hostip=self.host, datas=address_set,
                                             tablename='h3c_address_set')
            return res
        self.device.closed()
        return False

    # 新建服务组
    def create_service(self, **kwargs):
        """
        {
            "vendor": "H3C",
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
                    }
                ]
            },
            "hostip": "10.254.12.101"
        }
        :param kwargs:
        :return:
        """
        name = kwargs['create_service_obj']['name']
        description = ''
        if kwargs['create_service_obj'].get('description'):
            description = kwargs['create_service_obj']['description']
        contents = kwargs['create_service_obj']['object']
        Obj = []
        if contents:
            for _cmd in contents:
                if _cmd['type'] == 'tcp':
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='3',
                        StartSrcPort=_cmd['src_port_start'],
                        EndSrcPort=_cmd['src_port_end'],
                        StartDestPort=_cmd['dst_port_start'],
                        EndDestPort=_cmd['dst_port_end'],
                    ))
                elif _cmd['type'] == 'udp':
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='4',
                        StartSrcPort=_cmd['src_port_start'],
                        EndSrcPort=_cmd['src_port_end'],
                        StartDestPort=_cmd['dst_port_start'],
                        EndDestPort=_cmd['dst_port_end'],
                    ))
                elif _cmd['type'] == 'icmp':
                    Obj.append(dict(
                        Group=name,
                        ID='4294967295',  # 固定值，代表系统自动分配
                        Type='2',  # ICMP ANY
                    ))
        if Obj:
            group_res = self.device.create_service_groups(name=name, description=description)
            if group_res:
                # 生成OMS 下 ServObjs 的create方法
                OMS = {
                    '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                    '@xc:operation': 'create',
                    'ServObjs':
                        {
                            'Obj': Obj
                        }
                }
                res = self.device.config_oms_objs(OMS=OMS)
                if res:
                    address_set = self.device.get_server_groups()
                    if address_set:
                        for i in address_set:
                            i['hostip'] = self.host
                        AutomationMongo.insert_table(db='NETCONF', hostip=self.host, datas=address_set,
                                                     tablename='h3c_service_set')
                return res
        self.device.closed()
        return False

    # 编辑服务组
    def edit_service(self, **kwargs):
        old_service_res = self.device.get_server_groups(name=kwargs['edit_service_obj']['name'])
        if not old_service_res:
            return False
        old_service_res = old_service_res[0]
        # {'Name': 'test_addr', 'Description': 'jmli12_test', 'ObjNum': '1', 'InUse': 'false', 'items': [{'Group': 'test_addr', 'ID': '10', 'Type': '2'}]}
        name = kwargs['edit_service_obj']['name']
        description = ''
        if kwargs['edit_service_obj'].get('description'):
            description = kwargs['edit_service_obj']['description']
        contents = kwargs['edit_service_obj']['object']
        new_service_res = copy.deepcopy(old_service_res)
        new_service_res['Name'] = name
        new_service_res['Description'] = description
        old_obj = []
        # 归集集合
        if 'items' in old_service_res.keys():
            for item in old_service_res['items']:
                # item.pop('ID')
                old_obj.append(item)

        addObj = []  # 新增
        delObj = []  # 删除
        if contents:
            for _cmd in contents:
                if _cmd['type'] == 'tcp' or _cmd['type'] == 'udp':
                    add_tcp_udp = True
                    for old in old_obj:
                        if old['Type'] == '3' and _cmd['type'] == 'tcp':
                            if old['StartSrcPort'] == _cmd['src_port_start'] and \
                                    old['EndSrcPort'] == _cmd['src_port_end'] and \
                                    old['StartDestPort'] == _cmd['dst_port_start'] and \
                                    old['EndDestPort'] == _cmd['dst_port_end']:
                                add_tcp_udp = False
                        elif old['Type'] == '4' and _cmd['type'] == 'udp':
                            if old['StartSrcPort'] == _cmd['src_port_start'] and \
                                    old['EndSrcPort'] == _cmd['src_port_end'] and \
                                    old['StartDestPort'] == _cmd['dst_port_start'] and \
                                    old['EndDestPort'] == _cmd['dst_port_end']:
                                add_tcp_udp = False
                    if add_tcp_udp:
                        addObj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='3' if _cmd['type'] == 'tcp' else '4',
                            StartSrcPort=_cmd['src_port_start'],
                            EndSrcPort=_cmd['src_port_end'],
                            StartDestPort=_cmd['dst_port_start'],
                            EndDestPort=_cmd['dst_port_end'],
                        ))
                elif _cmd['type'] == 'icmp':
                    add_icmp = True
                    for old in old_obj:
                        if old['Type'] == '2':
                            add_icmp = False
                    if add_icmp:
                        addObj.append(dict(
                            Group=name,
                            ID='4294967295',  # 固定值，代表系统自动分配
                            Type='2',  # ICMP ANY
                        ))
            for old in old_obj:
                if old['Type'] == '3' or old['Type'] == '4':
                    del_tcp_udp = True
                    for _cmd in contents:
                        if old['Type'] == '3' and _cmd['type'] == 'tcp':
                            if old['StartSrcPort'] == _cmd['src_port_start'] and \
                                    old['EndSrcPort'] == _cmd['src_port_end'] and \
                                    old['StartDestPort'] == _cmd['dst_port_start'] and \
                                    old['EndDestPort'] == _cmd['dst_port_end']:
                                del_tcp_udp = False
                        elif old['Type'] == '4' and _cmd['type'] == 'udp':
                            if old['StartSrcPort'] == _cmd['src_port_start'] and \
                                    old['EndSrcPort'] == _cmd['src_port_end'] and \
                                    old['StartDestPort'] == _cmd['dst_port_start'] and \
                                    old['EndDestPort'] == _cmd['dst_port_end']:
                                del_tcp_udp = False
                    if del_tcp_udp:
                        delObj.append(dict(
                            Group=name,
                            ID=old['ID'],  # 固定值，代表系统自动分配
                            # Type=old['Type'],
                            # StartSrcPort=old['StartSrcPort'],
                            # EndSrcPort=old['EndSrcPort'],
                            # StartDestPort=old['StartDestPort'],
                            # EndDestPort=old['EndDestPort'],
                        ))
                elif old['Type'] == '2':
                    del_icmp = True
                    for _cmd in contents:
                        if _cmd['type'] == 'icmp':
                            del_icmp = False
                    if del_icmp:
                        delObj.append(dict(
                            Group=name,
                            ID=old['ID'],  # 固定值，代表系统自动分配
                        ))
        cmp = CompareTwoDict(new_service_res, old_service_res)
        # print(cmp.main())
        res = cmp.main()
        if res.get('description') != '=' or res.get('Name') != '=':
            service_res = self.device.create_service_groups(method="replace", name=name, description=description)
        OMS = []
        if addObj:
            OMS.append({
                'ServObjs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'create',
                        'Obj': addObj
                    }
            })
        if delObj:
            OMS.append({
                'ServObjs':
                    {
                        '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                        '@xc:operation': 'remove',
                        'Obj': delObj
                    }
            })
        if OMS:
            res = self.device.config_oms_objs(OMS=OMS)
            if res:
                service_set = self.device.get_server_groups()
                if service_set:
                    for i in service_set:
                        i['hostip'] = self.host
                    AutomationMongo.insert_table(db='NETCONF', hostip=self.host, datas=service_set,
                                                 tablename='h3c_service_set')
            return res
        self.device.closed()
        return False

    # 删除服务组
    def delete_service(self, name):
        # name = kwargs['delete_service_obj']['name']
        res = self.device.delete_server_groups(name=name)
        self.device.closed()
        if res:
            # service_set = self.device.get_server_groups()
            # if service_set:
            #     for i in service_set:
            #         i['hostip'] = kwargs['hostip']
            #     AutomationMongo.insert_table(db='NETCONF', hostip=kwargs['hostip'], datas=service_set,
            #                                  tablename='h3c_service_set')
            return res
        return False

