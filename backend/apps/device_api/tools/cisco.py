import re
from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


def cisco_interface_format(interface):
    """格式化思科接口名称，将Gi转换为GigabitEthernet"""
    if interface and re.search(r'^(Gi)', interface):
        return interface.replace('Gi', 'GigabitEthernet')
    return interface


class CiscoPlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # 处理MAC地址格式：将点替换为横线（与旧代码逻辑保持一致）
            try:
                macaddress = i['mac'].replace('.', '-')
            except Exception:
                macaddress = i.get('mac', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("address", ""),  # 旧代码使用 i['address']
                macaddress=macaddress,
                aging=i.get("age", ""),  # 旧代码使用 i['age']
                type=i.get("type", ""),  # 旧代码使用 i['type']
                vlan=i.get("vlan", ""),  # 旧代码使用 i.get('vlan', '')
                interface=i.get("interface", "").strip(),  # 旧代码不格式化
                vpninstance="",
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        """处理MAC地址表数据（与旧代码逻辑保持一致）"""
        mac_datas = []

        for i in data_list:
            # 处理MAC地址格式：将点替换为横线（与旧代码逻辑保持一致）
            try:
                macaddress = i['destination_address'].replace('.', '-')
            except Exception:
                macaddress = i.get('destination_address', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("vlan", ""),  # 旧代码使用 i['vlan']
                interface=cisco_interface_format(i.get("destination_port", "").strip()),  # 旧代码使用 i['destination_port'].strip()
                type=i.get("type", "").lower(),  # 旧代码使用 i['type'].lower()
                log_time=i.get("log_time", ""),
            )
            mac_datas.append(temp)
        return mac_datas

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据（与旧代码逻辑保持一致）"""
        import json
        from django.core.cache import cache
        from apps.asset.models import NetworkDevice
        
        lldp_datas = []

        for i in data_list:
            # 解析neighbor_ip（与旧代码逻辑保持一致）
            neighbor_ip = ''
            if i.get('neighbor'):
                tmp_neighbor_ip = cache.get('cmdb_' + i['neighbor'])
                if tmp_neighbor_ip:
                    tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                    neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                else:
                    tmp_neighbor_ip = NetworkDevice.objects.filter(name=i['neighbor']).values('manage_ip').first()
                    neighbor_ip = tmp_neighbor_ip['manage_ip'] if tmp_neighbor_ip else ''

            temp = dict(
                hostip=i.get("hostip", ""),
                local_interface=cisco_interface_format(i.get("local_interface", "")),  # 旧代码使用 i['local_interface']
                chassis_id='',  # 旧代码固定为空
                neighbor_port=i.get("neighbor_port_id", ""),  # 旧代码使用 i['neighbor_port_id']
                portdescription='',  # 旧代码固定为空
                neighborsysname=i.get("neighbor", ""),  # 旧代码使用 i['neighbor']
                management_ip=i.get("management_ip", ""),
                management_type='ipv4',  # 旧代码固定为 'ipv4'
                neighbor_ip=neighbor_ip,
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（与旧代码逻辑保持一致：直接使用原始IP地址）"""
        layer3datas = []

        for i in data_list:
            # 旧代码直接使用 i['ip_address']，不做额外处理
            if i.get('ip_address'):
                _ip = IPNetwork(i['ip_address'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码不格式化
                    line_status=i.get("link_status", ""),  # 旧代码使用 i['link_status']
                    protocol_status=i.get("protocol_status", ""),  # 旧代码使用 i['protocol_status']
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Primary',  # 旧代码固定为 'Primary'
                    location=location,
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（与旧代码逻辑保持一致：不检查IP地址，直接处理所有接口）"""
        layer2datas = []

        # 定义正则表达式：排除某些接口类型（与旧代码逻辑保持一致）
        int_regex = re.compile('^\w+[\d\/]+$')
        exclude_regex = re.compile('^((?!(Serial|Embedded|NVI|Virtual|Vlan|Loopback|Tunnel)).)*$')

        for i in data_list:
            interface = i.get("interface", "")
            
            # 排除一些接口列表并且接口名称不包含子接口（与旧代码逻辑保持一致）
            if exclude_regex.search(interface) and int_regex.search(interface):
                # 处理duplex字段（与旧代码逻辑保持一致）
                duplex = 'auto'  # 旧代码初始值为 'auto'
                if 'Auto' in i.get("duplex", ""):
                    duplex = 'auto'
                elif 'Full' in i.get("duplex", ""):
                    duplex = 'full'
                elif 'Half' in i.get("duplex", ""):
                    duplex = 'half'

                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=interface,  # 旧代码不格式化
                    status=i.get("link_status", ""),  # 旧代码使用 i['link_status']
                    speed=InterfaceFormat.cisco_speed_format(interface),
                    duplex=duplex,
                    description=i.get("description", ""),
                    log_time=i.get("log_time", ""),
                )
                layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（思科设备可能使用Port-Channel或EtherChannel）"""
        aggre_datas = []

        for i in data_list:
            # 处理成员端口，可能是列表或字符串
            memberports = i.get("memberports", "") or i.get("portname", "")
            if isinstance(memberports, list):
                memberports_list = memberports
            elif isinstance(memberports, str):
                # 如果是字符串，尝试分割（可能是逗号分隔）
                memberports_list = [p.strip() for p in memberports.split(',') if p.strip()]
            else:
                memberports_list = []

            # 格式化每个成员端口
            formatted_memberports = []
            for port in memberports_list:
                formatted_port = cisco_interface_format(port)
                formatted_memberports.append(formatted_port)

            # 处理状态，可能是列表或字符串
            status = i.get("status", "") or i.get("portstatus", "") or i.get("member_port_status", "")
            if isinstance(status, list):
                status_list = status
            else:
                status_list = [status] if status else []

            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=cisco_interface_format(i.get("aggregroup", "") or i.get("trunk_num", "") or i.get("port_channel", "")),
                memberports=formatted_memberports,
                status=status_list,
                mode=i.get("mode", ""),
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas
