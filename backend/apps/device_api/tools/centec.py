from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class CentecPlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据"""
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # 处理MAC地址格式：将点替换为横线
                macaddress = i.get("macaddress", "")
                if macaddress:
                    try:
                        macaddress = macaddress.replace('.', '-')
                    except Exception:
                        pass
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("ipaddress", "") or i.get("ip", ""),
                    macaddress=macaddress,
                    aging=i.get("aging", "") or i.get("age", ""),
                    type=i.get("type", ""),
                    vlan=i.get("vlan", ""),
                    interface=i.get("interface", "").strip(),
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
                macaddress = i.get("macaddress", "")
                if macaddress:
                    try:
                        macaddress = macaddress.replace('.', '-')
                    except Exception:
                        pass
                
                # 获取接口名称，可能是ports或interface字段
                interface = i.get("interface", "") or i.get("ports", "")
                interface = interface.strip()
                
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
        """处理LLDP数据（盛科可能不支持LLDP，返回原数据）"""
        lldp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                temp = dict(
                    hostip=i.get("hostip", ""),
                    local_interface=i.get("local_interface", "").strip(),
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
                ip_address = i.get("ipaddress", "") or i.get("ip", "")
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
                            interface=i.get("interface", "").strip(),
                            line_status=i.get("line_status", "") or i.get("status", ""),
                            protocol_status=i.get("protocol_status", "") or i.get("protocol", ""),
                            ipaddress=_ip.ip.format(),
                            ipmask=_ip.netmask.format(),
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
                # 处理速度字段：如果以'a-'开头，需要去掉前缀
                speed = i.get("speed", "")
                if speed and isinstance(speed, str) and speed.startswith('a-'):
                    speed = speed.split('a-')[1]
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", "").strip(),
                    status=i.get("status", ""),
                    speed=InterfaceFormat.mathintspeed(speed),
                    duplex=i.get("duplex", ""),
                    description=i.get("description", ""),
                    log_time=i.get("log_time", ""),
                )
                layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（盛科的聚合口没有做解析，返回原数据）"""
        return data_list
