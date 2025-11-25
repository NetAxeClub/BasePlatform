import re
from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class RuiJiePlan:

    @staticmethod
    def _ruijie_interface_format(interface):
        """格式化Ruijie设备接口名称"""
        if re.search(r'^(Ag)', interface):
            return interface.replace('Ag', 'AggregatePort')
        elif re.search(r'^(Te)', interface):
            return interface.replace('Te', 'TenGigabitEthernetn')
        return interface

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # Ruijie设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['hardware'].replace('.', '-')
            except Exception:
                macaddress = i.get('hardware', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("address", ""),  # 旧代码使用 i['address']
                macaddress=macaddress,
                aging=i.get("agemin", ""),  # 旧代码使用 i['agemin']
                type=i.get("type", ""),  # 旧代码使用 i['type']
                vlan=i.get("vlan", ""),  # 旧代码使用 i.get('vlan')
                interface=i.get("interface", "").strip(),  # 旧代码使用 i['interface'].strip()
                vpninstance="",
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        """处理MAC地址表数据（与旧代码逻辑保持一致）"""
        mac_data = []

        for i in data_list:
            # Ruijie设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("vlan", ""),  # 旧代码使用 i['vlan']
                interface=i.get("interface", "").strip(),  # 旧代码使用 i['interface'].strip()
                type=i.get("type", "").lower(),  # 旧代码使用 i['type'].lower()
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        lldp_datas = []

        for i in data_list:
            # 处理接口名称格式化
            local_interface = i.get("local_interface", "")
            if local_interface:
                local_interface = RuiJiePlan._ruijie_interface_format(local_interface)

            temp = dict(
                hostip=i.get("hostip", ""),
                local_interface=local_interface,
                chassis_id=i.get("chassis_id", ""),
                neighbor_port=i.get("neighbor_port", ""),
                portdescription=i.get("portdescription", ""),
                neighborsysname=i.get("neighborsysname", ""),
                management_ip=i.get("management_ip", ""),
                management_type=i.get("management_type", ""),
                neighbor_ip=i.get("neighbor_ip", ""),
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（与旧代码逻辑保持一致：if-elif-else结构）"""
        layer3datas = []

        for i in data_list:
            # 旧代码使用 if-elif-else 结构
            if i.get('priipaddr') != 'no address':
                _ip = IPNetwork(i['priipaddr'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Primary',
                    location=location,
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
            elif i.get('secipaddr') != 'no address':
                # 注意：旧代码这里用的是 i['priipaddr'] 而不是 i['secipaddr']！
                _ip = IPNetwork(i['priipaddr'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Sub',
                    location=location,
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
            else:
                # 旧代码还有一个 else 分支处理没有IP的情况
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=i.get("priipaddr", ""),  # 旧代码使用 i['priipaddr']
                    ip_type='',
                    location=[],
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（与旧代码逻辑保持一致：不检查IP地址，直接处理所有接口）"""
        layer2datas = []

        for i in data_list:
            interface = i.get("interface", "")
            
            # 跳过AggregatePort开头的接口（与旧代码逻辑保持一致）
            if interface.startswith('AggregatePort'):
                continue

            # 处理速度字段（与旧代码逻辑保持一致）
            speed = i.get("speed", "")  # 旧代码使用 i['speed']
            if speed == 'Unknown' or speed == 'unknown':
                speed = InterfaceFormat.ruijie_speed_format(interface)  # 旧代码使用 i['interface']
            # 旧代码直接使用 InterfaceFormat.mathintspeed(i['speed'])
            speed = InterfaceFormat.mathintspeed(speed)

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=interface,  # 旧代码使用 i['interface']
                status=i.get("status", ""),  # 旧代码使用 i['status']
                speed=speed,
                duplex=i.get("duplex", ""),  # 旧代码使用 i['duplex']
                description=i.get("description", ""),  # 旧代码使用 i.get('description')
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（与旧代码逻辑保持一致）"""
        aggre_datas = []

        for i in data_list:
            # 处理成员端口（与旧代码逻辑保持一致）
            try:
                memberports = []
                tmp_members = i['ports'].split(',')
                for member in tmp_members:
                    memberports.append(RuiJiePlan._ruijie_interface_format(member))
            except Exception:
                memberports = i['memberports'].split(',')

            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=RuiJiePlan._ruijie_interface_format(i.get("aggregateport", "")),  # 旧代码使用 i['aggregateport']
                memberports=memberports,
                status='',  # 旧代码固定为空
                mode='',  # 旧代码固定为空
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas
