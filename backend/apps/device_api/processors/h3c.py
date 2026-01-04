import re
import math
from .base import register_processor


# 专门处理交换机端口速率的版本
def format_switch_port_speed(speed_str):
    """
    针对交换机端口速率的格式化
    输入: '10000000' -> 输出: '10G'
    """
    try:
        speed = int(speed_str)

        # 常见交换机端口速率映射
        speed_mapping = {
            10: "10M",
            100: "100M",
            1000: "1G",
            10000: "10G",
            25000: "25G",
            40000: "40G",
            100000: "100G",
            200000: "200G",
            400000: "400G"
        }

        # 尝试直接匹配常见速率
        if speed in speed_mapping:
            return speed_mapping[speed]

        # 如果不是标准速率，按千进制计算
        if speed >= 1000000:  # 1G以上
            g_speed = speed / 1000000
            if g_speed.is_integer():
                return f"{int(g_speed)}G"
            else:
                return f"{g_speed}G"
        elif speed >= 1000:  # 1M以上
            m_speed = speed / 1000
            if m_speed.is_integer():
                return f"{int(m_speed)}M"
            else:
                return f"{m_speed}M"
        else:
            return f"{speed}bps"

    except (ValueError, TypeError):
        return "N/A"


def h3c_speed_format(interface):
    if re.search(r'^(GE)', interface) or re.search(
            r'^(GigabitEthernet)', interface):
        return '1G'

    elif re.search(r'^(XGE)', interface) or re.search(r'^(Ten-GigabitEthernet)', interface):
        return '10G'

    elif re.search(r'^(FGE)', interface) or re.search(r'^(FortyGigE)', interface):
        return '40G'

    elif re.search(r'^(Twenty-FiveGigE)', interface):
        return '25G'

    elif re.search(r'^(TwentyGigE)', interface):
        return '20G'

    elif re.search(r'^(TwoHundredGigE)', interface):
        return '200G'

    elif re.search(r'^(FourHundredGigE)', interface):
        return '400G'

    elif re.search(r'^(HGE)', interface):
        return '100G'

    elif re.search(r'^(MGE)', interface) or re.search(r'^(MEth)', interface):
        return '1G'

    elif re.search(r'^(M-GE)', interface):
        return '1G'
    return interface


@register_processor(vendor='H3C', device_type='交换机', collection_type='interface_brief', method='netconf')
def process_interface_brief_netconf(data):
    """H3C 交换机 ARP 处理 (NETCONF)"""
    data = data['data']['top']['Ifmgr']['Interfaces']['Interface']
    layer2datas = []
    for i in data:
        # 正常物理接口都会带speed和duplex的key，不带则是逻辑接口
        if 'ActualSpeed' in i.keys() and 'ActualDuplex' in i.keys():
            if i['Name'].startswith('M-'):
                continue
            elif i['Name'].startswith('Bridge-Aggregation'):
                continue
            elif i['Name'].startswith('Vlan-interface'):
                continue
            elif i['Name'].startswith('InLoopBack'):
                continue
            elif i['Name'].startswith('NULL'):
                continue
            if i['ActualSpeed'] == '0':
                i['ActualSpeed'] = h3c_speed_format(
                    i['Name'])
            if format_switch_port_speed(i['ActualSpeed']) == '830G':
                i['ActualSpeed'] = h3c_speed_format(
                    i['Name'])
            layer2datas.append(dict(
                        interface=i['Name'],
                        status=i['OperStatus'],
                        speed=format_switch_port_speed(
                            i['ActualSpeed']),
                        duplex=i['ActualDuplex'],
                        description=i['Description']))
    return layer2datas