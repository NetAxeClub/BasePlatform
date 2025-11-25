from netaddr import IPNetwork


class MellanoxPlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # Mellanox设备MAC地址格式需要从 : 分隔转换为 - 分隔（与旧代码逻辑保持一致）
            try:
                tmp = i['macaddress'].split(':')
                macaddress = tmp[0] + tmp[1] + '-' + tmp[2] + tmp[3] + '-' + tmp[4] + tmp[5]
            except Exception:
                macaddress = i.get('macaddress', '')
            macaddress = macaddress.lower()

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ipaddr", ""),  # 旧代码使用 i['ipaddr']
                macaddress=macaddress,
                aging='',  # 旧代码固定为空
                type=i.get("type", ""),  # 旧代码使用 i['type']
                vlan='',  # 旧代码固定为空
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
            # Mellanox设备MAC地址格式需要从 : 分隔转换为 - 分隔（与旧代码逻辑保持一致）
            try:
                tmp = i['macaddress'].split(':')
                macaddress = tmp[0] + tmp[1] + '-' + tmp[2] + tmp[3] + '-' + tmp[4] + tmp[5]
            except Exception:
                macaddress = i.get('macaddress', '')
            macaddress = macaddress.lower()

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("vlan", ""),  # 旧代码使用 i['vlan']
                interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                type=i.get("type", ""),  # 旧代码使用 i['type']
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        lldp_datas = []

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
        """处理三层接口数据（与旧代码逻辑保持一致）"""
        layer3datas = []

        for i in data_list:
            # 旧代码直接判断 if i['ipaddr'] != 'Unassigned':
            if i.get('ipaddr') != 'Unassigned':
                _ip = IPNetwork(i['ipaddr'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("operstate", ""),  # 旧代码使用 i['operstate']
                    protocol_status='',  # 旧代码固定为空
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type=i.get("primary", ""),  # 旧代码使用 i['primary']
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
            interface = i.get("interface", "")
            
            # 跳过某些特殊接口（与旧代码逻辑保持一致）
            if interface.startswith('mgmt'):
                continue
            if interface.startswith('lo'):
                continue

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=interface,  # 旧代码使用 i['interface']
                status=i.get("operationalstate", "").lower(),  # 旧代码使用 i['operationalstate'].lower()
                speed=i.get("advertisedspeeds", ""),  # 旧代码使用 i['advertisedspeeds']
                duplex='',  # 旧代码固定为空
                description=i.get("description", ""),  # 旧代码使用 i['description']
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（与旧代码逻辑保持一致）"""
        aggre_datas = []

        for i in data_list:
            # 处理成员端口（与旧代码逻辑保持一致）
            try:
                memberports = []
                tmp_members = i['memberports'].split()
                for member in tmp_members:
                    memberports.append(member.split('(')[0])
            except Exception:
                memberports = i['memberports'].split()

            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=i.get("portchannel", ""),  # 旧代码使用 i['portchannel']
                memberports=memberports,
                status='',  # 旧代码固定为空
                mode=i.get("type", ""),  # 旧代码使用 i.get('type')
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas
