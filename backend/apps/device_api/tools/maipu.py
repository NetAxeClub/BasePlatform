from netaddr import IPNetwork
from apps.device_api.common import InterfaceFormat


class MaipuPlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # Maipu设备MAC地址格式需要将 . 替换为 -，并转为小写（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')
            macaddress = macaddress.lower()

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ipaddress", ""),  # 旧代码使用 i['ipaddress']
                macaddress=macaddress,
                aging=i.get("age", ""),  # 旧代码使用 i['age']
                type=i.get("type", ""),  # 旧代码使用 i['type']
                vlan=i.get("vlan", ""),  # 旧代码使用 i['vlan']
                interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                vpninstance="",
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        """处理MAC地址表数据（与旧代码逻辑保持一致）"""
        mac_data = []

        for i in data_list:
            # Maipu设备MAC地址格式需要将 . 替换为 -，并转为小写（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')
            macaddress = macaddress.lower()

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("vlan", ""),  # 旧代码使用 i['vlan']
                interface=i.get("interface", "").strip(),  # 旧代码使用 i['interface'].strip()
                type=i.get("type", "").lower(),  # 旧代码使用 i['type'].lower()
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据（与旧代码逻辑保持一致）"""
        import json
        from django.core.cache import cache
        from apps.asset.models import NetworkDevice
        
        lldp_datas = []

        for i in data_list:
            # 解析neighbor_ip（与旧代码逻辑保持一致）
            neighbor_ip = ''
            if i.get('neighborsysname'):
                tmp_neighbor_ip = cache.get('cmdb_' + i['neighborsysname'])
                if tmp_neighbor_ip:
                    tmp_neighbor_ip = json.loads(tmp_neighbor_ip)
                    neighbor_ip = tmp_neighbor_ip[0]['manage_ip']
                else:
                    tmp_neighbor_ip = NetworkDevice.objects.filter(name=i['neighborsysname']).values('manage_ip').first()
                    neighbor_ip = tmp_neighbor_ip['manage_ip'] if tmp_neighbor_ip else ''

            temp = dict(
                hostip=i.get("hostip", ""),
                local_interface=InterfaceFormat.maipu_interface_format(i.get("local_interface", "")),  # 旧代码使用 i['local_interface']
                chassis_id='',  # 旧代码固定为空
                neighbor_port=i.get("neighbor_port", ""),  # 旧代码使用 i['neighbor_port']
                portdescription='',  # 旧代码固定为空
                neighborsysname=i.get("neighborsysname", ""),  # 旧代码使用 i['neighborsysname']
                management_ip=neighbor_ip,  # 旧代码使用 neighbor_ip
                management_type='',  # 旧代码固定为空
                neighbor_ip=neighbor_ip,  # 旧代码使用 neighbor_ip
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（与旧代码逻辑保持一致：直接使用 i['ipaddr'] 列表）"""
        layer3datas = []

        for i in data_list:
            # 旧代码直接使用 i['ipaddr']，遍历列表中的每个IP
            if i.get('ipaddr'):
                for _ip in i['ipaddr']:
                    _ipnet = IPNetwork(_ip)
                    location = [dict(start=_ipnet.first, end=_ipnet.last)]
                    temp = dict(
                        hostip=i.get("hostip", ""),
                        interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                        line_status=i.get("protocolstatus", ""),  # 旧代码使用 i['protocolstatus']
                        protocol_status=i.get("protocolstatus", ""),  # 旧代码使用 i['protocolstatus']
                        ipaddress=_ipnet.ip.format(),
                        ipmask=_ipnet.netmask.format(),
                        ip_type='',  # 旧代码固定为空
                        location=location,
                        mtu=i.get("mtu", ""),  # 旧代码使用 i['mtu']
                        log_time=i.get("log_time", ""),
                    )
                    layer3datas.append(temp)
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（与旧代码逻辑保持一致：不检查IP地址，直接处理所有接口）"""
        layer2datas = []

        for i in data_list:
            # 处理速度字段，Maipu设备有特殊的速度格式（与旧代码逻辑保持一致）
            speed = i.get("speed", "")  # 旧代码使用 i['speed']
            if speed == '1000 M':
                speed = '1G'
            elif speed == '10000 M':
                speed = '10G'
            elif speed == '1000M':
                speed = '10G'

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                status=i.get("protocolstatus", ""),  # 旧代码使用 i['protocolstatus']
                speed=speed,
                duplex=i.get("duplex", ""),  # 旧代码使用 i['duplex']
                description=i.get("description", ""),  # 旧代码使用 i.get('description')
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（与旧代码逻辑保持一致）"""
        aggre_datas = []

        # Maipu设备的聚合端口需要按aggregate字段分组（与旧代码逻辑保持一致）
        tmp = {}
        for i in data_list:
            if i.get('aggregate') in tmp.keys():
                tmp[i['aggregate']]['memberports'].append(i['interface'])
                tmp[i['aggregate']]['status'].append(i['selected'])
                tmp[i['aggregate']]['mode'].append(i['mode'])
            else:
                tmp[i['aggregate']] = {
                    'memberports': [i['interface']],
                    'status': [i['selected']],
                    'mode': [i['mode']]
                }

        # 将分组后的数据转换为标准格式（与旧代码逻辑保持一致）
        for aggregate in tmp.keys():
            # 从原始数据中获取hostip（假设同一聚合组的数据hostip相同）
            hostip = ""
            for item in data_list:
                if item.get("aggregate", "") == aggregate:
                    hostip = item.get("hostip", "")
                    break
            
            temp = dict(
                hostip=hostip,  # 旧代码使用 self.hostip
                aggregroup=aggregate,
                memberports=tmp[aggregate]['memberports'],
                status=tmp[aggregate]['status'],
                mode=tmp[aggregate]['mode'],
                log_time="",  # 旧代码没有 log_time
            )
            aggre_datas.append(temp)
        return aggre_datas
