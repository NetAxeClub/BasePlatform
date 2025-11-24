import re
from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class HillstonePlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # Hillstone设备MAC地址格式需要将 . 替换为 -
                macaddress = i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                except Exception:
                    pass
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("ipaddress", ""),
                    macaddress=macaddress,
                    aging=i.get("age", "") or i.get("aging", ""),
                    type=i.get("typeflag", "") or i.get("type", ""),
                    vlan=i.get("vlan", ""),
                    interface=i.get("interface", ""),
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
                # Hillstone设备MAC地址格式需要将 . 替换为 -
                macaddress = i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                except Exception:
                    pass
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    macaddress=macaddress,
                    vlan=i.get("switch", "") or i.get("vlan", ""),
                    interface=i.get("interface", ""),
                    type=i.get("type", ""),
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
                # Hillstone设备使用ipaddr字段
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                
                if not ipaddr:
                    continue
                
                try:
                    # 处理IP地址格式，可能包含掩码
                    _ipnet = IPNetwork(ipaddr)
                    
                    # 安全纳管引擎，服务发布 定位用
                    location = []
                    if str(ipaddr) != '0.0.0.0/0':
                        location = [dict(start=_ipnet.first, end=_ipnet.last)]
                    
                    # 处理halp字段获取状态信息
                    # H:physical state;A:admin state;L:link state;P:protocol state;U:up;D:down;K:ha keep up
                    halp = i.get("halp", "")
                    physical_status_map = {'U': 'up', 'D': 'down', 'K': 'ha'}
                    line_status = ''
                    protocol_status = ''
                    
                    if halp:
                        try:
                            tmp = halp.split()
                            if len(tmp) >= 4:
                                line_status = physical_status_map.get(tmp[2], '')
                                protocol_status = physical_status_map.get(tmp[3], '')
                        except Exception:
                            pass
                    
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=i.get("interface", ""),
                        line_status=line_status or i.get("line_status", ""),
                        protocol_status=protocol_status or i.get("protocol_status", ""),
                        ipaddress=_ipnet.ip.format(),
                        ipmask=_ipnet.netmask.format(),
                        ip_type=i.get("ip_type", ""),
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
            int_regex = re.compile('ethernet')
            for i in data_list:
                interface = i.get("interface", "")
                
                # Hillstone设备只处理ethernet类型的物理接口
                if not interface or not int_regex.search(interface):
                    continue
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "") or i.get("internet_address", "")
                if ipaddr:
                    continue
                
                # 处理halp字段获取状态信息
                halp = i.get("halp", "")
                physical_status_map = {'U': 'up', 'D': 'down', 'K': 'ha'}
                physical_status = ''
                
                if halp:
                    try:
                        tmp = halp.split()
                        if len(tmp) >= 1:
                            physical_status = physical_status_map.get(tmp[0], '')
                    except Exception:
                        pass
                
                # 根据接口名称推断速度
                speed = HillstonePlan._hillstone_speed_format(interface)
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=interface,
                    status=physical_status or i.get("status", ""),
                    speed=speed,
                    duplex=i.get("duplex", ""),
                    description=i.get("description", ""),
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
                # 处理聚合组名称
                aggregroup = i.get("aggregroup", "") or i.get("aggregate", "")
                
                # 处理成员端口，可能是列表或字符串
                memberports = i.get("memberports", "")
                if isinstance(memberports, list):
                    memberports_list = memberports
                elif isinstance(memberports, str):
                    # 如果是字符串，尝试分割（可能是逗号分隔）
                    memberports_list = [p.strip() for p in memberports.split(',') if p.strip()]
                else:
                    memberports_list = []
                
                # 处理状态，可能是列表或字符串
                status = i.get("status", "")
                if isinstance(status, list):
                    # 如果status是字典列表（如 [{'xethernet4/0': ''}, {'xethernet4/1': ''}]）
                    if len(status) > 0 and isinstance(status[0], dict):
                        status_list = []
                        # 如果memberports_list还没有从status中提取，则从status中提取
                        if not memberports_list:
                            for member in status:
                                for mem_k, mem_v in member.items():
                                    memberports_list.append(mem_k)
                                    tmp_status = 'Up' if mem_v != 'shutdown' else 'shutdown'
                                    status_list.append(tmp_status)
                        else:
                            # 如果memberports_list已经存在，则只提取status
                            for idx, member in enumerate(status):
                                if idx < len(memberports_list):
                                    for mem_v in member.values():
                                        tmp_status = 'Up' if mem_v != 'shutdown' else 'shutdown'
                                        status_list.append(tmp_status)
                    else:
                        status_list = status
                else:
                    status_list = [status] if status else []
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    aggregroup=aggregroup,
                    memberports=memberports_list,
                    status=status_list,
                    mode=i.get("mode", ""),
                    log_time=i.get("log_time", ""),
                )
                aggre_datas.append(temp)
        return aggre_datas

    @staticmethod
    def _hillstone_speed_format(interface):
        """根据接口名称推断速度（Hillstone设备）"""
        if re.search(r'^(ethernet)', interface):
            return '1G'
        elif re.search(r'^(xethernet)', interface):
            return '10G'
        elif re.search(r'^(cethernet)', interface):
            return '100G'
        elif re.search(r'^(xxvethernet)', interface):
            return '25G'
        return 'auto'
