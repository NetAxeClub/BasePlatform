from apps.device_api.common import InterfaceFormat


class CentecPlan:

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # 处理MAC地址格式：将点替换为横线（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ip", ""),  # 旧代码使用 i['ip']
                macaddress=macaddress,
                aging=i.get("age", ""),  # 旧代码使用 i['age']
                type='',  # 旧代码固定为空字符串
                vlan='',  # 旧代码固定为空字符串
                interface=i.get("interface", "").strip(),
                vpninstance="",
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        """处理MAC地址表数据（与旧代码逻辑保持一致）"""
        mac_datas = []

        for i in data_list:
            # 处理MAC地址格式：将点替换为横线（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("vlan", ""),
                interface=i.get("ports", "").strip(),  # 旧代码使用 i['ports'].strip()
                type=i.get("type", "").lower(),  # 旧代码使用 i['type'].lower()
                log_time=i.get("log_time", ""),
            )
            mac_datas.append(temp)
        return mac_datas

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据（盛科可能不支持LLDP，返回原数据）"""
        lldp_datas = []

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
        """处理三层接口数据（与旧代码逻辑保持一致：直接使用原始IP，不做解析）"""
        layer3datas = []

        for i in data_list:
            # 旧代码直接使用 i['ip']，不做IP地址解析和location处理
            temp = dict(
                hostip=i.get("hostip", ""),
                interface=i.get("interface", "").strip(),
                line_status=i.get("status", ""),  # 旧代码使用 i['status']
                protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                ipaddress=i.get("ip", ""),  # 旧代码使用 i['ip']，不做解析
                ip_type='',  # 旧代码固定为空字符串
                mtu='',  # 旧代码固定为空字符串
                log_time=i.get("log_time", ""),
            )
            layer3datas.append(temp)
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（与旧代码逻辑保持一致）"""
        layer2datas = []

        for i in data_list:
            # 处理速度字段：如果以'a-'开头，需要去掉前缀（与旧代码逻辑保持一致）
            speed = i.get("speed", "")
            if speed and speed.startswith('a-'):
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
