import json
from netaddr import IPNetwork
from django.core.cache import cache
from apps.automation.tools.base_connection import InterfaceFormat
from apps.asset.models import NetworkDevice


class HuaweiPlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []
        for i in data_list:
            if i['interface'].find('.') != -1:
                i['interface'] = i['interface'].split('.')[0]
            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ipaddress", ""),
                macaddress=i.get("macaddress", ""),
                aging=i.get("aging", ""),
                type=i.get("type", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.huawei_interface_format(i.get("interface", "")),
                vpninstance=i.get("vpninstance", ""),
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        mac_data = []
        for i in data_list:
            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=i.get("macaddress", ""),
                vlan=i.get("vlan", ""),
                interface=InterfaceFormat.huawei_interface_format(i.get("interface", "")),
                type=i.get("type", ""),
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        lldp_datas = []
        for i in data_list:
            # 根据neighborsysname查询neighbor_ip（与旧代码逻辑保持一致）
            neighbor_ip = ''
            neighborsysname = i.get("neighborsysname", "")
            if neighborsysname:
                tmp_neighbor_ip = cache.get('cmdb_' + neighborsysname)
                if tmp_neighbor_ip:
                    tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                    neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                else:
                    tmp_neighbor_ip = NetworkDevice.objects.filter(name=neighborsysname).values('manage_ip')
                    neighbor_ip = tmp_neighbor_ip[0]['manage_ip'] if tmp_neighbor_ip else ''
            
            temp = dict(
                hostip=i.get("hostip", ""),
                local_interface=i.get("local_interface", ""),
                chassis_id=i.get("chassis_id", ""),
                neighbor_port=i.get("neighbor_port", ""),
                portdescription=i.get("portdescription", ""),
                neighborsysname=neighborsysname,
                management_ip=i.get("management_ip", ""),
                management_type=i.get("management_type", ""),
                neighbor_ip=neighbor_ip,
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []
        for i in data_list:
            internet_address = i.get("internet_address", "") or i.get("ipaddress", "")
            if internet_address:
                try:
                    # 处理IP地址格式，可能包含掩码
                    if '/' not in internet_address:
                        # 如果没有掩码，尝试从ipmask获取
                        ipmask = i.get("ipmask", "") or i.get("subnet_mask", "")
                        if ipmask:
                            internet_address = f"{internet_address}/{ipmask}"
                        else:
                            internet_address = f"{internet_address}/32"
                    
                    _ip = IPNetwork(internet_address)
                    location = [dict(start=_ip.first, end=_ip.last)]
                    
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=i.get("interface", ""),
                        line_status=i.get("line_status", ""),
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
        for i in data_list:
            interface = i.get("interface", "")
            internet_address = i.get("internet_address", "") or i.get("ipaddress", "")
            
            # 跳过某些特殊接口
            if interface:
                if interface.startswith('LoopBack'):
                    continue
                if interface.startswith('NULL'):
                    continue
                if interface.startswith('Vlanif'):
                    continue
                if interface.startswith('Ethernet0/0/0'):
                    continue
            
            # 如果有IP地址，跳过（应该由get_ip_interface处理）
            if internet_address:
                continue
            
            # 处理速度字段
            speed = i.get("speed", "")
            if speed:
                try:
                    speed = InterfaceFormat.mathintspeed(int(speed))
                except (ValueError, TypeError):
                    speed = InterfaceFormat.mathintspeed(speed) if isinstance(speed, str) else ""
            
            temp = dict(
                hostip=i.get("hostip", ""),
                interface=InterfaceFormat.huawei_interface_format(interface),
                status=i.get("protocol_status", "") or i.get("status", ""),
                speed=speed,
                duplex=i.get("duplex", ""),
                description=i.get("interface_description", "") or i.get("description", ""),
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据"""
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
                formatted_port = InterfaceFormat.huawei_interface_format(port)
                formatted_memberports.append(formatted_port)
            
            # 处理状态，可能是列表或字符串
            status = i.get("status", "") or i.get("portstatus", "") or i.get("member_port_status", "")
            if isinstance(status, list):
                status_list = status
            else:
                status_list = [status] if status else []
            
            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=InterfaceFormat.huawei_interface_format(i.get("aggregroup", "") or i.get("trunk_num", "")),
                memberports=formatted_memberports,
                status=status_list,
                mode=i.get("mode", ""),
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas
