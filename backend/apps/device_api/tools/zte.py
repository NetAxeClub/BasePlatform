from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class ZtePlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # ZTE设备MAC地址格式需要将 . 替换为 -
                # 使用mac_address字段作为macaddress
                macaddress = i.get("mac_address", "") or i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                except Exception:
                    pass
                
                # 接口使用sub_interface字段（可能是列表，需要join）
                sub_interface = i.get("sub_interface", "")
                if isinstance(sub_interface, list):
                    interface = ''.join(sub_interface)
                else:
                    interface = sub_interface or i.get("interface", "")
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("address", "") or i.get("ipaddress", ""),
                    macaddress=macaddress,
                    aging=i.get("age", "") or i.get("aging", ""),
                    type=i.get("type", ""),
                    vlan=i.get("external_vlan", "") or i.get("vlan", ""),
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
                # ZTE设备MAC地址格式需要将 . 替换为 -
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
                # ZTE设备使用ip_address和mask字段
                ip_address = i.get("ip_address", "") or i.get("ipaddress", "")
                mask = i.get("mask", "") or i.get("ipmask", "")
                
                if not ip_address:
                    continue
                
                try:
                    # 处理IP地址格式，可能包含掩码
                    if '/' in ip_address:
                        internet_address = ip_address
                    elif mask:
                        internet_address = f"{ip_address}/{mask}"
                    else:
                        internet_address = f"{ip_address}/32"
                    
                    _ip = IPNetwork(internet_address)
                    location = [dict(start=_ip.first, end=_ip.last)]
                    
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=i.get("interface", ""),
                        line_status=i.get("link_status", "") or i.get("line_status", ""),
                        protocol_status=i.get("protocol_status", "") or i.get("ipv4_protocol", ""),
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
            for i in data_list:
                interface = i.get("interface", "")
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                ip_address = i.get("ip_address", "") or i.get("ipaddress", "")
                if ip_address:
                    continue
                
                # 处理速度字段，ZTE设备使用bandwith字段
                speed = i.get("bandwith", "") or i.get("speed", "")
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=interface,
                    status=i.get("link_status", "") or i.get("status", ""),
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
            # ZTE设备的聚合端口需要按group字段分组
            group_data = {}
            for i in data_list:
                group = i.get("group", "")
                if group:
                    if group not in group_data.keys():
                        group_data[group] = [i]
                    else:
                        group_data[group].append(i)
            
            # 将分组后的数据转换为标准格式
            for group, items in group_data.items():
                # 提取成员端口（去掉括号后的内容）
                member_ports = []
                states = []
                
                for item in items:
                    port = item.get("port", "")
                    if port:
                        # 去掉括号后的内容（如 "xxvgei-0/1/1/41[SA*" -> "xxvgei-0/1/1/41"）
                        port_clean = port.split('[')[0].strip()
                        if port_clean:
                            member_ports.append(port_clean)
                    
                    state = item.get("state", "")
                    if state:
                        states.append(state)
                
                # 从原始数据中获取hostip和log_time
                hostip = ""
                log_time = ""
                if items:
                    hostip = items[0].get("hostip", "")
                    log_time = items[0].get("log_time", "")
                
                temp = dict(
                    hostip=hostip,
                    aggregroup=f"smartgroup{group}",
                    memberports=member_ports,
                    status=states,
                    mode=items[0].get("mode", "") if items else "",
                    log_time=log_time,
                )
                aggre_datas.append(temp)
        return aggre_datas
