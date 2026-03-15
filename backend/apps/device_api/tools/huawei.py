import json
from netaddr import IPNetwork
from django.core.cache import cache
from apps.device_api.common import InterfaceFormat
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
            internet_address = i.get("internet_address", "")
            if internet_address:  
                _ip = IPNetwork(internet_address)
                location = [dict(start=_ip.first, end=_ip.last)]
                
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),
                    line_status=i.get("line_status", ""),
                    protocol_status=i.get("protocol_status", ""),
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Primary',
                    location=location,
                    mtu="",
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（不包含IP地址的接口）"""
        layer2datas = []
        for i in data_list:
            interface = i.get("interface", "")
            
            # 跳过某些特殊接口（与旧代码逻辑保持一致）
            if interface:
                if interface.startswith('LoopBack'):
                    continue
                if interface.startswith('NULL'):
                    continue
                if interface.startswith('Vlanif'):
                    continue
                if interface.startswith('Ethernet0/0/0'):
                    continue
                  
            temp = dict(
                hostip=i.get("hostip", ""),
                interface=interface, 
                status=i.get("status", ""),  # 旧代码只用Status字段
                speed=InterfaceFormat.mathintspeed(i.get("speed", "")),
                duplex=i.get("duplex", ""),
                description=i.get("description", ""),  # 旧代码只用Description字段
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据"""
        aggre_datas = []
        for i in data_list:
            # 处理成员端口（与旧代码逻辑保持一致）
            if isinstance(i.get("portname"), list):
                memberports = []
                for member in i['portname']:
                    memberports.append(member)
            else:
                memberports = i.get("memberports", [])
            
            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=i.get("aggregroup", "") or i.get("trunk_num", ""),  # 旧代码不格式化
                memberports=memberports,  
                status=i.get("status", "") or i.get("portstatus", ""),  
                mode=i.get("mode", "") or "",
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)  
        return aggre_datas
