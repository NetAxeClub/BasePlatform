from netaddr import IPNetwork


class ZtePlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # ZTE设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['mac_address'].replace('.', '-')
            except Exception:
                macaddress = i.get('mac_address', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("address", ""),  # 旧代码使用 i['address']
                macaddress=macaddress,
                aging=i.get("age", ""),  # 旧代码使用 i['age']
                type='',  # 旧代码固定为空
                vlan=i.get("external_vlan", ""),  # 旧代码使用 i['external_vlan']
                interface=''.join(i.get("sub_interface", [])),  # 旧代码使用 ''.join(i['sub_interface'])
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
            # ZTE设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

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
            if 'neighborsysname' in i.keys():
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
                local_interface=i.get("local_interface", ""),  # 旧代码使用 i['local_interface']
                chassis_id=i.get("chassis_id", ""),  # 旧代码使用 i['chassis_id']
                neighbor_port=i.get("neighbor_port", ""),  # 旧代码使用 i['neighbor_port']
                portdescription=i.get("portdescription", ""),  # 旧代码使用 i['portdescription']
                neighborsysname=i.get("neighborsysname", ""),  # 旧代码使用 i['neighborsysname']
                management_ip=i.get("management_ip", ""),  # 旧代码使用 i['management_ip']
                management_type=i.get("management_type", ""),  # 旧代码使用 i['management_type']
                neighbor_ip=neighbor_ip,  # 旧代码使用解析后的 neighbor_ip
                log_time=i.get("log_time", ""),
            )
            lldp_datas.append(temp)
        return lldp_datas

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []

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
        """处理二层接口数据（与旧代码逻辑保持一致：不检查IP地址，直接处理所有接口）"""
        layer2datas = []

        for i in data_list:
            temp = dict(
                hostip=i.get("hostip", ""),
                interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                status=i.get("link_status", ""),  # 旧代码使用 i['link_status']
                speed=i.get("bandwith", ""),  # 旧代码使用 i['bandwith']
                duplex='',  # 旧代码固定为空
                description=i.get("description", ""),  # 旧代码使用 i.get('description')
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（与旧代码逻辑保持一致）"""
        aggre_datas = []

        # ZTE设备的聚合端口需要按group字段分组（与旧代码逻辑保持一致）
        group_data = {}
        for i in data_list:
            if i.get('group') not in group_data.keys():
                group_data[i['group']] = [i]
            else:
                group_data[i['group']].append(i)

        # 将分组后的数据转换为标准格式（与旧代码逻辑保持一致）
        for group in group_data.keys():
            member_ports = [x['port'].split('[')[0] for x in group_data[group]]
            state = [x['state'] for x in group_data[group]]
            # 从原始数据中获取hostip（假设同一聚合组的数据hostip相同）
            hostip = ""
            if group_data[group]:
                hostip = group_data[group][0].get("hostip", "")
            temp = dict(
                hostip=hostip,  # 旧代码使用 self.hostip
                aggregroup=f"smartgroup{group}",
                memberports=member_ports,
                status=state,
                mode='',  # 旧代码固定为空
                log_time="",  # 旧代码没有 log_time
            )
            aggre_datas.append(temp)
        return aggre_datas
