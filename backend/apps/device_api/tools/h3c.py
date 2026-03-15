import json
import re
from netaddr import IPNetwork, IPAddress
from django.core.cache import cache
from apps.device_api.common import InterfaceFormat
from apps.asset.models import NetworkDevice


class H3CPlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []

        for i in data_list:
            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ipaddress", ""),
                macaddress=i.get("macaddress", ""),
                aging=i.get("aging", ""),
                type=i.get("type", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.h3c_interface_format(i.get("interface", "")),
                vpninstance=i.get("vpninstance", ""),
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        mac_data = []

        for i in data_list:
            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=i.get("macaddress", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.h3c_interface_format(i.get("interface", "")),
                type=i.get("type", "") or i.get("state", ""),
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        lldp_datas = []

        for i in data_list:
            # 根据neighborsysname查询neighbor_ip（与旧代码逻辑保持一致）
            neighbor_ip = ''
            neighborsysname = i.get("neighborsysname", "")
            if neighborsysname:
                tmp_neighbor_ip = cache.get('cmdb_' + neighborsysname)
                if tmp_neighbor_ip:
                    tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                    neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                else:
                    tmp_neighbor_ip = NetworkDevice.objects.filter(name=neighborsysname).values('manage_ip').first()
                    neighbor_ip = tmp_neighbor_ip['manage_ip'] if tmp_neighbor_ip else ''

            temp = dict(
                hostip=i.get("hostip", ""),
                local_interface=i.get("local_interface", ""),
                chassis_id=i.get("chassis_id", ""),
                neighbor_port=i.get("neighbor_port", ""),
                portdescription=i.get("portdescription", ""),
                neighborsysname=neighborsysname,
                management_ip=i.get("management_ip", ""),
                management_type=i.get("management_type", ""),
                neighbor_ip=neighbor_ip,
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []

        for i in data_list:
            ipaddr = i.get("ipaddr", '')
           
            # 处理IP地址列表或单个IP地址（与旧代码逻辑保持一致）
            if isinstance(ipaddr, list):
                ip_type_list = i.get("ip_type", [])
                for _ip in range(len(ipaddr)):
                    # _ip 为数组下标 0，1，2，3
                    if str(ipaddr[_ip]).find('/') != -1:
                        _ipnet = IPNetwork(ipaddr[_ip])
                        location = [dict(start=_ipnet.first, end=_ipnet.last)]
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=InterfaceFormat.h3c_interface_format(i.get("intf", "")),
                            line_status=i.get("line_status", ""),
                            protocol_status=i.get("protocol_status", ""),
                            ipaddress=_ipnet.ip.format(),
                            ipmask=_ipnet.netmask.format(),
                            ip_type=ip_type_list[_ip],
                            location=location,
                            mtu=i.get("mtu", ""),
                            log_time=i.get("log_time", ""),
                        )
                        layer3datas.append(temp)
                    else:
                        _ipnet = IPAddress(ipaddr[_ip])
                        location = [dict(start=_ipnet.value, end=_ipnet.value)]
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=InterfaceFormat.h3c_interface_format(i.get("intf", "")),
                            line_status=i.get("line_status", ""),
                            protocol_status=i.get("protocol_status", ""),
                            ipaddress=_ipnet.format(),
                            ipmask='255.255.255.255',
                            ip_type=ip_type_list[_ip],
                            location=location,
                            mtu=i.get("mtu", ""),
                            log_time=i.get("log_time", ""),
                        )
                        layer3datas.append(temp)
            else:
                # 单个IP地址
                if str(ipaddr).find('/') != -1:
                    _ipnet = IPNetwork(ipaddr)
                    location = [dict(start=_ipnet.first, end=_ipnet.last)]
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=InterfaceFormat.h3c_interface_format(i.get("intf", "")),
                        line_status=i.get("line_status", ""),
                        protocol_status=i.get("protocol_status", ""),
                        ipaddress=_ipnet.ip.format(),
                        ipmask=_ipnet.netmask.format(),
                        ip_type=i.get("ip_type", ""),
                        location=location,
                        mtu=i.get("mtu", ""),
                        log_time=i.get("log_time", ""),
                    )
                    layer3datas.append(temp)
                else:
                    _ipnet = IPAddress(ipaddr)
                    location = [dict(start=_ipnet.value, end=_ipnet.value)]
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=InterfaceFormat.h3c_interface_format(i.get("intf", "")),
                        line_status=i.get("line_status", ""),
                        protocol_status=i.get("protocol_status", ""),
                        ipaddress=_ipnet.format(),
                        ipmask='255.255.255.255',
                        ip_type=i.get("ip_type", ""),
                        location=location,
                        mtu=i.get("mtu", ""),
                        log_time=i.get("log_time", ""),
                    )
                    layer3datas.append(temp)

        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（不包含IP地址的接口）"""
        layer2datas = []

        for i in data_list:
            interface = i.get("interface", "")

            # 跳过某些特殊接口（与旧代码逻辑保持一致）
            if interface.startswith('BAGG'):
                continue
            elif interface.startswith('RAGG'):
                continue
            elif interface.startswith('Vlan'):
                continue
            elif interface.startswith('Loop'):
                continue
            elif interface.startswith('InLoop'):
                continue

            # 处理速度字段（与旧代码逻辑保持一致）
            speed = i.get("speed", "")
            if speed and isinstance(speed, str):
                if speed.find('-') != -1:
                    speed = 'IRF'
                elif speed.find('(') != -1:
                    speed = speed.split('(')[0]

            # 处理双工模式（与旧代码逻辑保持一致）
            duplex = i.get("duplex", "")
            if duplex and isinstance(duplex, str) and duplex.find('-') != -1:
                duplex = 'IRF'

            # 处理特殊速度值
            if speed == 'auto':
                speed = H3CPlan._h3c_speed_format(interface)
            if speed == 'UP':
                speed = H3CPlan._h3c_speed_format(interface)
                duplex = '--'

            # 格式化速度（与旧代码逻辑保持一致）
            if speed:
                speed = InterfaceFormat.mathintspeed(speed)

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=InterfaceFormat.h3c_interface_format(interface),
                status=i.get("status", ""),  # 旧代码只用status字段
                speed=speed,
                duplex=duplex,
                description=i.get("description", ""),  # 旧代码只用description字段
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据"""
        aggre_datas = []

        for i in data_list:
            # 处理成员端口（与旧代码逻辑保持一致）
            memberports = i.get("memberports", "")
            if isinstance(memberports, list):
                formatted_memberports = []
                for member in memberports:
                    formatted_memberports.append(InterfaceFormat.h3c_interface_format(member))
            else:
                # 如果不是列表，直接使用（不格式化）
                formatted_memberports = memberports

            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=i.get("aggname", ""),  # 旧代码不格式化
                memberports=formatted_memberports,
                status=i.get("status", ""),  # 旧代码直接使用
                mode=i.get("mode", ""),
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas

    @staticmethod
    def _h3c_speed_format(interface):
        """根据接口名称推断速度（H3C设备）"""
        if re.search(r'^(GE)', interface) or re.search(r'^(GigabitEthernet)', interface):
            return '1G'
        elif re.search(r'^(XGE)', interface) or re.search(r'^(Ten-GigabitEthernet)', interface):
            return '10G'
        elif re.search(r'^(FGE)', interface) or re.search(r'^(FortyGigE)', interface):
            return '40G'
        elif re.search(r'^(Twenty-FiveGigE)', interface):
            return '25G'
        elif re.search(r'^(TwentyGigE)', interface):
            return '20G'
        elif re.search(r'^(TwoHundredGigE)', interface):
            return '200G'
        elif re.search(r'^(FourHundredGigE)', interface):
            return '400G'
        elif re.search(r'^(HGE)', interface) or re.search(r'^(HundredGigE)', interface):
            return '100G'
        elif re.search(r'^(MGE)', interface) or re.search(r'^(MEth)', interface):
            return '1G'
        elif re.search(r'^(M-GE)', interface):
            return '1G'
        return interface
