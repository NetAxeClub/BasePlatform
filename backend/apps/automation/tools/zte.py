# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      zte
   Description:
   Author:          jmli12
   date：           2024/12/19 15:38
-------------------------------------------------
   Change Activity:
                    2024/12/19 15:38
-------------------------------------------------
"""
import re
import json
from datetime import datetime
from django.core.cache import cache
from netaddr import IPNetwork

from apps.asset.models import NetworkDevice, Model, Vendor
from utils.connect_layer.auto_main import BatManMain
from utils.db.mongo_ops import MongoNetOps
from utils.wechat_api import send_msg_netops
from .base_connection import BaseConn, InterfaceFormat


def zte_interface_format(interface):
    if re.search(r'^(Ag)', interface):
        return interface.replace('Ag', 'AggregatePort')
    elif re.search(r'^(Te)', interface):
        return interface.replace('Te', 'TenGigabitEthernetn')

    return interface


class ZteProc(BaseConn):
    """
    show ip arp
    show mac
    show ip interface brief
    show interfaces status
    show aggregatePort summary
    show version
    show switch virtual
    show member
    """

    def arp_proc(self, res):
        """
        {'address': '30.116.154.62', 'age': 'H', 'mac_address': 'fc44.9f6a.7a18', 'interface': ['vlan519'], 'state': '', 'external_vlan': '519', 'internal_vlan': 'N/A', 'sub_interface': ['N/A']}

        """
        arp_datas = []
        for i in res:
            try:
                macaddress = i['mac_address'].replace('.', '-')
            except Exception as e:
                macaddress = i.get('mac_address', '')
                pass
            tmp = dict(
                hostip=self.hostip,
                hostname=self.hostname,
                idc_name=self.idc_name,
                ipaddress=i['address'],
                macaddress=macaddress,
                aging=i['age'],
                type='',
                vlan=i['external_vlan'],
                interface=''.join(i['sub_interface']),
                vpninstance='',
                log_time=datetime.now()
            )
            arp_datas.append(tmp)
        if arp_datas:
            MongoNetOps.insert_table(
                'Automation', self.hostip, arp_datas, 'ARPTable')

    def mac_proc(self, res):
        """
        {'vlan': '1', 'macaddress': '30b9.301b.017f', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': '30b9.301c.38d1', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f7.0159', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': '30b9.301a.ff52', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f7.080e', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f7.080d', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f6.eb20', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f7.0916', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '1', 'macaddress': 'acce.92f7.0915', 'type': 'Dynamic', 'interface': 'smartgroup1'}
        {'vlan': '520', 'macaddress': 'fada.33a3.e300', 'type': 'Dynamic', 'interface': 'xxvgei-0/1/1/2'}
        """
        if isinstance(res, list):
            mac_datas = []
            for i in res:
                try:
                    macaddress = i['macaddress'].replace('.', '-')
                except Exception as e:
                    macaddress = i.get('macaddress')
                    pass
                tmp = dict(
                    hostip=self.hostip,
                    hostname=self.hostname,
                    idc_name=self.idc_name,
                    macaddress=macaddress,
                    vlan=i['vlan'],
                    interface=i['interface'].strip(),
                    type=i['type'].lower(),
                    log_time=datetime.now()
                )
                mac_datas.append(tmp)
            if mac_datas:
                MongoNetOps.insert_table(
                    'Automation', self.hostip, mac_datas, 'MACTable')

    def aggre_port_proc(self, res):
        """
        {'group': '1', 'port': 'xxvgei-0/1/1/41[SA*', 'state': 'ACTIVE'}
        {'group': '1', 'port': 'xxvgei-1/1/1/41[SA', 'state': 'INACTIVE'}
        {'group': '19', 'port': 'xxvgei-0/1/1/9[FA*]', 'state': 'ACTIVE'}
        {'group': '19', 'port': 'xxvgei-0/1/1/10[FA*', 'state': 'ACTIVE'}
        {'group': '19', 'port': 'xxvgei-1/1/1/9[FA*]', 'state': 'ACTIVE'}
        """
        if isinstance(res, str):
            return
        aggre_datas = []
        group_data = {}
        for i in res:
            if i['group'] not in group_data.keys():
                group_data[i['group']] = [i]
            else:
                group_data[i['group']].append(i)

        for i in group_data.keys():
            member_ports = [x['port'].split('[')[0] for x in group_data[i]]
            state = [x['state'] for x in group_data[i]]
            tmp = dict(
                hostip=self.hostip,
                aggregroup=f"smartgroup{i}",
                memberports=member_ports,
                status=state,
                mode=''
            )
            aggre_datas.append(tmp)
        if aggre_datas:
            MongoNetOps.insert_table(
                'Automation', self.hostip, aggre_datas, 'AggreTable')

    def interface_proc(self, res):
        """
        {'interface': 'cgei-0/1/1/49', 'link_status': 'administratively down', 'interface_index': '8240', 'description': 'NO-USE', 'protocol_status': 'down', 'ipv4_protocol': 'down', 'ipv6_protocol': 'down', 'detect_status': 'RX-OK/TX-OK', 'uptime': '-', 'hardware_type': 'CGigabit Ethernet', 'mac_address': 'fc44.9f6a.7a18', 'ip_address': '', 'mask': '', 'bandwith': '40 Gbit/s', 'mtu': ['1600']}
        """
        layer2datas = []
        for i in res:
            # if i['interface'].startswith('AggregatePort'):
            #     continue
            # if i['speed'] == 'Unknown' or i['speed'] == 'unknown':
            #     i['speed'] = InterfaceFormat.ruijie_speed_format(
            #         i['interface'])
            data = dict(hostip=self.hostip,
                        interface=i['interface'],
                        status=i['link_status'],
                        # speed=i['speed'],
                        speed=i['bandwith'],
                        duplex='',
                        description=i.get('description'))
            layer2datas.append(data)
        if layer2datas:
            MongoNetOps.insert_table(
                db='Automation',
                hostip=self.hostip,
                datas=layer2datas,
                tablename='layer2interface')
        return

    def version_proc(self, res):
        """
       [{'slot': '0', 'version': '5900 V6.00.03.94P01', 'hardware': '5960X-56QU-HF', 'master': 'M'},
       {'slot': '1', 'version': '5900 V6.00.03.94P01', 'hardware': '5960X-56QU-HF', 'master': 'S'}]
        """
        if isinstance(res, dict):
            model_name = res['hardware']
            model_q = Model.objects.get_or_create(name=model_name,
                                                  vendor=Vendor.objects.get(alias='ZTE'))
            NetworkDevice.objects.filter(
                manage_ip=self.hostip).update(model=model_q[0])
        elif isinstance(res, list):
            for i in res:
                model_name = i['hardware']
                model_q = Model.objects.get_or_create(name=model_name,
                                                      vendor=Vendor.objects.get(alias='ZTE'))
                NetworkDevice.objects.filter(
                    manage_ip=self.hostip).update(model=model_q[0])

    def switch_virtual_proc(self, res):
        if isinstance(res, dict):
            if res['role'] == 'ACTIVE':
                NetworkDevice.objects.filter(
                    manage_ip=self.hostip, slot=int(
                        res['member'])).update(
                    ha_status=1)
            elif res['role'] == 'STANDBY':
                NetworkDevice.objects.filter(
                    manage_ip=self.hostip, slot=int(
                        res['member'])).update(
                    ha_status=2)
        elif isinstance(res, list):
            for i in res:
                if i['role'] == 'ACTIVE':
                    NetworkDevice.objects.filter(
                        manage_ip=self.hostip, slot=int(
                            i['member'])).update(
                        ha_status=1)
                elif i['role'] == 'STANDBY':
                    NetworkDevice.objects.filter(
                        manage_ip=self.hostip, slot=int(
                            i['member'])).update(
                        ha_status=2)
        return

    def lldp_proc(self, res):
        """
        {'local_interface': 'xxvgei-0/1/1/9', 'chassis_id': 'fc44.9f6a.f32c', 'neighbor_port': 'xgei-0/1/1/49', 'portdescription': 'uT:SRDSJJL-3F-C-11_C-12-MHSW-ZX5960-1U34.30.116.151.126.xxv', 'neighborsysname': 'SRDSJJL-3F-A-13_A-14-SMSW-ZX5952-1U40', 'management_ip': '30.116.151.1', 'management_type': 'IPv4'}

        """
        lldp_datas = []
        for i in res:
            neighbor_ip = ''
            if 'neighborsysname' in i.keys():
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
                hostip=self.hostip,
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
        if lldp_datas:
            MongoNetOps.insert_table(
                'Automation', self.hostip, lldp_datas, 'LLDPTable')

    def path_map(self, file_name, res: list):
        fsm_map = {
            'show_arp': self.arp_proc,
            'show_mac_table': self.mac_proc,
            'show_interface': self.interface_proc,
            'show_version': self.version_proc,
            'show_lacp_internal': self.aggre_port_proc,
            'show_lldp_entry': self.lldp_proc,
        }
        if file_name in fsm_map.keys():
            fsm_map[file_name](res)
        else:
            pass
            # send_msg_netops"设备:{}\n命令:{}\n不被解析".format(self.hostip, file_name))

    def _collection_analysis(self, paths: list):
        for path in paths:
            res = BatManMain.info_fsm(path=path['path'], fsm_platform=self.fsm_flag)
            self.path_map(path['cmd_file'], res)
