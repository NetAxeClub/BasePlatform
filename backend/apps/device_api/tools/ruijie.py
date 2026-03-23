import re
from netaddr import IPNetwork
from apps.device_api.common import InterfaceFormat


class RuiJiePlan:
    @staticmethod
    def _pick_first(item, *keys):
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return ""

    @staticmethod
    def _ruijie_interface_format(interface):
        """格式化Ruijie设备接口名称"""
        interface = str(interface or "").strip()
        if re.search(r'^(Ag)', interface):
            return interface.replace('Ag', 'AggregatePort')
        elif re.search(r'^(Te)', interface):
            return interface.replace('Te', 'TenGigabitEthernetn')
        return interface

    @staticmethod
    def get_version(data_list):
        """处理锐捷设备标识数据。"""
        records = data_list if isinstance(data_list, list) else [data_list]
        for item in records:
            if not isinstance(item, dict):
                continue
            description = str(RuiJiePlan._pick_first(item, "Description", "description")).strip()
            version = str(RuiJiePlan._pick_first(item, "Version", "version")).strip()
            serial_num = str(
                RuiJiePlan._pick_first(item, "SerialNum", "serialnum", "serial_num")
            ).strip()
            model_name = ""
            model_match = re.search(r"\(([^)]+)\)", description)
            if model_match:
                model_name = model_match.group(1).strip()
            elif description:
                model_name = description.split(",")[0].strip()
            if any((serial_num, model_name, version)):
                return [
                    dict(
                        serial_num=serial_num,
                        vendor_alias="Ruijie",
                        model_name=model_name,
                        soft_version=version,
                        patch_version="",
                    )
                ]
        return []

    @staticmethod
    def get_arp(data_list):
        """处理ARP数据（与旧代码逻辑保持一致）"""
        arp_datas = []

        for i in data_list:
            # Ruijie设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
            try:
                macaddress = i['hardware'].replace('.', '-')
            except Exception:
                macaddress = i.get('hardware', '')

            temp = dict(
                hostip=i.get("hostip", ""),
                hostname=i.get("hostname", ""),
                idc_name=i.get("idc_name", ""),
                ipaddress=i.get("address", ""),  # 旧代码使用 i['address']
                macaddress=macaddress,
                aging=i.get("agemin", ""),  # 旧代码使用 i['agemin']
                type=i.get("type", ""),  # 旧代码使用 i['type']
                vlan=i.get("vlan", ""),  # 旧代码使用 i.get('vlan')
                interface=i.get("interface", "").strip(),  # 旧代码使用 i['interface'].strip()
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
            # Ruijie设备MAC地址格式需要将 . 替换为 -（与旧代码逻辑保持一致）
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
        """处理LLDP数据"""
        lldp_datas = []

        for i in data_list:
            # 处理接口名称格式化
            local_interface = i.get("local_interface", "")
            if local_interface:
                local_interface = RuiJiePlan._ruijie_interface_format(local_interface)

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
        """处理三层接口数据（与旧代码逻辑保持一致：if-elif-else结构）"""
        layer3datas = []

        for i in data_list:
            # 旧代码使用 if-elif-else 结构
            if i.get('priipaddr') != 'no address':
                _ip = IPNetwork(i['priipaddr'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Primary',
                    location=location,
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
            elif i.get('secipaddr') != 'no address':
                # 注意：旧代码这里用的是 i['priipaddr'] 而不是 i['secipaddr']！
                _ip = IPNetwork(i['priipaddr'])
                location = [dict(start=_ip.first, end=_ip.last)]
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=_ip.ip.format(),
                    ipmask=_ip.netmask.format(),
                    ip_type='Sub',
                    location=location,
                    mtu='',  # 旧代码固定为空
                    log_time=i.get("log_time", ""),
                )
                layer3datas.append(temp)
            else:
                # 旧代码还有一个 else 分支处理没有IP的情况
                temp = dict(
                    hostip=i.get("hostip", ""),
                    interface=i.get("interface", ""),  # 旧代码使用 i['interface']
                    line_status=i.get("status", ""),  # 旧代码使用 i['status']
                    protocol_status=i.get("protocol", ""),  # 旧代码使用 i['protocol']
                    ipaddress=i.get("priipaddr", ""),  # 旧代码使用 i['priipaddr']
                    ip_type='',
                    location=[],
                    mtu='',  # 旧代码固定为空
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
            
            # 跳过AggregatePort开头的接口（与旧代码逻辑保持一致）
            if interface.startswith('AggregatePort'):
                continue

            # 处理速度字段（与旧代码逻辑保持一致）
            speed = i.get("speed", "")  # 旧代码使用 i['speed']
            if speed == 'Unknown' or speed == 'unknown':
                speed = InterfaceFormat.ruijie_speed_format(interface)  # 旧代码使用 i['interface']
            # 旧代码直接使用 InterfaceFormat.mathintspeed(i['speed'])
            speed = InterfaceFormat.mathintspeed(speed)

            temp = dict(
                hostip=i.get("hostip", ""),
                interface=interface,  # 旧代码使用 i['interface']
                status=i.get("status", ""),  # 旧代码使用 i['status']
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

        for i in data_list:
            # 处理成员端口（与旧代码逻辑保持一致）
            try:
                memberports = []
                tmp_members = i['ports'].split(',')
                for member in tmp_members:
                    memberports.append(RuiJiePlan._ruijie_interface_format(member))
            except Exception:
                memberports = i['memberports'].split(',')

            temp = dict(
                hostip=i.get("hostip", ""),
                aggregroup=RuiJiePlan._ruijie_interface_format(i.get("aggregateport", "")),  # 旧代码使用 i['aggregateport']
                memberports=memberports,
                status='',  # 旧代码固定为空
                mode='',  # 旧代码固定为空
                log_time=i.get("log_time", ""),
            )
            aggre_datas.append(temp)
        return aggre_datas

    @staticmethod
    def get_stack_status(data_list):
        """处理锐捷虚拟交换/堆叠状态。"""
        records = data_list if isinstance(data_list, list) else [data_list]
        rows = []
        for item in records:
            if not isinstance(item, dict):
                continue
            member_id = str(RuiJiePlan._pick_first(item, "MEMBER", "member")).strip()
            rows.append(
                dict(
                    member_id=member_id,
                    slot=member_id,
                    role=str(RuiJiePlan._pick_first(item, "ROLE", "role")).strip(),
                    priority=str(RuiJiePlan._pick_first(item, "PRIORITY", "priority")).strip(),
                    mac="",
                    position=str(RuiJiePlan._pick_first(item, "POSITION", "position")).strip(),
                    status=str(RuiJiePlan._pick_first(item, "STATUS", "status")).strip(),
                    domain=str(RuiJiePlan._pick_first(item, "DOMAIN", "domain")).strip(),
                )
            )
        return rows

    @staticmethod
    def get_irf_status(data_list):
        """兼容 show member 输出到统一成员状态字段。"""
        records = [
            item for item in (data_list if isinstance(data_list, list) else [data_list])
            if isinstance(item, dict)
        ]
        priorities = []
        for item in records:
            try:
                priorities.append(int(RuiJiePlan._pick_first(item, "PRIORITY", "priority")))
            except Exception:
                continue
        max_priority = max(priorities) if priorities else None
        min_priority = min(priorities) if priorities else None

        rows = []
        for item in records:
            member_id = str(RuiJiePlan._pick_first(item, "MEMBER", "member")).strip()
            priority = str(RuiJiePlan._pick_first(item, "PRIORITY", "priority")).strip()
            mac = str(RuiJiePlan._pick_first(item, "MACADDR", "macaddr", "mac")).strip()
            role = ""
            try:
                numeric_priority = int(priority)
            except Exception:
                numeric_priority = None
            if (
                numeric_priority is not None
                and max_priority is not None
                and min_priority is not None
                and max_priority != min_priority
            ):
                if numeric_priority == max_priority:
                    role = "master"
                elif numeric_priority == min_priority:
                    role = "standby"
            elif len(records) == 1:
                role = "master"

            rows.append(
                dict(
                    chassis_id="",
                    member_id=member_id,
                    slot=member_id,
                    role=role,
                    priority=priority,
                    mac=mac.replace(".", "-"),
                    soft_version=str(RuiJiePlan._pick_first(item, "SOFTVER", "softver")).strip(),
                )
            )
        return rows
