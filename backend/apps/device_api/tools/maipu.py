from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class MaipuPlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # Maipu设备MAC地址格式需要将 . 替换为 -，并转为小写
                macaddress = i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                    if macaddress:
                        macaddress = macaddress.lower()
                except Exception:
                    pass
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("ipaddress", ""),
                    macaddress=macaddress,
                    aging=i.get("age", "") or i.get("aging", ""),
                    type=i.get("type", ""),
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
                # Maipu设备MAC地址格式需要将 . 替换为 -，并转为小写
                macaddress = i.get("macaddress", "")
                try:
                    if macaddress and '.' in macaddress:
                        macaddress = macaddress.replace('.', '-')
                    if macaddress:
                        macaddress = macaddress.lower()
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
                    local_interface = InterfaceFormat.maipu_interface_format(local_interface)
                
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
                # Maipu设备使用ipaddr字段，可能是列表
                ipaddr = i.get("ipaddr", "")
                
                if not ipaddr:
                    continue
                
                # 处理IP地址列表
                if isinstance(ipaddr, list):
                    for _ip in ipaddr:
                        try:
                            _ipnet = IPNetwork(_ip)
                            location = [dict(start=_ipnet.first, end=_ipnet.last)]
                            
                            temp = dict(
                                hostip=i.get("hostip", ""),
                                interface=i.get("interface", ""),
                                line_status=i.get("protocolstatus", "") or i.get("line_status", ""),
                                protocol_status=i.get("protocolstatus", "") or i.get("protocol_status", ""),
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
                else:
                    # 单个IP地址
                    try:
                        _ipnet = IPNetwork(ipaddr)
                        location = [dict(start=_ipnet.first, end=_ipnet.last)]
                        
                        temp = dict(
                            hostip=i.get("hostip", ""),
                            interface=i.get("interface", ""),
                            line_status=i.get("protocolstatus", "") or i.get("line_status", ""),
                            protocol_status=i.get("protocolstatus", "") or i.get("protocol_status", ""),
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
            for i in data_list:
                interface = i.get("interface", "")
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                ipaddr = i.get("ipaddr", "")
                if ipaddr:
                    continue
                
                # 处理速度字段，Maipu设备有特殊的速度格式
                speed = i.get("speed", "")
                if speed:
                    if speed == '1000 M':
                        speed = '1G'
                    elif speed == '10000 M':
                        speed = '10G'
                    elif speed == '1000M':
                        speed = '10G'
                    else:
                        # 尝试使用通用方法转换
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
                    status=i.get("protocolstatus", "") or i.get("status", ""),
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
            # Maipu设备的聚合端口需要按aggregate字段分组
            tmp = {}
            for i in data_list:
                aggregate = i.get("aggregate", "")
                interface = i.get("interface", "")
                selected = i.get("selected", "")
                mode = i.get("mode", "")
                
                if aggregate:
                    if aggregate in tmp.keys():
                        tmp[aggregate]['memberports'].append(interface)
                        tmp[aggregate]['status'].append(selected)
                        tmp[aggregate]['mode'].append(mode)
                    else:
                        tmp[aggregate] = {
                            'memberports': [interface],
                            'status': [selected],
                            'mode': [mode]
                        }
            
            # 将分组后的数据转换为标准格式
            for aggregate, data in tmp.items():
                # 从原始数据中获取hostip和log_time（假设同一聚合组的数据hostip相同）
                hostip = ""
                log_time = ""
                for item in data_list:
                    if item.get("aggregate", "") == aggregate:
                        hostip = item.get("hostip", "")
                        log_time = item.get("log_time", "")
                        break
                
                temp = dict(
                    hostip=hostip,
                    aggregroup=aggregate,
                    memberports=data['memberports'],
                    status=data['status'],
                    mode=data['mode'],
                    log_time=log_time,
                )
                aggre_datas.append(temp)
        return aggre_datas
