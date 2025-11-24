
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
        """处理ARP数据"""
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # 处理MAC地址格式：将点替换为横线
                macaddress = i.get("macaddress", "") or i.get("mac", "")
                if macaddress:
                    try:
                        macaddress = macaddress.replace('.', '-')
                    except Exception:
                        pass
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("ipaddress", "") or i.get("address", ""),
                    macaddress=macaddress,
                    aging=i.get("aging", "") or i.get("age", ""),
                    type=i.get("type", ""),
                    vlan=i.get("vlan", ""),
                    interface=cisco_interface_format(i.get("interface", "").strip()),
                    vpninstance="",
                    log_time=i.get("log_time", ""),
                )
                arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        """处理MAC地址表数据"""
        mac_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # 处理MAC地址格式：将点替换为横线
                macaddress = i.get("macaddress", "") or i.get("destination_address", "")
                if macaddress:
                    try:
                        macaddress = macaddress.replace('.', '-')
                    except Exception:
                        pass
                
                # 获取接口名称
                interface = i.get("interface", "") or i.get("destination_port", "")
                interface = cisco_interface_format(interface.strip())
                
                # 处理类型字段，转换为小写
                mac_type = i.get("type", "").lower()
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    macaddress=macaddress,
                    vlan=i.get("vlan", ""),
                    interface=interface,
                    type=mac_type,
                    log_time=i.get("log_time", ""),
                )
                mac_datas.append(temp)
        return mac_datas

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        lldp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # 处理接口名称格式化
                local_interface = cisco_interface_format(i.get("local_interface", "").strip())
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    local_interface=local_interface,
                    chassis_id=i.get("chassis_id", ""),
                    neighbor_port=i.get("neighbor_port", "") or i.get("neighbor_port_id", ""),
                    portdescription=i.get("portdescription", ""),
                    neighborsysname=i.get("neighborsysname", "") or i.get("neighbor", ""),
                    management_ip=i.get("management_ip", ""),
                    management_type=i.get("management_type", "ipv4"),
                    neighbor_ip=i.get("neighbor_ip", ""),
                    log_time=i.get("log_time", ""),
                )
                lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []
        if isinstance(data_list, list):
            for i in data_list:
                ip_address = i.get("ip_address", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                if ip_address:
                    try:
                        # 处理IP地址格式，可能包含掩码
                        if '/' not in ip_address:
                            # 如果没有掩码，尝试从ipmask获取
                            ipmask = i.get("ipmask", "") or i.get("subnet_mask", "")
                            if ipmask:
                                ip_address = f"{ip_address}/{ipmask}"
                            else:
                                ip_address = f"{ip_address}/32"
                        
                        _ip = IPNetwork(ip_address)
                        location = [dict(start=_ip.first, end=_ip.last)]
                        
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=cisco_interface_format(i.get("interface", "")),
                            line_status=i.get("link_status", "") or i.get("line_status", ""),
                            protocol_status=i.get("protocol_status", "") or i.get("protocol_status", ""),
                            ipaddress=_ip.ip.format(),
                            ipmask=_ip.netmask.format(),
                            ip_type=i.get("ip_type", "Primary"),
                            location=location,
                            mtu=i.get("mtu", ""),
                            log_time=i.get("log_time", ""),
                        )
                        layer3datas.append(temp)
                    except Exception:
                        # 如果IP地址解析失败，跳过该记录
                        continue
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（不包含IP地址的接口）"""
        layer2datas = []
        if isinstance(data_list, list):
            # 定义正则表达式：排除某些接口类型
            int_regex = re.compile(r'^\w+[\d\/]+$')
            exclude_regex = re.compile(r'^((?!(Serial|Embedded|NVI|Virtual|Vlan|Loopback|Tunnel)).)*$')
            
            for i in data_list:
                interface = i.get("interface", "")
                ip_address = i.get("ip_address", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                
                # 如果有IP地址，跳过（应该由get_ip_interface处理）
                if ip_address:
                    continue
                
                # 排除一些接口列表并且接口名称不包含子接口
                if not (exclude_regex.search(interface) and int_regex.search(interface)):
                    continue
                
                # 处理duplex字段
                duplex = i.get("duplex", "auto")
                if 'Auto' in duplex:
                    duplex = 'auto'
                elif 'Full' in duplex:
                    duplex = 'full'
                elif 'Half' in duplex:
                    duplex = 'half'
                
                # 处理速度字段，使用思科特定的速度格式化
                speed = InterfaceFormat.cisco_speed_format(interface)
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=cisco_interface_format(interface),
                    status=i.get("link_status", "") or i.get("status", ""),
                    speed=speed,
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
        if isinstance(data_list, list):
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
