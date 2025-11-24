from netaddr import IPNetwork
from apps.automation.tools.base_connection import InterfaceFormat


class MellanoxPlan:

    @staticmethod
    def _format_mac_address(macaddress):
        """格式化Mellanox设备的MAC地址：从 : 分隔转换为 - 分隔"""
        if not macaddress:
            return ""
        try:
            # 处理 aa:bb:cc:dd:ee:ff 格式
            if ':' in macaddress:
                tmp = macaddress.split(':')
                if len(tmp) == 6:
                    macaddress = tmp[0] + tmp[1] + '-' + tmp[2] + tmp[3] + '-' + tmp[4] + tmp[5]
            # 转为小写
            return macaddress.lower()
        except Exception:
            return macaddress.lower() if macaddress else ""

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        if isinstance(data_list, list):
            for i in data_list:
                # Mellanox设备MAC地址格式需要从 : 分隔转换为 - 分隔
                macaddress = MellanoxPlan._format_mac_address(i.get("macaddress", ""))
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    ipaddress=i.get("ipaddr", "") or i.get("ipaddress", ""),
                    macaddress=macaddress,
                    aging=i.get("aging", ""),
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
                # Mellanox设备MAC地址格式需要从 : 分隔转换为 - 分隔
                macaddress = MellanoxPlan._format_mac_address(i.get("macaddress", ""))
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    hostname=i.get("hostname", ""),
                    idc_name=i.get("idc_name", ""),
                    macaddress=macaddress,
                    vlan=i.get("vlan", ""),
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
                # Mellanox设备使用ipaddr字段
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "")
                
                # 跳过 'Unassigned' 的IP地址
                if not ipaddr or ipaddr == 'Unassigned':
                    continue
                
                try:
                    _ip = IPNetwork(ipaddr)
                    location = [dict(start=_ip.first, end=_ip.last)]
                    
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=i.get("interface", ""),
                        line_status=i.get("operstate", "") or i.get("line_status", ""),
                        protocol_status=i.get("protocol_status", ""),
                        ipaddress=_ip.ip.format(),
                        ipmask=_ip.netmask.format(),
                        ip_type=i.get("primary", "") or i.get("ip_type", ""),
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
                    if interface.startswith('mgmt'):
                        continue
                    if interface.startswith('lo'):
                        continue
                
                # 检查是否有IP地址，如果有则跳过（应该由get_ip_interface处理）
                ipaddr = i.get("ipaddr", "") or i.get("ipaddress", "")
                if ipaddr and ipaddr != 'Unassigned':
                    continue
                
                # 处理状态，转为小写
                status = i.get("operationalstate", "") or i.get("status", "")
                if status:
                    status = status.lower()
                
                # 处理速度字段
                speed = i.get("advertisedspeeds", "") or i.get("speed", "")
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=interface,
                    status=status,
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
                aggregroup = i.get("portchannel", "") or i.get("aggregroup", "")
                
                # 处理成员端口，Mellanox设备的memberports是字符串，需要按空格分割
                memberports = i.get("memberports", "")
                memberports_list = []
                
                if memberports:
                    try:
                        if isinstance(memberports, list):
                            memberports_list = memberports
                        elif isinstance(memberports, str):
                            # 按空格分割
                            tmp_members = memberports.split()
                            for member in tmp_members:
                                # 去掉括号后的内容（如 "Eth1/1(Up)" -> "Eth1/1"）
                                member_clean = member.split('(')[0]
                                memberports_list.append(member_clean.strip())
                    except Exception:
                        # 如果处理失败，尝试直接分割
                        if isinstance(memberports, str):
                            memberports_list = [p.strip() for p in memberports.split() if p.strip()]
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    aggregroup=aggregroup,
                    memberports=memberports_list,
                    status=i.get("status", ""),
                    mode=i.get("type", "") or i.get("mode", ""),
                    log_time=i.get("log_time", ""),
                )
                aggre_datas.append(temp)
        return aggre_datas
