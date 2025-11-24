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
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # Ruijie设备MAC地址格式需要将 . 替换为 -
                # 使用hardware字段作为macaddress
                macaddress = i.get("hardware", "") or i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                except Exception:
                    pass
                
                # 接口需要strip()
                interface = i.get("interface", "")
                if interface:
                    interface = interface.strip()
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("address", "") or i.get("ipaddress", ""),
                    macaddress=macaddress,
                    aging=i.get("agemin", "") or i.get("aging", ""),
                    type=i.get("type", ""),
                    vlan=i.get("vlan", ""),
                    interface=interface,
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
                # Ruijie设备MAC地址格式需要将 . 替换为 -
                macaddress = i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                except Exception:
                    pass
                
                # 接口需要strip()，type转为小写
                interface = i.get("interface", "")
                if interface:
                    interface = interface.strip()
                
                type_value = i.get("type", "")
                if type_value:
                    type_value = type_value.lower()
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    macaddress=macaddress,
                    vlan=i.get("vlan", ""),
                    interface=interface,
                    type=type_value,
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
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # Ruijie设备使用priipaddr和secipaddr字段
                priipaddr = i.get("priipaddr", "")
                secipaddr = i.get("secipaddr", "")
                
                # 处理主IP地址
                if priipaddr and priipaddr != 'no address':
                    try:
                        _ip = IPNetwork(priipaddr)
                        location = [dict(start=_ip.first, end=_ip.last)]
                        
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=i.get("interface", ""),
                            line_status=i.get("status", "") or i.get("line_status", ""),
                            protocol_status=i.get("protocol", "") or i.get("protocol_status", ""),
                            ipaddress=_ip.ip.format(),
                            ipmask=_ip.netmask.format(),
                            ip_type='Primary',
                            location=location,
                            mtu=i.get("mtu", ""),
                            log_time=i.get("log_time", ""),
                        )
                        layer3datas.append(temp)
                    except Exception:
                        # 如果IP地址解析失败，跳过该记录
                        pass
                
                # 处理次IP地址
                if secipaddr and secipaddr != 'no address':
                    try:
                        _ip = IPNetwork(secipaddr)
                        location = [dict(start=_ip.first, end=_ip.last)]
                        
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=i.get("interface", ""),
                            line_status=i.get("status", "") or i.get("line_status", ""),
                            protocol_status=i.get("protocol", "") or i.get("protocol_status", ""),
                            ipaddress=_ip.ip.format(),
                            ipmask=_ip.netmask.format(),
                            ip_type='Sub',
                            location=location,
                            mtu=i.get("mtu", ""),
                            log_time=i.get("log_time", ""),
                        )
                        layer3datas.append(temp)
                    except Exception:
                        # 如果IP地址解析失败，跳过该记录
                        pass
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（不包含IP地址的接口）"""
        layer2datas = []
        if isinstance(data_list, list):
            for i in data_list:
                interface = i.get("interface", "")
                
                # 跳过AggregatePort开头的接口
                if interface and interface.startswith('AggregatePort'):
                    continue
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                priipaddr = i.get("priipaddr", "")
                secipaddr = i.get("secipaddr", "")
                if (priipaddr and priipaddr != 'no address') or (secipaddr and secipaddr != 'no address'):
                    continue
                
                # 处理速度字段
                speed = i.get("speed", "")
                if speed:
                    # 如果速度是Unknown或unknown，根据接口名称推断
                    if speed == 'Unknown' or speed == 'unknown':
                        speed = InterfaceFormat.ruijie_speed_format(interface)
                    else:
                        # 使用通用方法转换速度
                        try:
                            speed = InterfaceFormat.mathintspeed(int(speed))
                        except (ValueError, TypeError):
                            try:
                                speed = InterfaceFormat.mathintspeed(speed) if isinstance(speed, str) else ""
                            except:
                                speed = ""
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=interface,
                    status=i.get("status", ""),
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
                aggregroup = i.get("aggregateport", "") or i.get("aggregroup", "")
                if aggregroup:
                    aggregroup = RuiJiePlan._ruijie_interface_format(aggregroup)
                
                # 处理成员端口，Ruijie设备使用ports字段（逗号分隔）
                memberports = i.get("ports", "") or i.get("memberports", "")
                memberports_list = []
                
                if memberports:
                    try:
                        if isinstance(memberports, list):
                            memberports_list = memberports
                        elif isinstance(memberports, str):
                            # 按逗号分割
                            tmp_members = memberports.split(',')
                            for member in tmp_members:
                                member_clean = member.strip()
                                if member_clean:
                                    # 格式化接口名称
                                    formatted_port = RuiJiePlan._ruijie_interface_format(member_clean)
                                    memberports_list.append(formatted_port)
                    except Exception:
                        # 如果处理失败，尝试直接分割
                        if isinstance(memberports, str):
                            memberports_list = [RuiJiePlan._ruijie_interface_format(p.strip()) 
                                               for p in memberports.split(',') if p.strip()]
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    aggregroup=aggregroup,
                    memberports=memberports_list,
                    status=i.get("status", ""),
                    mode=i.get("mode", ""),
                    log_time=i.get("log_time", ""),
                )
                aggre_datas.append(temp)
        return aggre_datas
