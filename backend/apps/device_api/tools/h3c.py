import re
from netaddr import IPNetwork, IPAddress
from apps.automation.tools.base_connection import InterfaceFormat


class H3CPlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        if isinstance(data_list, list):
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
        if isinstance(data_list, list):
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
        if isinstance(data_list, list):
            for i in data_list:
                # 处理接口名称格式化
                local_interface = i.get("local_interface", "")
                if local_interface:
                    local_interface = InterfaceFormat.h3c_interface_format(local_interface)
                
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
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # H3C设备可能使用ipaddr或ipaddress字段
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                
                if not ipaddr:
                    continue
                
                # 处理接口名称，可能使用intf或interface字段
                interface = i.get("intf", "") or i.get("interface", "")
                
                # 处理IP地址列表或单个IP地址
                if isinstance(ipaddr, list):
                    ip_type_list = i.get("ip_type", [])
                    if not isinstance(ip_type_list, list):
                        ip_type_list = [ip_type_list] if ip_type_list else ["Primary"]
                    
                    for idx, _ip in enumerate(ipaddr):
                        try:
                            ip_type = ip_type_list[idx] if idx < len(ip_type_list) else "Primary"
                            
                            if '/' in str(_ip):
                                _ipnet = IPNetwork(_ip)
                                location = [dict(start=_ipnet.first, end=_ipnet.last)]
                                
                                temp = dict(
                                    hostip=i.get("hostip", ""),
                                    interface=InterfaceFormat.h3c_interface_format(interface),
                                    line_status=i.get("line_status", ""),
                                    protocol_status=i.get("protocol_status", ""),
                                    ipaddress=_ipnet.ip.format(),
                                    ipmask=_ipnet.netmask.format(),
                                    ip_type=ip_type,
                                    location=location,
                                    mtu=i.get("mtu", ""),
                                    log_time=i.get("log_time", ""),
                                )
                                layer3datas.append(temp)
                            else:
                                _ipnet = IPAddress(_ip)
                                location = [dict(start=_ipnet.value, end=_ipnet.value)]
                                
                                temp = dict(
                                    hostip=i.get("hostip", ""),
                                    interface=InterfaceFormat.h3c_interface_format(interface),
                                    line_status=i.get("line_status", ""),
                                    protocol_status=i.get("protocol_status", ""),
                                    ipaddress=_ipnet.format(),
                                    ipmask='255.255.255.255',
                                    ip_type=ip_type,
                                    location=location,
                                    mtu=i.get("mtu", ""),
                                    log_time=i.get("log_time", ""),
                                )
                                layer3datas.append(temp)
                        except Exception:
                            # 如果IP地址解析失败，跳过该记录
                            continue
                else:
                    # 单个IP地址
                    try:
                        if '/' in str(ipaddr):
                            _ipnet = IPNetwork(ipaddr)
                            location = [dict(start=_ipnet.first, end=_ipnet.last)]
                            
                            temp = dict(
                                hostip=i.get("hostip", ""),
                                interface=InterfaceFormat.h3c_interface_format(interface),
                                line_status=i.get("line_status", ""),
                                protocol_status=i.get("protocol_status", ""),
                                ipaddress=_ipnet.ip.format(),
                                ipmask=_ipnet.netmask.format(),
                                ip_type=i.get("ip_type", "Primary"),
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
                                interface=InterfaceFormat.h3c_interface_format(interface),
                                line_status=i.get("line_status", ""),
                                protocol_status=i.get("protocol_status", ""),
                                ipaddress=_ipnet.format(),
                                ipmask='255.255.255.255',
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
            for i in data_list:
                interface = i.get("interface", "")
                
                # 跳过某些特殊接口
                if interface:
                    if interface.startswith('BAGG'):
                        continue
                    if interface.startswith('RAGG'):
                        continue
                    if interface.startswith('Vlan'):
                        continue
                    if interface.startswith('Loop'):
                        continue
                    if interface.startswith('InLoop'):
                        continue
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                if ipaddr:
                    continue
                
                # 处理速度字段
                speed = i.get("speed", "")
                if speed:
                    # 处理特殊速度值
                    if isinstance(speed, str):
                        if speed.find('-') != -1:
                            speed = 'IRF'
                        elif speed.find('(') != -1:
                            speed = speed.split('(')[0]
                        elif speed == 'auto':
                            # 根据接口名称推断速度
                            speed = H3CPlan._h3c_speed_format(interface)
                        elif speed == 'UP':
                            speed = H3CPlan._h3c_speed_format(interface)
                    
                    try:
                        speed = InterfaceFormat.mathintspeed(int(speed))
                    except (ValueError, TypeError):
                        try:
                            speed = InterfaceFormat.mathintspeed(speed) if isinstance(speed, str) else ""
                        except:
                            speed = ""
                
                # 处理双工模式
                duplex = i.get("duplex", "")
                if isinstance(duplex, str) and duplex.find('-') != -1:
                    duplex = 'IRF'
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=InterfaceFormat.h3c_interface_format(interface),
                    status=i.get("status", "") or i.get("protocol_status", ""),
                    speed=speed,
                    duplex=duplex,
                    description=i.get("description", "") or i.get("interface_description", ""),
                    log_time=i.get("log_time", ""),
                )
                layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据"""
        aggre_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # 处理聚合组名称，可能使用aggname或aggregroup字段
                aggregroup = i.get("aggname", "") or i.get("aggregroup", "")
                
                # 处理成员端口，可能是列表或字符串
                memberports = i.get("memberports", "")
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
                    formatted_port = InterfaceFormat.h3c_interface_format(port)
                    formatted_memberports.append(formatted_port)
                
                # 处理状态，可能是列表或字符串
                status = i.get("status", "")
                if isinstance(status, list):
                    status_list = status
                else:
                    status_list = [status] if status else []
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    aggregroup=InterfaceFormat.h3c_interface_format(aggregroup),
                    memberports=formatted_memberports,
                    status=status_list,
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
