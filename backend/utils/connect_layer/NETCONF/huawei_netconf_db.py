#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import logging
from utils.connect_layer.NETCONF.netconf_connect import HuaweiyangNetconfConnect, XmlToDict

logger = logging.getLogger(__name__)


class HuaweiUSGDB(HuaweiyangNetconfConnect):
    """基于数据库的华为USG NETCONF类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = 'Huawei'
        self.device_type = kwargs.get('device_type', 'firewall')

    @staticmethod
    def get_method():
        """获取支持的方法列表"""
        return [
            'get_vrrp_info',
            'get_system_info',
            'get_hrp_state',
            'get_sec_policy_counting',
            'get_interface_list',
            'get_sec_policy',
            'get_sec_policy_single',
            'get_nat_policy',
            'get_nat_server',
            'get_nat_address',
            'get_slb_info',
            'get_address_set',
            'get_service_set',
            'get_application',
            'config_sec_policy',
            'del_sec_policy',
            'move_sec_policy',
            'get_sec_zone',
            'config_address',
            'config_service',
            'config_nat_policy',
            'config_dnat',
            'get_trunk_lacp',
            'get_device_cpu',
            'get_device_ntp',
            'get_device_route'
        ]

    # 以下是所有方法的实现
    def get_vrrp_info(self, **kwargs):
        """获取VRRP信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("VRRP信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        res = self.netconfig_get_config(data_xml)
        return res['vrrp']['vrrp-instance'] if 'vrrp-instance' in res['vrrp'] else None
    
    def get_system_info(self, **kwargs):
        """获取系统信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("系统信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)
        if res:
            return res['device-state']
        else:
            return None        
    
    def get_hrp_state(self, **kwargs):
        """获取HRP状态"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("HRP状态采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        res = self.netconf_get(data_xml)
        if res:
            return res['hrp-state']
        else:
            return None
    
    def get_sec_policy_counting(self, **kwargs):
        """获取安全策略计数"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("安全策略计数采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)
        if res:
            return res['sec-policy-state']
        else:
            return None
    
    def get_interface_list(self, **kwargs):
        """获取接口列表"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("接口列表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        res = self.netconfig_get_config(data=data_xml)
        return res['interfaces']['interface'] if res else None

    def get_sec_policy(self, **kwargs):
        """获取安全策略 - 展示如何灵活控制XML模板执行"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("接口列表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconfig_get_config(data=data_xml)
        if res:
            return res['sec-policy']['vsys']
        else:
            return None
        
    def get_sec_policy_single(self, rule_name, **kwargs):
        """获取单个安全策略"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("单个安全策略采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(rule_name=rule_name)
        res = self.netconfig_get_config(data=data_xml)
        if res:
            return res['sec-policy']['vsys']
        else:
            return None
    
    def get_nat_policy(self, **kwargs):
        """获取NAT策略"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("NAT策略采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        if res:
            if isinstance(res['nat-policy']['vsys'], dict):
                return [res['nat-policy']['vsys']]
            elif isinstance(res['nat-policy']['vsys'], list):
                return res['nat-policy']['vsys']
        else:
            return None
    
    def get_nat_server(self, **kwargs):
        """获取NAT服务器"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("NAT服务器采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        if res:
            if isinstance(res['nat-server']['server-mapping'], dict):
                return [res['nat-server']['server-mapping']]
            else:
                return res['nat-server']['server-mapping']
        else:
            return None
    
    def get_nat_address(self, **kwargs):
        """获取NAT地址"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("NAT地址采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        if res and 'nat-address-group' in res['nat-address-group'].keys():
            if isinstance(res['nat-address-group']['nat-address-group'], dict):
                return [res['nat-address-group']['nat-address-group']]
            else:
                return res['nat-address-group']['nat-address-group']
        else:
            return None
        
    def get_slb_info(self, **kwargs):
        """获取SLB信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("SLB信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        """
        slb-pool 实服务组
        slb-loadbalancer 虚服务
        """
        if res:
            if isinstance(res['slb']['slb-pool'], dict):
                return [res['slb']['slb-pool']]
            else:
                return res['slb']['slb-pool']
        else:
            return None
    
    def get_address_set(self, **kwargs):
        """获取地址集"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("地址集采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        """
        两个KEY
        addr-object 表示一个地址实例
        addr-group 表示一个地址组实例
        """
        if res:
            if isinstance(res['address-set']['addr-object'], dict):
                try:
                    if isinstance(res['address-set']['addr-object']['elements'], dict):
                        res['address-set']['addr-object']['elements'] = [res['address-set']['addr-object']['elements']]
                except:
                    pass
                return [res['address-set']['addr-object']]
            else:
                for i in res['address-set']['addr-object']:
                    if 'elements' in i.keys():
                        if isinstance(i['elements'], dict):
                            i['elements'] = [i['elements']]
                    else:
                        i['elements'] = []
                return res['address-set']['addr-object']
        else:
            return None
    
    def get_service_set(self, **kwargs):
        """获取服务集"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("服务集采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data=data_xml)
        """
        service-object
        """
        if res:
            if isinstance(res['service-set']['service-object'], dict):
                if 'pre-defined-service' in res['service-set'].keys():
                    return [res['service-set']['service-object']] + res['service-set']['pre-defined-service']
                else:
                    return [res['service-set']['service-object']]
            else:
                if 'pre-defined-service' in res['service-set'].keys():
                    return res['service-set']['service-object'] + res['service-set']['pre-defined-service']
                else:
                    return res['service-set']['service-object']
        else:
            return None

    def get_application(self, **kwargs):
        """获取应用"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("应用采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)

        """
        {'application': {'name': 'BT', 'protocol': ['BT_TCP_Encrypted', 'BT', 'BT_HTTP', 'BT_DHT'], 
        'risk-value': '4', 'label': ['Productivity-Loss', 'Data-Loss', 'Bandwidth-Consuming', 'Evasive', 'Tunneling',
         'P2P-Based'], 'abandon': 'false', 'multichannel': 'true', 'data-model': 'peer-to-peer', 
         'category': 'General_Internet', 'subcategory': 'FileShare_P2P', 
         'description': 'BitTorrent (BT) is a P2P protocol for multi-point downloading and can be used for many 
         different kinds of applications. The client downloads and uploads data at the same time. Example: 
         BitTorrent, BitSpirit and BitComet.'}}
        """
        if res:
            """
            两个key
            user-defined-application  用户自定义应用组
            predefined-application  系统预定义应用组
            """
            return res['application-state']
        else:
            return None
    
    def config_sec_policy(self, rule, **kwargs):
        """配置安全策略"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略配置需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        dict_data = {
            'config':
                {
                    'sec-policy':
                        {
                            '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-security-policy',
                            '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                            '@xmlns:yang': 'urn:ietf:params:xml:ns:yang:1',
                            'vsys':
                                {
                                    'name': 'public',
                                    'static-policy': rule
                                }
                        }
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        logger.debug(f"配置安全策略XML: {data_xml}")
        res = self.edit_config(data_xml)
        if isinstance(res, tuple):
            return res[0], res[1]
        return res, ''
    
    def del_sec_policy(self, rule_name):
        res = self.get_sec_policy_single(rule_name=rule_name)
        if res:
            if 'static-policy' in res.keys():
                rule = res['static-policy']['rule']
                rule['@nc:operation'] = 'delete'
                dict_data = {
                    'config':
                        {
                            'sec-policy': {
                                '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-security-policy',
                                '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                                '@xmlns:yang': 'urn:ietf:params:xml:ns:yang:1',
                                'vsys':
                                    {'name': 'public',
                                     'static-policy':
                                         {'rule': rule}
                                     }
                            }
                        }
                }
                res = XmlToDict().dicttoxml(dict=dict_data)
                data_xml = res.split('\n')[1]
                res = self.edit_config(data_xml)
                if isinstance(res, tuple):
                    return res[0], res[1]
                return res, ''
        return False, '规则不存在'   
    
    def move_sec_policy(self, **kwargs):
        """移动安全策略"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("移动安全策略需要XML模板配置")
        
        if len(xml_templates) < 2:
            raise ValueError("移动安全策略需要至少2个XML模板")
        
        if kwargs.get('rule_name') and kwargs.get('target_name') and kwargs.get('insert'):
            data_xml = xml_templates[0].xml_template.format(rule_name=kwargs['rule_name'], target_name=kwargs['target_name'], insert=kwargs['insert'])
            res = self.edit_config(data_xml)
            return res
        elif kwargs.get('rule_name') and kwargs.get('insert'):
            data_xml = xml_templates[1].xml_template.format(rule_name=kwargs['rule_name'], insert=kwargs['insert'])
            res = self.edit_config(data_xml)
            return res
        return False
    
    def get_sec_zone(self, **kwargs):
        """获取安全区域"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("安全区域采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconfig_get_config(data=data_xml)
        if res:
            if isinstance(res['security-zone']['zone-instance'], list):
                return [res['security-zone']['zone-instance']]
            else:
                return res['security-zone']['zone-instance']
        else:
            return None

    def config_address(self, addr_object):
        # 配置地址组
        """
        :param addr_object:
        {
            '@nc:operation': 'create',
            'vsys': 'public',
            'name': 'test',
            'desc': 'how are you',
            'elements':
                [
                    {
                        'elem-id': '1',
                        'address-ipv4': '192.168.1.0/24'
                    },
                    {
                        'elem-id': '2',
                        'start-ipv4': '192.168.1.1',
                        'end-ipv4': '192.168.1.10'
                    }
                ]
        }
        :return:
        """
        dict_data = {
            'config': {
                'address-set':
                    {
                        '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-address-set',
                        '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                        'addr-object': addr_object
                    }
            }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        res = self.edit_config(data_xml)
        if isinstance(res, tuple):
            return res[0], res[1]
        elif isinstance(res, bool):
            return res, ''
        return False, 'netconf未捕获到预期的返回结果'
    
    def config_service(self, service_object):
        """配置服务"""
        """
        :param service_object:
        {
            '@nc:operation': 'create',
            'vsys': 'public',
            'name': 'test',
            'desc': 'how are you',
            'elements':
            [
            {
            'id': '0',
            'tcp': {'source-port': {'start': '0', 'end': '65535'},
            'dest-port': {'start': '5938', 'end': '5938'}}
            },
            {
            'id': '1',
            'udp': {'source-port': {'start': '0', 'end': '65535'},
            'dest-port': {'start': '5938', 'end': '5938'}}
            }
            ]
        }
        :return:
        """
        dict_data = {
            'config': {
                'service-set':
                    {
                        '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-service-set',
                        '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                        'service-object': service_object
                    }
            }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        res = self.edit_config(data_xml)
        # print(res)
        if isinstance(res, tuple):
            return res[0], res[1]
        elif isinstance(res, bool):
            return res, ''
        return res
    
    def config_nat_policy(self, policy_obj):
        """
        <config>
        <nat-policy xmlns="urn:huawei:params:xml:ns:yang:huawei-nat-policy"
        xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0"
        xmlns:yang="urn:ietf:params:xml:ns:yang:1">
        <vsys>
        <name>public</name>
        <rule nc:operation='create'>
        <name>test</name>
        <description>just for test</description>
        <source-zone>any</source-zone>
        <destination-zone>any</destination-zone>
        <source-ip>
        <address-ipv4>1.1.1.1/32</address-ipv4>
        </source-ip>
        <destination-ip>
        <address-ipv4>2.2.2.2/32</address-ipv4>
        </destination-ip>
        <service>
        <service-items>
        <tcp>
        <source-port>100 200 to 300 600</source-port>
        <dest-port>700 888 to 999 1023</dest-port>
        </tcp>
        </service-items>
        </service>
        <action>no-nat</action>
        </rule>
        </vsys>
        </nat-policy>
        </config>
        {
         'name': 'public', 虚拟系统的名称
         'rule': {
         '@nc:operation': 'create',
         'name': 'test',  # nat规则名称
         'description': 'just for test',
         'source-zone': 'any',
         'destination-zone': 'any',
         'egress-interface' : nat 策略引用的报文出接口名称 和 destination-zone 只能2选1
         'source-ip': {'address-ipv4': '1.1.1.1/32'},
           引用的源地址信息 address-ipv4、address-set address-ipv6 address-ipv4-range:{'start-ipv4': 'end-ipv4':}
           address-set-exclude address-ipv4-exclude address-ipv6-exclude address-ipv4-range-exclude
           address-mac
         'destination-ip': {'address-ipv4': '2.2.2.2/32'}, nat 目的地址信息 节点元素和source-ip一样
         'service': {'service-items': {'tcp': {'source-port': '100 200 to 300 600', 'dest-port': '700 888 to 999 1023'}}},
          引用的服务对象 service-object 和 service-items
         'action': 'no-nat'
         }}
        """
        dict_data = {
            'config': {
                'nat-policy':
                    {
                        '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-nat-policy',
                        '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                        '@xmlns:yang': 'urn:ietf:params:xml:ns:yang:1',
                        'vsys': policy_obj
                    }
            }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        res = self.edit_config(data_xml)
        # print(res)
        if isinstance(res, tuple):
            return res[0], res[1]
        elif isinstance(res, bool):
            return res, ''
        return res, ''
    
    # 配置DNAT规则
    def config_dnat(self, object):
        """
        目前就支持三种，如下
        ICMP——1 (Internet控制报文协议)
        TCP  ——6 (传输控制协议)
        UDP  ——17 (用户数据报协议)
        'server-mapping': {
            '@nc:operation': 'create',
            'name': 'test1234567890',
            'vsys': 'public',
            'global-vpn-name': 'test1',
            'protocol': '6',
            'global': {
                'if-type': 'GigabitEthernet1/0/0'
            },
            'global-port': {
                'start-port': '100',
                'end-port': '200'
            },
            'inside': {
                'start-ip': '1.2.3.4'
            },
            'inside-port': {
                'start-port': '100',
                'end-port': '200'
            },
            'no-reverse': 'true', # True 表示内部服务器无法主动访问外 部，False 表示内部服务器可以主动访问 外部网络。
            'inside-vpn-name': 'test1'
        }
        """
        dict_data = {
            'config': {
                'nat-server':
                    {
                        '@xmlns': 'urn:huawei:params:xml:ns:yang:huawei-nat-server',
                        '@xmlns:nc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                        'server-mapping': object
                    }
            }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        res = self.edit_config(data_xml)
        # print(res)
        if isinstance(res, tuple):
            return res[0], res[1]
        elif isinstance(res, bool):
            return res, ''
        return res
    
    def get_trunk_lacp(self, **kwargs):
        """获取Trunk LACP"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("Trunk LACP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconfig_get_config(data=data_xml)
        if res:
            if isinstance(res['interfaces']['interface'], dict):
                return [res['interfaces']['interface']]
            else:
                return res['interfaces']['interface']
        else:
            return None     
    
    def get_device_cpu(self, **kwargs):
        """获取设备CPU"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("设备CPU采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)

        res2 = res['system-state']['hw-system:device-resource']
        return res2
    
    def get_device_ntp(self, **kwargs):
        """获取设备NTP"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("设备NTP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data_xml)

        if 'ntp' in res['system'].keys():
            return True
        else:
            return False
    
    def get_device_route(self, **kwargs):
        """获取设备路由"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("设备路由采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconfig_get_config(data_xml)
        res2 = []

        for i in res['routing']['routing-instance']:
            # print(i.keys())
            if 'routing-protocols' in i.keys():
                for j in i['routing-protocols']['routing-protocol']['static-routes']['v4ur:ipv4']['v4ur:route']:
                    tmp = dict()
                    tmp['name'] = i['name']
                    tmp['VRF'] = None
                    tmp['Topology'] = None
                    tmp['Nexthop'] = j['v4ur:next-hop']['v4ur:next-hop-address']
                    tmp['Preference'] = j['hw-v4sr:preference']
                    tmp['Metric'] = '0'
                    tmp['Neighbor'] = 'NotExist'
                    tmp['Ipv4'] = j['v4ur:destination-prefix']
                    tmp['intf'] = 'NotExist'
                    tmp['Protocol'] = 'Static'
                    res2.append(tmp)

        return res2


class HuaweiCollectionDB(HuaweiyangNetconfConnect):
    """基于数据库的华为Collection NETCONF类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = 'Huawei'
        self.device_type = kwargs.get('device_type', 'switch')

    @staticmethod
    def get_method():
        """获取支持的方法列表"""
        return [
            'collection_system_info',
            'collection_stack',
            'get_phyentitys',
            'get_master_board',
            'collection_moduleinfo',
            'collection_trunk_lacp',
            'collection_subif',
            'collection_arp_list',
            'collection_mac_vlanFdbs',
            'collection_mac_vlanFdbDynamics',
            'collection_mac_bdFdbs',
            'collection_mac_bdFdbDynamic',
            'collection_mac_table',
            'collection_mac_bd',
            'collection_mac_vxlan',
            'collection_mac_vxlan_control',
            'collection_lldp_ip',
            'collection_intf_ipv4v6',
            'collection_mlag',
            'collection_device_cpu',
            'collection_device_memory',
            'collection_aggregation',
            'collection_intf_status',
            'collection_ospf_peer',
            'collection_bgp_peer',
            'collection_bgp_error',
            'collection_ntp_status',
            'collection_ip_routing_table',
            'collection_mac_flap',
            'collection_foo'
        ]

    # 以下是所有方法的实现
    def collection_system_info(self, **kwargs):
        """采集系统信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("系统信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['system']['systemInfo'] if res else None
    
    def collection_stack(self, **kwargs):
        """采集堆叠信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("堆叠信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        backup_xml = xml_templates[1].xml_template

        try:
            res = self.netconf_get(data_xml)
        except:
            res = self.netconf_get(backup_xml)
        return res['stack']['stackMemberInfos']['stackMemberInfo'] if res else None

    def get_phyentitys(self, **kwargs):
        """获取物理实体"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("物理实体采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        request = self.netconf_get(data_xml)
        return request['devm']['phyEntitys']['phyEntity']
    
    def get_master_board(self, **kwargs):
        """获取主控板"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("主控板采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        request = self.netconf_get(data_xml)
        
        return request['devm']['mpuBoards']['mpuBoard']
    
    def collection_moduleinfo(self, **kwargs):
        """采集模块信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("模块信息采集需要XML模板配置")
        
        obtain_xml = xml_templates[0].xml_template
        back_xml = xml_templates[1].xml_template

        req = self.netconf_get(obtain_xml)
        if req:
            res = req['devm']['rUModuleInfos']['rUModuleInfo']
            if isinstance(res, dict):
                if res['entSerialNum'] == 'NA':
                    req = self.netconf_get(back_xml)
                    return req['devm']['rUModuleInfos']['rUModuleInfo']
            return res
    
    def collection_trunk_lacp(self, **kwargs):
        """采集Trunk LACP"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("Trunk LACP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['ifmtrunk']['TrunkIfs']['TrunkIf'] if res else []     
    
    def collection_subif(self, **kwargs):
        """采集子接口"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("子接口采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['ethernet']['ethSubIfs']['ethSubIf'] if res else []
    
    def collection_arp_list(self, **kwargs):
        """采集ARP列表"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("ARP列表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['arp']['arpTables']['arpTable'] if res else []
    
    def collection_mac_vlanFdbs(self, **kwargs):
        """采集MAC VLAN FDB"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC VLAN FDB采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['vlanFdbs']['vlanFdb'] if res else []
    
    def collection_mac_vlanFdbDynamics(self, **kwargs):
        """采集MAC VLAN FDB动态"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC VLAN FDB动态采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['vlanFdbDynamics']['vlanFdbDynamic'] if res else []
    
    def collection_mac_bdFdbs(self, **kwargs):
        """采集MAC BD FDB"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC BD FDB采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['bdFdbs']['bdFdb'] if res else []
    
    def collection_mac_bdFdbDynamic(self, **kwargs):
        """采集MAC BD FDB动态"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC BD FDB动态采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['bdFdbDynamics']['bdFdbDynamic'] if res else []
    
    def collection_mac_table(self):
        xml_dict = {'mac': {
            '@xmlns': 'http://www.huawei.com/netconf/vrp/huawei-mac',
            'vlanFdbDynamics': {
                'vlanFdbDynamic': {
                    'slotId': None,
                    'vlanId': None,
                    'macAddress': None,
                    'macType': None,
                    'outIfName': None}
            },
            'vlanFdbs': {
                'vlanFdb': {
                    'slotId': None,
                    'vlanId': None,
                    'macAddress': None,
                    'macType': None,
                    'outIfName': None
                }
            }
        }}
        regex = re.compile(r'(vlanFdbDynamics|vlanFdbs)')
        tmp_xml = XmlToDict().dicttoxml(dict=xml_dict)
        flag, res = self._netconf_get(tmp_xml)
        # {'slotId': '0', 'vlanId': '4', 'macAddress': '082e-5ff0-2981',
        # 'macType': 'dynamic', 'outIfName': '10GE1/3/0/47'}
        # return res['mac']['vlanFdbDynamics']['vlanFdbDynamic'] if res else None
        if not flag:
            regex_commpile = re.search(regex, res)
            if regex_commpile is not None:
                regex_res = regex_commpile.group()
                xml_dict['mac'].pop(str(regex_res))
                tmp_xml = XmlToDict().dicttoxml(dict=xml_dict)
                flag, res = self._netconf_get(tmp_xml)
        if res:
            mac_res = []
            # if 'bdFdbs' in res['mac']:
            #     if isinstance(res['mac']['bdFdbs']['bdFdb'], list):
            #         mac_res += res['mac']['bdFdbs']['bdFdb']
            #     else:
            #         mac_res += [res['mac']['bdFdbs']['bdFdb']]
            if 'vlanFdbs' in res['mac']:
                if isinstance(res['mac']['vlanFdbs']['vlanFdb'], list):
                    mac_res += res['mac']['vlanFdbs']['vlanFdb']
                else:
                    mac_res += [res['mac']['vlanFdbs']['vlanFdb']]
            if 'vlanFdbDynamics' in res['mac']:
                if isinstance(res['mac']['vlanFdbDynamics']['vlanFdbDynamic'], list):
                    mac_res += res['mac']['vlanFdbDynamics']['vlanFdbDynamic']
                else:
                    mac_res += [res['mac']['vlanFdbDynamics']['vlanFdbDynamic']]
            return mac_res
        else:
            return []

    def collection_mac_bd(self, **kwargs):
        """采集MAC BD"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC BD采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        flag, res = self._netconf_get(data_xml)
        if flag:
            return res['mac']['bdFdbs']['bdFdb'] if res else []
        return []
    
    def collection_mac_vxlan(self, **kwargs):
        """采集MAC VXLAN"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC VXLAN采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['vxlanFdbs']['vxlanFdb'] if res else []
    
    def collection_mac_vxlan_control(self, **kwargs):
        """采集MAC VXLAN控制"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC VXLAN控制采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mac']['vxlanControls']['vxlanControl'] if res else None
    
    def collection_lldp_ip(self, **kwargs):
        """采集LLDP IP"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("LLDP IP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['lldp']['lldpInterfaces']['lldpInterface'] if res else None
    
    def collection_intf_ipv4v6(self, **kwargs):
        """采集接口IPv4/IPv6"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("接口IPv4/IPv6采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        
        if res:
            for i in res['ifm']['interfaces']['interface']:
                if 'ifDynamicInfo' in i.keys():
                    if 'ifOperSpeed' in i['ifDynamicInfo'].keys():
                        i['ifDynamicInfo']['ifOperSpeed'] = str(int(int(i['ifDynamicInfo']['ifOperSpeed']) / 1000000))
            return res['ifm']['interfaces']['interface']
        return []
    
    def collection_mlag(self, **kwargs):
        """采集MLAG"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MLAG采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['mlag']['mlagInstances']['mlagInstance'] if res else None
    
    def collection_device_cpu(self, **kwargs):
        """采集设备CPU"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("设备CPU采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            return 'device do not suport netconf about cpu'

        res = data['devm']['cpuInfos']['cpuInfo']
        return res
    
    def collection_device_memory(self, **kwargs):
        """采集设备内存"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("设备内存采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            return 'device do not suport netconf about memory'
        
        res = data['devm']['memoryInfos']['memoryInfo']
        return res
    
    def collection_aggregation(self, **kwargs):
        """采集聚合"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("聚合采集需要XML模板配置")
        
        
        trunkIfs_xml = xml_templates[0].xml_template
        trunkMemberIfs_xml0 = xml_templates[1].xml_template
        trunkMemberIfs_xml1 = xml_templates[2].xml_template
        trunkMemberIfs_xml2 = xml_templates[3].xml_template

        try:
            trunkIfs_data = self.netconf_get(trunkIfs_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"聚合采集失败: {e}")
            return 'device do not suport netconf about aggregation'
        if isinstance(trunkIfs_data['ifmtrunk']['TrunkIfs']['TrunkIf'], list):
            for i in trunkIfs_data['ifmtrunk']['TrunkIfs']['TrunkIf']:
                tmp_xml = trunkMemberIfs_xml1.format(i['ifName'])
                trunkMemberIfs_xml0 = trunkMemberIfs_xml0 + tmp_xml
            trunkMemberIfs_xml = trunkMemberIfs_xml0 + trunkMemberIfs_xml2
            trunkMemberIfs_data = self.netconf_get(trunkMemberIfs_xml)
        else:
            return
        res = trunkMemberIfs_data['ifmtrunk']['TrunkIfs']['TrunkIf']
        return res

    def collection_intf_status(self, **kwargs):
        """采集接口状态"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("接口状态采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        r1 = self.netconf_get(data_xml)
        
        data_st = '''
        <devm xmlns="http://www.huawei.com/netconf/vrp/huawei-devm">
        <ports>'''
        data_end = '''</ports></devm>'''
        if r1:
            for i in r1['ifm']['interfaces']['interface']:
                if any(i["ifName"].startswith(str_) for str_ in
                       ["Tunnel", "Port", "MEth", "Vbdif", "Vlanif", "Sip", "LoopBack", "NULL0", "Stack-Port",
                        "Eth-Trunk"]):
                    continue
                elif i["ifName"].find('.') != -1:
                    continue
                else:
                    # print(i["ifName"])
                    tmp_data = '''<port>
                                <position>{}</position>
                                <ethernetPort>
                                <duplex/>
                                </ethernetPort>
                                </port>'''.format(i["ifName"])
                    data_st += tmp_data
        data_xml2 = data_st + data_end
        r2 = self.netconf_get(data_xml2)
        r2_res = dict()
        for i in r2['devm']['ports']['port']:
            r2_res[i['position']] = i['ethernetPort']['duplex']
        datas = list()
        for i in r1['ifm']['interfaces']['interface']:
            if any(i["ifName"].startswith(str_) for str_ in
                   ["Tunnel", "Port", "MEth", "Vbdif", "Vlanif", "Sip", "LoopBack", "NULL0", "Stack-Port",
                    "Eth-Trunk"]):
                continue
            elif i["ifName"].find('.') != -1:
                continue
            if 'ifDynamicInfo' in i.keys() and not i['ifName'].startswith('Eth-Trunk'):
                if 'ifOperSpeed' in i['ifDynamicInfo'].keys():
                    data = dict(
                        interface=i['ifName'],
                        status=i['ifDynamicInfo']['ifOperStatus'],
                        speed=i['ifDynamicInfo']['ifOperSpeed'],
                        duplex=r2_res[i['ifName']],
                        description='')
                    datas.append(data)
        return datas

    def collection_ospf_peer(self, **kwargs):
        """采集OSPF对等体信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("OSPF对等体采集需要XML模板配置")
        
        try:
            data_xml = xml_templates[0].xml_template
            res = self.netconf_get(data_xml)
            return res['ospf']['ospfSites']['ospfSite'] if res else []
        except Exception as e:
            logger.error(f"OSPF对等体采集失败: {e}")
            return []
    
    def collection_bgp_peer(self, **kwargs):
        """采集BGP对等体"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("BGP对等体采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"BGP对等体采集失败: {e}")
            return []

        res = []
        res1 = data['bgp']['bgpcomm']['bgpVrfs']['bgpVrf']['bgpVrfAFs']['bgpVrfAF']
        # print(dict(aa = res1))
        if isinstance(res1, list):
            for i in res1:
                if isinstance(i['peerAFs']['peerAF'], list):
                    for j in i['peerAFs']['peerAF']:
                        tmp = dict(
                            Name=None,
                            VRF=None,
                            AF=i.get('afType', 'NotExist'),
                        )
                        tmp['IpAddress'] = j.get('remoteAddress', 'NotExist')
                        tmp['ASNumber'] = 'NotExist'
                        tmp['State'] = j['peerInfo']['bgpCurState']

                        res.append(tmp)
                else:
                    j = i['peerAFs']['peerAF']
                    tmp = dict(
                        Name=None,
                        VRF=None,
                        AF=i.get('afType', 'NotExist'),
                    )
                    tmp['IpAddress'] = j.get('remoteAddress', 'NotExist')
                    tmp['ASNumber'] = 'NotExist'
                    tmp['State'] = j['peerInfo']['bgpCurState']

                    res.append(tmp)

        return res
    
    def collection_bgp_error(self, **kwargs):
        """采集BGP错误"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("BGP错误采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"BGP错误采集失败: {e}")
            return []

        logger.debug(f"BGP错误数据: {data}")
        return []
    
    def collection_ntp_status(self, **kwargs):
        """采集NTP状态"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NTP状态采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"NTP状态采集失败: {e}")
            return []

        res = data['ntp']['ntpStatus']
        return res
    
    def collection_ip_routing_table(self, **kwargs):
        """采集IP路由表"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IP路由表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"IP路由表采集失败: {e}")
            return []

        res = data['rm']['rmbase']['uniAfs']['uniAf']['topologys']['topology']['routes']['route']
        return res
    
    def collection_mac_flap(self, **kwargs):
        """采集MAC翻转"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC翻转采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        try:
            data = self.netconf_get(data_xml)  # 存在不支持情况
        except Exception as e:
            logger.error(f"MAC翻转采集失败: {e}")
            return []

        res = data['mac']['macflpDetectRecords']['macflpDetectRecord']
        return res
    
    def collection_foo(self, **kwargs):
        """采集foo信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("foo信息采集需要XML模板配置")
        
        try:
            data_xml = xml_templates[0].xml_template
            res = self.netconf_get(data_xml)
            return res if res else []
        except Exception as e:
            logger.error(f"foo信息采集失败: {e}")
            return []


class HuaweiYunShanCollection(HuaweiyangNetconfConnect):
    def __init__(self, *args, **kwargs):
        super(HuaweiYunShanCollection, self).__init__(*args, **kwargs)
        self.device_type = kwargs.get("device_type")

    def collection_arp_list_test(self, **kwargs):
        """
        采集ARP信息
        请求的XML命令
        <vni></vni>
        """
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("ARP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['ifm']['interfaces']['interface'] if res else []

    def collection_arp_list(self, **kwargs):
        """
        https://support.huawei.com/hedex/hdx.do?docid=EDOC1100344999&id=ahuawei-arp_list_bb2c34aaf6579b4b21e6b4fbb9dd9c0d
        """
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("ARP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['arp']['query-entries']['query-entry']

    def collection_mac_table(self, **kwargs):
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("MAC表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        return res['vlan']['vlans'] if res is not None else []


if __name__ == '__main__':
    pass
