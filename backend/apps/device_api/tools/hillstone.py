import re
from netaddr import IPNetwork


class HillstonePlan:

    @staticmethod
    def get_arp(data_list):
        arp_datas = []

        for i in data_list:
            # Hillstone设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("ipaddress", ""),
                macaddress=macaddress,
                aging=i.get("age", ""),
                type=i.get("typeflag", ""),
                vlan='',
                interface=i.get("interface", ""),
                vpninstance='',
                log_time=i.get("log_time", ""),
            )
            arp_datas.append(temp)
        return arp_datas

    @staticmethod
    def get_mac(data_list):
        mac_data = []

        for i in data_list:
            # Hillstone设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['macaddress'].replace('.', '-')
            except Exception:
                macaddress = i.get('macaddress', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                macaddress=macaddress,
                vlan=i.get("switch", ""),
                interface=i.get("interface", ""),
                type=i.get("type", ""),
                log_time=i.get("log_time", ""),
            )
            mac_data.append(temp)
        return mac_data

    @staticmethod
    def get_lldp(data_list):
        """处理LLDP数据"""
        
        return data_list

    @staticmethod
    def get_ip_interface(data_list):
        """处理三层接口数据（包含IP地址的接口）"""
        layer3datas = []

        for i in data_list:
            # Hillstone设备使用ipaddr字段（与旧代码逻辑保持一致：直接判断 i['ipaddr']）
            if not i.get('ipaddr'):
                continue

            try:
                ipaddr = i['ipaddr']
                # 处理IP地址格式，可能包含掩码
                _ipnet = IPNetwork(ipaddr)

                # 安全纳管引擎，服务发布 定位用
                location = []
                if ipaddr != '0.0.0.0/0':
                    location = [dict(start=_ipnet.first, end=_ipnet.last)]

                # 处理halp字段获取状态信息（与旧代码逻辑保持一致：直接访问 i['halp']）
                # H:physical state;A:admin state;L:link state;P:protocol state;U:up;D:down;K:ha keep up
                physical_status_map = {'U': 'up', 'D': 'down', 'K': 'ha'}
                line_status = ''
                protocol_status = ''

                try:
                    tmp = i['halp'].split()
                    line_status = physical_status_map[tmp[2]]
                    protocol_status = physical_status_map[tmp[3]]
                except Exception:
                    line_status = ''
                    protocol_status = ''

                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),
                    line_status=line_status,
                    protocol_status=protocol_status,
                    ipaddress=_ipnet.ip.format(),
                    ipmask=_ipnet.netmask.format(),
                    ip_type='',
                    location=location,
                    mtu='',
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
            except Exception:
                # 如果IP地址解析失败，跳过该记录
                continue
        return layer3datas

    @staticmethod
    def get_interface_brief(data_list):
        """处理二层接口数据（与旧代码逻辑保持一致：只要接口名匹配ethernet就添加到layer2，不管是否有IP）"""
        layer2datas = []

        int_regex = re.compile('ethernet')
        for i in data_list:
            interface = i.get("interface", "")

            # Hillstone设备只处理ethernet类型的物理接口（与旧代码逻辑保持一致）
            if not int_regex.search(interface):
                continue

            # 处理halp字段获取状态信息（与旧代码逻辑保持一致：直接访问 i['halp']）
            physical_status_map = {'U': 'up', 'D': 'down', 'K': 'ha'}
            physical_status = ''

            try:
                tmp = i['halp'].split()
                physical_status = physical_status_map[tmp[0]]
            except Exception:
                physical_status = ''

            # 根据接口名称推断速度（与旧代码逻辑保持一致）
            speed = HillstonePlan._hillstone_speed_format(interface)

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=interface,
                status=physical_status,
                speed=speed,
                duplex='',
                description=i.get("description", ""),
                log_time=i.get("log_time", ""),
            )
            layer2datas.append(temp)
        return layer2datas

    @staticmethod
    def get_aggre_port(data_list):
        """处理聚合端口数据（与旧代码逻辑保持一致）"""
        return data_list

    @staticmethod
    def _hillstone_speed_format(interface):
        """根据接口名称推断速度（Hillstone设备）"""
        if re.search(r'^(ethernet)', interface):
            return '1G'
        elif re.search(r'^(xethernet)', interface):
            return '10G'
        elif re.search(r'^(cethernet)', interface):
            return '100G'
        elif re.search(r'^(xxvethernet)', interface):
            return '25G'
        return 'auto'
